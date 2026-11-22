"""Chống lệch giữa docs/api-contract.md và code phát stream."""

import inspect
from pathlib import Path

from app import stream

DOC = (Path(__file__).resolve().parents[2] / "docs" / "api-contract.md").read_text(encoding="utf-8")
ROUTES = ["/api/chat", "/api/health", "/api/docs", "/api/feedback", "/api/cron/keepalive"]


def _emitted_types() -> set[str]:
    types = set()
    for name, fn in inspect.getmembers(stream, inspect.isfunction):
        if fn.__module__ != stream.__name__ or name == "sse":
            continue
        args = [[] if "list" in str(p.annotation) else "x" for p in inspect.signature(fn).parameters.values()]
        types.add(fn(*args)["type"])
    return types


def test_routes_documented():
    for r in ROUTES:
        assert r in DOC, r


def test_stream_part_types_documented():
    types = _emitted_types()
    assert {"start", "data-status", "data-trace", "data-citation-warning", "source-url", "error", "finish"} <= types
    for t in types:
        assert f"`{t}`" in DOC, t
    assert "[DONE]" in DOC
