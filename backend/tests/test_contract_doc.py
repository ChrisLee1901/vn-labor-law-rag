"""Chống lệch giữa docs/api-contract.md và code phát stream / routes."""

import inspect
import re
from pathlib import Path

from app import stream

DOC = (Path(__file__).resolve().parents[2] / "docs" / "api-contract.md").read_text(encoding="utf-8")
ENDPOINTS = {
    ("POST", "/api/chat"),
    ("GET", "/api/health"),
    ("GET", "/api/docs"),
    ("GET", "/api/docs/{code}"),
    ("POST", "/api/feedback"),
    ("GET", "/api/cron/keepalive"),
}
ORDER = (
    "start → data-status → source-url* → text-start → text-delta* → text-end → "
    "(data-citation-warning)? → data-trace → finish → [DONE]"
)


def table_endpoints(doc: str) -> set[tuple[str, str]]:
    """(METHOD, path) của các dòng bảng dạng `| POST | `/api/chat` | ...`."""
    return set(re.findall(r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`(/api/[^`]*)`", doc, re.M))


def missing_from_doc(doc: str) -> list[str]:
    miss = [f"{m} {p}" for m, p in sorted(ENDPOINTS - table_endpoints(doc))]
    if ORDER not in doc:
        miss.append("part order line")
    for t in sorted(emitted_types()):
        if f"`{t}`" not in doc:
            miss.append(f"part type {t}")
    if "[DONE]" not in doc:
        miss.append("[DONE]")
    return miss


def emitted_types() -> set[str]:
    types = set()
    for name, fn in inspect.getmembers(stream, inspect.isfunction):
        if fn.__module__ != stream.__name__ or name == "sse":
            continue
        args = [[] if "list" in str(p.annotation) else "x" for p in inspect.signature(fn).parameters.values()]
        types.add(fn(*args)["type"])
    return types


def test_contract_complete():
    assert {"start", "data-status", "data-trace", "data-citation-warning", "source-url", "error", "finish"} <= emitted_types()
    assert missing_from_doc(DOC) == []


def test_guard_detects_removed_docs_row():
    broken = "\n".join(line for line in DOC.splitlines() if not re.match(r"^\|\s*GET\s*\|\s*`/api/docs`\s*\|", line))
    assert missing_from_doc(broken) == ["GET /api/docs"]


def test_guard_detects_changed_order():
    assert "part order line" in missing_from_doc(DOC.replace(ORDER, "start → finish"))


def test_real_routes_in_contract():
    from app.main import app

    # openapi() thay vì app.routes: FastAPI mới bọc router con trong _IncludedRouter nên app.routes không liệt kê route thật.
    routes = {(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops}
    documented = table_endpoints(DOC)
    assert routes == ENDPOINTS, routes ^ ENDPOINTS
    assert routes <= documented, routes - documented
