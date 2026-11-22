"""POST /api/feedback: lưu điểm người dùng cho một câu trả lời (trace_id lạ vẫn nhận)."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import db_conn, read_json

router = APIRouter()


@router.post("/api/feedback", status_code=204)
async def feedback(request: Request):
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
    return Response(status_code=204)
