import hashlib
import random
from datetime import date

import psycopg
import pytest
from app.llm.gateway import LLMOffline

from rag_pipelines import ingest

COUNT = lambda s: len(s.split())  # noqa: E731


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic L2-normalized 1024-d vectors."""
    out = []
    for t in texts:
        rng = random.Random(hashlib.sha256(t.encode()).digest())
        v = [rng.gauss(0, 1) for _ in range(1024)]
        n = sum(x * x for x in v) ** 0.5
        out.append([x / n for x in v])
    return out


def doc(code: str, doc_type: str = "nghi_dinh", **kw) -> dict:
    return dict(code=code, number=f"{code}/n", short_title="Tên ngắn", title="Tiêu đề", doc_type=doc_type, issuer="Chính phủ",
                issued_on=date(2020, 1, 1), effective_from=date(2021, 1, 1), effective_to=None, status="con_hieu_luc",
                replaced_by=None, amends=[], source_url="http://x", page="p", files=["f"], **kw)


ND145 = """Điều 1. Phạm vi
Nghị định này quy định chi tiết khoản 1 Điều 2 của Bộ luật Lao động.
Điều 2. Giải thích
1. Người lao động làm việc theo hợp đồng.
a) Làm việc đủ giờ;
b) Hưởng lương đủ tháng.
2. Người sử dụng lao động có nghĩa vụ trả lương.
Điều 3. Thi hành
Các Điều 1 và 2 của Nghị định này có hiệu lực kể từ ngày ký.
"""
LUAT = """Điều 1. Quy định chung
1. Luật này áp dụng cho mọi người.
Điều 2. Hướng dẫn
Quy định chi tiết Điều 1 của Luật này, theo Điều 1 Luật Bảo hiểm y tế.
"""
CORPUS = [doc("ND145-2020"), doc("LBHXH-2024", "luat")]
TEXTS = {"ND145-2020": ND145, "LBHXH-2024": LUAT}


def count(conn, table: str, v: int | None = None) -> int:
    q = f"select count(*) from {table}" + (f" where index_version = {v}" if v else "")
    return conn.execute(q).fetchone()[0]


def run(conn, version: int, docs=CORPUS, texts=TEXTS, **kw):
    return ingest.run(conn, docs, texts, version, fake_embed, COUNT, **kw)


def test_ingest_idempotent(conn):
    run(conn, 2)
    n = (count(conn, "chunks", 2), count(conn, "articles", 2), count(conn, "legal_refs", 2))
    assert n[0] > 0
    run(conn, 2)
    assert (count(conn, "chunks", 2), count(conn, "articles", 2), count(conn, "legal_refs", 2)) == n
    assert count(conn, "legal_docs") == 2


def test_ingest_does_not_switch_active_version(conn):
    run(conn, 2)
    assert conn.execute("select value from app_config where key = 'active_index_version'").fetchone()[0] == 1


def test_refs_resolved_to_existing_articles(conn, capsys):
    stats = run(conn, 2)
    rows = conn.execute(
        """select r.dst_doc_code, r.dst_article from legal_refs r
           where r.index_version = 2 and r.dst_doc_code in ('BLLD','ND145-2020','ND293-2025','ND399-2026','LBHXH-2024','ND158-2025','LVL-2025','ND374-2025')
             and not exists (select 1 from articles a where a.index_version = 2 and a.doc_code = r.dst_doc_code and a.number = r.dst_article)"""
    ).fetchall()
    assert rows == []
    assert stats["unresolved"] >= 1  # ND145 Điều 1 -> "Bộ luật Lao động" (BLLD not in this run)
    assert "unresolved" in capsys.readouterr().out


def test_refuses_active_version_without_force(conn):
    with pytest.raises(ingest.ActiveVersionError):
        run(conn, 1)
    assert count(conn, "chunks") == 0
    run(conn, 1, force=True)
    assert count(conn, "chunks", 1) > 0


def test_appendix_rows_are_phu_luc(conn):
    d = doc("ND293-2025", keep_appendix=True)
    text = ND145 + "Phụ lục I\nDANH MỤC ĐỊA BÀN\n1. Vùng theo địa bàn\n- Vùng I: Hà Nội, Hồ Chí Minh\n"
    run(conn, 2, [d], {"ND293-2025": text})
    kinds = dict(conn.execute("select id, kind from articles where index_version = 2").fetchall())
    assert kinds["ND293-2025:PL1"] == "phu_luc" and kinds["ND293-2025:D1"] == "dieu"
    row = conn.execute("select number, title from articles where id = 'ND293-2025:PL1'").fetchone()
    assert row == (1, "DANH MỤC ĐỊA BÀN")
    assert conn.execute("select parent_id, article, clause from chunks where id = 'ND293-2025:PL1:M1'").fetchone() == ("ND293-2025:PL1", 1, 1)


def test_fts_noaccent_and_embedding_stored(conn):
    run(conn, 2)
    assert conn.execute("select count(*) from chunks where fts_noaccent @@ to_tsquery('simple', 'nguoi & lao & dong')").fetchone()[0] > 0
    assert conn.execute("select count(*) from chunks where embedding is null").fetchone()[0] == 0


def _parsed(code, text, doc_type="nghi_dinh"):
    return ingest.parse(doc(code, doc_type), text, COUNT)


def _refs(*parsed):
    return ingest.collect_refs(list(parsed))


def test_rule_a_drops_refs_without_article():
    p = _parsed("ND145-2020", "Điều 1. A\nTheo Luật Việc làm và Nghị định số 158/2025/NĐ-CP.\n")
    rows, stats = _refs(p)
    assert rows == [] and stats["unresolved"] == 0


def test_rule_b_drops_implicit_doc_in_nghi_dinh_and_amends():
    nd = _parsed("ND145-2020", "Điều 1. A\nTheo quy định tại Điều 2.\nĐiều 2. B\nNội dung.\n")
    assert _refs(nd)[0] == []  # bare "Điều 2" in nghi_dinh
    luat = _parsed("LBHXH-2024", "Điều 1. A\nTheo Điều 2.\nSửa đổi, bổ sung Điều 2.\nĐiều 2. B\nNội dung.\n", "luat")
    rows, _ = _refs(luat)
    assert [(r["rel"], r["dst_article"]) for r in rows] == [("cites", 2)]  # implicit cites kept, implicit amends dropped


def test_rule_c_unresolved_dropped_external_kept():
    p = _parsed("ND145-2020", "Điều 1. A\nTheo Điều 99 Nghị định này và Điều 3 Luật Bảo hiểm y tế, Điều 2 Nghị định này.\nĐiều 2. B\nNội dung.\n")
    rows, stats = _refs(p)
    assert sorted((r["dst_doc_code"], r["dst_article"]) for r in rows if r["dst_doc_code"]) == [("ND145-2020", 2)]
    assert [r["dst_article"] for r in rows if r["dst_doc_code"] is None] == [3]
    assert stats["unresolved"] == 1


def test_src_id_is_most_specific():
    p = _parsed("ND145-2020", "Điều 1. A\nXem Điều 2 Nghị định này.\n1. Theo Điều 2 Nghị định này.\na) theo Điều 2 Nghị định này;\nĐiều 2. B\nNội dung.\n")
    rows, _ = _refs(p)
    assert sorted(r["src_id"] for r in rows) == ["ND145-2020:D1", "ND145-2020:D1:K1", "ND145-2020:D1:K1:a"]


def test_dry_run_touches_no_db(capsys):
    stats = ingest.dry_run(CORPUS, TEXTS, COUNT)
    assert stats["ND145-2020"]["chunks"] > 0
    assert "ND145-2020" in capsys.readouterr().out


def test_export_roundtrip(conn, tmp_path, db_url):
    import pyarrow.parquet as pq

    from rag_pipelines import export_index

    run(conn, 2)
    export_index.export(db_url, 2, tmp_path)
    t = pq.read_table(tmp_path / "v2.parquet").to_pylist()
    db = {r[0]: r[1] for r in conn.execute("select id, embedding::text from chunks where index_version = 2")}
    assert {r["id"] for r in t} == set(db)
    assert list(t[0]) == ["id", "parent_id", "doc_code", "article", "clause", "point", "embed_text", "content", "embedding"]
    for r in t:
        want = [float(x) for x in db[r["id"]].strip("[]").split(",")]
        assert len(r["embedding"]) == 1024
        assert max(abs(float(a) - b) for a, b in zip(r["embedding"], want)) < 1e-3
    assert len(pq.read_table(tmp_path / "v2.articles.parquet")) == count(conn, "articles", 2)
    assert len(pq.read_table(tmp_path / "v2.legal_docs.parquet")) == 2
    assert len(pq.read_table(tmp_path / "v2.legal_refs.parquet")) == count(conn, "legal_refs", 2)


# ---- safety: nothing partial is ever written -------------------------------------------------------------------------


def snapshot(conn, v: int):
    return [conn.execute(q, (v,)).fetchall() for q in (
        "select id, embed_text, embedding::text, fts_noaccent::text from chunks where index_version = %s order by id",
        "select id, content, kind from articles where index_version = %s order by id",
        "select src_id, dst_doc_code, dst_article, rel from legal_refs where index_version = %s order by 1, 2, 3, 4",
    )]


def boom(texts):
    raise RuntimeError("embedder down")


def test_embed_failure_leaves_existing_rows_unchanged(conn):
    run(conn, 2)
    before = snapshot(conn, 2)
    with pytest.raises(RuntimeError):
        ingest.run(conn, CORPUS, TEXTS, 2, boom, COUNT)
    assert snapshot(conn, 2) == before


def test_embed_failure_on_new_version_writes_nothing(conn):
    with pytest.raises(RuntimeError):
        ingest.run(conn, CORPUS, TEXTS, 3, boom, COUNT)
    assert (count(conn, "chunks"), count(conn, "articles"), count(conn, "legal_refs"), count(conn, "legal_docs")) == (0, 0, 0, 0)


def test_mid_transaction_failure_rolls_back(conn, monkeypatch):
    run(conn, 2)
    before = snapshot(conn, 2)
    # articles are already inserted (and the old rows deleted) when chunk params are built -> _vec raises mid-transaction
    monkeypatch.setattr(ingest, "_vec", lambda v: (_ for _ in ()).throw(RuntimeError("bad row")))
    with pytest.raises(RuntimeError, match="bad row"):
        run(conn, 2)
    assert snapshot(conn, 2) == before


def test_db_constraint_failure_rolls_back(conn):
    run(conn, 2)
    before = snapshot(conn, 2)
    bad = [CORPUS[0] | {"replaced_by": "NOPE"}, CORPUS[1]]  # FK violation after the deletes
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        run(conn, 2, bad)
    assert snapshot(conn, 2) == before


def test_active_version_flipped_during_embedding_is_caught(conn):
    def flip(texts):
        conn.execute("update app_config set value = '2' where key = 'active_index_version'")
        return fake_embed(texts)

    with pytest.raises(ingest.ActiveVersionError):
        ingest.run(conn, CORPUS, TEXTS, 2, flip, COUNT)
    assert count(conn, "chunks") == 0 and count(conn, "legal_docs") == 0


def test_missing_active_row_fails_closed(conn):
    conn.execute("delete from app_config where key = 'active_index_version'")
    with pytest.raises(ingest.ActiveVersionError):
        run(conn, 2)
    assert count(conn, "chunks") == 0
    run(conn, 2, force=True)
    assert count(conn, "chunks", 2) > 0


# ---- embed retry ------------------------------------------------------------------------------------------------------


def test_embed_retries_then_succeeds(monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr(ingest, "_sleep", sleeps.append)

    def flaky(texts):
        calls.append(1)
        if len(calls) < 3:
            raise LLMOffline("ngrok hiccup")
        return fake_embed(texts)

    assert len(ingest.embed_all(["a", "b"], flaky)) == 2
    assert sleeps == [1, 2] and len(calls) == 3


def test_embed_gives_up_after_three_attempts(monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr(ingest, "_sleep", sleeps.append)

    def down(texts):
        calls.append(1)
        raise LLMOffline("down")

    with pytest.raises(LLMOffline):
        ingest.embed_all(["a"], down)
    assert len(calls) == 3 and sleeps == [1, 2]


def test_export_missing_version_raises(conn, tmp_path, db_url):
    from rag_pipelines import export_index

    with pytest.raises(ValueError, match="no chunks"):
        export_index.export(db_url, 9, tmp_path)
    assert not (tmp_path / "v9.parquet").exists()
