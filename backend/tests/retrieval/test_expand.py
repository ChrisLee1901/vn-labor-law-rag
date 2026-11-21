from datetime import date

import pytest
from app.retrieval.expand import expand

AS_OF = date(2026, 6, 1)


@pytest.fixture(scope="module", autouse=True)
def data(sync_conn):
    c = sync_conn
    c.execute("delete from chunks; delete from articles; delete from legal_refs; delete from legal_docs")
    c.execute(
        """insert into legal_docs(code, number, title, doc_type, effective_from, effective_to, status) values
           ('LBHXH-2024','41/2024/QH15','Luật BHXH','luat','2025-07-01',null,'con_hieu_luc'),
           ('LVL-2025','74/2025/QH15','Luật Việc làm','luat','2026-01-01',null,'con_hieu_luc'),
           ('ND158-2025','158/2025/NĐ-CP','NĐ BHXH','nghi_dinh','2025-07-01',null,'con_hieu_luc'),
           ('OLD-2000','1/2000/NĐ-CP','Cũ','nghi_dinh','2000-01-01','2010-01-01','het_hieu_luc')"""
    )
    for code, art, kind in [
        ("LBHXH-2024", 33, "dieu"),
        ("LVL-2025", 47, "dieu"),
        ("LVL-2025", 48, "dieu"),
        ("ND158-2025", 5, "dieu"),
        ("OLD-2000", 1, "dieu"),
        ("LVL-2025", 1, "phu_luc"),
    ]:
        c.execute(
            "insert into articles(index_version, id, doc_code, number, title, content, kind) values (1, %s, %s, %s, %s, %s, %s)",
            (f"{code}:D{art}" if kind == "dieu" else f"{code}:PL{art}", code, art, f"Điều {art}", f"nội dung {code} {art}", kind),
        )
    refs = [
        ("LBHXH-2024:D33:K1", "LVL-2025", 47, "cites"),
        ("LBHXH-2024:D33:K2", "LVL-2025", 47, "cites"),  # duplicate target
        ("LBHXH-2024:D33", "LVL-2025", 48, "cites"),
        ("LBHXH-2024:D33:K3", "OLD-2000", 1, "cites"),  # not effective
        ("LBHXH-2024:D33:K4", "LVL-2025", 99, "cites"),  # missing article
        ("ND158-2025:D5:K1", "LBHXH-2024", 33, "details"),  # decree details law article
    ]
    for src, dc, da, rel in refs:
        c.execute(
            "insert into legal_refs(index_version, src_id, dst_doc_code, dst_article, rel) values (1, %s, %s, %s, %s)",
            (src, dc, da, rel),
        )


async def test_expand_adds_ref_targets_once(aconn):
    out = await expand(["LBHXH-2024:D33"], aconn, 1, AS_OF)
    assert [d.id for d in out if d.via_ref and d.id == "LVL-2025:D47"] == ["LVL-2025:D47"]
    ids = [d.id for d in out]
    assert len(ids) == len(set(ids))
    assert "OLD-2000:D1" not in ids and "LVL-2025:D99" not in ids


async def test_expand_order_sids_reverse_details_and_cap(aconn):
    out = await expand(["LBHXH-2024:D33"], aconn, 1, AS_OF, max_extra=4)
    assert out[0].id == "LBHXH-2024:D33" and out[0].via_ref is False
    assert out[0].doc_number == "41/2024/QH15" and out[0].effective_to is None
    assert [d.sid for d in out] == [f"S{i}" for i in range(1, len(out) + 1)]
    assert {d.id for d in out[1:]} == {"LVL-2025:D47", "LVL-2025:D48", "ND158-2025:D5"}
    assert all(d.via_ref for d in out[1:])
    assert len(await expand(["LBHXH-2024:D33"], aconn, 1, AS_OF, max_extra=1)) == 2


async def test_expand_parent_not_duplicated_as_extra_and_appendix(aconn):
    out = await expand(["LVL-2025:D47", "LBHXH-2024:D33", "LVL-2025:PL1"], aconn, 1, AS_OF)
    assert [d.id for d in out[:3]] == ["LVL-2025:D47", "LBHXH-2024:D33", "LVL-2025:PL1"]
    assert len([d for d in out if d.id == "LVL-2025:D47"]) == 1
