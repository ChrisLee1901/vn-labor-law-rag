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
    bad = client.post("/v1/embeddings", json=body, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert bad.json() == {"detail": "unauthorized"}
    with respx.mock:
        respx.get(f"{LLM}/health").mock(return_value=httpx.Response(200, json={"status": "ok"}))
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
    r = client.post("/v1/rerank", json={"query": "q", "documents": docs, "top_n": 4}, headers=AUTH)
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
        return_value=httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})
    )
    with client.stream(
        "POST", "/v1/chat/completions", json={"stream": True, "messages": []}, headers=AUTH
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        lines = [l for l in r.iter_lines() if l]
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
    respx.get(f"{LLM}/health").mock(return_value=httpx.Response(503, json={"status": "loading"}))
    h = client.get("/health").json()
    assert h["llm"] is False
    assert h["status"] == "loading"
    assert h["embedder"] is True and h["reranker"] is True
