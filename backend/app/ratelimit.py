"""Fixed-window rate limiting over the Upstash Redis REST API (per IP + global daily cap)."""

import asyncio
import hashlib
import ipaddress
import logging
import time

import httpx
from fastapi import Request

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

IP_LIMIT, IP_WINDOW = 20, 600
GLOBAL_LIMIT, DAY = 300, 86400
TIMEOUT = 1.0  # total deadline for both Upstash calls
_warned_missing = False


def _first_hop(value: str) -> str:
    ip = value.split(",")[0].strip()
    return ip.rsplit(":", 1)[0] if ip.count(":") == 1 else ip  # drop IPv4 ":port"


def client_ip(request: Request) -> str:
    # shortcut: these headers are only trustworthy behind Vercel (it sets them, clients cannot spoof); upgrade if hosted elsewhere.
    h = request.headers
    for name in ("x-vercel-forwarded-for", "x-real-ip", "x-forwarded-for"):
        if h.get(name):
            return _first_hop(h[name])
    return request.client.host if request.client else ""


def _ip_key(ip: str, window: int) -> str:
    try:
        addr = ipaddress.ip_address(ip.strip())
        if isinstance(addr, ipaddress.IPv6Address):
            # IPv6 clients hold a whole /64, so key on that; unwrap IPv4-mapped addresses.
            norm = str(addr.ipv4_mapped or ipaddress.ip_network(f"{addr}/64", strict=False))
        else:
            norm = str(addr)
    except ValueError:
        norm = "unknown"  # shared bucket
    return f"ip:{hashlib.sha256(norm.encode()).hexdigest()[:16]}:{window}"  # hashed: no raw IPs in Redis


async def check(
    ip: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    now: float | None = None,
) -> bool:
    """True = request allowed. Fails open on any Upstash problem."""
    global _warned_missing
    s = settings or get_settings()
    if not (s.UPSTASH_REDIS_REST_URL and s.UPSTASH_REDIS_REST_TOKEN):
        if not _warned_missing:
            _warned_missing = True
            logger.warning("rate limit disabled: Upstash settings missing")
        return True
    now = time.time() if now is None else now
    ip_key, glob_key = _ip_key(ip, int(now // IP_WINDOW)), f"glob:{int(now // DAY)}"
    url = s.UPSTASH_REDIS_REST_URL.rstrip("/") + "/pipeline"
    headers = {"Authorization": f"Bearer {s.UPSTASH_REDIS_REST_TOKEN}"}

    async def count(c: httpx.AsyncClient, key: str, ttl: int) -> int:
        r = await c.post(url, json=[["INCR", key], ["EXPIRE", key, str(ttl), "NX"]], headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return int(r.json()[0]["result"])

    try:
        async with asyncio.timeout(TIMEOUT):
            c = client or httpx.AsyncClient(timeout=TIMEOUT)
            try:
                # Sequential on purpose: a blocked IP must not burn the shared daily budget.
                if await count(c, ip_key, IP_WINDOW) > IP_LIMIT:
                    return False
                return await count(c, glob_key, DAY) <= GLOBAL_LIMIT
            finally:
                if client is None:
                    await c.aclose()
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as e:
        # Fail open: the Vercel WAF rate-limit rule is the second layer, an Upstash outage must not take chat down.
        logger.warning("rate limit check failed, allowing request: %r", e)
        return True
