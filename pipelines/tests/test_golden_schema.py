import json
from pathlib import Path

import pytest

from rag_pipelines.eval.golden_schema import QUOTA, GoldItem, load_golden, syllable_jaccard, validate_set

IDS = {"X:D1", "X:D2", "X:D3:K1"}
NO_GOLD = {"unanswerable", "out_of_domain", "injection"}


def make_set(**over) -> list[GoldItem]:
    items, n = [], 0
    for t, q in QUOTA.items():
        for i in range(q):
            n += 1
            dev = i < q // 3
            items.append(GoldItem(f"q{n:03d}", f"cau hoi so {n} ve {t}", "tra loi", [] if t in NO_GOLD else ["X:D1"], t,
                                  "2026-01-01", "dev" if dev else "test", "trich dan khac hoan toan"))
    return items


def errs(items, ids=IDS):
    return validate_set(items, ids)


def test_valid_set_has_no_errors():
    assert sum(QUOTA.values()) == 120
    assert errs(make_set()) == []


def test_unknown_gold_id():
    items = make_set()
    items[0].gold = ["X:D99"]
    assert any("X:D99" in e for e in errs(items))


def test_total_and_quota():
    items = make_set()[:-1]
    e = errs(items)
    assert any("119" in e_ or "120" in e_ for e_ in e)
    items = make_set()
    for it in items[:10]:  # single -> numeric: quota deviation
        it.type = "numeric"
    assert any("quota" in e_ for e_ in errs(items))


def test_split_counts_and_stratification():
    items = make_set()
    items[0].split = "test"  # one fewer dev
    assert any("split" in e for e in errs(items))
    items = make_set()
    singles = [i for i in items if i.type == "single"]
    for i in singles[:14]:  # skew the per-type dev share: single loses 14 dev, numeric gains 14 dev
        i.split = "test"
    for i in [i for i in items if i.type == "numeric"][6:20]:
        i.split = "dev"
    e = errs(items)
    assert any("strat" in e_ for e_ in e)


def test_jaccard_copy_detected():
    items = make_set()
    items[0].source_quote = items[0].question
    assert any("jaccard" in e for e in errs(items))
    assert syllable_jaccard("Điều 5, khoản 1!", "điều 5 khoản 1") == 1.0
    assert syllable_jaccard("a b", "c d") == 0.0


def test_load_golden_validates(tmp_path: Path):
    good = dict(id="q001", question="q", answer="a", gold=["X:D1"], type="single", as_of="2026-01-01", split="dev", source_quote="s")
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps(good) + "\n", encoding="utf-8")
    assert load_golden(p)[0].id == "q001"
    for bad in (dict(good, gold=[]), dict(good, type="unanswerable"), dict(good, type="nope"), dict(good, split="x"),
                dict(good, as_of="01/01/2026"), {k: v for k, v in good.items() if k != "answer"}):
        p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_golden(p)


_V1 = Path(__file__).parents[2] / "eval/golden/v1.jsonl"


@pytest.mark.skipif(not _V1.exists(), reason="golden set not generated yet")
def test_golden_valid():
    assert validate_set(load_golden(_V1)) == []
