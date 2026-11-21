import random

import pytest


def emb(seed: int) -> str:
    r = random.Random(seed)
    v = [r.uniform(-1, 1) for _ in range(1024)]
    n = sum(x * x for x in v) ** 0.5
    return "[" + ",".join(f"{x / n:.6f}" for x in v) + "]"


NOACCENT = "muc luong toi thieu vung I"
TEXT = "mức lương tối thiểu vùng I"
Q = "lương | tối | thiểu"
QN = "luong | toi | thieu"


@pytest.fixture(scope="module", autouse=True)
def data(conn):
    conn.execute(
        """insert into legal_docs(code, number, title, doc_type, issuer, issued_on, effective_from, effective_to, status)
           values ('ND293-2025','293/2025/NĐ-CP','Lương tối thiểu','nghi_dinh','CP','2025-10-01','2026-01-01','2027-01-01','het_hieu_luc'),
                  ('ND399-2026','399/2026/NĐ-CP','Lương tối thiểu','nghi_dinh','CP','2026-10-01','2027-01-01',null,'con_hieu_luc')"""
    )
    for i, code in enumerate(["ND293-2025", "ND399-2026"]):
        conn.execute(
            """insert into chunks(index_version, id, parent_id, doc_code, article, content, embed_text, n_tokens, embedding, fts_noaccent)
               values (1, %s, %s, %s, 3, %s, %s, 10, %s::halfvec, to_tsvector('simple', %s))""",
            (f"{code}:D3:K1", f"{code}:D3", code, TEXT, TEXT, emb(i), NOACCENT),
        )


def ids(conn, as_of, qe, q=Q, qn=QN):
    rows = conn.execute(
        "select id, parent_id, score from hybrid_search(%s, %s, %s::halfvec, 1, %s::date)",
        (q, qn, qe, as_of),
    ).fetchall()
    return [r[0] for r in rows]


def test_hybrid_search_as_of_filters_effective_docs(conn):
    assert ids(conn, "2026-06-01", emb(0)) == ["ND293-2025:D3:K1"]
    assert ids(conn, "2027-02-01", emb(0)) == ["ND399-2026:D3:K1"]


def test_hybrid_search_fts_only_when_embedding_null(conn):
    assert ids(conn, "2026-06-01", None) == ["ND293-2025:D3:K1"]


def test_fts_noaccent_matches_unaccented_query(conn):
    assert ids(conn, "2026-06-01", None, q="", qn="luong & toi & thieu") == ["ND293-2025:D3:K1"]
