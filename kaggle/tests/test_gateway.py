import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from gateway import create_app

LLM = "http://llm.test:8080"
KEY = "secret"
AUTH = {"Authorization": f"Bearer {KEY}"}


class FakeEmbedder:
    def encode(self, texts):
        return [[float(len(t))] + [0.0] * 1023 for t in texts]


class FakeReranker:
    def predict(self, pairs):
        # raw logits, deliberately unsorted and outside [0,1]
        return [(-1.0) ** i * (i + 1) * 3.0 for i, _ in enumerate(pairs)]


@pytest.fixture
def client():
    return TestClient(create_app(FakeEmbedder(), FakeReranker(), LLM, KEY))


def test_requires_bearer(client):
    body = {"input": ["a"]}
    assert client.post("/v1/embeddings", json=body).status_code == 401
    bad = client.post(
        "/v1/embeddings", json=body, headers={"Authorization": "Bearer nope"}
    )
    assert bad.status_code == 401
    assert bad.json() == {"detail": "unauthorized"}
    with respx.mock:
        respx.get(f"{LLM}/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        assert client.get("/health").status_code == 200


def test_embeddings_shape(client):
    r = client.post("/v1/embeddings", json={"input": ["a", "bb", "ccc"]}, headers=AUTH)
    assert r.status_code == 200
    data = r.json()["data"]
    assert [d["index"] for d in data] == [0, 1, 2]
    assert all(len(d["embedding"]) == 1024 for d in data)


def test_embeddings_input_limit(client):
    r = client.post("/v1/embeddings", json={"input": ["a"] * 65}, headers=AUTH)
    assert r.status_code in (413, 422)
    r = client.post("/v1/embeddings", json={"input": ["a" * 8001]}, headers=AUTH)
    assert r.status_code in (413, 422)


def test_rerank_sorted_and_bounded(client):
    docs = [f"d{i}" for i in range(6)]
    r = client.post(
        "/v1/rerank", json={"query": "q", "documents": docs, "top_n": 4}, headers=AUTH
    )
    assert r.status_code == 200
    res = r.json()["results"]
    scores = [x["relevance_score"] for x in res]
    assert len(res) == 4
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


@respx.mock
def test_chat_proxy_streams_chunks(client):
    sse = b'data: {"n":1}\n\ndata: {"n":2}\n\ndata: [DONE]\n\n'
    respx.post(f"{LLM}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, content=sse, headers={"content-type": "text/event-stream"}
        )
    )
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"stream": True, "messages": []},
        headers=AUTH,
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        lines = [ln for ln in r.iter_lines() if ln]
    assert lines == ['data: {"n":1}', 'data: {"n":2}', "data: [DONE]"]


@respx.mock
def test_chat_non_stream_and_unreachable(client):
    route = respx.post(f"{LLM}/v1/chat/completions")
    route.mock(return_value=httpx.Response(200, json={"id": "x"}))
    r = client.post("/v1/chat/completions", json={"messages": []}, headers=AUTH)
    assert r.json() == {"id": "x"}
    route.mock(side_effect=httpx.ConnectError("down"))
    r = client.post("/v1/chat/completions", json={"messages": []}, headers=AUTH)
    assert r.status_code == 503 and r.json() == {"detail": "llm unavailable"}


@respx.mock
def test_health_loading_when_llm_not_ok(client):
    respx.get(f"{LLM}/health").mock(
        return_value=httpx.Response(503, json={"status": "loading"})
    )
    h = client.get("/health").json()
    assert h["llm"] is False
    assert h["status"] == "loading"
    assert h["embedder"] is True and h["reranker"] is True


def test_docs_and_openapi_not_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=AUTH).status_code == 404


def test_unauthenticated_malformed_json_gets_401(client):
    r = client.post(
        "/v1/chat/completions",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 401


def test_oversized_body_413(client):
    big = b'{"input": ["' + b"a" * 1_100_000 + b'"]}'
    r = client.post(
        "/v1/embeddings",
        content=big,
        headers={**AUTH, "content-type": "application/json"},
    )
    assert r.status_code == 413

    def gen():  # chunked, no content-length
        yield b'{"input": ["'
        for _ in range(11):
            yield b"a" * 100_000
        yield b'"]}'

    r = client.post(
        "/v1/embeddings",
        content=gen(),
        headers={**AUTH, "content-type": "application/json"},
    )
    assert r.status_code == 413


def test_empty_api_key_rejected():
    with pytest.raises(ValueError):
        create_app(FakeEmbedder(), FakeReranker(), LLM, "")


def test_missing_models_503():
    c = TestClient(create_app(None, None, LLM, KEY))
    assert (
        c.post("/v1/embeddings", json={"input": ["a"]}, headers=AUTH).status_code == 503
    )
    assert (
        c.post(
            "/v1/rerank", json={"query": "q", "documents": ["a"]}, headers=AUTH
        ).status_code
        == 503
    )


@respx.mock
def test_chat_non_json_upstream_502(client):
    respx.post(f"{LLM}/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=b"<html>")
    )
    r = client.post("/v1/chat/completions", json={"messages": []}, headers=AUTH)
    assert r.status_code == 502 and r.json() == {"detail": "llm bad response"}


def test_model_calls_are_serialized():
    import threading
    import time

    class Probe:
        active = peak = 0
        lock = threading.Lock()

        def _enter(self):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1

        def encode(self, texts):
            self._enter()
            return [[0.0] * 1024 for _ in texts]

        def predict(self, pairs):
            self._enter()
            return [0.0] * len(pairs)

    emb, rer = Probe(), Probe()
    c = TestClient(create_app(emb, rer, LLM, KEY))
    threads = [
        threading.Thread(
            target=lambda: c.post("/v1/embeddings", json={"input": ["a"]}, headers=AUTH)
        )
        for _ in range(4)
    ] + [
        threading.Thread(
            target=lambda: c.post(
                "/v1/rerank", json={"query": "q", "documents": ["a"]}, headers=AUTH
            )
        )
        for _ in range(4)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert emb.peak == 1 and rer.peak == 1


@pytest.mark.asyncio
@respx.mock
async def test_upstream_closed_on_client_disconnect():
    import asyncio
    import json

    closed = asyncio.Event()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"data: 1\n\n"
            await asyncio.sleep(30)  # upstream keeps going until closed
            yield b"data: 2\n\n"

        async def aclose(self):
            closed.set()

    respx.post(f"{LLM}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, stream=Stream(), headers={"content-type": "text/event-stream"}
        )
    )
    app = create_app(FakeEmbedder(), FakeReranker(), LLM, KEY)
    body = json.dumps({"stream": True, "messages": []}).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "path": "/v1/chat/completions",
        "raw_path": b"/v1/chat/completions",
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "server": ("t", 80),
        "client": ("c", 1),
        "headers": [
            (b"authorization", f"Bearer {KEY}".encode()),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    disconnect = asyncio.Event()
    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(msg):
        if msg["type"] == "http.response.body" and msg.get("body"):
            disconnect.set()  # client goes away after first chunk

    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    assert closed.is_set()


@respx.mock
def test_health_caches_llm_probe_and_hides_model(client):
    route = respx.get(f"{LLM}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    for _ in range(3):
        h = client.get("/health").json()
    assert route.call_count == 1 and h["llm"] is True and "model" not in h
