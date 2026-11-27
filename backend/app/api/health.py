"""GET /api/health: luôn 200; lỗi DB báo bằng db="down"."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import PROBE_TIMEOUT, db_conn, llm_online
from app.db import active_index_version

log = logging.getLogger(__name__)
router = APIRouter()


async def _db_version(request: Request) -> int | None:
    try:
        async with db_conn(request, timeout=PROBE_TIMEOUT) as conn:
            return await active_index_version(conn)
    except Exception as e:  # HTTPException 503 hoặc lỗi truy vấn: đều là "down"
        log.warning("health: db down: %r", e)
        return None


@router.get("/api/health")
async def health(request: Request):
    online, version = await asyncio.gather(
        llm_online(request.app.state.gw), _db_version(request)
    )
    return JSONResponse(
        {
            "llm": "online" if online else "offline",
            "db": "ok" if version is not None else "down",
            "index_version": version or 0,
        },
        headers={"cache-control": "no-store"},
    )
