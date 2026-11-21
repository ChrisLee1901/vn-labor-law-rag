import json

from rag_pipelines.eval.golden_schema import QUOTA
from rag_pipelines.eval.select_golden import main, select

IDS = {"X:D1", "X:D2"}
NL = chr(10)
NO_GOLD = {"unanswerable", "out_of_domain", "injection"}


def cand(t, i, **over):
    c = dict(question=f"hoi {t} {i}", answer="a", gold=[] if t in NO_GOLD else ["X:D1"], type=t, as_of="2026-01-01", source_quote="khac hoan toan")
    return {**c, **over}


def ver(i, c, **over):
    return {"cand_index": i, "answer": "a", "gold": c["gold"], "answerable": c["type"] not in NO_GOLD, **over}


def build(extra=3):
    cands = [cand(t, i) for t, q in QUOTA.items() for i in range(q + extra)]
    return cands, [ver(i, c) for i, c in enumerate(cands)]


def test_select_full_quota_split_and_determinism():
    cands, vers = build()
    items, stats, short = select(cands, vers, IDS)
    assert short == {} and len(items) == 120
    assert [i.id for i in items][:2] == ["q001", "q002"]
    assert sum(i.split == "dev" for i in items) == 40
    assert {t: sum(i.type == t for i in items) for t in QUOTA} == QUOTA
    assert [i.__dict__ for i in select(cands, vers, IDS)[0]] == [i.__dict__ for i in items]


def test_select_rejection_rules():
    cands, vers = build()
    cands[0]["gold"] = ["X:D404"]; vers[0]["gold"] = ["X:D404"]       # invalid gold
    vers[1]["gold"] = ["X:D2"]                                         # no intersection
    vers[2]["answerable"] = False                                      # verifier says unanswerable
    cands[3]["source_quote"] = cands[3]["question"]                    # copied
    u = next(i for i, c in enumerate(cands) if c["type"] == "unanswerable")
    vers[u]["answerable"] = True                                       # verifier answered an unanswerable
    del vers[4]                                                        # no verification
    _, stats, _ = select(cands, vers, IDS)
    s = stats["single"]
    assert s["invalid_gold"] == 1 and s["no_gold_overlap"] == 1 and s["not_answerable"] == 1
    assert s["copy"] == 1 and s["no_verification"] == 1
    assert stats["unanswerable"]["answerable_but_should_not"] == 1


def test_shortfall_and_cli_exit(tmp_path):
    cands, vers = build(extra=0)
    vers[0]["answerable"] = False  # a single candidate fails -> single short by 1
    _, _, short = select(cands, vers, IDS)
    assert short == {"single": 1}
    d = tmp_path
    (d / "c.jsonl").write_text("\n".join(json.dumps(c) for c in cands), encoding="utf-8")
    (d / "v.jsonl").write_text("\n".join(json.dumps(v) for v in vers), encoding="utf-8")
    rc = main(["--candidates", str(d / "c.jsonl"), "--verification", str(d / "v.jsonl"), "--out", str(d / "v1.jsonl"),
               "--sample", str(d / "s.csv"), "--stats", str(d / "stats.json")], ids=IDS)
    assert rc != 0 and (d / "stats.json").exists() and not (d / "v1.jsonl").exists()


def test_nfc_and_duplicate_questions():
    import unicodedata
    cands, vers = build()
    nfd = unicodedata.normalize("NFD", "Hợp đồng lao động")
    cands[0]["question"] = nfd
    cands[1]["question"] = "  " + unicodedata.normalize("NFC", nfd)  # same question after NFC/strip
    items, stats, _ = select(cands, vers, IDS)
    assert stats["single"]["duplicate"] == 1
    assert all(unicodedata.is_normalized("NFC", i.question) for i in items)
    assert sum(i.question == "Hợp đồng lao động" for i in items) == 1


def test_cli_refuses_to_write_invalid_set(tmp_path, monkeypatch):
    cands, vers = build()
    d = tmp_path
    (d / "c.jsonl").write_text(NL.join(json.dumps(c) for c in cands), encoding="utf-8")
    (d / "v.jsonl").write_text(NL.join(json.dumps(v) for v in vers), encoding="utf-8")
    args = ["--candidates", str(d / "c.jsonl"), "--verification", str(d / "v.jsonl"), "--out", str(d / "v1.jsonl"),
            "--sample", str(d / "s.csv"), "--stats", str(d / "stats.json")]
    assert main(args, ids=IDS) == 0 and (d / "v1.jsonl").exists()  # valid set is written
    (d / "v1.jsonl").unlink()
    monkeypatch.setattr("rag_pipelines.eval.select_golden.validate_set", lambda items, ids=None: ["boom"])
    assert main(args, ids=IDS) != 0 and not (d / "v1.jsonl").exists()
