import re
from pathlib import Path

import yaml

from rag_pipelines.chunk import appendix_chunks_for, chunk_appendices
from rag_pipelines.extract import extract_text
from rag_pipelines.structure import parse_appendices

DOCS = {d["code"]: d for d in yaml.safe_load((Path(__file__).parents[2] / "docs/corpus/legal_docs.yaml").read_text(encoding="utf-8"))["docs"]}
count = lambda s: len(s.split())  # noqa: E731
SYN = "Điều 1. X\nA\nTM. CHÍNH PHỦ\nPhụ lục\nDANH MỤC\n(Kèm theo Nghị định)\n1. Tỉnh A\n- Vùng I, gồm a,\nb.\n-\nVùng II, còn lại.\n2. Tỉnh B\n- Vùng IV, c."


def test_nd293_appendix_parsed():
    (ap,) = parse_appendices(extract_text("ND293-2025"), "ND293-2025")
    assert ap.number == 1 and len(ap.items) == 34
    assert [i[0] for i in ap.items] == list(range(1, 35))
    n, heading, text = ap.items[0]
    assert heading == "Thành phố Hà Nội" and "Vùng I" in text and "Hoàn Kiếm" in text
    assert ap.items[-1][1] == "Tỉnh Cà Mau"


def test_synthetic_wrap_and_lone_dash():
    (ap,) = parse_appendices(SYN, "X")
    assert ap.title == "DANH MỤC (Kèm theo Nghị định)"
    assert ap.items == [(1, "Tỉnh A", "- Vùng I, gồm a, b.\n- Vùng II, còn lại."), (2, "Tỉnh B", "- Vùng IV, c.")]


def test_appendix_chunks_ids_and_limit():
    doc = DOCS["ND293-2025"]
    ch = appendix_chunks_for(doc, extract_text("ND293-2025"), count)
    assert len(ch) >= 34
    ids = [c.id for c in ch]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"ND293-2025:PL1:M\d+(#\d+)?", i) for i in ids)
    assert all(c.n_tokens <= 450 and c.n_tokens == count(c.embed_text) for c in ch)
    assert {c.parent_id for c in ch} == {"ND293-2025:PL1"}
    assert ch[0].embed_text.startswith("[293/2025/NĐ-CP – Mức lương tối thiểu] Phụ lục 1. DANH MỤC")
    assert ch[0].embed_text.split("\n")[0].endswith("| Thành phố Hà Nội:")


def test_oversized_item_split_keeps_vung_label():
    (ap,) = parse_appendices(SYN.replace("a,", " ".join(f"w{i}," for i in range(40))), "X")
    ch = chunk_appendices([ap], {"number": "n", "short_title": "t"}, count, max_tokens=30)
    first = [c for c in ch if c.id.startswith("X:PL1:M1")]
    assert len(first) > 2 and all(re.fullmatch(r"X:PL1:M1#\d+", c.id) for c in first)
    assert all(c.n_tokens <= 30 for c in ch)
    assert all(re.match(r"- Vùng (I|II)\b", c.content) for c in first)


def test_doc_without_keep_appendix_yields_nothing():
    assert "keep_appendix" not in DOCS["ND145-2020"]
    assert appendix_chunks_for(DOCS["ND145-2020"], extract_text("ND145-2020"), count) == []
