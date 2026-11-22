"""Hybrid retrieval: FTS + vector (RRF trong SQL) -> rerank qua gateway -> top Điều cha; ID nêu rõ trong câu hỏi được ghim lên đầu."""

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date

from psycopg import AsyncConnection

from app.config import EMBED_TIMEOUT_S, RERANK_TIMEOUT_S
from app.legal.ids import make_id, parse_id
from app.legal.normalize import strip_diacritics
from app.legal.refs import extract_refs
from app.llm.gateway import Gateway, LLMOffline
from app.retrieval.tsquery import build_tsquery

TOP_PARENTS = 6
CANDIDATES = 40
MAX_QUERY_CHARS = 2000  # trần đầu vào cho regex ref (an toàn độ phức tạp / lạm dụng)
MAX_RERANK_CHARS = 8000  # giới hạn của gateway /v1/rerank


@dataclass
class Candidate:
    id: str
    parent_id: str
    score: float
    rerank: float | None = None


def extract_query_ids(q: str) -> list[str]:
    """ID pháp lý người dùng nêu rõ cả văn bản lẫn Điều, vd `ND145-2020:D12:K2`."""
    ids: list[str] = []
    for r in extract_refs(q[:MAX_QUERY_CHARS], self_doc=None):
        if r.explicit_doc and r.dst_doc_code is not None and r.article is not None:
            i = make_id(r.dst_doc_code, r.article, r.clause, r.point)
            if i not in ids:
                ids.append(i)
    return ids


async def _pinned(
    conn: AsyncConnection, question: str, index_version: int
) -> list[Candidate]:
    parents: list[str] = []
    for i in extract_query_ids(question):
        code, art, _, _ = parse_id(i)
        p = make_id(code, art)  # ghim ở mức Điều cha
        if p not in parents:
            parents.append(p)
    if not parents:
        return []
    cur = await conn.execute(
        "select id from articles where index_version = %s and id = any(%s)",
        (index_version, parents),
    )
    exist = {r[0] for r in await cur.fetchall()}
    return [Candidate(p, p, 1.0, 1.0) for p in parents if p in exist]


async def _hybrid(
    conn, question: str, as_of: date, index_version: int, vec: list[float] | None
) -> list[tuple[str, str, float]]:
    qe = "[" + ",".join(map(str, vec)) + "]" if vec is not None else None
    cur = await conn.execute(
        "select id, parent_id, score from hybrid_search(%s::text, %s::text, %s::halfvec, %s, %s::date, %s)",
        (
            build_tsquery(question),
            build_tsquery(strip_diacritics(question)),
            qe,
            index_version,
            as_of,
            CANDIDATES,
        ),
    )
    return await cur.fetchall()


async def _rerank(
    conn, gw: Gateway, question: str, rows, index_version: int
) -> list[Candidate]:
    ids = [r[0] for r in rows]
    cur = await conn.execute(
        "select id, embed_text from chunks where index_version = %s and id = any(%s)",
        (index_version, ids),
    )
    text = dict(await cur.fetchall())
    kept = [r for r in rows if r[0] in text]
    ranked = await gw.rerank(
        question, [text[r[0]][:MAX_RERANK_CHARS] for r in kept], len(kept)
    )
    best: dict[str, Candidate] = {}
    for idx, s in ranked:
        cid, pid, rrf = kept[idx]
        if pid not in best or s > (best[pid].rerank or 0.0):
            best[pid] = Candidate(cid, pid, rrf, s)
    return sorted(best.values(), key=lambda c: c.rerank or 0.0, reverse=True)


def _by_rrf(rows) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for cid, pid, score in rows:  # rows đã sắp theo điểm RRF giảm dần
        seen.setdefault(pid, Candidate(cid, pid, score))
    return list(seen.values())


async def retrieve(
    question: str,
    as_of: date,
    gw: Gateway,
    conn: AsyncConnection,
    index_version: int,
    online: bool,
    trace=None,
    pin_text: str | None = None,
) -> list[Candidate]:
    """Online: embed + hybrid + rerank. Offline (hoặc gateway lỗi): FTS-only, xếp theo RRF. Tối đa 6 Điều cha, ID ghim đứng đầu.

    `trace` (tùy chọn, app.tracing.Trace) ghi span embed / hybrid_search / rerank.
    `pin_text`: câu hỏi gốc; ID nêu rõ trong đó cũng được ghim (hợp với ID của `question`, bỏ trùng, ID của câu gốc đứng trước).
    embed / rerank quá EMBED_TIMEOUT_S / RERANK_TIMEOUT_S thì coi như LLMOffline (xuống cấp về FTS / thứ tự RRF)."""
    span = trace.span if trace is not None else (lambda _name: nullcontext())
    vec = None
    if online:
        try:
            with span("embed"):
                async with asyncio.timeout(EMBED_TIMEOUT_S):
                    vec = (await gw.embed([question]))[0]
        except (LLMOffline, TimeoutError):
            pass
    with span("hybrid_search"):
        rows = await _hybrid(conn, question, as_of, index_version, vec)
    cands = _by_rrf(rows)
    if vec is not None and rows:
        try:
            with span("rerank"):
                async with asyncio.timeout(RERANK_TIMEOUT_S):
                    cands = await _rerank(conn, gw, question, rows, index_version)
        except (LLMOffline, TimeoutError):
            pass
    pinned = await _pinned(conn, question, index_version)
    if pin_text and pin_text != question:
        raw = await _pinned(conn, pin_text, index_version)
        pinned = raw + [
            c for c in pinned if c.parent_id not in {r.parent_id for r in raw}
        ]
    taken = {c.parent_id for c in pinned}
    return (pinned + [c for c in cands if c.parent_id not in taken])[:TOP_PARENTS]
