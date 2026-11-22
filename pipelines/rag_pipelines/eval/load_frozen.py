"""Nạp index đóng băng (parquet từ export_index) vào Postgres LOCAL rồi đặt app_config.active_index_version.

Chạy: python -m rag_pipelines.eval.load_frozen --index eval/index/v1.parquet --database-url postgresql://...
Giả định schema đã có (migration áp trước). Idempotent: xóa chunks/articles/legal_refs của version đó rồi chèn lại,
legal_docs upsert. Từ chối DB không phải localhost (lệnh này ghi đè version và đổi active) trừ khi --allow-remote.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import psycopg
import pyarrow.parquet as pq
from app.legal.normalize import strip_diacritics
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb


def _rows(path: Path) -> tuple[list[str], list[dict]]:
    t = pq.read_table(path)
    return t.column_names, t.to_pylist()


def _insert(cur: psycopg.Cursor, table: str, cols: list[str], rows: list[dict]) -> None:
    cur.executemany(
        f"insert into {table} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
        [[r[c] for c in cols] for r in rows],
    )


def load_frozen(index_path: str | Path, conn: psycopg.Connection) -> int:
    p = Path(index_path)
    version = int(p.stem.removeprefix("v"))
    side = lambda n: _rows(p.with_name(f"{p.stem}.{n}.parquet"))  # noqa: E731
    docs_cols, docs = side("legal_docs")
    art_cols, arts = side("articles")
    ref_cols, refs = side("legal_refs")
    _, chunks = _rows(p)
    with conn.transaction(), conn.cursor() as cur:
        for t in ("chunks", "legal_refs", "articles"):
            cur.execute(f"delete from {t} where index_version = %s", (version,))
        sets = ", ".join(f"{c} = excluded.{c}" for c in docs_cols if c != "code")
        cur.executemany(
            f"insert into legal_docs ({', '.join(docs_cols)}) values ({', '.join(['%s'] * len(docs_cols))}) on conflict (code) do update set {sets}",
            [[None if c == "replaced_by" else d[c] for c in docs_cols] for d in docs],
        )  # replaced_by FK: đặt sau khi đủ văn bản
        cur.executemany(
            "update legal_docs set replaced_by = %s where code = %s",
            [(d["replaced_by"], d["code"]) for d in docs if d["replaced_by"]],
        )
        _insert(cur, "articles", art_cols, arts)
        cur.executemany(
            "insert into chunks (index_version, id, parent_id, doc_code, article, clause, point, content, embed_text, embedding, fts_noaccent) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::halfvec, to_tsvector('simple', %s))",
            [
                (
                    version,
                    c["id"],
                    c["parent_id"],
                    c["doc_code"],
                    c["article"],
                    c["clause"],
                    c["point"],
                    c["content"],
                    c["embed_text"],
                    "["
                    + ",".join(
                        f"{x:.7g}" for x in np.asarray(c["embedding"], dtype=np.float32)
                    )
                    + "]",
                    strip_diacritics(c["embed_text"]),
                )
                for c in chunks
            ],
        )
        _insert(cur, "legal_refs", ref_cols, refs)
        cur.execute(
            "update app_config set value = %s, updated_at = now() where key = 'active_index_version'",
            (Jsonb(version),),
        )
    return version


def ensure_local(url: str) -> None:
    if conninfo_to_dict(url).get("host") not in (None, "localhost", "127.0.0.1", "::1"):
        raise SystemExit(
            "refusing: load_frozen overwrites an index version and switches active_index_version; DB is not local (--allow-remote to override)"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--allow-remote", action="store_true")
    a = ap.parse_args()
    if not a.allow_remote:
        ensure_local(a.database_url)
    with psycopg.connect(a.database_url, autocommit=True) as conn:
        print(f"loaded index_version {load_frozen(a.index, conn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
