"""POST /api/feedback: lưu điểm người dùng cho một câu trả lời (trace_id lạ vẫn nhận) và gửi thành score Langfuse."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.background import BackgroundTask

from app.api.deps import db_conn, read_json
from app.config import Settings, get_settings
from app.tracing import run_bounded, send_feedback_score

router = APIRouter()


@router.post("/api/feedback", status_code=204)
async def feedback(request: Request, settings: Settings = Depends(get_settings)):
    body = await read_json(request)
    if not isinstance(body, dict):
        raise HTTPException(422, "Nội dung yêu cầu không hợp lệ.")
    trace_id, score, comment = (
        body.get("trace_id"),
        body.get("score"),
        body.get("comment"),
    )
    if not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 64:
        raise HTTPException(422, "Mã phản hồi không hợp lệ (1 đến 64 ký tự).")
    if isinstance(score, bool) or score not in (1, -1):
        raise HTTPException(422, "Điểm phải là 1 hoặc -1.")
    if comment is not None and (not isinstance(comment, str) or len(comment) > 500):
        raise HTTPException(422, "Nhận xét quá dài (tối đa 500 ký tự).")
    async with db_conn(request) as conn:
        await conn.execute(
            "insert into feedback(trace_id, score, comment) values (%s, %s, %s)",
            (trace_id, score, comment or None),
        )
    # Langfuse chạy sau response, có timeout, lỗi bị nuốt: không bao giờ làm hỏng feedback đã lưu.
    return Response(
        status_code=204,
        background=BackgroundTask(
            run_bounded, send_feedback_score, settings, trace_id, score, comment
        ),
    )
