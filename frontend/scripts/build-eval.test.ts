import { describe, expect, it } from "vitest";
import { buildEvalContent } from "./build-eval.mjs";

const metrics = (x: number) => ({ "hit_rate@1": x, "recall@5": x + 0.1, "recall@10": x + 0.2, "recall@20": x + 0.3, "mrr@10": x + 0.05, "ndcg@10": x + 0.06 });
const RETRIEVAL = {
  fts: metrics(0.2),
  hybrid: metrics(0.4),
  dense: metrics(0.3),
  n_queries: 80,
  split: "test",
  index: "eval/index/v1.parquet",
};
const NOW = "2026-12-01T00:00:00.000Z";

describe("buildEvalContent", () => {
  it("maps retrieval modes in canonical order, renaming `@` keys and ignoring metadata keys", () => {
    const c = buildEvalContent(RETRIEVAL, undefined, undefined, NOW);
    expect(c.status).toBe("ready");
    expect(c.generatedAt).toBe(NOW);
    expect(c.retrieval).toEqual({ n_queries: 80 });
    expect(c).not.toHaveProperty("golden");
    expect(c.ablation?.map((r: { mode: string }) => r.mode)).toEqual(["fts", "dense", "hybrid"]);
    expect(c.ablation?.[2]).toEqual({
      mode: "hybrid",
      hit_rate_at_1: 0.4,
      recall_at_5: 0.5,
      recall_at_10: 0.6000000000000001,
      recall_at_20: 0.7,
      mrr_at_10: 0.45,
      ndcg_at_10: 0.46,
    });
    expect(c.answers).toBeUndefined();
    expect(c.latency).toBeUndefined();
  });

  it("adds answers, latency and model when given, picking only the documented keys", () => {
    const answers = { split: "test", n_queries: 120, citation_precision: 0.9, citation_recall: 0.8, numeric_match: 0.7, refusal_accuracy: 0.95, injection_resisted: 1, model: "Qwen3-8B Q5_K_M", extra: 1 };
    const latency = { split: "test", n_queries: 40, ttft_p50_s: 1.1, ttft_p95_s: 2.2, total_p50_s: 8, total_p95_s: 15.5, extra: 1 };
    const c = buildEvalContent(RETRIEVAL, answers, latency, NOW);
    expect(c.model).toBe("Qwen3-8B Q5_K_M");
    expect(c.answers).toEqual({ n_queries: 120, citation_precision: 0.9, citation_recall: 0.8, numeric_match: 0.7, refusal_accuracy: 0.95, injection_resisted: 1 });
    expect(c.latency).toEqual({ n_queries: 40, ttft_p50_s: 1.1, ttft_p95_s: 2.2, total_p50_s: 8, total_p95_s: 15.5 });
  });

  it("refuses non-test splits, so dev numbers are never published as test results", () => {
    expect(() => buildEvalContent({ ...RETRIEVAL, split: "dev" }, undefined, undefined, NOW)).toThrow(/split/);
  });

  it("keeps each block's own n_queries, never the retrieval one", () => {
    const answers = { split: "test", n_queries: 80, citation_precision: 1, citation_recall: 1, numeric_match: 1, refusal_accuracy: 1, injection_resisted: 1 };
    const c = buildEvalContent({ ...RETRIEVAL, n_queries: 68 }, answers, undefined, NOW);
    expect(c.retrieval.n_queries).toBe(68);
    expect(c.answers?.n_queries).toBe(80);
  });

  it("applies the test-split guard to answers and latency too (missing or dev split, bad n_queries)", () => {
    const A = { split: "test", n_queries: 80, citation_precision: 1, citation_recall: 1, numeric_match: 1, refusal_accuracy: 1, injection_resisted: 1 };
    const L = { split: "test", n_queries: 80, ttft_p50_s: 1, ttft_p95_s: 2, total_p50_s: 3, total_p95_s: 4 };
    expect(() => buildEvalContent(RETRIEVAL, { ...A, split: "dev" }, undefined, NOW)).toThrow(/answers.*split/);
    expect(() => buildEvalContent(RETRIEVAL, { ...A, split: undefined }, undefined, NOW)).toThrow(/answers.*split/);
    expect(() => buildEvalContent(RETRIEVAL, { ...A, n_queries: 0 }, undefined, NOW)).toThrow(/answers.*n_queries/);
    expect(() => buildEvalContent(RETRIEVAL, undefined, { ...L, split: "dev" }, NOW)).toThrow(/latency.*split/);
    expect(() => buildEvalContent(RETRIEVAL, undefined, { ...L, split: undefined }, NOW)).toThrow(/latency.*split/);
    expect(() => buildEvalContent(RETRIEVAL, undefined, { ...L, n_queries: 1.5 }, NOW)).toThrow(/latency.*n_queries/);
    expect(buildEvalContent(RETRIEVAL, A, L, NOW).status).toBe("ready");
  });

  it("throws on missing or non-numeric metrics instead of writing a partial table", () => {
    const partial = Object.fromEntries(Object.entries(metrics(0.1)).filter(([k]) => k !== "ndcg@10"));
    expect(() => buildEvalContent({ ...RETRIEVAL, fts: partial }, undefined, undefined, NOW)).toThrow(/fts.*ndcg@10/);
    expect(() => buildEvalContent({ ...RETRIEVAL, fts: { ...metrics(0.1), "mrr@10": "0.5" } }, undefined, undefined, NOW)).toThrow(/mrr@10/);
    expect(() => buildEvalContent({ n_queries: 80, split: "test" }, undefined, undefined, NOW)).toThrow(/mode/);
    expect(() => buildEvalContent(RETRIEVAL, { split: "test", n_queries: 1, citation_precision: 1 }, undefined, NOW)).toThrow(/answers/);
    expect(() => buildEvalContent(RETRIEVAL, undefined, { split: "test", n_queries: 1, ttft_p50_s: 1 }, NOW)).toThrow(/latency/);
  });
});
