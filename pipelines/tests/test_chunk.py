from pathlib import Path

import pytest
import yaml

from rag_pipelines.chunk import chunk_articles, default_count_tokens
from rag_pipelines.extract import extract_text
from rag_pipelines.structure import Article, Clause, Point, parse_document

from app.legal.ids import make_id

CODES = [
    "BLLD",
    "ND145-2020",
    "ND293-2025",
    "ND399-2026",
    "LBHXH-2024",
    "ND158-2025",
    "LVL-2025",
    "ND374-2025",
]
DOCS = {
    d["code"]: d
    for d in yaml.safe_load(
        (Path(__file__).parents[2] / "docs/corpus/legal_docs.yaml").read_text(
            encoding="utf-8"
        )
    )["docs"]
}
count = lambda s: len(s.split())  # noqa: E731


@pytest.fixture(scope="module")
def chunked():
    out = {}
    for c in CODES:
        arts = parse_document(extract_text(c), c)
        out[c] = (arts, chunk_articles(arts, DOCS[c], count))
    return out


def test_breadcrumb_format(chunked):
    ch = next(c for c in chunked["ND145-2020"][1] if c.article == 15 and c.clause == 2)
    assert ch.embed_text.startswith("[145/2020/NĐ-CP – ")
    assert "Điều 15." in ch.embed_text and "| Khoản 2:" in ch.embed_text
    assert ch.embed_text == ch.embed_text.split("\n")[0] + "\n" + ch.content


def test_no_chunk_exceeds_max(chunked):
    for chunks in (c for _, c in chunked.values()):
        assert all(
            c.n_tokens <= 450 and c.n_tokens == count(c.embed_text) for c in chunks
        )


def test_every_article_has_parent_and_children(chunked):
    for code, (arts, chunks) in chunked.items():
        assert {c.parent_id for c in chunks} == {
            make_id(code, a.number, suffix=a.suffix) for a in arts
        }


def test_chunk_ids_unique(chunked):
    for chunks in (c for _, c in chunked.values()):
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))


def test_splitting_by_point_then_sentence():
    doc = {"number": "1/X", "short_title": "T"}
    long_pt = " ".join(f"Câu số {i} dài thêm chút." for i in range(30))  # 150 từ
    art = Article(
        "X",
        3,
        None,
        "Tiêu đề",
        None,
        None,
        "Lời dẫn.",
        [
            Clause(1, "Dẫn khoản một:", [Point("a", "ngắn"), Point("b", long_pt)]),
            Clause(2, long_pt, []),
            Clause(3, "ngắn", [Point("a", "x")]),
        ],
    )
    chunks = chunk_articles([art], doc, count, max_tokens=60)
    ids = [c.id for c in chunks]
    assert (
        ids[0] == "X:D3"
        and chunks[0].content == "Lời dẫn."
        and "Khoản" not in chunks[0].embed_text
    )
    assert (
        "X:D3:K1:a" in ids
        and "X:D3:K1:b#1" in ids
        and "X:D3:K2#1" in ids
        and "X:D3:K3" in ids
    )
    assert len(ids) == len(set(ids)) and all(
        c.n_tokens <= 60 and c.parent_id == "X:D3" for c in chunks
    )
    assert (
        next(c for c in chunks if c.id == "X:D3:K1:a").content
        == "Dẫn khoản một:\na) ngắn"
    )


def test_default_count_tokens_real():
    try:
        f = default_count_tokens()
    except Exception as e:  # mạng/HF không tải được
        pytest.skip(f"HF tokenizer unavailable: {e}")
    n = f("Mức lương tối thiểu vùng I")
    assert isinstance(n, int) and n > 0
