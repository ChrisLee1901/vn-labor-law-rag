"""POST /api/chat: kiểm tra đầu vào -> rate limit -> truy hồi (mọi thứ có thể lỗi HTTP) -> stream SSE (lỗi thành chunk `error`)."""

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection
from starlette.background import BackgroundTask

from app import ratelimit, stream
from app.api.deps import PooledReader, llm_online, read_json, refusal_tau, today_vn
from app.config import CHAT_BUDGET_S, CONDENSE_TIMEOUT_S, Settings, get_settings
from app.db import active_index_version
from app.legal.dates import extract_as_of
from app.legal.ids import is_appendix_id
from app.legal.normalize import nfc, question_key
from app.llm.citations import REFUSAL_TEXT, check_citations, should_refuse
from app.llm.gateway import Gateway
from app.llm.prompt import PROMPT_VERSION, build_messages, condense_messages
from app.retrieval.expand import SourceDoc, expand
from app.retrieval.search import MAX_QUERY_CHARS, retrieve
from app.tracing import Trace

log = logging.getLogger(__name__)
router = APIRouter()

MAX_Q, MAX_MESSAGES = 1000, 10
OFFLINE_TEXT = "Mô hình đang ngoại tuyến. Dưới đây là các điều luật liên quan nhất:"
CANNED_LABEL = "Câu trả lời đã lưu từ phiên trực tuyến."
OVERTIME_TEXT = "Mô hình trả lời quá lâu, vui lòng thử lại."
STREAM_ERROR = "Kết nối tới mô hình bị gián đoạn, vui lòng thử lại."
RATE_LIMITED = "Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút."
TEXT_ID = "t1"
DISCONNECT_POLL_EVERY = 8  # số delta giữa hai lần hỏi request.is_disconnected()
ABORT_FLUSH_S = 1.0
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Plan:
    mode: str  # rag | offline | refused
    llm: str  # online | offline
    sources: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (sid, url, title)
    text: str | None = (
        None  # văn bản cố định (offline/refused/canned); None khi mode == rag
    )
    messages: list[dict] | None = None
    docs: list[SourceDoc] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _text(m: dict) -> str:
    parts = m.get("parts")
    if isinstance(parts, list):
        return "".join(
            p["text"]
            for p in parts
            if isinstance(p, dict)
            and p.get("type") == "text"
            and isinstance(p.get("text"), str)
        )
    return m["content"] if isinstance(m.get("content"), str) else ""


def parse_chat(body) -> tuple[str, list[dict], date | None]:
    """-> (câu hỏi đã NFC, lịch sử [{role, content}] không gồm câu hỏi, as_of). Sai thì HTTP 422 tiếng Việt."""

    def bad(msg: str):
        raise HTTPException(422, msg)

    if (
        not isinstance(body, dict)
        or not isinstance(body.get("messages"), list)
        or not body["messages"]
    ):
        bad("Cần ít nhất một tin nhắn.")
    msgs = body["messages"]
    if len(msgs) > MAX_MESSAGES:
        bad(f"Cuộc trò chuyện quá dài (tối đa {MAX_MESSAGES} tin nhắn).")
    if not all(
        isinstance(m, dict) and m.get("role") in ("user", "assistant") for m in msgs
    ):
        bad("Tin nhắn không hợp lệ.")
    if msgs[-1]["role"] != "user":
        bad("Tin nhắn cuối phải là của người dùng.")
    question = nfc(_text(msgs[-1])).strip()
    if not question:
        bad("Câu hỏi không được để trống.")
    if len(question) > MAX_Q:
        bad("Câu hỏi quá dài (tối đa 1000 ký tự).")
    history = [
        {"role": m["role"], "content": t}
        for m in msgs[:-1]
        if (t := nfc(_text(m)).strip())
    ]
    as_of = body.get("as_of")
    if as_of is not None:
        try:
            if not (isinstance(as_of, str) and _DATE.fullmatch(as_of)):
                raise ValueError
            as_of = date.fromisoformat(as_of)
        except ValueError:
            bad("Ngày tra cứu không hợp lệ (định dạng YYYY-MM-DD).")
    return question, history, as_of


def _source_parts(docs: list[SourceDoc]) -> list[tuple[str, str, str]]:
    out = []
    for s in docs:
        appendix = is_appendix_id(s.id)
        label = "Phụ lục" if appendix else "Điều"
        title = f"{s.doc_number or s.doc_code}, {label} {s.article}" + (
            f". {s.title}" if s.title else ""
        )
        out.append(
            (
                s.sid,
                f"/van-ban/{s.doc_code}#{'PL' if appendix else 'D'}{s.article}",
                title,
            )
        )
    return out


async def _canned(conn: AsyncConnection, question: str, llm: str) -> Plan | None:
    """`canned_answers.sources`: mảng {url, title}; sid gán S1..Sn theo thứ tự."""
    cur = await conn.execute(
        "select answer, sources from canned_answers where question_norm = %s",
        (question_key(question),),
    )
    row = await cur.fetchone()
    if not row or not row[0]:
        return None
    items = [
        s
        for s in (row[1] or [])
        if isinstance(s, dict)
        and isinstance(s.get("url"), str)
        and isinstance(s.get("title"), str)
    ]
    sources = [(f"S{i}", s["url"], s["title"]) for i, s in enumerate(items, 1)]
    return Plan("offline", llm, sources, f"{CANNED_LABEL}\n\n{row[0]}")


async def build_plan(
    request: Request,
    gw: Gateway,
    question: str,
    history: list[dict],
    as_of_req: date | None,
    trace: Trace,
) -> Plan:
    online = await llm_online(gw)
    llm = "online" if online else "offline"
    as_of = as_of_req or extract_as_of(question[:MAX_QUERY_CHARS], today_vn())
    search_q = question
    if online and any(m["role"] == "user" for m in history):  # từ lượt hỏi thứ 2
        with trace.span("condense"):
            try:
                async with asyncio.timeout(CONDENSE_TIMEOUT_S):
                    condensed = nfc(
                        await gw.chat_once(condense_messages(history, question))
                    ).strip()
                search_q = condensed[:MAX_Q] or question
            except Exception as e:  # condense hỏng thì dùng câu hỏi gốc
                log.warning("condense failed, using raw question: %r", e)
    conn = PooledReader(
        request
    )  # mượn pool từng câu lệnh: không giữ kết nối khi chờ embed / rerank
    iv = await active_index_version(conn)  # type: ignore[arg-type]
    meta = {
        "index_version": iv,
        "as_of": as_of.isoformat(),
        "prompt_version": PROMPT_VERSION,
    }
    if not online and (canned := await _canned(conn, question, llm)):  # type: ignore[arg-type]
        canned.meta = {**meta, "mode": "offline", "canned": True}
        return canned
    tau = await refusal_tau(conn)  # type: ignore[arg-type]
    cands = await retrieve(
        search_q[:MAX_QUERY_CHARS],
        as_of,
        gw,
        conn,  # type: ignore[arg-type]
        iv,
        online,
        trace=trace,
        pin_text=question[:MAX_QUERY_CHARS],
    )
    docs: list[SourceDoc] = []
    if cands and not should_refuse(cands, tau):
        with trace.span("expand"):
            docs = await expand(
                [c.parent_id for c in cands],
                conn,  # type: ignore[arg-type]
                iv,
                as_of,
                max_extra=4 if online else 0,
            )
    if not docs:
        return Plan("refused", llm, text=REFUSAL_TEXT, meta={**meta, "mode": "refused"})
    sources = _source_parts(docs)
    if not online:
        listing = "\n".join(f"- [{sid}] {title}" for sid, _, title in sources)
        return Plan(
            "offline",
            llm,
            sources,
            f"{OFFLINE_TEXT}\n\n{listing}",
            docs=docs,
            meta={**meta, "mode": "offline"},
        )
    return Plan(
        "rag",
        llm,
        sources,
        messages=build_messages(question, docs, history, as_of),
        docs=docs,
        meta={**meta, "mode": "rag"},
    )


async def flush_trace(trace: Trace) -> None:
    """Flush Langfuse (chặn mạng nên chạy trong thread). Đường thường: chạy làm BackgroundTask sau khi response đã đóng."""
    if trace.enabled:
        await anyio.to_thread.run_sync(trace.flush)


async def close_trace(
    trace: Trace,
    output: str | None = None,
    meta: dict | None = None,
    flush: bool = True,
) -> None:
    """Kết thúc trace. `flush=True` (đường hủy/lỗi, response không còn chạy được background): flush shield nhưng tối đa ABORT_FLUSH_S."""
    trace.finish(output, meta)
    if flush and trace.enabled:
        with anyio.move_on_after(ABORT_FLUSH_S, shield=True):
            await anyio.to_thread.run_sync(trace.flush, abandon_on_cancel=True)


class _Overtime(Exception):
    pass


async def _disconnected(request: Request | None) -> bool:
    if request is None:
        return False
    try:
        return await request.is_disconnected()
    except Exception:
        return False


async def event_stream(
    plan: Plan,
    gw: Gateway,
    trace: Trace,
    request: Request | None = None,
    deadline: float | None = None,
) -> AsyncIterator[bytes]:
    """`deadline`: thời điểm `time.monotonic()` phải xong (None = không giới hạn). Ngắt kết nối: dừng, đóng upstream, không phát gì thêm."""
    answer: list[str] = []
    upstream = None
    meta = dict(plan.meta)
    done = False
    try:
        try:
            yield stream.sse(stream.start("msg_" + trace.trace_id[:12]))
            yield stream.sse(stream.data_status(plan.llm, plan.mode))  # type: ignore[arg-type]
            for sid, url, title in plan.sources:
                yield stream.sse(stream.source_url(sid, url, title))
            yield stream.sse(stream.text_start(TEXT_ID))
            if plan.mode == "rag":
                upstream = gw.chat_stream(plan.messages or [])
                it = upstream.__aiter__()
                n = 0
                with trace.span("llm"):
                    while True:
                        if n % DISCONNECT_POLL_EVERY == 0 and await _disconnected(
                            request
                        ):
                            meta["disconnected"] = True
                            return
                        left = None if deadline is None else deadline - time.monotonic()
                        if left is not None and left <= 0:
                            raise _Overtime
                        try:
                            async with asyncio.timeout(left) as scope:
                                delta = await anext(it)
                        except StopAsyncIteration:
                            break
                        except TimeoutError:
                            if scope.expired():
                                raise _Overtime from None
                            raise
                        n += 1
                        answer.append(delta)
                        yield stream.sse(stream.text_delta(TEXT_ID, delta))
            else:
                answer.append(plan.text or "")
                yield stream.sse(stream.text_delta(TEXT_ID, plan.text or ""))
            yield stream.sse(stream.text_end(TEXT_ID))
            if plan.mode == "rag":
                rep = check_citations("".join(answer), plan.docs)
                if rep.invalid or rep.article_mismatch:
                    yield stream.sse(
                        stream.data_citation_warning(rep.invalid, rep.article_mismatch)
                    )
            yield stream.sse(stream.data_trace(trace.trace_id))
            yield stream.sse(stream.finish())
        except _Overtime:
            meta["error"] = "timeout"
            yield stream.sse(stream.error(OVERTIME_TEXT))
        except Exception as e:  # sau `start`: báo lỗi trong stream, không có `finish`
            log.warning("chat stream failed: %r", e)
            meta["error"] = type(e).__name__
            yield stream.sse(stream.error(STREAM_ERROR))
        yield stream.DONE
        done = True  # tới đây tức là response đã gửi hết; flush do BackgroundTask lo
    finally:  # chạy cả khi client ngắt kết nối (hủy / GeneratorExit)
        with anyio.CancelScope(shield=True):
            if upstream is not None:
                try:
                    await upstream.aclose()
                except Exception:
                    log.debug("upstream close failed", exc_info=True)
        await close_trace(trace, "".join(answer), meta, flush=not done)


@router.post("/api/chat")
async def chat(request: Request, settings: Settings = Depends(get_settings)):
    deadline = time.monotonic() + CHAT_BUDGET_S
    question, history, as_of = parse_chat(await read_json(request))
    if not await ratelimit.check(
        ratelimit.client_ip(request), settings=settings, client=request.app.state.http
    ):
        raise HTTPException(429, RATE_LIMITED)
    gw: Gateway = request.app.state.gw
    trace = Trace(question, settings)
    try:
        plan = await build_plan(request, gw, question, history, as_of, trace)
    except BaseException as e:
        await close_trace(trace, None, {"error": type(e).__name__})
        raise
    return StreamingResponse(
        event_stream(plan, gw, trace, request, deadline),
        headers=stream.STREAM_HEADERS,
        background=BackgroundTask(flush_trace, trace),
    )
