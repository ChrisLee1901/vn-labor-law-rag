import contextlib

import psycopg
import pytest
from app.api.deps import DB_DOWN
from apimock import Gateway
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded")


class DownPool:
    def connection(self, timeout=None):
        raise psycopg.OperationalError("down")

    async def close(self):
        pass


@contextlib.contextmanager
def db_down(client):
    """Thay pool tạm thời; phải trả pool thật lại để lifespan đóng nó (nếu không worker của pool treo khi đóng loop)."""
    real, client.app.state.pool = client.app.state.pool, DownPool()
    try:
        yield
    finally:
        client.app.state.pool = real


# ---- health
def test_health_ok(client):
    with Gateway():
        r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {
        "llm": "online",
        "db": "ok",
        "index_version": 1,
    }
    assert r.headers["cache-control"] == "no-store"


def test_health_db_down_and_llm_offline_is_still_200(client):
    with db_down(client), Gateway(online=False):
        r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {
        "llm": "offline",
        "db": "down",
        "index_version": 0,
    }
    assert r.headers["cache-control"] == "no-store"


def test_health_probe_timeout_means_offline(client, monkeypatch):
    import asyncio

    from app.api import deps

    async def slow():
        await asyncio.sleep(10)

    monkeypatch.setattr(deps, "PROBE_TIMEOUT", 0.05)
    monkeypatch.setattr(client.app.state.gw, "health", slow)
    assert client.get("/api/health").json()["llm"] == "offline"


# ---- docs
@pytest.fixture
def docs_data(seeded):
    c = seeded
    c.execute(
        """insert into legal_docs(code, number, title, doc_type, issuer, issued_on, effective_from, effective_to, status, amends, source_url) values
           ('A-1', '1/2025/NĐ-CP', 'Văn bản A', 'nghi_dinh', 'Chính phủ', '2025-01-01', '2025-02-01', null, 'con_hieu_luc', '{ND145-2020}', 'https://x/a'),
           ('NULL-TYPE', 'n', 't', null, null, null, '2025-01-01', null, 'con_hieu_luc', '{}', null),
           ('NULL-STATUS', 'n', 't', 'luat', null, null, '2025-01-01', null, null, '{}', null),
           ('NULLNUM', null, null, 'luat', null, null, '2025-01-01', null, 'het_hieu_luc', '{}', null)"""
    )
    for i, num, suf, kind, content in [
        ("A-1:D10", 10, None, "dieu", "mười"),
        ("A-1:D2", 2, None, "dieu", None),  # NULL content
        ("A-1:D2a", 2, "a", "dieu", "hai a"),
        ("A-1:PL1", 1, None, "phu_luc", "phụ lục"),
        ("NULL-TYPE:D1", 1, None, "dieu", "x"),
    ]:
        c.execute(
            "insert into articles(index_version, id, doc_code, number, suffix, title, content, kind) values (1, %s, %s, %s, %s, 't', %s, %s)",
            (i, i.split(":")[0], num, suf, content, kind),
        )
    # index version khác không được tính
    c.execute(
        "insert into articles(index_version, id, doc_code, number, content) values (2, 'A-1:D99', 'A-1', 99, 'v2')"
    )
    return c


def test_docs_list_filters_nulls_counts_dieu_only(client, docs_data):
    r = client.get("/api/docs")
    assert (
        r.status_code == 200 and r.headers["cache-control"] == "public, s-maxage=3600"
    )
    by = {d["code"]: d for d in r.json()}
    assert set(by) == {
        "A-1",
        "NULLNUM",
        "ND293-2025",
        "ND145-2020",
    }  # NULL doc_type / status bị loại
    assert by["A-1"] == {
        "code": "A-1",
        "number": "1/2025/NĐ-CP",
        "title": "Văn bản A",
        "doc_type": "nghi_dinh",
        "effective_from": "2025-02-01",
        "effective_to": None,
        "status": "con_hieu_luc",
        "articles": 3,
    }
    assert by["NULLNUM"]["number"] is None and by["NULLNUM"]["articles"] == 0


def test_docs_detail(client, docs_data):
    r = client.get("/api/docs/A-1")
    assert (
        r.status_code == 200 and r.headers["cache-control"] == "public, s-maxage=3600"
    )
    body = r.json()
    assert body["doc"] == {
        "code": "A-1",
        "number": "1/2025/NĐ-CP",
        "title": "Văn bản A",
        "doc_type": "nghi_dinh",
        "effective_from": "2025-02-01",
        "effective_to": None,
        "status": "con_hieu_luc",
        "issuer": "Chính phủ",
        "issued_on": "2025-01-01",
        "replaced_by": None,
        "amends": ["ND145-2020"],
        "source_url": "https://x/a",
    }
    assert [a["id"] for a in body["articles"]] == [
        "A-1:D2",
        "A-1:D2a",
        "A-1:D10",
        "A-1:PL1",
    ]
    assert [a["kind"] for a in body["articles"]] == ["dieu", "dieu", "dieu", "phu_luc"]
    assert body["articles"][0]["content"] == "" and body["articles"][1]["suffix"] == "a"


@pytest.mark.parametrize("code", ["NOPE", "NULL-TYPE", "NULL-STATUS"])
def test_docs_detail_404(client, docs_data, code):
    r = client.get(f"/api/docs/{code}")
    assert r.status_code == 404 and r.json() == {"detail": "Không tìm thấy văn bản."}


def test_docs_db_down_503(client):
    with db_down(client):
        for path in ("/api/docs", "/api/docs/ND293-2025"):
            r = client.get(path)
            assert r.status_code == 503 and r.json() == {"detail": DB_DOWN}


# ---- feedback
def rows(c):
    return c.execute(
        "select trace_id, score, comment from feedback order by id"
    ).fetchall()


def test_feedback_inserts_unknown_trace_id(client, seeded):
    r = client.post(
        "/api/feedback",
        json={"trace_id": "never-seen", "score": -1, "comment": "chưa đúng"},
    )
    assert r.status_code == 204 and r.content == b""
    assert (
        client.post("/api/feedback", json={"trace_id": "t2", "score": 1}).status_code
        == 204
    )
    assert rows(seeded) == [("never-seen", -1, "chưa đúng"), ("t2", 1, None)]


@pytest.mark.parametrize(
    "body",
    [
        {"trace_id": "t", "score": 0},
        {"trace_id": "t", "score": 2},
        {"trace_id": "t", "score": True},
        {"trace_id": "t", "score": "1"},
        {"score": 1},
        {"trace_id": "", "score": 1},
        {"trace_id": "x" * 65, "score": 1},
        {"trace_id": "t", "score": 1, "comment": "c" * 501},
        {"trace_id": "t", "score": 1, "comment": 5},
        [1],
    ],
)
def test_feedback_validation_422(client, seeded, body):
    r = client.post("/api/feedback", json=body)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)
    assert rows(seeded) == []


def test_feedback_limits_are_inclusive(client, seeded):
    assert (
        client.post(
            "/api/feedback",
            json={"trace_id": "x" * 64, "score": 1, "comment": "c" * 500},
        ).status_code
        == 204
    )


def test_feedback_db_down_503(client):
    with db_down(client):
        r = client.post("/api/feedback", json={"trace_id": "t", "score": 1})
    assert r.status_code == 503 and r.json() == {"detail": DB_DOWN}


# ---- cron
def test_cron_requires_secret(client):
    r = client.get("/api/cron/keepalive")
    assert r.status_code == 401 and r.json() == {"detail": "Không được phép."}
    assert (
        client.get(
            "/api/cron/keepalive", headers={"authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/cron/keepalive", headers={"authorization": "s3cret"}
        ).status_code
        == 401
    )
    ok = client.get("/api/cron/keepalive", headers={"authorization": "Bearer s3cret"})
    assert ok.status_code == 204 and ok.content == b""


def test_cron_runs_select_1(client):
    executed = []

    class Conn:
        async def execute(self, q, *a):
            executed.append(q)

    class Pool:
        def connection(self, timeout=None):
            class CM:
                async def __aenter__(s):
                    return Conn()

                async def __aexit__(s, *e):
                    return False

            return CM()

        async def close(self):
            pass

    real, client.app.state.pool = client.app.state.pool, Pool()
    try:
        assert (
            client.get(
                "/api/cron/keepalive", headers={"authorization": "Bearer s3cret"}
            ).status_code
            == 204
        )
    finally:
        client.app.state.pool = real
    assert executed == ["select 1"]


def test_cron_401_when_secret_unset(env):
    env.delenv("CRON_SECRET")
    from app.main import create_app

    with TestClient(create_app()) as c:
        for h in (
            {},
            {"authorization": "Bearer "},
            {"authorization": "Bearer None"},
            {"authorization": "Bearer"},
        ):
            assert c.get("/api/cron/keepalive", headers=h).status_code == 401


def test_cron_non_ascii_header_is_401_not_500(client):
    r = client.get("/api/cron/keepalive", headers={"authorization": b"Bearer \xc4\x91"})
    assert r.status_code == 401


# ---- security / limits / lifecycle
@pytest.mark.parametrize("path", ["/api/chat", "/api/feedback"])
def test_body_over_64kb_is_413(client, path):
    r = client.post(
        path,
        content=b"x" * (64 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413 and r.json() == {"detail": "Yêu cầu quá lớn."}
    assert r.headers["x-content-type-options"] == "nosniff"


def test_chunked_body_over_64kb_is_413(client):
    def gen():
        for _ in range(70):
            yield b" " * 1024

    r = client.post(
        "/api/feedback", content=gen(), headers={"content-type": "application/json"}
    )
    assert r.status_code == 413


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_shared_client_pool_and_gateway_closed_on_shutdown(env):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        http, pool, gw = c.app.state.http, c.app.state.pool, c.app.state.gw
        assert gw._client is http and not http.is_closed
    assert http.is_closed and pool.closed


def test_app_starts_without_database_url(env):
    env.delenv("DATABASE_URL")
    from app.main import create_app

    with TestClient(create_app()) as c:
        assert c.app.state.pool is None
        assert c.get("/api/health").json()["db"] == "down"
