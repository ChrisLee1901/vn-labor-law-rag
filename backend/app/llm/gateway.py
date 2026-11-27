"""Client cho gateway Kaggle (embed / rerank / chat). Mọi lỗi hạ tầng -> LLMOffline để caller chuyển sang chế độ offline."""

import json
import re
from collections.abc import AsyncIterator

import httpx

from app.config import CHAT_MAX_TOKENS

_ALLOWED = re.compile(r"https://[a-z0-9-]+\.ngrok-free\.(app|dev)")
_TIMEOUT = httpx.Timeout(60.0, connect=3.0)


class LLMOffline(Exception):
    """Gateway không dùng được (URL không hợp lệ, mạng lỗi, 4xx/5xx)."""


class LLMStreamError(Exception):
    """Lỗi giữa chừng khi đang stream chat (đã yield một phần)."""


class Gateway:
    def __init__(
        self,
        base_url: str | None,
        api_key: str,
        *,
        allow_any: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        # allow_any chỉ dùng trong test (bỏ kiểm tra allowlist ngrok); production luôn để False.
        # client: client dùng chung của app; Gateway không sở hữu nên aclose() không đóng nó.
        self.base_url = base_url.strip().rstrip("/") if base_url else None
        self.api_key = api_key
        self.allow_any = allow_any
        self._client = client
        self._owns_client = client is None

    def is_allowed(self, url: str | None = None) -> bool:
        return bool(url) and _ALLOWED.fullmatch(url) is not None  # type: ignore[arg-type]

    def _url(self, path: str) -> str:
        if not self.base_url or not (self.allow_any or self.is_allowed(self.base_url)):
            raise LLMOffline("gateway url not allowed")
        return self.base_url + path

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _http(self) -> httpx.AsyncClient:
        # Một client/Gateway: tái dùng kết nối (tránh bắt tay TLS lại mỗi call qua ngrok). Gọi aclose() khi xong.
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._client

    async def aclose(self) -> None:
        if not self._owns_client:
            return
        c, self._client = self._client, None
        if c is not None:
            await c.aclose()

    async def _post(self, path: str, body: dict) -> dict:
        url = self._url(path)
        try:
            r = await self._http().post(url, json=body, headers=self._headers)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise LLMOffline(str(e)) from e

    async def embed(self, texts: list[str]) -> list[list[float]]:
        res = await self._post("/v1/embeddings", {"input": texts})
        try:
            vecs = [
                d["embedding"] for d in sorted(res["data"], key=lambda d: d["index"])
            ]
        except (KeyError, TypeError) as e:
            raise LLMOffline(f"malformed embeddings response: {e!r}") from e
        if len(vecs) != len(texts):
            raise LLMOffline("embeddings count mismatch")
        return vecs

    async def rerank(
        self, query: str, docs: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        res = await self._post(
            "/v1/rerank", {"query": query, "documents": docs, "top_n": top_n}
        )
        try:
            out = [
                (int(r["index"]), float(r["relevance_score"])) for r in res["results"]
            ]
        except (KeyError, TypeError, ValueError) as e:
            raise LLMOffline(f"malformed rerank response: {e!r}") from e
        if any(not 0 <= i < len(docs) for i, _ in out):
            raise LLMOffline("rerank index out of range")
        return out

    async def chat_once(self, messages: list[dict], max_tokens: int = 128) -> str:
        """Gọi chat không stream (viết lại câu hỏi). LLMOffline nếu lỗi hạ tầng hoặc phản hồi sai dạng."""
        res = await self._post(
            "/v1/chat/completions",
            {
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": 0,
            },
        )
        try:
            return str(res["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as e:
            raise LLMOffline(f"malformed chat response: {e!r}") from e

    async def health(self) -> bool:
        try:
            r = await self._http().get(self._url("/health"))
            return r.status_code == 200 and r.json().get("status") == "ok"
        except (LLMOffline, httpx.HTTPError, ValueError, AttributeError):
            return False

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield text deltas. LLMOffline nếu không kết nối/HTTP lỗi trước byte đầu; LLMStreamError nếu stream đứt,
        có `error` trong luồng, hoặc kết thúc mà không có `[DONE]` (câu trả lời cụt)."""
        url = self._url("/v1/chat/completions")
        body = {"messages": messages, "stream": True, "max_tokens": CHAT_MAX_TOKENS}
        try:
            async with self._http().stream(
                "POST", url, json=body, headers=self._headers
            ) as r:
                r.raise_for_status()
                done = False
                try:
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            done = True
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        if isinstance(obj, dict) and "error" in obj:
                            raise LLMStreamError(str(obj["error"]))
                        try:
                            delta = obj["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError, TypeError, AttributeError):
                            continue
                        if delta:
                            yield delta
                except httpx.HTTPError as e:
                    raise LLMStreamError(str(e)) from e
                if not done:
                    raise LLMStreamError("stream ended without [DONE]")
        except httpx.HTTPError as e:
            raise LLMOffline(str(e)) from e
