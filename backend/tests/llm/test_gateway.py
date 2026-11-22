import json
import httpx
import pytest
import respx
from app.llm.gateway import Gateway, LLMOffline, LLMStreamError

URL = "https://abc-12.ngrok-free.app"


def gw(**kw):
    return Gateway(URL, "secret", **kw)


async def test_gateway_rejects_non_ngrok_url():
    g = Gateway("http://169.254.169.254", "k")
    assert g.is_allowed(g.base_url) is False
    with pytest.raises(LLMOffline):
        await g.embed(["x"])


@pytest.mark.parametrize(
    "u", ["https://a.ngrok-free.app", "https://a-b.ngrok-free.dev"]
)
def test_allowed(u):
    assert Gateway(None, "k").is_allowed(u)


@pytest.mark.parametrize(
    "u",
    [
        "https://a.ngrok-free.app.evil.com",
        "http://a.ngrok-free.app",
        "https://a.ngrok-free.app/x",
        "https://evil.com#.ngrok-free.app",
        None,
    ],
)
def test_not_allowed(u):
    assert not Gateway(None, "k").is_allowed(u)


async def test_none_url_offline():
    with pytest.raises(LLMOffline):
        await Gateway(None, "k").rerank("q", ["d"], 1)
    assert await Gateway(None, "k").health() is False


@respx.mock
async def test_embed_and_auth_header():
    route = respx.post(f"{URL}/v1/embeddings").respond(
        json={
            "data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]
        }
    )
    assert await gw().embed(["a", "b"]) == [[1.0], [2.0]]
    assert route.calls[0].request.headers["authorization"] == "Bearer secret"


@respx.mock
async def test_rerank():
    respx.post(f"{URL}/v1/rerank").respond(
        json={
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.1},
            ]
        }
    )
    assert await gw().rerank("q", ["a", "b"], 2) == [(1, 0.9), (0, 0.1)]


@respx.mock
async def test_5xx_and_network_error_are_offline():
    respx.post(f"{URL}/v1/embeddings").respond(503)
    with pytest.raises(LLMOffline):
        await gw().embed(["a"])
    respx.post(f"{URL}/v1/rerank").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(LLMOffline):
        await gw().rerank("q", ["a"], 1)


@respx.mock
async def test_health():
    respx.get(f"{URL}/health").respond(json={"status": "ok", "llm": True})
    assert await gw().health() is True
    respx.get(f"{URL}/health").respond(json={"status": "loading"})
    assert await gw().health() is False


def sse(*events: str) -> bytes:
    return "".join(f"data: {e}\n\n" for e in events).encode()


@respx.mock
async def test_chat_stream_yields_deltas_until_done():
    body = sse(
        '{"choices":[{"delta":{"role":"assistant"}}]}',
        '{"choices":[{"delta":{"content":"Xin "}}]}',
        '{"choices":[{"delta":{"content":"chào"}}]}',
        "[DONE]",
        '{"choices":[{"delta":{"content":"IGNORED"}}]}',
    )
    respx.post(f"{URL}/v1/chat/completions").respond(content=body)
    assert [d async for d in gw().chat_stream([{"role": "user", "content": "hi"}])] == [
        "Xin ",
        "chào",
    ]


@respx.mock
async def test_chat_stream_midstream_error():
    async def boom():
        yield sse('{"choices":[{"delta":{"content":"a"}}]}')
        raise httpx.ReadError("cut")

    respx.post(f"{URL}/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=boom())
    )
    got = []
    with pytest.raises(LLMStreamError):
        async for d in gw().chat_stream([]):
            got.append(d)
    assert got == ["a"]


@respx.mock
async def test_chat_stream_connect_failure_offline():
    respx.post(f"{URL}/v1/chat/completions").respond(502)
    with pytest.raises(LLMOffline):
        async for _ in gw().chat_stream([]):
            pass


@respx.mock
async def test_allow_any_for_tests():
    respx.get("http://local.test/health").respond(json={"status": "ok"})
    assert await Gateway("http://local.test", "k", allow_any=True).health() is True


@respx.mock
async def test_chat_stream_inband_error_raises():
    body = sse('{"choices":[{"delta":{"content":"a"}}]}', '{"error":{"message":"oom"}}')
    respx.post(f"{URL}/v1/chat/completions").respond(content=body)
    got = []
    with pytest.raises(LLMStreamError):
        async for d in gw().chat_stream([]):
            got.append(d)
    assert got == ["a"]


@respx.mock
async def test_chat_stream_without_done_is_error():
    respx.post(f"{URL}/v1/chat/completions").respond(
        content=sse('{"choices":[{"delta":{"content":"a"}}]}')
    )
    with pytest.raises(LLMStreamError):
        async for _ in gw().chat_stream([]):
            pass


@respx.mock
async def test_malformed_json_is_offline():
    respx.post(f"{URL}/v1/embeddings").respond(json={"nope": 1})
    with pytest.raises(LLMOffline):
        await gw().embed(["a"])
    respx.post(f"{URL}/v1/rerank").respond(
        json={"results": [{"index": 5, "relevance_score": 0.5}]}
    )
    with pytest.raises(LLMOffline):
        await gw().rerank("q", ["a"], 1)
    respx.post(f"{URL}/v1/rerank").respond(json={"results": [{"index": 0}]})
    with pytest.raises(LLMOffline):
        await gw().rerank("q", ["a"], 1)


@respx.mock
async def test_client_reused_and_closed():
    respx.post(f"{URL}/v1/rerank").respond(json={"results": []})
    g = gw()
    await g.rerank("q", ["a"], 1)
    c = g._client
    await g.rerank("q", ["a"], 1)
    assert g._client is c and c is not None
    await g.aclose()
    assert g._client is None and c.is_closed


@respx.mock
async def test_chat_once_returns_stripped_content_non_streaming():
    route = respx.post(f"{URL}/v1/chat/completions").respond(
        json={"choices": [{"message": {"content": "  Câu hỏi độc lập?\n"}}]}
    )
    assert (
        await gw().chat_once([{"role": "user", "content": "x"}]) == "Câu hỏi độc lập?"
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["stream"] is False and sent["max_tokens"] <= 256


@respx.mock
@pytest.mark.parametrize(
    "payload", [{"choices": []}, {"x": 1}, {"choices": [{"message": {}}]}]
)
async def test_chat_once_malformed_is_offline(payload):
    respx.post(f"{URL}/v1/chat/completions").respond(json=payload)
    with pytest.raises(LLMOffline):
        await gw().chat_once([])


@respx.mock
async def test_injected_client_is_shared_and_not_closed_by_aclose():
    respx.get(f"{URL}/health").respond(json={"status": "ok"})
    async with httpx.AsyncClient() as shared:
        g = gw(client=shared)
        assert await g.health() is True
        await g.aclose()
        assert not shared.is_closed


@respx.mock
async def test_chat_stream_caps_max_tokens():
    route = respx.post(f"{URL}/v1/chat/completions").respond(content=sse("[DONE]"))
    _ = [d async for d in gw().chat_stream([{"role": "user", "content": "hi"}])]
    assert json.loads(route.calls[0].request.content)["max_tokens"] == 1024
