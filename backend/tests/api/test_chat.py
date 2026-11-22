import json
import re

import psycopg
import pytest
from app import ratelimit
from app.api import chat as chat_mod
from app.api import deps
from app.api.deps import DB_DOWN
from app.legal.normalize import question_key
from app.llm.citations import REFUSAL_TEXT
from apimock import QUESTION, Gateway, parse_sse, types

pytestmark = pytest.mark.usefixtures("seeded")


def ask(client, text=QUESTION, history=(), **extra):
    msgs = [
        *history,
        {"id": "u", "role": "user", "parts": [{"type": "text", "text": text}]},
    ]
    return client.post("/api/chat", json={"messages": msgs, **extra})


def turn(role, text):
    return {"id": role[0], "role": role, "parts": [{"type": "text", "text": text}]}


def status(parts):
    return next(
        p["data"] for p in parts if isinstance(p, dict) and p["type"] == "data-status"
    )


def text_of(parts):
    return "".join(
        p["delta"] for p in parts if isinstance(p, dict) and p["type"] == "text-delta"
    )


def test_chat_online_streams_sources_then_text(client):
    with Gateway() as gw:
        r = ask(client)
    assert r.status_code == 200
    assert (
        r.headers["x-vercel-ai-ui-message-stream"] == "v1"
        and r.headers["cache-control"] == "no-cache"
    )
    assert r.headers["x-content-type-options"] == "nosniff"
    parts = parse_sse(r.text)
    t = types(parts)
    assert (
        t[0] == "start"
        and t[1] == "data-status"
        and t[-3:] == ["data-trace", "finish", "[DONE]"]
    )
    assert t.index("source-url") < t.index("text-delta")
    assert "".join(t[2:-3]).count("text-start") == 1 and t.index("text-end") > t.index(
        "text-delta"
    )
    assert status(parts) == {"llm": "online", "mode": "rag"}
    src = next(p for p in parts if isinstance(p, dict) and p["type"] == "source-url")
    assert src == {
        "type": "source-url",
        "sourceId": "S1",
        "url": "/van-ban/ND293-2025#D3",
        "title": "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu",
    }
    assert "5.310.000" in text_of(parts) and "data-citation-warning" not in t
    assert re.fullmatch(
        r"[0-9a-f]{32}",
        next(p for p in parts if isinstance(p, dict) and p["type"] == "data-trace")[
            "data"
        ]["trace_id"],
    )
    assert gw.stream_calls == 1


def test_chat_citation_warning_for_unknown_source(client):
    with Gateway(answer=("Theo Điều 3 [S1] và [S9].",)):
        parts = parse_sse(ask(client).text)
    w = next(
        p for p in parts if isinstance(p, dict) and p["type"] == "data-citation-warning"
    )
    assert w["data"] == {"invalid": ["S9"], "mismatch": []}
    t = types(parts)
    assert (
        t.index("text-end") < t.index("data-citation-warning") < t.index("data-trace")
    )


def test_chat_offline_returns_fts_sources(client):
    with Gateway(online=False) as gw:
        parts = parse_sse(ask(client).text)
    assert status(parts) == {"llm": "offline", "mode": "offline"}
    assert types(parts).count("source-url") >= 1 and types(parts)[-2:] == [
        "finish",
        "[DONE]",
    ]
    assert text_of(parts).startswith(
        chat_mod.OFFLINE_TEXT
    ) and "- [S1] 293/2025/NĐ-CP, Điều 3" in text_of(parts)
    assert gw.chat_route.call_count == 0


def test_chat_offline_without_hits_is_refused(client):
    with Gateway(online=False) as gw:
        parts = parse_sse(ask(client, "xyzzy qwerty").text)
    assert (
        status(parts) == {"llm": "offline", "mode": "refused"}
        and text_of(parts) == REFUSAL_TEXT
    )
    assert "source-url" not in types(parts) and gw.chat_route.call_count == 0


def test_chat_refuses_without_llm_call(client):
    with Gateway(rerank=0.1) as gw:
        parts = parse_sse(ask(client).text)
    assert status(parts) == {"llm": "online", "mode": "refused"}
    assert text_of(parts) == REFUSAL_TEXT and "source-url" not in types(parts)
    assert types(parts)[-2:] == ["finish", "[DONE]"]
    assert gw.chat_route.call_count == 0


def test_refusal_threshold_read_from_app_config(client, seeded):
    seeded.execute("update app_config set value = '0.95' where key = 'refusal_tau'")
    with Gateway(rerank=0.9) as gw:
        assert status(parse_sse(ask(client).text))["mode"] == "refused"
    assert gw.chat_route.call_count == 0


def test_pinned_candidate_never_refused(client, seeded):
    seeded.execute("update app_config set value = '0.99' where key = 'refusal_tau'")
    with Gateway(rerank=0.0):
        parts = parse_sse(
            ask(client, "Điều 12 Nghị định 145/2020/NĐ-CP quy định gì").text
        )
    assert status(parts)["mode"] == "rag"
    assert (
        next(p for p in parts if isinstance(p, dict) and p["type"] == "source-url")[
            "sourceId"
        ]
        == "S1"
    )


def test_chat_stream_midway_disconnect_emits_error_then_done(client):
    with Gateway(answer=("Một ", "hai ", "ba")) as gw:
        gw.stream_error = True
        parts = parse_sse(ask(client).text)
    deltas = [
        p["delta"] for p in parts if isinstance(p, dict) and p["type"] == "text-delta"
    ]
    assert deltas == ["Một ", "hai "]
    err = [p for p in parts if isinstance(p, dict) and p["type"] == "error"]
    assert len(err) == 1 and "gián đoạn" in err[0]["errorText"]
    assert parts[-1] == "[DONE]" and "finish" not in types(parts)


def test_chat_db_down_returns_503_vietnamese(client):
    class DownPool:
        def connection(self, timeout=None):
            raise psycopg.OperationalError("connection refused")

        async def close(self):
            pass

    real = client.app.state.pool
    client.app.state.pool = DownPool()
    with Gateway():
        r = ask(client)
    client.app.state.pool = real
    assert (
        r.status_code == 503
        and r.json()["detail"] == DB_DOWN
        and "Cơ sở dữ liệu" in DB_DOWN
    )


def test_chat_no_database_configured_is_503(env):
    env.delenv("DATABASE_URL")
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as c, Gateway():
        assert ask(c).status_code == 503


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (
            {"messages": [turn("user", "a" * 1001)]},
            "Câu hỏi quá dài (tối đa 1000 ký tự).",
        ),
        ({"messages": [turn("user", "   ")]}, "Câu hỏi không được để trống."),
        ({"messages": []}, "Cần ít nhất một tin nhắn."),
        (
            {"messages": [turn("user", "x")] * 11},
            "Cuộc trò chuyện quá dài (tối đa 10 tin nhắn).",
        ),
        (
            {"messages": [turn("user", "x"), turn("assistant", "y")]},
            "Tin nhắn cuối phải là của người dùng.",
        ),
        (
            {"messages": [turn("user", "x")], "as_of": "2026-13-45"},
            "Ngày tra cứu không hợp lệ (định dạng YYYY-MM-DD).",
        ),
        (
            {"messages": [turn("user", "x")], "as_of": "20260101"},
            "Ngày tra cứu không hợp lệ (định dạng YYYY-MM-DD).",
        ),
        ({"messages": [{"role": "system", "parts": []}]}, "Tin nhắn không hợp lệ."),
        ([1, 2], "Cần ít nhất một tin nhắn."),
    ],
)
def test_chat_input_validation_422(client, body, detail):
    r = client.post("/api/chat", json=body)
    assert r.status_code == 422 and r.json() == {"detail": detail}
    assert r.headers["cache-control"] == "no-store"


def test_chat_input_too_long_422_exactly_1000_ok(client):
    with Gateway():
        assert ask(client, "a" * 1000).status_code == 200
        assert ask(client, "a" * 1001).status_code == 422


def test_chat_invalid_json_422(client):
    r = client.post(
        "/api/chat", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422 and "detail" in r.json()


def test_chat_nfd_question_is_normalised(client):
    import unicodedata

    nfd = unicodedata.normalize("NFD", QUESTION)
    with Gateway() as gw:
        assert status(parse_sse(ask(client, nfd).text))["mode"] == "rag"
    assert any(QUESTION in m["content"] for m in gw.chat_bodies[0]["messages"])


def test_chat_rate_limited_429(client, monkeypatch):
    calls = []

    async def deny(ip, **kw):
        calls.append((ip, kw))
        return False

    monkeypatch.setattr(ratelimit, "check", deny)
    with Gateway() as gw:
        r = ask(client)
    assert r.status_code == 429 and r.json() == {
        "detail": "Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút."
    }
    assert (
        calls[0][1]["client"] is client.app.state.http
    )  # client dùng chung được tiêm vào
    assert gw.chat_route.call_count == 0


def test_chat_rate_limit_allows_when_under(client, monkeypatch):
    async def allow(ip, **kw):
        return True

    monkeypatch.setattr(ratelimit, "check", allow)
    with Gateway():
        assert ask(client).status_code == 200


def test_canned_answer_offline(client, seeded):
    seeded.execute(
        "insert into canned_answers(question_norm, answer, sources) values (%s, %s, %s::jsonb)",
        (
            question_key(QUESTION),
            "Mức lương vùng I là 5.310.000 đồng [S1].",
            json.dumps(
                [
                    {
                        "url": "/van-ban/ND293-2025#D3",
                        "title": "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu",
                    }
                ]
            ),
        ),
    )
    with Gateway(online=False) as gw:
        parts = parse_sse(
            ask(client, "  MỨC LƯƠNG tối thiểu vùng I là bao nhiêu???  ").text
        )
    assert status(parts) == {"llm": "offline", "mode": "offline"}
    body = text_of(parts)
    assert "Câu trả lời đã lưu từ phiên trực tuyến" in body and "5.310.000" in body
    assert [
        p["url"] for p in parts if isinstance(p, dict) and p["type"] == "source-url"
    ] == ["/van-ban/ND293-2025#D3"]
    assert types(parts)[-2:] == ["finish", "[DONE]"] and gw.chat_route.call_count == 0


def test_canned_ignored_when_online(client, seeded):
    seeded.execute(
        "insert into canned_answers(question_norm, answer, sources) values (%s, 'cũ', '[]')",
        (question_key(QUESTION),),
    )
    with Gateway():
        parts = parse_sse(ask(client).text)
    assert status(parts)["mode"] == "rag" and "cũ" not in text_of(parts)


def test_condense_used_from_second_turn(client):
    hist = [
        turn("user", "Lương tối thiểu vùng I?"),
        turn("assistant", "5.310.000 đồng [S1]"),
    ]
    with Gateway(condensed="mức lương tối thiểu vùng I tháng 7") as gw:
        parts = parse_sse(ask(client, "còn vùng II?", hist).text)
    assert status(parts)["mode"] == "rag"
    assert gw.embed_inputs == ["mức lương tối thiểu vùng I tháng 7"]
    assert [b.get("stream") for b in gw.chat_bodies] == [False, True]
    assert (
        "còn vùng II?" in gw.chat_bodies[1]["messages"][-1]["content"]
    )  # prompt cuối vẫn dùng câu hỏi gốc


def test_condense_failure_falls_back_to_raw_question(client):
    hist = [
        turn("user", "Lương tối thiểu vùng I?"),
        turn("assistant", "5.310.000 đồng"),
    ]
    with Gateway() as gw:
        gw.condense_fails = True
        parts = parse_sse(ask(client, "mức lương tối thiểu vùng II thì sao", hist).text)
    assert status(parts)["mode"] == "rag" and types(parts)[-2:] == ["finish", "[DONE]"]
    assert gw.embed_inputs == ["mức lương tối thiểu vùng II thì sao"]


def test_first_turn_and_offline_do_not_condense(client):
    with Gateway() as gw:
        ask(client)
    assert [b.get("stream") for b in gw.chat_bodies] == [True]
    deps.reset_caches()
    hist = [turn("user", "a"), turn("assistant", "b")]
    with Gateway(online=False) as gw2:
        ask(client, "lương tối thiểu", hist)
    assert gw2.chat_route.call_count == 0


def test_llm_health_cached_15s(client):
    with Gateway() as gw:
        ask(client)
        ask(client)
    assert gw.health_route.call_count == 1  # /health probe một lần cho hai request
