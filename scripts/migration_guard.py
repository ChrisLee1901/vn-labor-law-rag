"""Chặn migration phá dữ liệu trước `supabase db push` (CLAUDE.md luật 5: migration chỉ additive).

Đọc đầu ra của `supabase db push --dry-run` (file hoặc stdin), lấy tên các migration sắp áp, quét SQL đã bỏ comment tìm
DROP TABLE / DROP COLUMN / TRUNCATE / DELETE FROM. Có hit thì exit 1, trừ khi file có dòng comment
`-- allow-destructive: <lý do>` (override có chủ đích, nằm trong diff nên được review).
shortcut: bỏ comment bằng regex, không hiểu `--` hay `/*` nằm trong chuỗi ký tự; DROP INDEX/FUNCTION/POLICY không bị chặn.
Nâng cấp bằng parser SQL thật nếu migration bắt đầu dùng chuỗi dài hoặc dynamic SQL.
"""

import argparse
import re
import sys
from pathlib import Path

DESTRUCTIVE = re.compile(
    r"\b(drop\s+table|drop\s+column|truncate|delete\s+from)\b", re.IGNORECASE
)
OVERRIDE = re.compile(r"^[ \t]*--[ \t]*allow-destructive:[ \t]*\S", re.MULTILINE)
NAME = re.compile(r"\b(\d{14}_[\w-]+\.sql)\b")


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", sql)


def check(dry_run: str, migrations: Path) -> list[str]:
    names = list(dict.fromkeys(NAME.findall(dry_run)))
    if "would push" in dry_run.lower() and not names:
        return [
            "Không đọc được tên migration từ đầu ra --dry-run (định dạng CLI đổi?)."
        ]
    problems = []
    for name in names:
        raw = (migrations / name).read_text(encoding="utf-8")
        hits = sorted(
            {m.group(1).lower() for m in DESTRUCTIVE.finditer(strip_comments(raw))}
        )
        if hits and not OVERRIDE.search(raw):
            problems.append(
                f"{name}: {', '.join(hits).upper()} (thêm `-- allow-destructive: <lý do>` nếu cố ý)"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dry_run", nargs="?", help="file đầu ra --dry-run; bỏ trống = stdin")
    p.add_argument("--migrations", default="supabase/migrations")
    a = p.parse_args(argv)
    text = (
        Path(a.dry_run).read_text(encoding="utf-8") if a.dry_run else sys.stdin.read()
    )
    problems = check(text, Path(a.migrations))
    for line in problems:
        print(f"::error::Migration có thể phá dữ liệu: {line}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
