"""Bootstrap rule của eval gate (docs/ci.md). Chạy ở gốc repo bằng python thường (không cần uv sync).

- eval/baselines/main.json VẮNG  -> exit 0, ::warning::, ghi lời báo "Gate inactive" vào --comment, đặt active=false.
- baseline CÓ nhưng thiếu index đóng băng hoặc cache embedding -> exit 1, ghi lý do vào --comment.
- đủ cả -> exit 0, active=true (gate nghiêm ngặt, không cần sửa code khi baseline được commit).
Giữ tên file đồng bộ với pipelines/rag_pipelines/eval/retrieval_eval.py (cache_base) và export_index.py.
"""

import argparse
import os
import sys
from pathlib import Path

BASELINE = "eval/baselines/main.json"
REQUIRED = [
    "eval/index/v1.parquet",
    "eval/index/v1.legal_docs.parquet",
    "eval/index/v1.articles.parquet",
    "eval/index/v1.legal_refs.parquet",
    "eval/cache/query_emb_AITeamVN-Vietnamese_Embedding.npy",
    "eval/cache/query_emb_AITeamVN-Vietnamese_Embedding.ids.json",
]
INACTIVE = (
    "Gate inactive: no frozen baseline committed yet (run the live batch, see runbook)"
)


def precheck(root: Path, comment: Path | None) -> tuple[int, bool]:
    def say(msg: str) -> None:
        if comment:
            comment.write_text(f"### Retrieval eval gate\n\n{msg}\n", encoding="utf-8")

    if not (root / BASELINE).is_file():
        print(f"::warning title=Retrieval eval gate inactive::{INACTIVE}")
        say(f"**{INACTIVE}**")
        return 0, False
    if missing := [p for p in REQUIRED if not (root / p).is_file()]:
        msg = (
            "Gate FAILED: baseline exists but frozen artefacts are missing: "
            + ", ".join(missing)
        )
        print(f"::error title=Retrieval eval gate::{msg}")
        say(f"**{msg}**")
        return 1, False
    return 0, True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--comment", type=Path)
    a = ap.parse_args(argv)
    code, active = precheck(a.root, a.comment)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"active={'true' if active else 'false'}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
