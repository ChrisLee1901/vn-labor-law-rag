"""Giới hạn thời gian của /api/chat, polling ngắt kết nối, flush Langfuse ngoài đường găng, lỗi chuẩn hóa."""

import asyncio
import time

import pytest
from app import ratelimit, tracing
from app.api import chat as chat_mod
from app.api.chat import Plan, event_stream
from app.config import Settings
from app.retrieval import search as search_mod
from app.retrieval.expand import SourceDoc
from app.tracing import Trace
from apimock import QUESTION, Gateway, parse_sse, types
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded")
NO_LANGFUSE = Settings(
    _env_file=None, LANGFUSE_PUBLIC_KEY=None, LANGFUSE_SECRET_KEY=None
)
OVERTIME = "Mô hình trả lời quá lâu, vui lòng thử lại."


def ask(client, text=QUESTION, history=()):
    msgs = [
        *history,
        {"id": "u", "role": "user", "parts": [{"type": "text", "text": text}]},
    ]
    return client.post("/api/chat", json={"messages": msgs})


def turn(role, text):
    return {"id": role[0], "role": role, "parts": [{"type": "text", "text": text}]}


def status(parts):
    return next(
        p["data"] for p in parts if isinstance(p, dict) and p["type"] == "data-status"
    )


def urls(parts):
    return [
        p["url"] for p in parts if isinstance(p, dict) and p["type"] == "source-url"
    ]


def doc():
    from datetime import date

    return SourceDoc(
        "S1",
        "ND293-2025:D3",
        "ND293-2025",
        "293/2025/NĐ-CP",
        3,
        "t",
        "nd",
        date(2021, 1, 1),
        None,
        "con_hieu_luc",
        False,
    )


def rag_plan():
    return Plan(
        "rag",
        "online",
        [("S1", "/van-ban/ND293-2025#D3", "t")],
        messages=[],
        docs=[doc()],
        meta={"mode": "rag"},
    )


class FakeClient:
    def __init__(self, flush_seconds=0.0):
        self.events, self.flush_seconds = [], flush_seconds

    def start_observation(self, **kw):
        return FakeObs(self.events, kw["name"])

    def flush(self):
        self.events.append("flush")
        time.sleep(self.flush_seconds)

    @property
    def flushed(self):
        return self.events.count("flush")


class FakeObs:
    def __init__(self, events, name):
        self.events, self.name = events, name

    def start_observation(self, **kw):
        return FakeObs(self.events, kw["name"])

    def update(self, **kw):
        pass

    def end(self):
        self.events.append(f"end:{self.name}")


class Upstream:
    """chat_stream giả: `stall_after` delta rồi treo; không đặt thì phát vô hạn mà không bao giờ nhường event loop."""

    def __init__(self, stall_after=None, finite=None):
        self.stall_after, self.finite = stall_after, finite
        self.pulled, self.closed = 0, False

    async def chat_stream(self, messages):
        try:
            while True:
                if self.finite is not None and self.pulled >= self.finite:
                    return
                if self.stall_after is not None and self.pulled >= self.stall_after:
                    await asyncio.sleep(3600)
                self.pulled += 1
                yield "x"
        finally:
            self.closed = True


async def collect(gen):
    return parse_sse(b"".join([c async for c in gen]).decode())


# ---- 1. thời gian tối đa
async def test_endless_nonsuspending_upstream_hits_deadline():
    gw, t0 = Upstream(), time.monotonic()
    parts = await collect(
        event_stream(
            rag_plan(), gw, Trace("q", NO_LANGFUSE), deadline=time.monotonic() + 0.1
        )
    )
    assert (
        types(parts)[-2:] == ["error", "[DONE]"] and parts[-2]["errorText"] == OVERTIME
    )
    assert "finish" not in types(parts) and gw.closed and time.monotonic() - t0 < 3


async def test_stalled_upstream_hits_deadline_via_timeout():
    gw, t0 = Upstream(stall_after=2), time.monotonic()
    parts = await collect(
        event_stream(
            rag_plan(), gw, Trace("q", NO_LANGFUSE), deadline=time.monotonic() + 0.3
        )
    )
    assert types(parts).count("text-delta") == 2 and types(parts)[-2:] == [
        "error",
        "[DONE]",
    ]
    assert (
        parts[-2]["errorText"] == OVERTIME and gw.closed and time.monotonic() - t0 < 3
    )


def test_endpoint_applies_chat_budget(client, monkeypatch):
    monkeypatch.setattr(chat_mod, "CHAT_BUDGET_S", 0.5)
    with Gateway() as gw:
        gw.endless = True
        t0 = time.monotonic()
        parts = parse_sse(ask(client).text)
    assert (
        types(parts)[-2:] == ["error", "[DONE]"] and parts[-2]["errorText"] == OVERTIME
    )
    assert time.monotonic() - t0 < 10


def test_embed_hang_falls_back_to_fts_within_step_timeout(client, monkeypatch):
    monkeypatch.setattr(search_mod, "EMBED_TIMEOUT_S", 0.2)
    calls = []
    with Gateway() as gw:
        gw.hang, gw.probe = {"embed"}, calls.append
        t0 = time.monotonic()
        parts = parse_sse(ask(client).text)
    assert time.monotonic() - t0 < 10
    assert urls(parts) == ["/van-ban/ND293-2025#D3"] and types(parts)[-2:] == [
        "finish",
        "[DONE]",
    ]
    assert calls == ["embed"]  # không rerank sau khi embed hỏng


def test_rerank_hang_falls_back_to_rrf_order(client, monkeypatch):
    monkeypatch.setattr(search_mod, "RERANK_TIMEOUT_S", 0.2)
    with Gateway() as gw:
        gw.hang = {"rerank"}
        parts = parse_sse(ask(client).text)
    assert (
        urls(parts)
        and types(parts)[-2:] == ["finish", "[DONE]"]
        and status(parts)["mode"] == "rag"
    )


def test_condense_hang_uses_raw_question(client, monkeypatch):
    monkeypatch.setattr(chat_mod, "CONDENSE_TIMEOUT_S", 0.2)
    hist = [
        turn("user", "Lương tối thiểu vùng I?"),
        turn("assistant", "5.310.000 đồng"),
    ]
    with Gateway() as gw:
        gw.hang = {"condense"}
        parts = parse_sse(ask(client, "mức lương tối thiểu vùng II thì sao", hist).text)
    assert status(parts)["mode"] == "rag" and types(parts)[-2:] == ["finish", "[DONE]"]
    assert gw.embed_inputs == ["mức lương tối thiểu vùng II thì sao"]


def test_gateway_stream_request_is_capped(client):
    with Gateway() as gw:
        ask(client)
    assert gw.chat_bodies[0]["max_tokens"] == 1024


class CountingPool:
    def __init__(self, real):
        self.real, self.in_use = real, 0

    def connection(self, timeout=None):
        pool = self

        class CM:
            async def __aenter__(self):
                self.cm = pool.real.connection(timeout=timeout)
                conn = await self.cm.__aenter__()
                pool.in_use += 1
                return conn

            async def __aexit__(self, *e):
                pool.in_use -= 1
                return await self.cm.__aexit__(*e)

        return CM()

    async def close(self):
        await self.real.close()


def test_db_connection_not_held_during_embed_and_rerank(client):
    real = client.app.state.pool
    pool = client.app.state.pool = CountingPool(real)
    held = {}
    try:
        with Gateway() as gw:
            gw.probe = lambda name: held.__setitem__(name, pool.in_use)
            parts = parse_sse(ask(client).text)
    finally:
        client.app.state.pool = real
    assert held == {"embed": 0, "rerank": 0}
    assert urls(parts) == ["/van-ban/ND293-2025#D3"] and types(parts)[-2:] == [
        "finish",
        "[DONE]",
    ]
    assert pool.in_use == 0


# ---- 2. ngắt kết nối
class FakeRequest:
    def __init__(self, gw, after):
        self.gw, self.after, self.calls = gw, after, 0

    async def is_disconnected(self):
        self.calls += 1
        return self.gw.pulled >= self.after


async def test_disconnect_polled_every_8_deltas_stops_and_closes_upstream():
    gw = Upstream()
    req = FakeRequest(
        gw, after=3
    )  # client đi sau 3 delta, được phát hiện ở lần poll kế (delta thứ 8)
    fc = FakeClient()
    chunks = [
        c
        async for c in event_stream(
            rag_plan(), gw, Trace("q", NO_LANGFUSE, client=fc), request=req
        )
    ]
    parts = parse_sse(b"".join(chunks).decode())
    assert gw.pulled == 8 and gw.closed and req.calls == 2
    assert types(parts).count("text-delta") == 8
    assert "finish" not in types(parts) and "[DONE]" not in types(parts)
    assert (
        fc.flushed == 1 and "end:chat" in fc.events
    )  # đường hủy: flush có chặn thời gian


async def test_disconnect_checked_before_first_upstream_read():
    gw = Upstream()
    parts = await collect(
        event_stream(
            rag_plan(), gw, Trace("q", NO_LANGFUSE), request=FakeRequest(gw, after=0)
        )
    )
    assert (
        gw.pulled == 0
        and "text-delta" not in types(parts)
        and "[DONE]" not in types(parts)
    )


async def test_connected_client_streams_to_the_end():
    gw = Upstream(finite=20)
    req = FakeRequest(gw, after=10**9)
    parts = await collect(
        event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE), request=req)
    )
    assert types(parts)[-2:] == ["finish", "[DONE]"] and req.calls == 3  # n = 0, 8, 16


# ---- 3. flush không làm chậm kết thúc response
async def test_flush_happens_after_done_not_in_generator():
    fc = FakeClient()
    gw = Upstream(finite=2)
    order = []
    async for chunk in event_stream(rag_plan(), gw, Trace("q", NO_LANGFUSE, client=fc)):
        if chunk == b"data: [DONE]\n\n":
            order.append("done")
            assert fc.flushed == 0
    assert order == ["done"] and fc.flushed == 0  # flush là việc của BackgroundTask


def test_flush_runs_as_background_task_after_response(client, monkeypatch):
    fc = FakeClient()
    monkeypatch.setattr(tracing, "get_client", lambda s: fc)
    with Gateway():
        r = ask(client)
    assert types(parse_sse(r.text))[-2:] == ["finish", "[DONE]"]
    assert (
        fc.events[-1] == "flush"
        and fc.flushed == 1
        and fc.events.index("end:chat") < fc.events.index("flush")
    )


async def test_abort_path_flush_is_bounded_to_about_1s():
    fc = FakeClient(flush_seconds=3)
    t = Trace("q", NO_LANGFUSE, client=fc)
    t0 = time.monotonic()
    await chat_mod.close_trace(t, "out", {})
    assert time.monotonic() - t0 < 2


# ---- minors
def test_explicit_refs_from_raw_question_are_pinned_too(client):
    hist = [
        turn("user", "Lương tối thiểu vùng I?"),
        turn("assistant", "5.310.000 đồng"),
    ]
    with Gateway(
        condensed="mức lương tối thiểu vùng I"
    ) as gw:  # câu độc lập đã mất tham chiếu Điều 12
        parts = parse_sse(
            ask(client, "Điều 12 Nghị định 145/2020/NĐ-CP thì sao", hist).text
        )
    assert gw.embed_inputs == ["mức lương tối thiểu vùng I"]
    got = urls(parts)
    assert got[0] == "/van-ban/ND145-2020#D12" and "/van-ban/ND293-2025#D3" in got
    assert len(got) == len(set(got))


def test_invalid_input_never_calls_rate_limiter(client, monkeypatch):
    calls = []

    async def spy(ip, **kw):
        calls.append(ip)
        return True

    monkeypatch.setattr(ratelimit, "check", spy)
    assert (
        client.post(
            "/api/chat", json={"messages": [turn("user", "a" * 1001)]}
        ).status_code
        == 422
    )
    js = {"content-type": "application/json"}
    assert client.post("/api/chat", content=b"{bad", headers=js).status_code == 422
    assert client.post("/api/chat", content=b"x" * 70000, headers=js).status_code == 413
    assert (
        client.post("/api/chat", content=b"{}").status_code == 415
    )  # text/plain chéo trang
    assert (
        client.get("/docs").status_code == 404
        and client.get("/openapi.json").status_code == 404
    )
    assert calls == []


def test_standard_error_bodies_have_vietnamese_detail_and_safe_headers(env):
    from app.main import create_app

    app = create_app()

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as c:
        cases = [
            (c.get("/api/boom"), 500, "Đã xảy ra lỗi hệ thống, vui lòng thử lại sau."),
            (c.get("/api/khong-co"), 404, "Không tìm thấy đường dẫn."),
            (c.get("/api/chat"), 405, "Phương thức không được hỗ trợ."),
            (c.get("/api/docs/NOPE"), 404, "Không tìm thấy văn bản."),
        ]
    for r, code, detail in cases:
        assert r.status_code == code and r.json() == {"detail": detail}, r.text
        assert (
            r.headers["x-content-type-options"] == "nosniff"
            and r.headers["cache-control"] == "no-store"
        )
    assert "POST" in cases[2][0].headers["allow"]
