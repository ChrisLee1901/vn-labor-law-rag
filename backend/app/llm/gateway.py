"""Client cho gateway Kaggle (embed / rerank / chat). Mọi lỗi hạ tầng -> LLMOffline để caller chuyển sang chế độ offline."""
import json
import re
from collections.abc import AsyncIterator

import httpx

_ALLOWED = re.compile(r"^https://[a-z0-9-]+\.ngrok-free\.(app|dev)$")
_TIMEOUT = httpx.Timeout(60.0, connect=3.0)


class LLMOffline(Exception):
    """Gateway không dùng được (URL không hợp lệ, mạng lỗi, 4xx/5xx)."""


class LLMStreamError(Exception):
    """Lỗi giữa chừng khi đang stream chat (đã yield một phần)."""


class Gateway:
    def __init__(self, base_url: str | None, api_key: str, *, allow_any: bool = False):
        # allow_any chỉ dùng trong test (bỏ kiểm tra allowlist ngrok); production luôn để False.
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.allow_any = allow_any

    def is_allowed(self, url: str | None = None) -> bool:
        return bool(url) and _ALLOWED.match(url) is not None  # type: ignore[arg-type]

    def _url(self, path: str) -> str:
        if not self.base_url or not (self.allow_any or self.is_allowed(self.base_url)):
            raise LLMOffline("gateway url not allowed")
        return self.base_url + path

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _post(self, path: str, body: dict) -> dict:
        url = self._url(path)
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                r = await c.post(url, json=body, headers=self._headers)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise LLMOffline(str(e)) from e

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = (await self._post("/v1/embeddings", {"input": texts}))["data"]
        return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]

    async def rerank(self, query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]:
        res = (await self._post("/v1/rerank", {"query": query, "documents": docs, "top_n": top_n}))["results"]
        return [(r["index"], r["relevance_score"]) for r in res]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                r = await c.get(self._url("/health"))
            return r.status_code == 200 and r.json().get("status") == "ok"
        except (LLMOffline, httpx.HTTPError, ValueError):
            return False

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield text deltas. LLMOffline nếu không kết nối/HTTP lỗi trước byte đầu; LLMStreamError nếu đứt giữa chừng."""
        url = self._url("/v1/chat/completions")
        body = {"messages": messages, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                async with c.stream("POST", url, json=body, headers=self._headers) as r:
                    r.raise_for_status()
                    try:
                        async for line in r.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                return
                            try:
                                delta = json.loads(data)["choices"][0]["delta"].get("content")
                            except (ValueError, KeyError, IndexError, TypeError):
                                continue
                            if delta:
                                yield delta
                    except httpx.HTTPError as e:
                        raise LLMStreamError(str(e)) from e
        except httpx.HTTPError as e:
            raise LLMOffline(str(e)) from e
