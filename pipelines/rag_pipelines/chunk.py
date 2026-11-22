"""Chunk theo cấu trúc: Điều -> Khoản -> Điểm -> câu, mỗi chunk có breadcrumb; n_tokens đo trên embed_text."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.legal.ids import make_appendix_id, make_id

from rag_pipelines.structure import Appendix, Article, parse_appendices

_SENT = re.compile(r"(?<=[.;:!?])\s+|\n")


@dataclass
class Chunk:
    id: str
    parent_id: str
    doc_code: str
    article: int
    clause: int | None
    point: str | None
    content: str
    embed_text: str
    n_tokens: int


def default_count_tokens() -> Callable[[str], int]:
    from tokenizers import Tokenizer

    tok = Tokenizer.from_pretrained("AITeamVN/Vietnamese_Embedding")
    return lambda s: len(tok.encode(s, add_special_tokens=False).ids)


def _split(text: str, fits: Callable[[str], bool]) -> list[str]:
    """Gộp câu tham lam cho vừa; câu đơn vẫn quá dài thì cắt theo từ."""
    units: list[str] = []
    for s in filter(None, _SENT.split(text)):
        if fits(s):
            units.append(s)
            continue
        cur = ""
        for w in s.split():
            if cur and not fits(f"{cur} {w}"):
                units.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            units.append(cur)
    out: list[str] = []
    for u in units:
        if out and fits(f"{out[-1]} {u}"):
            out[-1] += f" {u}"
        else:
            out.append(u)
    return out


def chunk_articles(
    articles: list[Article],
    doc: dict,
    count_tokens: Callable[[str], int],
    max_tokens: int = 450,
) -> list[Chunk]:
    out: list[Chunk] = []

    for a in articles:
        aid = make_id(a.doc_code, a.number, suffix=a.suffix)
        art_crumb = (
            f"[{doc['number']} – {doc['short_title']}] {a.chapter + ' > ' if a.chapter else ''}"
            f"Điều {a.number}{a.suffix or ''}. {a.title}"
        )

        def emit(
            cid: str, clause: int | None, point: str | None, content: str, crumb: str
        ) -> None:
            fits = lambda s: count_tokens(f"{crumb}\n{s}") <= max_tokens  # noqa: E731
            parts = [content] if fits(content) else _split(content, fits)
            for i, p in enumerate(parts, 1):
                cid_i = cid if len(parts) == 1 else f"{cid}#{i}"
                embed = f"{crumb}\n{p}"
                out.append(
                    Chunk(
                        cid_i,
                        aid,
                        a.doc_code,
                        a.number,
                        clause,
                        point,
                        p,
                        embed,
                        count_tokens(embed),
                    )
                )

        def do_unit(
            base: str, clause: int | None, crumb: str, lead: str, points: list
        ) -> None:
            """Một Điều (khoản không số) hoặc Khoản: vừa thì 1 chunk, quá dài thì mỗi Điểm 1 chunk kèm lead."""
            lines = [f"{p.letter}) {p.text}" for p in points]
            whole = "\n".join(x for x in (lead, *lines) if x)
            if count_tokens(f"{crumb}\n{whole}") <= max_tokens or not points:
                emit(base, clause, None, whole, crumb)
                return
            for p, line in zip(points, lines):
                emit(
                    f"{base}:{p.letter}",
                    clause,
                    p.letter,
                    "\n".join(x for x in (lead, line) if x),
                    crumb,
                )

        clauses = a.clauses
        # Khoản không số (Điểm đứng trước mọi Khoản) gộp vào cấp Điều cùng intro.
        head = clauses[0] if clauses and clauses[0].number is None else None
        rest = clauses[1:] if head else clauses
        lead = "\n".join(x for x in (a.intro, head.text if head else "") if x) or (
            a.title if not clauses else ""
        )
        if lead or head:
            do_unit(aid, None, art_crumb, lead, head.points if head else [])
        for c in rest:
            do_unit(
                make_id(a.doc_code, a.number, c.number, suffix=a.suffix),
                c.number,
                f"{art_crumb} | Khoản {c.number}:",
                c.text,
                c.points,
            )
    return out


def chunk_appendices(
    appendices: list[Appendix],
    doc: dict,
    count_tokens: Callable[[str], int],
    max_tokens: int = 450,
) -> list[Chunk]:
    """1 chunk/mục; quá dài thì tách theo dòng `- Vùng …`, dòng quá dài tách tiếp theo câu/từ (id `#k`), mảnh sau giữ nhãn vùng."""
    out: list[Chunk] = []
    for ap in appendices:
        pid = make_appendix_id(ap.doc_code, ap.number)
        for n, heading, text in ap.items:
            cid = make_appendix_id(ap.doc_code, ap.number, n)
            crumb = f"[{doc['number']} – {doc['short_title']}] Phụ lục {ap.number}. {ap.title} | {heading}:"
            fits = lambda s: count_tokens(f"{crumb}\n{s}") <= max_tokens  # noqa: E731
            parts = [text]
            if not fits(text):
                parts = []
                for line in text.split("\n"):
                    if fits(line):
                        parts.append(line)
                        continue
                    label = (
                        re.match(r"- Vùng [IVX]+", line) or re.match(r"", line)
                    ).group()
                    pieces = _split(line, lambda s: fits(f"{label} (tiếp): {s}"))  # noqa: B023
                    parts += [pieces[0]] + [f"{label} (tiếp): {p}" for p in pieces[1:]]
            for i, p in enumerate(parts, 1):
                embed = f"{crumb}\n{p}"
                out.append(
                    Chunk(
                        cid if len(parts) == 1 else f"{cid}#{i}",
                        pid,
                        ap.doc_code,
                        ap.number,
                        n,
                        None,
                        p,
                        embed,
                        count_tokens(embed),
                    )
                )
    return out


def appendix_chunks_for(
    doc: dict, text: str, count_tokens: Callable[[str], int], max_tokens: int = 450
) -> list[Chunk]:
    """Chỉ văn bản có `keep_appendix: true` trong legal_docs.yaml mới sinh chunk phụ lục."""
    if not doc.get("keep_appendix"):
        return []
    return chunk_appendices(
        parse_appendices(text, doc["code"]), doc, count_tokens, max_tokens
    )
