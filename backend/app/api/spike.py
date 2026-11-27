"""TẠM THỜI (spike Task 0.4): xóa file này, dòng gắn trong app/main.py và tests/api/test_spike.py sau spike.

Chỉ được gắn khi env ENABLE_SPIKE_ENDPOINTS=1 (mặc định tắt, production không lộ). Không có auth vì không trả gì nhạy cảm
(không dump env: chỉ VERCEL_REGION). Định dạng SSE giống kaggle/spike_sse.py để scripts/spike_sse_check.py đọc được.
"""

import asyncio
import json
import os
import sys
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/api/ping")
async def ping(request: Request):
    # path / root_path / raw_path trả lời: FastAPI nhận tiền tố /api hay Vercel đã cắt?
    return {
        "ok": True,
        "path": request.url.path,
        "root_path": request.scope.get("root_path", ""),
        "raw_path": request.scope.get("raw_path", b"").decode("latin-1"),
        "vercel_region": os.environ.get("VERCEL_REGION"),
        "python": "%d.%d.%d" % sys.version_info[:3],
    }


@router.get("/api/sse")
async def sse(
    count: int = Query(30, ge=1, le=60), interval: float = Query(1.0, ge=0.01, le=2.0)
):
    async def events():
        for n in range(1, count + 1):
            yield f"id: {n}\ndata: {json.dumps({'n': n, 't': time.time()})}\n\n"
            await asyncio.sleep(interval)
        yield f"event: done\ndata: {json.dumps({'n': count})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
