import logging
import re

import pytest
from app import tracing
from app.api.chat import Plan, close_trace, event_stream
from app.config import Settings
from app.llm.gateway import LLMOffline
from app.pii import redact_pii
from app.retrieval.expand import SourceDoc
from app.tracing import Trace
from apimock import parse_sse, types

NO_LANGFUSE = Settings(
    _env_file=None, LANGFUSE_PUBLIC_KEY=None, LANGFUSE_SECRET_KEY=None
)


# ---- pii
def test_redact_pii():
    out = redact_pii("CCCD 001203004567, sđt 0912345678")
    assert not re.search(r"\d", out) and out.count("[đã ẩn]") == 2


@pytest.mark.parametrize(
    "text",
    [
        "gọi +84912345678 nhé",
        "mail a.b+c@example.com ok",
        "CMND 079123456 cũ",
        "cccd:012345678901.",
    ],
)
def test_redact_pii_variants(text):
    out = redact_pii(text)
    assert "[đã ẩn]" in out and not re.search(r"\d{9}|@", out)


def test_redact_pii_keeps_legal_numbers():
    s = "Nghị định 145/2020/NĐ-CP, Điều 12, lương 5.310.000 đồng, năm 2026"
    assert redact_pii(s) == s


# ---- tracing no-op
def test_noop_trace_is_complete_and_safe():
    t = Trace("câu hỏi", NO_LANGFUSE)
    assert re.fullmatch(r"[0-9a-f]{32}", t.trace_id) and not t.enabled
    with t.span("embed") as sp:
        sp.update(output=1)
    with pytest.raises(ValueError), t.span("llm"):
        raise ValueError("x")
    t.finish("out", {"mode": "rag"})
    t.flush()
    assert Trace("q", NO_LANGFUSE).trace_id != t.trace_id


# ---- tracing with a fake Langfuse client
class FakeObs:
    def __init__(self, log, name, kw):
        self.log, self.name, self.kw, self.updates, self.ended = (
            log,
            name,
            kw,
            [],
            False,
        )
        log.append(self)

    def start_observation(self, **kw):
        return FakeObs(self.log, kw["name"], kw)

    def update(self, **kw):
        self.updates.append(kw)

    def end(self):
        self.ended = True


class FakeClient:
    def __init__(self):
        self.obs, self.flushed = [], 0

    def start_observation(self, **kw):
        return FakeObs(self.obs, kw["name"], kw)

    def flush(self):
        self.flushed += 1


def test_trace_records_spans_redacted_input_and_metadata():
    fc = FakeClient()
    t = Trace("sđt 0912345678 hỏi gì", NO_LANGFUSE, client=fc)
    root = fc.obs[0]
    assert (
        root.kw["trace_context"] == {"trace_id": t.trace_id}
        and "0912345678" not in root.kw["input"]
    )
    for name in ("condense", "embed", "hybrid_search", "rerank", "expand", "llm"):
        with t.span(name):
            pass
    t.finish(
        "trả lời cho 0912345678",
        {
            "index_version": 1,
            "mode": "rag",
            "prompt_version": "answer_v1",
            "as_of": "2026-01-01",
        },
    )
    assert [o.name for o in fc.obs] == [
        "chat",
        "condense",
        "embed",
        "hybrid_search",
        "rerank",
        "expand",
        "llm",
    ]
    assert all(o.ended for o in fc.obs)
    upd = root.updates[0]
    assert upd["metadata"] == {
        "index_version": "1",
        "mode": "rag",
        "prompt_version": "answer_v1",
        "as_of": "2026-01-01",
    }
    assert "0912345678" not in upd["output"]


def test_trace_span_marks_error_level():
    fc = FakeClient()
    t = Trace("q", NO_LANGFUSE, client=fc)
    with pytest.raises(RuntimeError), t.span("llm"):
        raise RuntimeError
    assert fc.obs[1].updates[0]["level"] == "ERROR" and fc.obs[1].ended


class Exploding:
    def start_observation(self, **kw):
        raise RuntimeError("langfuse down")

    def flush(self):
        raise RuntimeError("flush down")


def test_tracing_errors_never_propagate():
    t = Trace("q", NO_LANGFUSE, client=Exploding())
    with t.span("embed"):
        pass
    t.finish("x", {})
    t.flush()
    assert re.fullmatch(r"[0-9a-f]{32}", t.trace_id)

    class BadRoot(FakeObs):
        def start_observation(self, **kw):
            raise RuntimeError

        def update(self, **kw):
            raise RuntimeError

        def end(self):
            raise RuntimeError

    class C(FakeClient):
        def start_observation(self, **kw):
            return BadRoot(self.obs, "chat", kw)

    t2 = Trace("q", NO_LANGFUSE, client=C())
    with t2.span("embed"):
        pass
    t2.finish("x", {})


def test_get_client_none_without_keys_and_survives_init_error(monkeypatch):
    assert tracing.get_client(NO_LANGFUSE) is None

    def boom(*a):
        raise RuntimeError("bad key")

    monkeypatch.setattr(tracing, "_client", boom)
    assert (
        tracing.get_client(
            Settings(_env_file=None, LANGFUSE_PUBLIC_KEY="p", LANGFUSE_SECRET_KEY="s")
        )
        is None
    )


async def test_close_trace_flushes_in_thread():
    fc = FakeClient()
    t = Trace("q", NO_LANGFUSE, client=fc)
    await close_trace(t, "out", {"mode": "rag"})
    assert fc.flushed == 1 and fc.obs[0].ended


# ---- event_stream: lifecycle
def doc():
    from datetime import date

    return SourceDoc(
        "S1",
        "ND293-2025:D3",
        "ND293-2025",
        "293/2025/NĐ-CP",
        3,
        "Mức lương",
        "nd",
        date(2021, 1, 1),
        None,
        "con_hieu_luc",
        False,
    )


class FakeGw:
    def __init__(self, deltas, then=None):
        self.deltas, self.then = deltas, then
        self.closed = False

    async def chat_stream(self, messages):
        try:
            for d in self.deltas:
                yield d
            if self.then:
                raise self.then
        finally:
            self.closed = True


def rag_plan():
    return Plan(
        "rag",
        "online",
        [("S1", "/van-ban/ND293-2025#D3", "t")],
        messages=[],
        docs=[doc()],
        meta={"mode": "rag"},
    )


async def collect(gen):
    return parse_sse(b"".join([c async for c in gen]).decode())


async def test_event_stream_happy_path_and_trace_finish():
    fc = FakeClient()
    gw = FakeGw(["Điều 3 ", "[S1]"])
    parts = await collect(
        event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE, client=fc))
    )
    assert types(parts) == [
        "start",
        "data-status",
        "source-url",
        "text-start",
        "text-delta",
        "text-delta",
        "text-end",
        "data-trace",
        "finish",
        "[DONE]",
    ]
    assert gw.closed and fc.flushed == 0  # flush chạy ở BackgroundTask sau response
    assert [o.name for o in fc.obs] == ["chat", "llm"] and fc.obs[0].updates[0][
        "output"
    ] == "Điều 3 [S1]"


async def test_event_stream_llm_offline_before_first_token_is_error_then_done():
    gw = FakeGw([], then=LLMOffline("x"))
    parts = await collect(event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE)))
    t = types(parts)
    assert t[-2:] == ["error", "[DONE]"] and "finish" not in t and "data-trace" not in t


async def test_event_stream_unexpected_exception_is_error_then_done(caplog):
    caplog.set_level(logging.WARNING)
    gw = FakeGw(["a"], then=RuntimeError("boom"))
    parts = await collect(event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE)))
    assert types(parts)[-2:] == ["error", "[DONE]"]
    assert "Kết nối tới mô hình bị gián đoạn" in parts[-2]["errorText"]


async def test_event_stream_client_disconnect_closes_upstream_and_trace():
    fc = FakeClient()
    gw = FakeGw(["một", "hai", "ba"])
    gen = event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE, client=fc))
    seen = []
    async for chunk in gen:
        seen.append(chunk)
        if b"text-delta" in chunk:
            break
    assert not gw.closed
    await gen.aclose()  # Starlette đóng generator khi client ngắt kết nối
    assert gw.closed and fc.flushed == 1 and all(o.ended for o in fc.obs)


async def test_event_stream_lone_surrogate_does_not_crash():
    gw = FakeGw(["xin \ud800 chào"])
    parts = await collect(event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE)))
    assert types(parts)[-2:] == ["finish", "[DONE]"]


async def test_event_stream_fixed_text_modes_do_not_call_llm():
    gw = FakeGw(["nope"])
    plan = Plan(
        "refused",
        "offline",
        text="Tôi không tìm thấy căn cứ trong các văn bản hiện có.",
    )
    parts = await collect(event_stream(plan, gw, Trace("q", NO_LANGFUSE)))
    assert types(parts) == [
        "start",
        "data-status",
        "text-start",
        "text-delta",
        "text-end",
        "data-trace",
        "finish",
        "[DONE]",
    ]
    assert not gw.closed
