"""Bọc mỏng Langfuse (SDK Python v3+, dựa trên OpenTelemetry). Không có LANGFUSE_* thì toàn bộ là no-op.

Dùng `start_observation` (không dùng context manager) để không phụ thuộc contextvars qua các `yield` của stream.
Mọi lỗi của Langfuse bị nuốt: tracing không bao giờ làm hỏng request.
"""

import logging
import uuid
from contextlib import contextmanager
from functools import lru_cache

import anyio

from app.config import LANGFUSE_FLUSH_TIMEOUT_S as FLUSH_TIMEOUT_S
from app.config import Settings
from app.pii import redact_pii

log = logging.getLogger(__name__)


class _NoSpan:
    def update(self, **kw) -> None:
        pass


@lru_cache
def _client(public_key: str, secret_key: str, host: str | None):
    from langfuse import Langfuse

    return Langfuse(public_key=public_key, secret_key=secret_key, base_url=host)


def get_client(s: Settings):
    if not (s.LANGFUSE_PUBLIC_KEY and s.LANGFUSE_SECRET_KEY):
        return None
    try:
        return _client(s.LANGFUSE_PUBLIC_KEY, s.LANGFUSE_SECRET_KEY, s.LANGFUSE_HOST)
    except Exception:
        log.warning("langfuse init failed; tracing disabled", exc_info=True)
        return None


class _Span:
    def __init__(self, obs):
        self._obs = obs

    def update(self, **kw) -> None:
        try:
            self._obs.update(**kw)
        except Exception:
            log.debug("langfuse span update failed", exc_info=True)


class Trace:
    """`trace_id` luôn là uuid4 hex hợp lệ (cũng là id Langfuse khi tracing bật)."""

    def __init__(self, question: str, settings: Settings, client=None):
        self.trace_id = uuid.uuid4().hex
        self._client = client if client is not None else get_client(settings)
        self._root = None
        if self._client is not None:
            try:
                self._root = self._client.start_observation(
                    trace_context={"trace_id": self.trace_id},
                    name="chat",
                    as_type="span",
                    input=redact_pii(question),
                )
            except Exception:
                log.warning("langfuse trace start failed", exc_info=True)

    @contextmanager
    def span(self, name: str):
        obs = None
        if self._root is not None:
            try:
                obs = self._root.start_observation(name=name, as_type="span")
            except Exception:
                log.debug("langfuse span start failed", exc_info=True)
        sp = _Span(obs) if obs is not None else _NoSpan()
        try:
            yield sp
        except BaseException as e:
            sp.update(level="ERROR", status_message=type(e).__name__)
            raise
        finally:
            if obs is not None:
                try:
                    obs.end()
                except Exception:
                    log.debug("langfuse span end failed", exc_info=True)

    def finish(self, output: str | None = None, metadata: dict | None = None) -> None:
        if self._root is None:
            return
        try:
            kw = {"metadata": {k: str(v) for k, v in (metadata or {}).items()}}
            if output is not None:
                kw["output"] = redact_pii(output)
            self._root.update(**kw)
            self._root.end()
        except Exception:
            log.debug("langfuse trace finish failed", exc_info=True)
        self._root = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def flush(self) -> None:
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception:
            log.debug("langfuse flush failed", exc_info=True)


async def run_bounded(fn, *args) -> None:
    """Chạy hàm chặn mạng của Langfuse trong thread, bỏ qua sau FLUSH_TIMEOUT_S (thread mồ côi tự kết thúc). Không bao giờ raise."""
    try:
        with anyio.move_on_after(FLUSH_TIMEOUT_S):
            await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=True)
    except Exception:
        log.debug("langfuse call failed", exc_info=True)


def send_feedback_score(
    settings: Settings, trace_id: str, score: int, comment: str | None
) -> None:
    """👍/👎 thành score `user-feedback` (+1/-1) trên đúng trace. Chặn mạng: gọi qua `run_bounded`. Lỗi bị nuốt."""
    client = get_client(settings)
    if client is None:
        return
    try:
        client.create_score(
            name="user-feedback",
            value=score,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=redact_pii(comment) if comment else None,
        )
        client.flush()
    except Exception:
        log.debug("langfuse score failed", exc_info=True)
