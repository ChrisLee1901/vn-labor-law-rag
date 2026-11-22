"""Emitter for the Vercel AI SDK UI Message Stream protocol (SSE).

Chunk shapes verified 2026-11-22 against https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
and https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data (see docs/ai-sdk-protocol.md).
Unverified: the `transient` field on data parts is documented only as a writer.write()
option, not as raw wire JSON (we do not emit it); the optional `title` on source-url
is not shown in the docs' wire example (it is in the UIMessageChunk type).
"""

import json
from typing import Literal

DONE = b"data: [DONE]\n\n"
STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
}


def sse(part: dict) -> bytes:
    return b"data: " + json.dumps(part, ensure_ascii=False, separators=(",", ":")).encode("utf-8", errors="replace") + b"\n\n"


def start(message_id: str) -> dict:
    return {"type": "start", "messageId": message_id}


def source_url(sid: str, url: str, title: str) -> dict:
    return {"type": "source-url", "sourceId": sid, "url": url, "title": title}


def text_start(id: str) -> dict:
    return {"type": "text-start", "id": id}


def text_delta(id: str, delta: str) -> dict:
    return {"type": "text-delta", "id": id, "delta": delta}


def text_end(id: str) -> dict:
    return {"type": "text-end", "id": id}


def data_status(llm: str, mode: Literal["rag", "offline", "refused"]) -> dict:
    return {"type": "data-status", "data": {"llm": llm, "mode": mode}}


def data_trace(trace_id: str) -> dict:
    return {"type": "data-trace", "data": {"trace_id": trace_id}}


def data_citation_warning(invalid: list[str], mismatch: list[str]) -> dict:
    return {"type": "data-citation-warning", "data": {"invalid": invalid, "mismatch": mismatch}}


def error(text: str) -> dict:
    return {"type": "error", "errorText": text}


def finish() -> dict:
    return {"type": "finish"}
