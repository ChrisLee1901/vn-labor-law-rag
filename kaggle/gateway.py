"""Authenticated gateway in front of llama-server + embedder + reranker (runs in a Kaggle notebook)."""
import hmac
import math
import os
from contextlib import asynccontextmanager
from typing import Annotated, Protocol

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from starlette.background import BackgroundTask

MAX_ITEMS = 64
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
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(lifespan=lifespan)
    llm_url = llm_url.rstrip("/")

    def auth(authorization: str = Header(default="")) -> None:
        if not hmac.compare_digest(authorization.encode(), f"Bearer {api_key}".encode()):
            raise HTTPException(status_code=401, detail="unauthorized")

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

    @app.post("/v1/embeddings", dependencies=[Depends(auth)])
    def embeddings(req: EmbedReq):
        vecs = embedder.encode(req.input)
        return {"data": [{"index": i, "embedding": v} for i, v in enumerate(vecs)]}

    @app.post("/v1/rerank", dependencies=[Depends(auth)])
    def rerank(req: RerankReq):
        logits = reranker.predict([(req.query, d) for d in req.documents])
        scored = sorted(
            ({"index": i, "relevance_score": _sigmoid(float(s))} for i, s in enumerate(logits)),
            key=lambda x: x["relevance_score"],
            reverse=True,
        )
        return {"results": scored[: req.top_n or len(scored)]}

    @app.post("/v1/chat/completions", dependencies=[Depends(auth)])
    async def chat(body: dict):
        url = f"{llm_url}/v1/chat/completions"
        try:
            if body.get("stream"):
                up = await client.send(client.build_request("POST", url, json=body), stream=True)
                return StreamingResponse(
                    up.aiter_raw(),
                    status_code=up.status_code,
                    media_type="text/event-stream",
                    background=BackgroundTask(up.aclose),
                )
            up = await client.post(url, json=body)
        except httpx.HTTPError:
            return JSONResponse({"detail": "llm unavailable"}, status_code=503)
        return JSONResponse(up.json(), status_code=up.status_code)

    return app


def load_models(device: str = "cuda:1"):
    """Load embedder + reranker (fp16). Imports are local so the module stays light for tests."""
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    class _Emb:
        def __init__(self):
            self.m = SentenceTransformer(
                "AITeamVN/Vietnamese_Embedding", device=device, model_kwargs={"torch_dtype": torch.float16}
            )

        def encode(self, texts):
            return self.m.encode(texts, batch_size=BATCH, normalize_embeddings=True).tolist()

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
