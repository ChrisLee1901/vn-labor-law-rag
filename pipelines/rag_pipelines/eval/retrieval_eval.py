"""Eval truy xuất (ranx, cấp Điều) trên index đóng băng + embedding câu hỏi đã cache.

Chạy: python -m rag_pipelines.eval.retrieval_eval --index eval/index/v1.parquet --golden eval/golden/v1.jsonl
        --modes fts,dense,hybrid[,hybrid_rerank] --split test --out eval/results/retrieval_v1.json [--markdown out.md]
        [--compare eval/baselines/main.json --max-drop 0.03] [--refresh-cache]

- Nạp index vào Postgres local (`--database-url`, mặc định rag-pg của scripts/test-db.sh) rồi gọi đúng đường đi của backend:
  fts = `_hybrid` không vector (nhánh offline của API), hybrid = `_hybrid` + vector đã cache, dense = hybrid_search chỉ nhánh vector,
  hybrid_rerank = `retrieve(online=True)` qua Gateway sống (cần LLM_BASE_URL + LLM_API_KEY, ngược lại bỏ qua mode).
- Mỗi mode: xếp Điều cha theo đoạn tốt nhất (dedupe), giữ 20 Điều; gold và kết quả đều quy về cấp Điều (`<code>:D<n>` / `<code>:PL<n>`).
- Chỉ tính các câu có gold. `--compare`: exit 1 nếu recall@10 hoặc mrr@10 của mode `hybrid` giảm quá `--max-drop` (tuyệt đối).
- Cache: eval/cache/query_emb_<model>.npy + .ids.json; thiếu id -> báo "chạy --refresh-cache khi Kaggle bật".
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import psycopg
from app.legal.normalize import strip_diacritics
from app.llm.gateway import Gateway, LLMOffline
from app.retrieval.search import CANDIDATES, _by_rrf, _hybrid, retrieve
from app.retrieval.tsquery import build_tsquery
from psycopg import AsyncConnection
from ranx import Qrels, Run, evaluate

from rag_pipelines.eval.golden_schema import GoldItem, load_golden
from rag_pipelines.eval.load_frozen import ensure_local, load_frozen
from rag_pipelines.ingest import GatewayEmbed, embed_all

ROOT = Path(__file__).resolve().parents[3]
METRICS = ["hit_rate@1", "recall@5", "recall@10", "recall@20", "mrr@10", "ndcg@10"]
GATED = ("recall@10", "mrr@10")
MODES = ("fts", "dense", "hybrid", "hybrid_rerank")
TOP = 20
DEFAULT_DB = "postgresql://postgres:postgres@localhost:54329/postgres"
DEFAULT_MODEL = "AITeamVN/Vietnamese_Embedding"
MISS = "chạy --refresh-cache khi Kaggle bật"


def article_of(i: str) -> str:
    """`LBHXH-2024:D33:K1` -> `LBHXH-2024:D33`; `ND293-2025:PL1:M3#2` -> `ND293-2025:PL1`."""
    return ":".join(i.split(":")[:2])


def _dedupe(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(article_of(i) for i in ids))


def compute_metrics(
    run: dict[str, list[str]], gold: dict[str, list[str]]
) -> dict[str, float]:
    qrels = Qrels.from_dict({q: {a: 1 for a in _dedupe(g)} for q, g in gold.items()})
    ranked = {
        q: _dedupe(run.get(q, []))[:TOP] or ["__none__"] for q in gold
    }  # ranx cần mỗi query có ít nhất 1 tài liệu
    r = Run.from_dict(
        {
            q: {a: float(len(ids) - n) for n, a in enumerate(ids)}
            for q, ids in ranked.items()
        }
    )
    return {
        k: float(v)
        for k, v in evaluate(qrels, r, METRICS, make_comparable=False).items()
    }


def gate(current: dict, baseline: dict, max_drop: float) -> int:
    """0 = đạt. Fail khi không so sánh được (thiếu hybrid, khác split/n_queries) hoặc recall@10 / mrr@10 của hybrid giảm quá ngưỡng."""
    bad = [
        f"cannot compare: `{k}` is {baseline.get(k)!r} in baseline vs {current.get(k)!r} now (regenerate the baseline)"
        for k in ("split", "n_queries")
        if baseline.get(k) != current.get(k)
    ]
    bad += [
        f"cannot compare: mode `hybrid` missing in {name}"
        for name, r in (("current run", current), ("baseline", baseline))
        if "hybrid" not in r
    ]
    if not bad:
        bad = [
            f"hybrid {m}: {baseline['hybrid'][m]:.4f} -> {current['hybrid'][m]:.4f} (max drop {max_drop})"
            for m in GATED
            if baseline["hybrid"][m] - current["hybrid"][m] > max_drop + 1e-9
        ]
    for b in bad:
        print(f"REGRESSION: {b}", file=sys.stderr)
    return 1 if bad else 0


def markdown(res: dict) -> str:
    modes = [m for m in MODES if m in res]
    lines = [
        f"Index `{res['index']}`, split `{res['split']}`, n={res['n_queries']}",
        "",
        "| mode | " + " | ".join(METRICS) + " |",
        "|---|" + "---|" * len(METRICS),
    ]
    lines += [
        f"| {m} | " + " | ".join(f"{res[m][k]:.3f}" for k in METRICS) + " |"
        for m in modes
    ]
    if "hybrid_rerank" in modes:
        lines += [
            "",
            "hybrid_rerank trả tối đa 6 Điều cha (đúng như API), nên recall@10/20 của dòng này xấp xỉ recall@6, không so trực tiếp với các mode khác.",
        ]
    return "\n".join(lines) + "\n"


# ---- cache embedding câu hỏi ----


def cache_base(model: str) -> Path:
    return ROOT / "eval/cache" / f"query_emb_{model.replace('/', '-')}"


def _sha(q: str) -> str:
    return hashlib.sha1(q.encode("utf-8")).hexdigest()


def write_cache(
    base: Path, items: list[GoldItem], vecs: list[list[float]], model: str
) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    np.save(base.with_suffix(".npy"), np.asarray(vecs, dtype=np.float32))
    meta = {
        "model": model,
        "ids": [g.id for g in items],
        "sha1": [_sha(g.question) for g in items],
    }
    base.with_suffix(".ids.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )


def load_cache(base: Path, items: list[GoldItem], model: str) -> dict[str, list[float]]:
    """Mỗi câu phải có trong cache với đúng nội dung (sha1) và đúng model, nếu không -> báo refresh."""
    npy, idf = base.with_suffix(".npy"), base.with_suffix(".ids.json")
    if not (npy.exists() and idf.exists()):
        raise ValueError(f"không có cache embedding câu hỏi ({npy.name}): {MISS}")
    meta = json.loads(idf.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or meta.get("model") != model:
        raise ValueError(f"cache không khớp model {model}: {MISS}")
    row = {i: n for n, i in enumerate(meta["ids"])}
    if bad := [
        g.id
        for g in items
        if g.id not in row or meta["sha1"][row[g.id]] != _sha(g.question)
    ]:
        raise ValueError(f"cache thiếu hoặc lỗi thời cho {bad[:5]}: {MISS}")
    m = np.load(npy)
    return {g.id: m[row[g.id]].tolist() for g in items}


# ---- truy xuất ----


def run_async(coro):
    """psycopg async cần selector loop (Windows mặc định là Proactor)."""
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as r:
        return r.run(coro)


class GatewayLost(RuntimeError):
    """Gateway sập giữa lúc eval hybrid_rerank (`retrieve` sẽ lặng lẽ rơi về FTS nên phải dừng thay vì ghi số sai)."""


class StrictGateway(Gateway):
    async def _post(self, path: str, body: dict) -> dict:
        try:
            return await super()._post(path, body)
        except LLMOffline as e:
            raise GatewayLost(f"gateway offline during hybrid_rerank eval: {e}") from e


async def _dense(
    conn, question: str, as_of: date, version: int, vec: list[float]
) -> list[tuple[str, str, float]]:
    qe = "[" + ",".join(map(str, vec)) + "]"
    cur = await conn.execute(
        "select id, parent_id, score from hybrid_search(%s::text, %s::text, %s::halfvec, %s, %s::date, %s, 0, 1)",
        (
            build_tsquery(question),
            build_tsquery(strip_diacritics(question)),
            qe,
            version,
            as_of,
            CANDIDATES,
        ),
    )
    return await cur.fetchall()


async def search(
    conn,
    it: GoldItem,
    mode: str,
    vec: list[float] | None,
    gw: Gateway | None,
    version: int,
) -> list[str]:
    as_of = date.fromisoformat(it.as_of)
    if mode == "hybrid_rerank":
        return [
            c.parent_id
            for c in await retrieve(it.question, as_of, gw, conn, version, online=True)
        ]
    rows = await (
        _dense(conn, it.question, as_of, version, vec)
        if mode == "dense"
        else _hybrid(
            conn, it.question, as_of, version, vec if mode == "hybrid" else None
        )
    )
    return [c.parent_id for c in _by_rrf(rows)]


async def run_modes(
    db_url: str,
    version: int,
    items: list[GoldItem],
    modes: list[str],
    vecs: dict[str, list[float]],
    gw: Gateway | None,
) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {m: {} for m in modes}
    async with await AsyncConnection.connect(db_url, autocommit=True) as conn:
        for m in modes:
            for it in items:
                out[m][it.id] = await search(conn, it, m, vecs.get(it.id), gw, version)
    return out


async def _ready(gw: Gateway) -> bool:
    try:
        return await gw.health()
    finally:
        await (
            gw.aclose()
        )  # client gắn với loop này; run_modes sẽ tạo lại trong loop của nó


def refresh_cache(golden: list[GoldItem], model: str) -> None:
    emb = GatewayEmbed()
    try:
        vecs = embed_all([g.question for g in golden], emb)  # batch 32 + retry
    finally:
        emb.close()
    write_cache(cache_base(model), golden, vecs, model)
    print(
        f"cache: {len(golden)} câu -> {cache_base(model).with_suffix('.npy')}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--golden", type=Path, default=ROOT / "eval/golden/v1.jsonl")
    ap.add_argument("--modes", default="fts,dense,hybrid")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="test")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--max-drop", type=float, default=0.03)
    ap.add_argument("--refresh-cache", action="store_true")
    ap.add_argument("--embed-model", default=DEFAULT_MODEL)
    ap.add_argument("--database-url", default=DEFAULT_DB)
    ap.add_argument("--allow-remote", action="store_true")
    a = ap.parse_args(argv)
    modes = a.modes.split(",")
    if bad := [m for m in modes if m not in MODES]:
        ap.error(f"unknown modes {bad}")

    baseline = None
    if a.compare:  # kiểm tra trước khi chạy tốn thời gian
        try:
            baseline = json.loads(a.compare.read_text(encoding="utf-8"))
            if not isinstance(baseline, dict):
                raise ValueError("baseline must be a JSON object")
        except (OSError, ValueError) as e:
            print(f"error: --compare {a.compare}: {e}", file=sys.stderr)
            return 2
    golden = load_golden(a.golden)
    if a.refresh_cache:
        refresh_cache(golden, a.embed_model)
    items = [g for g in golden if g.gold and a.split in ("all", g.split)]
    if not items:
        print(f"error: no golden items with gold in split '{a.split}'", file=sys.stderr)
        return 2
    gw = None
    if "hybrid_rerank" in modes:
        base = os.environ.get("LLM_BASE_URL")
        gw = StrictGateway(base, os.environ.get("LLM_API_KEY", "")) if base else None
        if gw is None or not run_async(_ready(gw)):
            print(
                "skip hybrid_rerank: LLM_BASE_URL chưa đặt hoặc gateway không sẵn sàng",
                file=sys.stderr,
            )
            modes.remove("hybrid_rerank")
    try:
        vecs = (
            load_cache(cache_base(a.embed_model), items, a.embed_model)
            if {"dense", "hybrid"} & set(modes)
            else {}
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not a.allow_remote:
        ensure_local(a.database_url)
    with psycopg.connect(a.database_url, autocommit=True) as conn:
        version = load_frozen(a.index, conn)
    try:
        runs = run_async(run_modes(a.database_url, version, items, modes, vecs, gw))
    except GatewayLost as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    gold = {i.id: i.gold for i in items}
    res = {m: compute_metrics(runs[m], gold) for m in modes}
    res |= {"n_queries": len(items), "split": a.split, "index": str(a.index)}

    md = markdown(res)
    print(md)
    if a.markdown:
        a.markdown.parent.mkdir(parents=True, exist_ok=True)
        a.markdown.write_text(md, encoding="utf-8")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return gate(res, baseline, a.max_drop) if baseline is not None else 0


if __name__ == "__main__":
    sys.exit(main())
