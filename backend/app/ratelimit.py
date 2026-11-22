"""Fixed-window rate limiting over the Upstash Redis REST API (per IP + global daily cap)."""

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
TIMEOUT = 1.0


def client_ip(request: Request) -> str:
    # shortcut: these headers are only trustworthy behind Vercel (it sets them, clients cannot spoof); upgrade if hosted elsewhere.
    h = request.headers
    for name in ("x-vercel-forwarded-for", "x-real-ip"):
        if h.get(name):
            return h[name].split(",")[0].strip()
    if h.get("x-forwarded-for"):
        return h["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else ""


def _ip_key(ip: str, window: int) -> str:
    try:
        norm = str(ipaddress.ip_address(ip.strip()))
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
    s = settings or get_settings()
    if not (s.UPSTASH_REDIS_REST_URL and s.UPSTASH_REDIS_REST_TOKEN):
        logger.warning("rate limit disabled: Upstash settings missing")
        return True
    now = time.time() if now is None else now
    ip_key, glob_key = _ip_key(ip, int(now // IP_WINDOW)), f"glob:{int(now // DAY)}"
    cmds = [
        ["INCR", ip_key],
        ["EXPIRE", ip_key, str(IP_WINDOW), "NX"],
        ["INCR", glob_key],
        ["EXPIRE", glob_key, str(DAY), "NX"],
    ]
    try:
        c = client or httpx.AsyncClient(timeout=TIMEOUT)
        try:
            r = await c.post(
                s.UPSTASH_REDIS_REST_URL.rstrip("/") + "/pipeline",
                json=cmds,
                headers={"Authorization": f"Bearer {s.UPSTASH_REDIS_REST_TOKEN}"},
                timeout=TIMEOUT,
            )
        finally:
            if client is None:
                await c.aclose()
        r.raise_for_status()
        ip_count, glob_count = r.json()[0]["result"], r.json()[2]["result"]
        ip_count, glob_count = int(ip_count), int(glob_count)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
        # Fail open: the Vercel WAF rate-limit rule is the second layer, an Upstash outage must not take chat down.
        logger.warning("rate limit check failed, allowing request: %r", e)
        return True
    return ip_count <= IP_LIMIT and glob_count <= GLOBAL_LIMIT
