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


@pytest.mark.parametrize("u", ["https://a.ngrok-free.app", "https://a-b.ngrok-free.dev"])
def test_allowed(u):
    assert Gateway(None, "k").is_allowed(u)


@pytest.mark.parametrize(
    "u",
    ["https://a.ngrok-free.app.evil.com", "http://a.ngrok-free.app", "https://a.ngrok-free.app/x", "https://evil.com#.ngrok-free.app", None],
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
        json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]}
    )
    assert await gw().embed(["a", "b"]) == [[1.0], [2.0]]
    assert route.calls[0].request.headers["authorization"] == "Bearer secret"


@respx.mock
async def test_rerank():
    respx.post(f"{URL}/v1/rerank").respond(
        json={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]}
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
    assert [d async for d in gw().chat_stream([{"role": "user", "content": "hi"}])] == ["Xin ", "chào"]


@respx.mock
async def test_chat_stream_midstream_error():
    async def boom():
        yield sse('{"choices":[{"delta":{"content":"a"}}]}')
        raise httpx.ReadError("cut")

    respx.post(f"{URL}/v1/chat/completions").mock(return_value=httpx.Response(200, content=boom()))
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
