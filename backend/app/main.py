"""FastAPI app (`app.main:app`). Route khai báo kèm tiền tố /api (rewrite của Vercel giữ nguyên tiền tố)."""

import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import chat, cron, docs, feedback, health
from app.config import get_settings
from app.db import make_pool
from app.llm.gateway import Gateway

log = logging.getLogger(__name__)
MAX_BODY = 64 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=3.0)
    )  # dùng chung: gateway + rate limit
    app.state.gw = Gateway(s.LLM_BASE_URL, s.LLM_API_KEY, client=app.state.http)
    app.state.pool = None
    if s.DATABASE_URL:
        app.state.pool = make_pool(s.DATABASE_URL)
        await app.state.pool.open(
            wait=False
        )  # DB chưa tới được thì từng request báo 503, app vẫn lên
    try:
        yield
    finally:
        if app.state.pool is not None:
            await app.state.pool.close()
        await app.state.gw.aclose()
        await app.state.http.aclose()


class SecurityMiddleware:
    """nosniff mọi response; /api/chat mặc định no-store; POST có Content-Length > 64 KB thì 413."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] == "POST":
            declared = dict(scope["headers"]).get(b"content-length", b"")
            if declared.isdigit() and int(declared) > MAX_BODY:
                resp = JSONResponse(
                    {"detail": "Yêu cầu quá lớn."},
                    status_code=413,
                    headers={"x-content-type-options": "nosniff"},
                )
                return await resp(scope, receive, send)

        async def send_wrapped(msg: Message) -> None:
            if msg["type"] == "http.response.start":
                h = MutableHeaders(scope=msg)
                h["x-content-type-options"] = "nosniff"
                if scope["path"] == "/api/chat":
                    h.setdefault("cache-control", "no-store")
            await send(msg)

        await self.app(scope, receive, send_wrapped)


def _error(status: int, detail, headers: dict | None = None) -> JSONResponse:
    # ServerErrorMiddleware (500) nằm ngoài SecurityMiddleware nên header an toàn đặt ở đây.
    return JSONResponse(
        {"detail": detail},
        status_code=status,
        headers={
            **(headers or {}),
            "x-content-type-options": "nosniff",
            "cache-control": "no-store",
        },
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Vietnamese legal RAG", lifespan=lifespan)
    app.add_middleware(SecurityMiddleware)
    for m in (chat, health, docs, feedback, cron):
        app.include_router(m.router)
    if os.environ.get("ENABLE_SPIKE_ENDPOINTS") == "1":  # spike Task 0.4, xóa sau spike
        from app.api import spike

        app.include_router(spike.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        # Mặc định của Starlette (tiếng Anh) -> tiếng Việt; HTTPException của mình đã có detail tiếng Việt.
        if exc.status_code == 404 and detail == "Not Found":
            detail = "Không tìm thấy đường dẫn."
        elif exc.status_code == 405 and detail == "Method Not Allowed":
            detail = "Phương thức không được hỗ trợ."
        return _error(exc.status_code, detail, exc.headers)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path, exc_info=exc)
        return _error(500, "Đã xảy ra lỗi hệ thống, vui lòng thử lại sau.")

    return app


app = create_app()
