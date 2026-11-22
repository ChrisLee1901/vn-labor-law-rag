"""GET /api/cron/keepalive: Vercel Cron, giữ DB không bị pause."""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from app.api.deps import db_conn
from app.config import Settings, get_settings

router = APIRouter()


@router.get("/api/cron/keepalive", status_code=204)
async def keepalive(
    request: Request, authorization: str | None = Header(None), settings: Settings = Depends(get_settings)
):
    secret = settings.CRON_SECRET
    if not secret or not authorization or not hmac.compare_digest(authorization.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(401, "Không được phép.")
    async with db_conn(request) as conn:
        await conn.execute("select 1")
    return Response(status_code=204)
