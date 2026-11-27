"""Xuất index đóng băng từ DB ra parquet (dữ liệu CI/eval dùng, không cần Supabase).

Chạy: DATABASE_URL=... python -m rag_pipelines.export_index --index-version N [--out eval/index]
Ghi 4 file vào thư mục out (mặc định eval/index/):
- v{N}.parquet              chunks: id, parent_id, doc_code, article, clause, point, embed_text, content, embedding (list<float16>, 1024)
- v{N}.legal_docs.parquet   toàn bộ bảng legal_docs
- v{N}.articles.parquet     articles của index_version N (gồm kind 'dieu'|'phu_luc')
- v{N}.legal_refs.parquet   legal_refs của index_version N
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
CHUNK_COLS = "id, parent_id, doc_code, article, clause, point, embed_text, content"


def _table(cur: psycopg.Cursor) -> pa.Table:
    names = [d.name for d in cur.description]
    return (
        pa.Table.from_pylist([dict(zip(names, r)) for r in cur.fetchall()])
        if cur.rowcount
        else pa.table({n: [] for n in names})
    )


def export(db_url: str, version: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(db_url) as conn:
        conn.isolation_level = (
            psycopg.IsolationLevel.REPEATABLE_READ
        )  # one snapshot for all four reads
        conn.read_only = True
        _export(conn, version, out)


def _export(conn: psycopg.Connection, version: int, out: Path) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"select {CHUNK_COLS}, embedding::text from chunks where index_version = %s order by id",
            (version,),
        )
        names = [d.name for d in cur.description][:-1]
        rows = cur.fetchall()
        if not rows:
            raise ValueError(
                f"index_version {version} has no chunks; nothing to export"
            )
        cols = {n: [r[i] for r in rows] for i, n in enumerate(names)}
        cols["embedding"] = pa.array(
            [np.array(r[-1].strip("[]").split(","), dtype=np.float16) for r in rows],
            type=pa.list_(pa.float16()),
        )
        pq.write_table(pa.table(cols), out / f"v{version}.parquet")
        for name, q, args in [
            ("legal_docs", "select * from legal_docs order by code", ()),
            (
                "articles",
                "select * from articles where index_version = %s order by id",
                (version,),
            ),
            (
                "legal_refs",
                "select * from legal_refs where index_version = %s order by src_id, dst_doc_number, dst_article, dst_clause, dst_point, rel",
                (version,),
            ),
        ]:
            cur.execute(q, args)
            pq.write_table(_table(cur), out / f"v{version}.{name}.parquet")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-version", type=int, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "eval/index")
    a = ap.parse_args()
    export(os.environ["DATABASE_URL"], a.index_version, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
