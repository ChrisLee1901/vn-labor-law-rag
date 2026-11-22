import json

import pytest
from test_ingest import CORPUS, COUNT, TEXTS, count, fake_embed

from rag_pipelines import export_index, ingest
from rag_pipelines.eval.golden_schema import GoldItem
from rag_pipelines.eval.load_frozen import load_frozen
from rag_pipelines.eval.retrieval_eval import article_of, compute_metrics, gate, load_cache, run_async, run_modes, write_cache


def item(qid: str, question: str, gold: list[str]) -> GoldItem:
    return GoldItem(qid, question, "", gold, "single", "2026-11-22", "test", "")


def test_metrics_article_level():
    run = {"q1": ["A:D1:K1", "A:D1:K2", "B:D2"]}  # 2 chunk cùng Điều cha, đều đúng
    m = compute_metrics(run, {"q1": ["A:D1:K1", "A:D1:K2"]})
    assert m["hit_rate@1"] == 1 and m["recall@5"] == 1 and m["mrr@10"] == 1  # không đếm trùng -> recall không vượt 1


def test_appendix_gold_maps_to_parent():
    assert article_of("ND293-2025:PL1:M3") == "ND293-2025:PL1"
    assert article_of("ND293-2025:PL1:M3#2") == "ND293-2025:PL1"
    assert article_of("LBHXH-2024:D33:K1") == "LBHXH-2024:D33"
    m = compute_metrics({"q": ["ND293-2025:PL1:M9"]}, {"q": ["ND293-2025:PL1:M3"]})
    assert m["hit_rate@1"] == 1


def test_compare_fails_on_drop(capsys):
    base = {"hybrid": {"recall@10": 0.80, "mrr@10": 0.5}}
    assert gate({"hybrid": {"recall@10": 0.76, "mrr@10": 0.5}}, base, 0.03) == 1
    assert gate({"hybrid": {"recall@10": 0.78, "mrr@10": 0.5}}, base, 0.03) == 0
    assert gate({"fts": {}}, base, 0.03) == 0  # không chạy mode hybrid thì không có gì để so


def test_cache_miss_raises_clear_error(tmp_path):
    base = tmp_path / "query_emb_x"
    write_cache(base, ["q1"], [[0.1, 0.2]])
    assert load_cache(base, ["q1"])["q1"] == pytest.approx([0.1, 0.2])
    with pytest.raises(ValueError, match="chạy --refresh-cache khi Kaggle bật"):
        load_cache(base, ["q1", "q2"])
    with pytest.raises(ValueError, match="chạy --refresh-cache khi Kaggle bật"):
        load_cache(tmp_path / "none", ["q1"])


@pytest.fixture
def tiny(conn, db_url, tmp_path):
    """Index đóng băng nhỏ: ingest bằng embedder giả rồi export ra parquet; DB để trống sau đó."""
    ingest.run(conn, CORPUS, TEXTS, 2, fake_embed, COUNT)
    export_index.export(db_url, 2, tmp_path)
    before = {t: count(conn, t) for t in ("chunks", "articles", "legal_refs", "legal_docs")}
    conn.execute("truncate chunks, legal_refs, articles, legal_docs cascade")
    return tmp_path / "v2.parquet", before


def test_load_frozen_round_trip(conn, tiny):
    path, before = tiny
    assert load_frozen(path, conn) == 2
    assert {t: count(conn, t) for t in before} == before
    assert conn.execute("select value from app_config where key = 'active_index_version'").fetchone()[0] == 2
    assert conn.execute("select count(*) from chunks where fts_noaccent is null or embedding is null").fetchone()[0] == 0
    assert load_frozen(path, conn) == 2  # idempotent
    assert count(conn, "chunks") == before["chunks"]


def test_modes_on_tiny_index(conn, db_url, tiny):
    load_frozen(tiny[0], conn)
    it = item("q1", "Người sử dụng lao động có nghĩa vụ trả lương", ["ND145-2020:D2:K2"])
    cid, text = conn.execute("select id, embed_text from chunks where index_version = 2 and parent_id = 'LBHXH-2024:D1' order by id limit 1").fetchone()
    vec = fake_embed([text])[0]
    runs = run_async(run_modes(db_url, 2, [it], ["fts", "dense", "hybrid"], {"q1": vec}, None))
    assert runs["fts"]["q1"][0] == "ND145-2020:D2"
    assert runs["dense"]["q1"][0] == "LBHXH-2024:D1"  # truy vấn trùng embedding đoạn của Điều 1 luật
    assert len(runs["hybrid"]["q1"]) == len(set(runs["hybrid"]["q1"]))  # đã dedupe theo Điều cha


def test_cli_end_to_end(conn, db_url, tiny, tmp_path, monkeypatch):
    from rag_pipelines.eval import retrieval_eval as re_

    q = "Người sử dụng lao động có nghĩa vụ trả lương"
    golden = tmp_path / "g.jsonl"
    golden.write_text(json.dumps(dict(id="q1", question=q, answer="a", gold=["ND145-2020:D2:K2"], type="single", as_of="2026-11-22", split="test", source_quote="x")) + "\n", encoding="utf-8")
    write_cache(tmp_path / "cache", ["q1"], fake_embed([q]))
    monkeypatch.setattr(re_, "cache_base", lambda model: tmp_path / "cache")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    out, md = tmp_path / "r.json", tmp_path / "r.md"
    assert re_.main(["--index", str(tiny[0]), "--golden", str(golden), "--modes", "fts,dense,hybrid,hybrid_rerank", "--database-url", db_url,
                     "--out", str(out), "--markdown", str(md)]) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["n_queries"] == 1 and res["fts"]["hit_rate@1"] == 1 and "hybrid_rerank" not in res
    assert "| fts |" in md.read_text(encoding="utf-8")
