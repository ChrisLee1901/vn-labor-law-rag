import re

from rag_pipelines.eval.dump_corpus import dump
from rag_pipelines.eval.golden_schema import valid_ids


def test_dump_ids_format(tmp_path):
    dump(tmp_path, codes=["ND293-2025"])
    md = (tmp_path / "ND293-2025.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (ND293-2025:D\d+\w?) — Điều \d+\w?\. ", md, re.M)
    assert heads and "ND293-2025:D1" in heads
    assert re.search(r"^\[ND293-2025:D\d+:K1\] ", md, re.M)
    assert re.search(r"^\[ND293-2025:PL1:M1\] ", md, re.M)
    ids = set(re.findall(r"^\[([^\]]+)\]", md, re.M)) | set(heads)
    assert ids <= valid_ids() and (tmp_path / "refs_pairs.md").exists()


def test_refs_pairs_format(tmp_path):
    dump(tmp_path)
    lines = (tmp_path / "refs_pairs.md").read_text(encoding="utf-8").splitlines()
    pairs = [ln for ln in lines if "->" in ln]
    assert pairs
    ids = valid_ids()
    for ln in pairs:
        m = re.fullmatch(r"(\S+) -> (\S+) \((cites|details|amends)\)", ln)
        assert m and m[1].split(":")[0] != m[2].split(":")[0] and m[2] in ids
