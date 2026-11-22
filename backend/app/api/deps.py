"""Tiện ích dùng chung của các endpoint: kết nối DB, trạng thái gateway (cache 15 s), ngưỡng từ chối (cache 60 s)."""
import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

import psycopg
from fastapi import HTTPException, Request

from app.llm.gateway import Gateway

log = logging.getLogger(__name__)

DB_DOWN = "Cơ sở dữ liệu tạm thời không khả dụng, vui lòng thử lại sau."
LLM_TTL, TAU_TTL, PROBE_TIMEOUT = 15.0, 60.0, 2.0
DEFAULT_TAU = 0.35
_llm_cache: dict[str | None, tuple[float, bool]] = {}
_tau_cache: tuple[float, float] | None = None


def reset_caches() -> None:
    global _tau_cache
    _llm_cache.clear()
    _tau_cache = None


def today_vn() -> date:
    return datetime.now(timezone(timedelta(hours=7))).date()


@asynccontextmanager
async def db_conn(request: Request, timeout: float = 5.0) -> AsyncIterator[psycopg.AsyncConnection]:
    """Kết nối từ pool của app; mọi lỗi kết nối thành HTTP 503 (tiếng Việt)."""
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(503, DB_DOWN)
    try:
        async with pool.connection(timeout=timeout) as conn:
            yield conn
    except (psycopg.OperationalError, psycopg.InterfaceError) as e:
        log.warning("database unavailable: %r", e)
        raise HTTPException(503, DB_DOWN) from e


async def llm_online(gw: Gateway) -> bool:
    """Gateway tới được và báo `status: ok`. Cache 15 s theo URL; probe tối đa 2 s."""
    now = time.monotonic()
    hit = _llm_cache.get(gw.base_url)
    if hit and now - hit[0] < LLM_TTL:
        return hit[1]
    try:
        ok = await asyncio.wait_for(gw.health(), PROBE_TIMEOUT)
    except Exception:
        ok = False
    _llm_cache[gw.base_url] = (now, ok)
    return ok


async def refusal_tau(conn: psycopg.AsyncConnection) -> float:
    """τ từ app_config.refusal_tau, cache 60 s; lỗi/giá trị sai thì dùng mặc định (chỉ lỗi dữ liệu, không nuốt lỗi kết nối)."""
    global _tau_cache
    now = time.monotonic()
    if _tau_cache and now - _tau_cache[0] < TAU_TTL:
        return _tau_cache[1]
    cur = await conn.execute("select value from app_config where key = 'refusal_tau'")
    row = await cur.fetchone()
    try:
        tau = float(row[0]) if row else DEFAULT_TAU
    except (TypeError, ValueError):
        tau = DEFAULT_TAU
    _tau_cache = (now, tau)
    return tau


async def read_json(request: Request, max_bytes: int = 64 * 1024):
    """Đọc body JSON có giới hạn kích thước (kể cả khi không có Content-Length). 413 nếu quá lớn, 422 nếu không phải JSON."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise HTTPException(413, "Yêu cầu quá lớn.")
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > max_bytes:
            raise HTTPException(413, "Yêu cầu quá lớn.")
    try:
        return json.loads(buf.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(422, "Nội dung yêu cầu không hợp lệ.") from e
