"""Báo cáo độ trễ theo span từ Langfuse -> eval/results/latency.md. Chạy ở gốc repo bằng python thường (chỉ stdlib).

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (vd https://cloud.langfuse.com). Không bao giờ in giá trị của chúng.
Dùng: python scripts/latency_report.py [--days 7 | --since 2026-12-01 [--until 2026-12-08]] [--out eval/results/latency.md]

API (docs/runbook-observability.md ghi trường nào đã đối chiếu tài liệu): GET {host}/api/public/v2/observations,
Basic auth public:secret, `fromStartTime` / `toStartTime` (ISO 8601), `limit` (<= 1000), phân trang bằng `cursor`
(`meta.cursor` vắng hoặc null thì hết; trang rỗng vẫn có thể kèm cursor). Mỗi phần tử `data`: `name`, `startTime`, `endTime`.
Độ trễ = endTime - startTime (trường core, luôn có), không dựa vào `latency` (thuộc nhóm trường khác).

Percentile: nearest-rank, cùng định nghĩa với percentile() trong pipelines/rag_pipelines/eval/answer_eval.py
(pipelines/tests/test_latency_report.py khóa hai bản bằng nhau).
Exit: 0 xong (kể cả khi không có dữ liệu), 2 thiếu env / tham số sai, 3 Langfuse lỗi.
"""

import argparse
import base64
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Thứ tự = thứ tự chạy trong một request; `chat` là span gốc (tổng thời gian request).
SPANS = ["condense", "embed", "hybrid_search", "rerank", "expand", "llm", "chat"]
PAGE_LIMIT = 1000
MAX_PAGES = 200  # shortcut: tối đa 200k observation mỗi báo cáo, khi nào cần hơn thì chia nhỏ cửa sổ thời gian
TIMEOUT_S = 30
ROOT = Path(__file__).resolve().parents[1]


class ReportError(Exception):
    pass


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank (giống answer_eval.percentile)."""
    if not values:
        raise ValueError("percentile of empty list")
    s = sorted(values)
    return s[max(1, math.ceil(p / 100 * len(s))) - 1]


def parse_time(s: str) -> datetime:
    """ISO 8601; chấp nhận hậu tố Z và phần giây dài hơn 6 chữ số. Không có múi giờ thì coi là UTC."""
    s = re.sub(r"(\.\d{6})\d+", r"\1", s.strip().replace("Z", "+00:00"))
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def http_get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # chỉ nêu mã trạng thái: không in URL / header
        raise ReportError(f"Langfuse trả HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        raise ReportError(f"không gọi được Langfuse ({type(e).__name__})") from None


def iter_observations(
    host: str,
    headers: dict[str, str],
    since: datetime,
    until: datetime,
    get: Callable[[str, dict[str, str]], dict] = http_get_json,
) -> Iterator[dict]:
    cursor = None
    for _ in range(MAX_PAGES):
        q = {
            "fromStartTime": since.isoformat().replace("+00:00", "Z"),
            "toStartTime": until.isoformat().replace("+00:00", "Z"),
            "limit": PAGE_LIMIT,
        }
        if cursor:
            q["cursor"] = cursor
        page = get(
            f"{host}/api/public/v2/observations?{urllib.parse.urlencode(q)}", headers
        )
        yield from page.get("data") or []
        cursor = (page.get("meta") or {}).get("cursor")
        if not cursor:
            return
    raise ReportError(f"quá {MAX_PAGES} trang, hãy thu hẹp cửa sổ --since/--until")


def durations_ms(observations) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {n: [] for n in SPANS}
    for o in observations:
        name, start, end = o.get("name"), o.get("startTime"), o.get("endTime")
        if name not in out or not start or not end:  # span chưa kết thúc: bỏ qua
            continue
        try:
            ms = (parse_time(end) - parse_time(start)).total_seconds() * 1000
        except ValueError:
            continue
        if ms >= 0:
            out[name].append(ms)
    return out


def render(durs: dict[str, list[float]], since: datetime, until: datetime) -> str:
    lines = [
        "# Độ trễ theo span (Langfuse)",
        "",
        f"Cửa sổ: {since.isoformat()} đến {until.isoformat()} (theo `startTime` của span).",
        "",
    ]
    if not any(durs.values()):
        lines.append(
            "Không có dữ liệu trong cửa sổ này (chưa có request nào được ghi trace)."
        )
    else:
        lines += ["| span | n | p50 (ms) | p95 (ms) |", "|---|---:|---:|---:|"]
        for name in SPANS:
            v = durs[name]
            row = f"{percentile(v, 50):.0f} | {percentile(v, 95):.0f}" if v else "- | -"
            lines.append(f"| {name} | {len(v)} | {row} |")
        lines += [
            "",
            "Span vắng mặt hợp lệ: `condense` (lượt đầu), `embed` / `rerank` / `llm` (offline, bị từ chối), nên `n` khác nhau giữa các dòng. `chat` là tổng thời gian request.",
        ]
    lines += ["", "generated by scripts/latency_report.py", ""]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None,
    env=os.environ,
    get: Callable[[str, dict[str, str]], dict] = http_get_json,
    now: datetime | None = None,
) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--days", type=float, default=7, help="cửa sổ tính lùi từ bây giờ (mặc định 7)"
    )
    ap.add_argument("--since", help="ISO 8601, ghi đè --days")
    ap.add_argument("--until", help="ISO 8601 (mặc định: bây giờ)")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "latency.md"))
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    missing = [
        k
        for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
        if not env.get(k)
    ]
    if missing:
        print(f"Thiếu biến môi trường: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        until = parse_time(a.until) if a.until else (now or datetime.now(UTC))
        since = parse_time(a.since) if a.since else until - timedelta(days=a.days)
    except ValueError:
        print(
            "--since / --until phải là ISO 8601 (vd 2026-12-01 hoặc 2026-12-01T00:00:00Z)",
            file=sys.stderr,
        )
        return 2
    if since >= until:
        print("--since phải trước --until", file=sys.stderr)
        return 2
    host = env["LANGFUSE_HOST"].rstrip("/")
    token = base64.b64encode(
        f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()
    try:
        durs = durations_ms(
            iter_observations(
                host, {"Authorization": f"Basic {token}"}, since, until, get
            )
        )
    except ReportError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 3
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(durs, since, until), encoding="utf-8")
    print(f"Đã ghi {out} ({sum(map(len, durs.values()))} span)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
