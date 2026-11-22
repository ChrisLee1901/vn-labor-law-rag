import json

from app import stream as s


def _parse(b: bytes) -> dict | str:
    assert b.startswith(b"data: ") and b.endswith(b"\n\n")
    body = b[6:-2].decode()
    return body if body == "[DONE]" else json.loads(body)


def test_sse_utf8_vietnamese():
    raw = s.sse(s.text_delta("t1", "Điều")).decode("utf-8")
    assert "Điều" in raw and chr(92) + "u" not in raw


def test_sequence_order():
    chunks = [
        s.start("m1"),
        s.data_status("online", "rag"),
        s.source_url("LBHXH-2024:D33", "https://x/y", "Điều 33"),
        s.source_url("BLLD:D5", "https://x/z", "Điều 5"),
        s.text_start("t1"),
        s.text_delta("t1", "a"),
        s.text_delta("t1", "b"),
        s.text_end("t1"),
        s.finish(),
    ]
    types = [_parse(s.sse(c))["type"] for c in chunks]
    assert types == ["start", "data-status", "source-url", "source-url",
                     "text-start", "text-delta", "text-delta", "text-end", "finish"]
    assert _parse(s.DONE) == "[DONE]"


def test_headers():
    assert s.STREAM_HEADERS == {
        "x-vercel-ai-ui-message-stream": "v1",
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
    }


def test_builder_shapes():
    assert s.start("m1") == {"type": "start", "messageId": "m1"}
    assert s.source_url("a", "https://u", "T") == {
        "type": "source-url", "sourceId": "a", "url": "https://u", "title": "T"}
    assert s.text_start("t") == {"type": "text-start", "id": "t"}
    assert s.text_delta("t", "x") == {"type": "text-delta", "id": "t", "delta": "x"}
    assert s.text_end("t") == {"type": "text-end", "id": "t"}
    assert s.data_status("offline", "offline") == {
        "type": "data-status", "data": {"llm": "offline", "mode": "offline"}}
    assert s.data_trace("tr1") == {"type": "data-trace", "data": {"trace_id": "tr1"}}
    assert s.data_citation_warning(["X:D1"], ["Y:D2"]) == {
        "type": "data-citation-warning", "data": {"invalid": ["X:D1"], "mismatch": ["Y:D2"]}}
    assert s.error("lỗi") == {"type": "error", "errorText": "lỗi"}
    assert s.finish() == {"type": "finish"}


def test_sse_roundtrip_bytes():
    assert s.sse({"type": "finish"}) == b'data: {"type":"finish"}\n\n'
