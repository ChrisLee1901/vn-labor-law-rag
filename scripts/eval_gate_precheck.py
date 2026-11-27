"""Bootstrap rule của eval gate (docs/ci.md). Chạy ở gốc repo bằng python thường (không cần uv sync).

- eval/baselines/main.json VẮNG  -> exit 0, ::warning::, ghi lời báo "Gate inactive" vào --comment, đặt active=false.
- baseline CÓ nhưng thiếu index đóng băng hoặc cache embedding -> exit 1, ghi lý do vào --comment.
- đủ cả -> exit 0, active=true (gate nghiêm ngặt, không cần sửa code khi baseline được commit).
- Chống xóa lách gate: trên PR (GITHUB_BASE_REF đặt), baseline hoặc index mà nhánh base CÓ nhưng head thiếu (hoặc baseline rỗng / không phải JSON)
  -> exit 1. Chỉ khi base cũng không có baseline thì mới "inactive". Push / không có base ref thì bỏ qua kiểm tra base.
Giới hạn còn lại: PR vẫn sửa được SỐ trong baseline (thấy trong diff) -> cần review bắt buộc cho eval/baselines/** (docs/ci.md).
Giữ tên file đồng bộ với pipelines/rag_pipelines/eval/retrieval_eval.py (cache_base) và export_index.py.
"""

import argparse
import json
import os
import subprocess
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


GUARDED = [
    BASELINE,
    "eval/index/v1.parquet",
]  # shortcut: chỉ baseline + index, cache chưa được canh; nâng cấp nếu cần


def base_has(root: Path, ref: str, path: str) -> bool:
    """Nhánh base có file này không. Ref không resolve được thì raise (fail closed, không coi là 'vắng')."""
    git = ["git", "-C", str(root)]
    if subprocess.run(
        [*git, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
    ).returncode:
        raise RuntimeError(f"base ref {ref} not fetched")
    return (
        subprocess.run(
            [*git, "cat-file", "-e", f"{ref}:{path}"], capture_output=True
        ).returncode
        == 0
    )


def precheck(
    root: Path, comment: Path | None, base_ref: str | None = None, has=base_has
) -> tuple[int, bool]:
    def say(msg: str) -> None:
        if comment:
            comment.write_text(f"### Retrieval eval gate\n\n{msg}\n", encoding="utf-8")

    def fail(msg: str) -> tuple[int, bool]:
        print(f"::error title=Retrieval eval gate::{msg}")
        say(f"**{msg}**")
        return 1, False

    if base_ref:
        try:
            for p in GUARDED:
                if has(root, base_ref, p) and not (root / p).is_file():
                    return fail(
                        f"Gate FAILED: `{p}` exists on base ({base_ref}) but is deleted in this PR"
                    )
            if has(root, base_ref, BASELINE):
                try:
                    if not isinstance(
                        json.loads((root / BASELINE).read_text(encoding="utf-8")), dict
                    ):
                        raise ValueError
                except ValueError:
                    return fail(
                        f"Gate FAILED: `{BASELINE}` exists on base but is empty or not a JSON object in this PR"
                    )
        except RuntimeError as e:
            return fail(f"Gate FAILED: cannot compare with base: {e}")

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
    base = os.environ.get("GITHUB_BASE_REF")  # chỉ có trên pull_request
    code, active = precheck(a.root, a.comment, f"origin/{base}" if base else None)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"active={'true' if active else 'false'}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
