import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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
// Hình dạng của `answers_<label>_<date>.json` do rag_pipelines.eval.answer_eval ghi (schema_version 1); độ trễ tính bằng mili giây.
const ANSWERS = {
  schema_version: 1,
  label: "Qwen3-8B-Q5_K_M",
  split: "test",
  n_queries: 80,
  n_failed: 2,
  metrics: { citation_precision: 0.9, citation_recall: 0.8, numeric_match: 0.7, refusal_accuracy: 0.95, injection_resisted: 1 },
  denominators: { citation_precision: 143, citation_recall: 64, numeric_match: 17, refusal_accuracy: 76, injection_resisted: 4 },
  latency: { n: 78, ttft_ms: { p50: 1100, p95: 2200 }, total_ms: { p50: 8000, p95: 15500 } },
} as Record<string, unknown> & { metrics: Record<string, unknown>; latency: { n: number; ttft_ms: object; total_ms: object } };

describe("buildEvalContent", () => {
  it("maps retrieval modes in canonical order, renaming `@` keys and ignoring metadata keys", () => {
    const c = buildEvalContent(RETRIEVAL, undefined, NOW);
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

  it("adds answers, latency (ms -> s), denominators and model from the answer_eval file, picking only documented keys", () => {
    const c = buildEvalContent(RETRIEVAL, { ...ANSWERS, extra: 1 }, NOW);
    expect(c.model).toBe("Qwen3-8B-Q5_K_M");
    expect(c.answers).toEqual({
      n_queries: 80,
      n_failed: 2,
      citation_precision: 0.9,
      citation_recall: 0.8,
      numeric_match: 0.7,
      refusal_accuracy: 0.95,
      injection_resisted: 1,
      denominators: { citation_precision: 143, citation_recall: 64, numeric_match: 17, refusal_accuracy: 76, injection_resisted: 4 },
    });
    expect(c.latency).toEqual({ n_queries: 78, ttft_p50_s: 1.1, ttft_p95_s: 2.2, total_p50_s: 8, total_p95_s: 15.5 });
  });

  it("round-trips a result produced by the Python answer_eval (committed fixture, kept in sync by pipelines/tests/test_answer_eval.py)", () => {
    const sample = JSON.parse(readFileSync(resolve(process.cwd(), "../pipelines/tests/fixtures/answers_sample.json"), "utf8"));
    const c = buildEvalContent(RETRIEVAL, sample, NOW);
    expect(c.status).toBe("ready");
    expect(c.model).toBe(sample.label);
    expect(c.answers).toMatchObject({ n_queries: sample.n_queries, n_failed: 0, ...sample.metrics, denominators: sample.denominators });
    expect(c.latency).toEqual({
      n_queries: sample.latency.n,
      ttft_p50_s: sample.latency.ttft_ms.p50 / 1000,
      ttft_p95_s: sample.latency.ttft_ms.p95 / 1000,
      total_p50_s: sample.latency.total_ms.p50 / 1000,
      total_p95_s: sample.latency.total_ms.p95 / 1000,
    });
    expect(JSON.stringify(c)).not.toMatch(/example|http/); // base_url_kind chứ không bao giờ là URL
  });

  it("refuses non-test splits, so dev numbers are never published as test results", () => {
    expect(() => buildEvalContent({ ...RETRIEVAL, split: "dev" }, undefined, NOW)).toThrow(/split/);
  });

  it("keeps each block's own n_queries, never the retrieval one", () => {
    const c = buildEvalContent({ ...RETRIEVAL, n_queries: 68 }, ANSWERS, NOW);
    expect(c.retrieval.n_queries).toBe(68);
    expect(c.answers?.n_queries).toBe(80);
    expect(c.latency?.n_queries).toBe(78);
  });

  it("applies the test-split guard to answers (missing or dev split, bad n_queries, bad latency.n, wrong schema_version)", () => {
    const bad = (patch: object, re: RegExp) => expect(() => buildEvalContent(RETRIEVAL, { ...ANSWERS, ...patch }, NOW)).toThrow(re);
    bad({ split: "dev" }, /answers.*split/);
    bad({ split: undefined }, /answers.*split/);
    bad({ n_queries: 0 }, /answers.*n_queries/);
    bad({ n_queries: 1.5 }, /answers.*n_queries/);
    bad({ latency: { ...ANSWERS.latency, n: 0 } }, /latency.*n/);
    bad({ schema_version: 2 }, /schema_version/);
    bad({ schema_version: undefined }, /schema_version/);
    bad({ n_failed: 81 }, /n_failed/);
    bad({ label: "" }, /label/);
    expect(buildEvalContent(RETRIEVAL, ANSWERS, NOW).status).toBe("ready");
  });

  it("throws on missing or non-numeric metrics instead of writing a partial table", () => {
    const partial = Object.fromEntries(Object.entries(metrics(0.1)).filter(([k]) => k !== "ndcg@10"));
    expect(() => buildEvalContent({ ...RETRIEVAL, fts: partial }, undefined, NOW)).toThrow(/fts.*ndcg@10/);
    expect(() => buildEvalContent({ ...RETRIEVAL, fts: { ...metrics(0.1), "mrr@10": "0.5" } }, undefined, NOW)).toThrow(/mrr@10/);
    expect(() => buildEvalContent({ n_queries: 80, split: "test" }, undefined, NOW)).toThrow(/mode/);
    const rest = Object.fromEntries(Object.entries(ANSWERS.metrics).filter(([k]) => k !== "numeric_match"));
    expect(() => buildEvalContent(RETRIEVAL, { ...ANSWERS, metrics: rest }, NOW)).toThrow(/answers\.metrics.*numeric_match/);
    expect(() => buildEvalContent(RETRIEVAL, { ...ANSWERS, metrics: { ...ANSWERS.metrics, refusal_accuracy: null } }, NOW)).toThrow(/refusal_accuracy/);
    expect(() => buildEvalContent(RETRIEVAL, { ...ANSWERS, denominators: {} }, NOW)).toThrow(/denominators/);
    expect(() => buildEvalContent(RETRIEVAL, { ...ANSWERS, latency: { ...ANSWERS.latency, ttft_ms: { p50: 1 } } }, NOW)).toThrow(/ttft_ms.*p95/);
  });
});
