"""Authenticated gateway in front of llama-server + embedder + reranker (runs in a Kaggle notebook)."""

import hmac
import math
import os
import threading
from contextlib import asynccontextmanager
from typing import Annotated, Protocol

import anyio
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

MAX_ITEMS = 64
MAX_BODY = 1_000_000
Text = Annotated[str, StringConstraints(max_length=8000)]
BATCH = 32


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]: ...  # raw logits


class EmbedReq(BaseModel):
    input: list[Text] = Field(min_length=1, max_length=MAX_ITEMS)
    model: str | None = None


class RerankReq(BaseModel):
    query: Text
    documents: list[Text] = Field(min_length=1, max_length=MAX_ITEMS)
    top_n: int | None = Field(default=None, ge=1)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


def create_app(
    embedder: Embedder | None,
    reranker: Reranker | None,
    llm_url: str,
    api_key: str,
    model_name: str = "",
) -> FastAPI:
    if not api_key:
        raise ValueError("api_key must not be empty")
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    llm_url = llm_url.rstrip("/")
    expected = f"Bearer {api_key}".encode()
    emb_lock, rer_lock = threading.Lock(), threading.Lock()

    class GuardMiddleware:
        """Pure ASGI: auth before any body is read, then cap body size."""

        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http" or scope["path"] == "/health":
                return await self.inner(scope, receive, send)
            got = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(got, expected):
                return await JSONResponse({"detail": "unauthorized"}, status_code=401)(
                    scope, receive, send
                )
            declared = dict(scope["headers"]).get(b"content-length", b"0")
            if declared.isdigit() and int(declared) > MAX_BODY:
                return await JSONResponse(
                    {"detail": "body too large"}, status_code=413
                )(scope, receive, send)
            seen = 0

            async def capped():
                nonlocal seen
                msg = await receive()
                if msg["type"] == "http.request":
                    seen += len(msg.get("body", b""))
                    if seen > MAX_BODY:
                        raise HTTPException(status_code=413, detail="body too large")
                return msg

            await self.inner(scope, capped, send)

    app.add_middleware(GuardMiddleware)

    @app.get("/health")
    async def health():
        try:
            r = await client.get(f"{llm_url}/health", timeout=2.0)
            llm = r.status_code == 200 and r.json().get("status") == "ok"
        except Exception:
            llm = False
        emb, rer = embedder is not None, reranker is not None
        return {
            "status": "ok" if llm and emb and rer else "loading",
            "llm": llm,
            "embedder": emb,
            "reranker": rer,
            "model": model_name,
        }

    @app.post("/v1/embeddings")
    def embeddings(req: EmbedReq):
        if embedder is None:
            raise HTTPException(status_code=503, detail="embedder unavailable")
        with emb_lock:
            vecs = embedder.encode(req.input)
        return {"data": [{"index": i, "embedding": v} for i, v in enumerate(vecs)]}

    @app.post("/v1/rerank")
    def rerank(req: RerankReq):
        if reranker is None:
            raise HTTPException(status_code=503, detail="reranker unavailable")
        with rer_lock:
            logits = reranker.predict([(req.query, d) for d in req.documents])
        scored = sorted(
            (
                {"index": i, "relevance_score": _sigmoid(float(s))}
                for i, s in enumerate(logits)
            ),
            key=lambda x: x["relevance_score"],
            reverse=True,
        )
        return {"results": scored[: req.top_n or len(scored)]}

    @app.post("/v1/chat/completions")
    async def chat(body: dict):
        url = f"{llm_url}/v1/chat/completions"
        try:
            if body.get("stream"):
                up = await client.send(
                    client.build_request("POST", url, json=body), stream=True
                )

                async def chunks():
                    try:
                        async for c in up.aiter_bytes():
                            yield c
                    finally:  # also runs on client disconnect (cancellation)
                        with anyio.CancelScope(shield=True):
                            await up.aclose()

                try:
                    return StreamingResponse(
                        chunks(),
                        status_code=up.status_code,
                        media_type="text/event-stream",
                    )
                except BaseException:
                    await up.aclose()
                    raise
            up = await client.post(url, json=body)
        except httpx.HTTPError:
            return JSONResponse({"detail": "llm unavailable"}, status_code=503)
        try:
            data = up.json()
        except ValueError:
            return JSONResponse({"detail": "llm bad response"}, status_code=502)
        return JSONResponse(data, status_code=up.status_code)

    return app


def load_models(device: str = "cuda:1"):
    """Load embedder + reranker (fp16). Imports are local so the module stays light for tests."""
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    class _Emb:
        def __init__(self):
            self.m = SentenceTransformer(
                "AITeamVN/Vietnamese_Embedding",
                device=device,
                model_kwargs={"torch_dtype": torch.float16},
            )

        def encode(self, texts):
            return self.m.encode(
                texts, batch_size=BATCH, normalize_embeddings=True
            ).tolist()

    class _Rer:
        def __init__(self):
            self.m = CrossEncoder(
                "AITeamVN/Vietnamese_Reranker",
                device=device,
                activation_fn=torch.nn.Identity(),  # raw logits; gateway applies sigmoid
                model_kwargs={"torch_dtype": torch.float16},
            )

        def predict(self, pairs):
            return [float(x) for x in self.m.predict(pairs, batch_size=BATCH)]

    return _Emb(), _Rer()


def main() -> None:
    import uvicorn

    embedder, reranker = load_models()
    app = create_app(
        embedder,
        reranker,
        os.environ.get("LLM_URL", "http://127.0.0.1:8080"),
        os.environ["GATEWAY_API_KEY"],
        os.environ.get("LLM_MODEL", ""),
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
