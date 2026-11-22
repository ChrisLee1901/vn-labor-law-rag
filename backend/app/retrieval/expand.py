"""Mở rộng 1-hop: thêm các Điều được tham chiếu (legal_refs) và các văn bản hướng dẫn chi tiết Điều đã chọn."""
from dataclasses import dataclass
from datetime import date

from psycopg import AsyncConnection

from app.legal.ids import make_id

_COLS = """a.id, a.doc_code, coalesce(d.number, a.doc_code), coalesce(a.number, 0), coalesce(a.title, ''), coalesce(a.content, ''),
           d.effective_from, d.effective_to, coalesce(d.status, '')"""

# Điều (hoặc Phụ lục) chứa một legal_refs.src_id: bỏ hậu tố khoản/điểm/mục.
_SRC_PARENT = r"regexp_replace(r.src_id, '(:K\d+.*|:M\d+|#.*)$', '')"


@dataclass
class SourceDoc:
    sid: str
    id: str
    doc_code: str
    doc_number: str
    article: int
    title: str
    content: str
    effective_from: date
    effective_to: date | None
    status: str
    via_ref: bool


async def _rows(conn: AsyncConnection, query: str, params: tuple) -> list[tuple]:
    cur = await conn.execute(query, params)
    return await cur.fetchall()


async def expand(
    parent_ids: list[str], conn: AsyncConnection, index_version: int, as_of: date, max_extra: int = 4
) -> list[SourceDoc]:
    parents = list(dict.fromkeys(parent_ids))
    by_id = {
        r[0]: r
        for r in await _rows(
            conn,
            f"select {_COLS} from articles a join legal_docs d on d.code = a.doc_code "
            "where a.index_version = %s and a.id = any(%s)",
            (index_version, parents),
        )
    }
    parents = [p for p in parents if p in by_id]

    # (a) Điều được tham chiếu từ parent hoặc từ khoản/điểm của parent, theo thứ tự parent.
    fwd = await _rows(
        conn,
        """select r.dst_doc_code, r.dst_article
           from unnest(%s::text[]) with ordinality p(id, ord)
           join legal_refs r on r.index_version = %s
             and (r.src_id = p.id or starts_with(r.src_id, p.id || ':') or starts_with(r.src_id, p.id || '#'))
           where r.dst_doc_code is not null and r.dst_article is not null
           order by p.ord, substring(r.src_id from ':K([0-9]+)')::int nulls first, r.src_id, r.dst_doc_code, r.dst_article""",
        (parents, index_version),
    )
    # (b) Điều của văn bản khác có khoản 'details' trỏ vào parent (nghị định hướng dẫn Điều của luật).
    rev = await _rows(
        conn,
        f"""select {_SRC_PARENT}
            from unnest(%s::text[]) with ordinality p(id, ord)
            join legal_refs r on r.index_version = %s and r.rel = 'details'
              and r.dst_doc_code || ':D' || r.dst_article = p.id
            order by p.ord, substring(r.src_id from ':D([0-9]+)')::int nulls last, r.src_id""",
        (parents, index_version),
    )
    extra_ids = [i for i in dict.fromkeys([make_id(c, a) for c, a in fwd] + [r[0] for r in rev]) if i not in by_id]
    extras = {
        r[0]: r
        for r in await _rows(
            conn,
            f"select {_COLS} from articles a join legal_docs d on d.code = a.doc_code "
            "where a.index_version = %s and a.id = any(%s) "
            "and d.effective_from <= %s and (d.effective_to is null or %s < d.effective_to)",
            (index_version, extra_ids, as_of, as_of),
        )
    }
    chosen = [(by_id[p], False) for p in parents]
    chosen += [(extras[i], True) for i in extra_ids if i in extras][:max_extra]
    return [SourceDoc(f"S{n}", *row, via) for n, (row, via) in enumerate(chosen, 1)]
