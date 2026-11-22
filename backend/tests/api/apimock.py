import json

import httpx
import respx

GW = "https://abc-12.ngrok-free.app"
QUESTION = "Mức lương tối thiểu vùng I là bao nhiêu?"


def sse_body(*deltas: str) -> bytes:
    chunks = [json.dumps({"choices": [{"delta": {"content": d}}]}, ensure_ascii=False) for d in deltas] + ["[DONE]"]
    return "".join(f"data: {c}\n\n" for c in chunks).encode()


def parse_sse(text: str) -> list[dict | str]:
    out: list[dict | str] = []
    for block in text.split("\n\n"):
        if block.startswith("data: "):
            payload = block[6:]
            out.append(payload if payload == "[DONE]" else json.loads(payload))
    return out


def types(parts) -> list[str]:
    return [p if isinstance(p, str) else p["type"] for p in parts]


class Gateway:
    """respx mock của gateway Kaggle; `chat` ghi lại mọi call (stream và không stream)."""

    def __init__(self, online=True, rerank=0.9, answer=("Mức lương vùng I là 5.310.000 đồng [S1].",), condensed="câu hỏi độc lập"):
        self.mock = respx.mock(assert_all_called=False)
        self.chat_bodies: list[dict] = []
        self.embed_inputs: list[str] = []
        self.rerank_score = rerank
        self.answer = answer
        self.condensed = condensed
        self.condense_fails = False
        self.stream_error = False
        self.online = online

    def _chat(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.chat_bodies.append(body)
        if not body.get("stream"):
            if self.condense_fails:
                return httpx.Response(500)
            return httpx.Response(200, json={"choices": [{"message": {"content": self.condensed}}]})
        if self.stream_error:
            async def boom():
                for d in self.answer[:2]:
                    yield sse_body(d)[: -len(b"data: [DONE]\n\n")]
                raise httpx.ReadError("cut")

            return httpx.Response(200, content=boom())
        return httpx.Response(200, content=sse_body(*self.answer))

    def _embed(self, request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        self.embed_inputs += texts
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [0.01] * 1024} for i in range(len(texts))]})

    def _rerank(self, request: httpx.Request) -> httpx.Response:
        docs = json.loads(request.content)["documents"]
        return httpx.Response(200, json={"results": [{"index": i, "relevance_score": self.rerank_score} for i in range(len(docs))]})

    def __enter__(self):
        self.mock.__enter__()
        self.health_route = self.mock.get(f"{GW}/health")
        if self.online:
            self.health_route.respond(json={"status": "ok", "llm": True})
        else:
            self.health_route.respond(503)
        self.chat_route = self.mock.post(f"{GW}/v1/chat/completions").mock(side_effect=self._chat)
        self.mock.post(f"{GW}/v1/embeddings").mock(side_effect=self._embed)
        self.mock.post(f"{GW}/v1/rerank").mock(side_effect=self._rerank)
        return self

    def __exit__(self, *a):
        self.mock.__exit__(*a)

    @property
    def stream_calls(self) -> int:
        return sum(1 for b in self.chat_bodies if b.get("stream"))
