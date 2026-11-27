"""Ingest corpus -> Postgres/Supabase cho một `index_version`. Không đổi `app_config.active_index_version`.

Chạy: DATABASE_URL=... LLM_BASE_URL=... LLM_API_KEY=... python -m rag_pipelines.ingest --index-version N [--dry-run] [--force]

- Một transaction/lần chạy: xóa chunks, legal_refs, articles của index_version đó rồi chèn lại (idempotent); legal_docs upsert.
  Embedding tính xong (batch 32) TRƯỚC khi mở transaction nên lỗi gateway không để lại trạng thái dở.
- Từ chối ghi vào version đang active (blue/green) trừ khi `--force`.
- Phụ lục (`keep_appendix`) ghi vào `articles` với kind='phu_luc' (id `<code>:PL<n>`), chunk phụ lục giữ nguyên Chunk.article/clause.
- legal_refs lọc theo ruling R15: giữ ref khi (a) có Điều; (b) không phải [điền văn bản đích ngầm định và (nghị định hoặc rel='amends')];
  (c) nếu đích thuộc corpus thì Điều đích phải tồn tại trong cấu trúc đã parse, ngược lại bỏ và đếm là "unresolved".
- `--dry-run`: parse + chunk + refs, in số liệu mỗi văn bản, không DB, không embedding.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
import yaml
from app.legal.ids import make_appendix_id, make_id
from app.legal.normalize import strip_diacritics
from app.legal.refs import DOC_NUMBERS, extract_refs
from app.llm.gateway import Gateway, LLMOffline

from rag_pipelines.chunk import (
    Chunk,
    chunk_articles,
    chunk_appendices,
    default_count_tokens,
)
from rag_pipelines.extract import extract_text
from rag_pipelines.structure import Appendix, Article, parse_appendices, parse_document

Embed = Callable[[list[str]], list[list[float]]]
BATCH = 32
DIM = 1024
ROOT = Path(__file__).resolve().parents[2]
DOC_COLS = [
    "code",
    "number",
    "title",
    "doc_type",
    "issuer",
    "issued_on",
    "effective_from",
    "effective_to",
    "status",
    "replaced_by",
    "amends",
    "source_url",
    "file_sha256",
]  # page/files/short_title/keep_appendix không vào DB


class ActiveVersionError(Exception):
    """index_version trùng version đang active mà không có --force."""


@dataclass
class Parsed:
    doc: dict
    arts: list[Article]
    appendices: list[Appendix]
    chunks: list[Chunk]
    n_appendix_chunks: int = 0
    refs: list[dict] = field(default_factory=list)


def parse(doc: dict, text: str, count_tokens: Callable[[str], int]) -> Parsed:
    arts = parse_document(text, doc["code"])
    apps = parse_appendices(text, doc["code"]) if doc.get("keep_appendix") else []
    app_chunks = chunk_appendices(apps, doc, count_tokens)
    return Parsed(
        doc,
        arts,
        apps,
        chunk_articles(arts, doc, count_tokens) + app_chunks,
        len(app_chunks),
    )


def _article_id(a: Article) -> str:
    return make_id(a.doc_code, a.number, suffix=a.suffix)


def _texts(a: Article):
    """(src_id, text) cho intro/khoản/điểm; src_id là id cụ thể nhất (Điểm của khoản không số dùng id Điều)."""
    aid = _article_id(a)
    yield aid, a.intro
    for c in a.clauses:
        cid = (
            make_id(a.doc_code, a.number, c.number, suffix=a.suffix)
            if c.number is not None
            else aid
        )
        yield cid, c.text
        for p in c.points:
            yield (
                (
                    make_id(a.doc_code, a.number, c.number, p.letter, suffix=a.suffix)
                    if c.number is not None
                    else aid
                ),
                p.text,
            )


def collect_refs(parsed: list[Parsed]) -> tuple[list[dict], dict]:
    known = {(p.doc["code"], a.number) for p in parsed for a in p.arts}
    rows: dict[tuple, dict] = {}
    stats = {"kept": 0, "unresolved": 0, "dropped": 0}
    for p in parsed:
        code, doc_type = p.doc["code"], p.doc["doc_type"]
        for a in p.arts:
            for src, text in _texts(a):
                for r in extract_refs(text, self_doc=code):
                    if r.article is None or (
                        not r.explicit_doc
                        and (doc_type == "nghi_dinh" or r.rel == "amends")
                    ):
                        stats["dropped"] += 1
                    elif (
                        r.dst_doc_code in DOC_NUMBERS
                        and (r.dst_doc_code, r.article) not in known
                    ):
                        stats["unresolved"] += 1
                    else:
                        row = dict(
                            src_id=src,
                            dst_doc_code=r.dst_doc_code,
                            dst_doc_number=r.dst_doc_number,
                            dst_article=r.article,
                            dst_clause=r.clause,
                            dst_point=r.point,
                            rel=r.rel,
                        )
                        rows.setdefault(tuple(row.values()), row)
    stats["kept"] = len(rows)
    return list(rows.values()), stats


def _content(a: Article) -> str:
    lines = [a.intro]
    for c in a.clauses:
        lines.append(f"{c.number}. {c.text}" if c.number is not None else c.text)
        lines += [f"{p.letter}) {p.text}" for p in c.points]
    return "\n".join(x for x in lines if x)


def article_rows(p: Parsed) -> list[dict]:
    rows = [
        dict(
            id=_article_id(a),
            doc_code=a.doc_code,
            number=a.number,
            suffix=a.suffix,
            title=a.title,
            chapter=a.chapter,
            content=_content(a),
            kind="dieu",
        )
        for a in p.arts
    ]
    rows += [
        dict(
            id=make_appendix_id(ap.doc_code, ap.number),
            doc_code=ap.doc_code,
            number=ap.number,
            suffix=None,
            title=ap.title,
            chapter=None,
            content="\n".join(f"{n}. {h}\n{t}" for n, h, t in ap.items),
            kind="phu_luc",
        )
        for ap in p.appendices
    ]
    return rows


def _summarize(parsed: list[Parsed], refs: list[dict], stats: dict) -> dict:
    out = {}
    for p in parsed:
        code = p.doc["code"]
        out[code] = dict(
            articles=len(p.arts),
            appendices=len(p.appendices),
            chunks=len(p.chunks),
            appendix_chunks=p.n_appendix_chunks,
            refs=sum(r["src_id"].split(":")[0] == code for r in refs),
        )
        print(f"{code}: " + ", ".join(f"{k}={v}" for k, v in out[code].items()))
    print(
        f"refs: kept={stats['kept']} unresolved={stats['unresolved']} dropped={stats['dropped']}"
    )
    return out


def _build(
    docs: list[dict], texts: dict[str, str], count_tokens
) -> tuple[list[Parsed], list[dict], dict]:
    parsed = [parse(d, texts[d["code"]], count_tokens) for d in docs]
    ids = [c.id for p in parsed for c in p.chunks]
    if dup := [i for i, n in Counter(ids).items() if n > 1]:
        raise ValueError(f"duplicate chunk ids: {dup[:5]}")
    refs, stats = collect_refs(parsed)
    return parsed, refs, stats


def dry_run(docs: list[dict], texts: dict[str, str], count_tokens) -> dict:
    parsed, refs, stats = _build(docs, texts, count_tokens)
    return _summarize(parsed, refs, stats)


def _check_active(conn, version: int, force: bool, lock: bool = False) -> None:
    """Fail closed: a missing active_index_version row also refuses unless --force."""
    row = conn.execute(
        "select value from app_config where key = 'active_index_version'"
        + (" for share" if lock else "")
    ).fetchone()
    if force:
        return
    if row is None:
        raise ActiveVersionError(
            "app_config.active_index_version is missing; refusing without --force"
        )
    if int(row[0]) == version:
        raise ActiveVersionError(
            f"index_version {version} is the active version; refusing without --force"
        )


_sleep = time.sleep
RETRIES = 3


def _embed_retry(batch: list[str], embed: Embed) -> list[list[float]]:
    for attempt in range(RETRIES):
        try:
            return embed(batch)
        except LLMOffline:
            if attempt == RETRIES - 1:
                raise
            _sleep(attempt + 1)  # 1 s, 2 s
    raise AssertionError("unreachable")


def embed_all(texts: list[str], embed: Embed) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out += _embed_retry(texts[i : i + BATCH], embed)
    if len(out) != len(texts) or any(len(v) != DIM for v in out):
        raise ValueError(f"embedder must return {len(texts)} vectors of {DIM} dims")
    return out


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def run(
    conn: psycopg.Connection,
    docs: list[dict],
    texts: dict[str, str],
    version: int,
    embed: Embed,
    count_tokens: Callable[[str], int],
    force: bool = False,
) -> dict:
    _check_active(
        conn, version, force
    )  # fail fast, before the expensive embedding; re-checked under lock below
    parsed, refs, stats = _build(docs, texts, count_tokens)
    chunks = [c for p in parsed for c in p.chunks]
    vecs = embed_all([c.embed_text for c in chunks], embed)
    with conn.transaction(), conn.cursor() as cur:
        _check_active(
            cur, version, force, lock=True
        )  # TOCTOU: `for share` blocks a concurrent switch until we commit
        for t in ("chunks", "legal_refs", "articles"):
            cur.execute(f"delete from {t} where index_version = %s", (version,))
        cols = ", ".join(DOC_COLS)
        sets = ", ".join(f"{c} = excluded.{c}" for c in DOC_COLS[1:])
        cur.executemany(
            f"insert into legal_docs ({cols}) values ({', '.join(['%s'] * len(DOC_COLS))}) on conflict (code) do update set {sets}",
            [
                [None if c == "replaced_by" else d.get(c) for c in DOC_COLS]
                for d in docs
            ],
        )
        cur.executemany(
            "update legal_docs set replaced_by = %s where code = %s",
            [(d["replaced_by"], d["code"]) for d in docs if d.get("replaced_by")],
        )
        cur.executemany(
            "insert into articles (index_version, id, doc_code, number, suffix, title, chapter, content, kind) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    version,
                    r["id"],
                    r["doc_code"],
                    r["number"],
                    r["suffix"],
                    r["title"],
                    r["chapter"],
                    r["content"],
                    r["kind"],
                )
                for p in parsed
                for r in article_rows(p)
            ],
        )
        cur.executemany(
            "insert into chunks (index_version, id, parent_id, doc_code, article, clause, point, content, embed_text, n_tokens, embedding, fts_noaccent) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::halfvec, to_tsvector('simple', %s))",
            [
                (
                    version,
                    c.id,
                    c.parent_id,
                    c.doc_code,
                    c.article,
                    c.clause,
                    c.point,
                    c.content,
                    c.embed_text,
                    c.n_tokens,
                    _vec(v),
                    strip_diacritics(c.embed_text),
                )
                for c, v in zip(chunks, vecs)
            ],
        )
        cur.executemany(
            "insert into legal_refs (index_version, src_id, dst_doc_code, dst_doc_number, dst_article, dst_clause, dst_point, rel) values (%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    version,
                    r["src_id"],
                    r["dst_doc_code"],
                    r["dst_doc_number"],
                    r["dst_article"],
                    r["dst_clause"],
                    r["dst_point"],
                    r["rel"],
                )
                for r in refs
            ],
        )
    summary = _summarize(parsed, refs, stats)
    return {
        "docs": summary,
        "chunks": len(chunks),
        "refs": len(refs),
        "unresolved": stats["unresolved"],
    }


class GatewayEmbed:
    """Sync wrapper over Gateway.embed with its own event loop; call close() when done."""

    def __init__(self) -> None:
        self.gw = Gateway(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"])
        self.loop = asyncio.new_event_loop()

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return self.loop.run_until_complete(self.gw.embed(texts))

    def close(self) -> None:
        self.loop.run_until_complete(self.gw.aclose())
        self.loop.close()


def load_corpus() -> tuple[list[dict], dict[str, str]]:
    docs = yaml.safe_load(
        (ROOT / "docs/corpus/legal_docs.yaml").read_text(encoding="utf-8")
    )["docs"]
    files = json.loads(
        (ROOT / "docs/corpus/manifest.json").read_text(encoding="utf-8")
    )["files"]
    for d in docs:
        shas = sorted(f["sha256"] for f in files if f["code"] == d["code"])
        d["file_sha256"] = (
            shas[0]
            if len(shas) == 1
            else hashlib.sha256("\n".join(shas).encode()).hexdigest()
            if shas
            else None
        )
    return docs, {d["code"]: extract_text(d["code"]) for d in docs}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-version", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--force", action="store_true", help="cho phép ghi đè version đang active"
    )
    a = ap.parse_args()
    docs, texts = load_corpus()
    count = default_count_tokens()
    if a.dry_run:
        dry_run(docs, texts, count)
        return 0
    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=None
        ) as conn:
            embed = GatewayEmbed()
            try:
                run(conn, docs, texts, a.index_version, embed, count, a.force)
            finally:
                embed.close()
    except ActiveVersionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
