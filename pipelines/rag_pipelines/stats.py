"""Thống kê corpus -> docs/corpus/STATS.md. Chạy: uv run --project pipelines python -m rag_pipelines.stats.
Thoát mã 1 nếu tổng chunk ngoài 2.000–8.000 hoặc có chunk > 450 token."""

import math
import sys
from pathlib import Path

import yaml
from app.legal.refs import extract_refs

from rag_pipelines.chunk import (
    appendix_chunks_for,
    chunk_articles,
    default_count_tokens,
)
from rag_pipelines.extract import extract_text
from rag_pipelines.structure import parse_document_with_stats

MAX_TOKENS = 450
CHUNK_RANGE = (2000, 8000)
HEAD = [
    "Văn bản",
    "Điều",
    "Khoản",
    "Điểm",
    "Chunk",
    "Chunk phụ lục",
    "Token p50",
    "Token p95",
    "Token max",
    "Ref trong corpus",
    "Ref ngoài corpus",
    "Ref explicit_doc=False",
    "Ký tự bị bỏ",
]


def percentile(xs: list[int], p: float) -> int:
    """Nearest-rank; rỗng => 0."""
    s = sorted(xs)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)] if s else 0


def _row(name: str, n: dict, toks: list[int]) -> list:
    return [
        name,
        n["art"],
        n["cl"],
        n["pt"],
        len(toks),
        n["app"],
        percentile(toks, 50),
        percentile(toks, 95),
        max(toks, default=0),
        n["in"],
        n["out"],
        n["imp"],
        n["drop"],
    ]


def render_table(rows: list[tuple[str, dict, list[int]]]) -> str:
    """rows = (tên, đếm, danh sách token mỗi chunk); thêm dòng Tổng."""
    keys = ("art", "cl", "pt", "in", "out", "imp", "drop", "app")
    total = (
        {k: sum(r[1][k] for r in rows) for k in keys},
        [t for r in rows for t in r[2]],
    )
    body = [_row(n, c, t) for n, c, t in rows] + [_row("**Tổng**", *total)]
    lines = ["| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    return "\n".join(lines + ["| " + " | ".join(map(str, r)) + " |" for r in body])


def collect(doc: dict, count_tokens) -> tuple[dict, list[int]]:
    code = doc["code"]
    text = extract_text(code)
    arts, dropped = parse_document_with_stats(text, code)
    chunks = chunk_articles(arts, doc, count_tokens, MAX_TOKENS)
    app = appendix_chunks_for(
        doc, text, count_tokens, MAX_TOKENS
    )  # phụ lục vẫn nằm trong "Ký tự bị bỏ" (parser Điều bỏ khối cuối)
    n = dict(
        art=len(arts),
        cl=0,
        pt=0,
        **{"in": 0, "out": 0, "imp": 0},
        drop=dropped,
        app=len(app),
    )
    for a in arts:
        n["cl"] += sum(c.number is not None for c in a.clauses)
        n["pt"] += sum(len(c.points) for c in a.clauses)
        for t in [
            a.intro,
            *(c.text for c in a.clauses),
            *(p.text for c in a.clauses for p in c.points),
        ]:
            for r in extract_refs(t, self_doc=code):
                if r.article is None:
                    continue
                n["in" if r.dst_doc_code else "out"] += 1
                n["imp"] += not r.explicit_doc
    return n, [c.n_tokens for c in chunks + app]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    docs = yaml.safe_load(
        (root / "docs/corpus/legal_docs.yaml").read_text(encoding="utf-8")
    )["docs"]
    count = default_count_tokens()
    rows = [(d["code"], *collect(d, count)) for d in docs]
    table = render_table(rows)
    (root / "docs/corpus/STATS.md").write_text(
        "# Thống kê corpus\n\nSinh bởi `python -m rag_pipelines.stats`. Token đo trên embed_text bằng tokenizer "
        f"`AITeamVN/Vietnamese_Embedding`. Ref: chỉ tham chiếu cấp Điều.\n\n{table}\n",
        encoding="utf-8",
    )
    toks = [t for r in rows for t in r[2]]
    ok = (
        CHUNK_RANGE[0] <= len(toks) <= CHUNK_RANGE[1]
        and max(toks, default=0) <= MAX_TOKENS
    )
    print(table)
    print(
        "ĐẠT"
        if ok
        else f"KHÔNG ĐẠT: {len(toks)} chunk (cần {CHUNK_RANGE}), max {max(toks, default=0)} token (cần ≤ {MAX_TOKENS})"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
