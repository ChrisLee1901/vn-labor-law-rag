"""Task 7.1: span, metadata, score gửi tới một Langfuse giả (SDK thật -> server loopback), và Langfuse hỏng không ảnh hưởng người dùng."""

import re
import time

import pytest
from app import tracing
from app.api.chat import flush_trace
from app.legal.normalize import question_key
from apimock import QUESTION, Gateway, parse_sse
from lfsink import LangfuseSink
from test_chat import ask, turn

pytestmark = pytest.mark.usefixtures("seeded")

SIX = ["condense", "embed", "hybrid_search", "rerank", "expand", "llm"]
PHONE, CCCD = "0912345678", "001203004567"
PII_Q = f"{QUESTION} Liên hệ {PHONE}, CCCD {CCCD}"


@pytest.fixture
def lf(env, request):
    """Langfuse giả; `indirect` param = kwargs của LangfuseSink (status, delay)."""
    sink = LangfuseSink(**getattr(request, "param", {}))
    env.setenv(
        "LANGFUSE_PUBLIC_KEY", f"pk-{sink.host[-5:]}"
    )  # SDK giữ singleton theo public key
    env.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    env.setenv("LANGFUSE_HOST", sink.host)
    yield sink
    tracing._client.cache_clear()
    sink.close()


def trace_id(parts) -> str:
    return next(p for p in parts if isinstance(p, dict) and p["type"] == "data-trace")[
        "data"
    ]["trace_id"]


def by_name(sink: LangfuseSink) -> dict[str, dict]:
    return {s["name"]: s for s in sink.spans}


def wait_spans(sink, n):
    assert sink.wait_for(lambda: len(sink.spans) >= n), [s["name"] for s in sink.spans]


def test_online_turn_two_emits_all_six_spans_with_metadata(lf, client):
    history = [turn("user", "Lương tối thiểu?"), turn("assistant", "Theo Điều 3.")]
    with Gateway(condensed=QUESTION):
        r = ask(client, QUESTION, history=history)
    parts = parse_sse(r.text)
    wait_spans(lf, 7)
    spans = by_name(lf)
    assert sorted(spans) == sorted(["chat", *SIX])
    tid = trace_id(parts)
    assert all(
        s["trace_id"] == tid for s in spans.values()
    )  # id client nhận == id ingest
    for name in SIX:  # mỗi span có thời gian bắt đầu/kết thúc để suy ra độ trễ
        assert 0 < spans[name]["start"] <= spans[name]["end"], name
    md = spans["chat"]["metadata"]
    assert md["index_version"] == "1" and md["mode"] == "rag"
    assert md["prompt_version"] == "answer_v1"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", md["as_of"])


def test_online_first_turn_skips_only_condense(lf, client):
    with Gateway():
        ask(client)
    wait_spans(lf, 6)
    assert sorted(by_name(lf)) == sorted(["chat", *SIX[1:]])


def test_offline_emits_only_fts_spans(lf, client):
    with Gateway(online=False):
        parts = parse_sse(ask(client).text)
    wait_spans(lf, 3)
    spans = by_name(lf)
    assert sorted(spans) == ["chat", "expand", "hybrid_search"]
    assert spans["chat"]["metadata"]["mode"] == "offline"
    assert spans["chat"]["trace_id"] == trace_id(parts)


def test_canned_answer_has_only_root(lf, client, seeded):
    seeded.execute(
        "insert into canned_answers(question_norm, answer, sources) values (%s, 'đã lưu', '[]')",
        (question_key(QUESTION),),
    )
    with Gateway(online=False):
        ask(client)
    wait_spans(lf, 1)
    spans = by_name(lf)
    assert list(spans) == ["chat"]
    assert spans["chat"]["metadata"]["mode"] == "offline"
    assert spans["chat"]["metadata"]["canned"] == "True"


def test_refused_mode_recorded(lf, client):
    with Gateway(rerank=0.1):
        ask(client)
    wait_spans(lf, 4)
    assert by_name(lf)["chat"]["metadata"]["mode"] == "refused"
    assert "llm" not in by_name(lf)


def test_pii_never_reaches_langfuse(lf, client):
    history = [turn("user", f"gọi {PHONE}"), turn("assistant", "ok")]
    with Gateway(condensed=QUESTION, answer=(f"Liên hệ {PHONE} nhé [S1].",)):
        parse_sse(ask(client, PII_Q, history=history).text)
    wait_spans(lf, 7)
    assert PHONE not in lf.raw_text and CCCD not in lf.raw_text
    assert "[đã ẩn]" in lf.raw_text  # đã che, không phải bị bỏ trống


def test_feedback_becomes_score_on_the_same_trace(lf, client, seeded):
    with Gateway():
        tid = trace_id(parse_sse(ask(client).text))
    r = client.post(
        "/api/feedback",
        json={"trace_id": tid, "score": -1, "comment": f"sai, gọi {PHONE}"},
    )
    assert r.status_code == 204
    assert lf.wait_for(lambda: lf.scores), "không có score"
    (s,) = lf.scores
    assert s["traceId"] == tid and s["name"] == "user-feedback" and s["value"] == -1
    assert PHONE not in s["comment"] and "sai" in s["comment"]
    assert seeded.execute("select trace_id, score from feedback").fetchall() == [
        (tid, -1)
    ]


def test_feedback_without_langfuse_still_204(env, client, seeded):
    r = client.post("/api/feedback", json={"trace_id": "t1", "score": 1})
    assert r.status_code == 204
    assert seeded.execute("select count(*) from feedback").fetchone() == (1,)


@pytest.mark.parametrize(
    "lf", [{"status": 500}, {"delay": 3.0}], ids=["http500", "hang"], indirect=True
)
def test_langfuse_failure_does_not_change_responses(lf, client, seeded, monkeypatch):
    monkeypatch.setattr(tracing, "FLUSH_TIMEOUT_S", 0.5)
    t0 = time.monotonic()
    with Gateway():
        r = ask(client)
    assert r.status_code == 200
    parts = parse_sse(r.text)
    assert parts[-1] == "[DONE]" and "5.310.000" in "".join(
        p["delta"] for p in parts if isinstance(p, dict) and p["type"] == "text-delta"
    )
    r2 = client.post("/api/feedback", json={"trace_id": trace_id(parts), "score": 1})
    assert r2.status_code == 204
    assert time.monotonic() - t0 < 2.9  # flush bị chặn bởi timeout, không chờ Langfuse
    assert seeded.execute("select count(*) from feedback").fetchone() == (1,)


async def test_flush_trace_is_bounded(monkeypatch):
    monkeypatch.setattr(tracing, "FLUSH_TIMEOUT_S", 0.2)

    class Hang:
        enabled = True

        def flush(self):
            time.sleep(1.5)

    t0 = time.monotonic()
    await flush_trace(Hang())  # type: ignore[arg-type]
    assert time.monotonic() - t0 < 1.0
