"""Chọn 120 câu golden từ ứng viên + kết quả kiểm chéo.
Chạy: python -m rag_pipelines.eval.select_golden --candidates ... --verification ... --out eval/golden/v1.jsonl --sample eval/golden/review_sample.csv"""

import argparse
import csv
import json
import random
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from rag_pipelines.eval.golden_schema import (
    MAX_JACCARD,
    NO_GOLD,
    QUOTA,
    ROOT,
    TYPES,
    GoldItem,
    syllable_jaccard,
    valid_ids,
    validate_set,
)

SEED = 42
WORK = ROOT / "eval/golden/_work"


def _jsonl(path) -> list[dict]:
    return [
        json.loads(ln)
        for ln in Path(path).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def _nfc(c: dict) -> dict:
    nfc = lambda s: unicodedata.normalize("NFC", s).strip()  # noqa: E731
    return {
        **c,
        **{k: nfc(c[k]) for k in ("question", "answer", "source_quote")},
        "gold": [nfc(g) for g in c["gold"]],
    }


def _reject(c: dict, v: dict | None, ids) -> str | None:
    """Lý do loại ứng viên (None = giữ)."""
    if v is None:
        return "no_verification"
    if c["type"] in NO_GOLD:
        return "answerable_but_should_not" if v["answerable"] else None
    if not v["answerable"]:
        return "not_answerable"
    if not c["gold"] or not all(g in ids for g in c["gold"]):
        return "invalid_gold"
    if not set(c["gold"]) & set(v["gold"]):
        return "no_gold_overlap"
    return None


def select(
    cands: list[dict], verif: list[dict], ids
) -> tuple[list[GoldItem], dict, dict]:
    """=> (items, thống kê loại theo type, thiếu theo type)."""
    ver = {v["cand_index"]: v for v in verif}
    cands = [_nfc(c) for c in cands]
    seen: set[str] = set()
    stats: dict[str, Counter] = {t: Counter() for t in TYPES}
    kept: dict[str, list[dict]] = defaultdict(list)
    for i, c in enumerate(cands):
        s = stats[c["type"]]
        s["total"] += 1
        why = _reject(c, ver.get(i), ids) or (
            "copy"
            if syllable_jaccard(c["question"], c["source_quote"]) > MAX_JACCARD
            else None
        )
        if not why and c["question"] in seen:
            why = "duplicate"
        if not why:
            seen.add(c["question"])
        if why:
            s[why] += 1
        else:
            s["kept"] += 1
            kept[c["type"]].append(
                {**c, "gold": [] if c["type"] in NO_GOLD else c["gold"]}
            )
    short = {t: QUOTA[t] - len(kept[t]) for t in TYPES if len(kept[t]) < QUOTA[t]}
    rng = random.Random(SEED)
    chosen = []
    for t in TYPES:
        pick = kept[t][: QUOTA[t]]  # ưu tiên ứng viên đứng trước
        order = list(range(len(pick)))
        rng.shuffle(order)
        dev = set(order[: len(pick) // 3])
        chosen += [(c, "dev" if j in dev else "test") for j, c in enumerate(pick)]
    rng.shuffle(chosen)
    items = [
        GoldItem(
            f"q{n:03d}",
            c["question"],
            c["answer"],
            c["gold"],
            c["type"],
            c["as_of"],
            sp,
            c["source_quote"],
        )
        for n, (c, sp) in enumerate(chosen, 1)
    ]
    return items, {t: dict(s) for t, s in stats.items()}, short


def main(argv=None, ids=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, default=WORK / "candidates.jsonl")
    ap.add_argument("--verification", type=Path, default=WORK / "verification.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "eval/golden/v1.jsonl")
    ap.add_argument(
        "--sample", type=Path, default=ROOT / "eval/golden/review_sample.csv"
    )
    ap.add_argument("--stats", type=Path, default=WORK / "select_stats.json")
    a = ap.parse_args(argv)
    items, stats, short = select(
        _jsonl(a.candidates),
        _jsonl(a.verification),
        valid_ids() if ids is None else ids,
    )
    a.stats.parent.mkdir(parents=True, exist_ok=True)
    a.stats.write_text(
        json.dumps({"stats": stats, "shortfall": short}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for t, s in stats.items():
        print(f"{t}: {s}")
    if short:
        print(f"SHORTFALL (need more kept candidates): {short}", file=sys.stderr)
        return 1
    if errs := validate_set(items, valid_ids() if ids is None else ids):
        print("INVALID SET, not written:", *errs, sep="\n", file=sys.stderr)
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(
        "".join(json.dumps(asdict(i), ensure_ascii=False) + "\n" for i in items),
        encoding="utf-8",
    )
    with a.sample.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "question", "answer", "gold", "ok"])
        w.writerows(
            [i.id, i.type, i.question, i.answer, ";".join(i.gold), ""]
            for i in random.Random(SEED).sample(items, 20)
        )
    print(f"wrote {len(items)} items -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
