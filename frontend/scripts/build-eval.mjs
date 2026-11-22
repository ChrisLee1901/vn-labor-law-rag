// Biến kết quả eval (Python) thành `src/content/eval.json`. Hàm thuần, dùng chung cho sync-eval.mjs và test.

export const MODES = ["fts", "dense", "hybrid", "hybrid_rerank"];
const RETRIEVAL_KEYS = ["hit_rate@1", "recall@5", "recall@10", "recall@20", "mrr@10", "ndcg@10"];
export const ANSWER_KEYS = ["citation_precision", "citation_recall", "numeric_match", "refusal_accuracy", "injection_resisted"];
export const LATENCY_KEYS = ["ttft_p50_s", "ttft_p95_s", "total_p50_s", "total_p95_s"];

const isObj = (v) => typeof v === "object" && v !== null && !Array.isArray(v);

function pick(src, keys, label) {
  if (!isObj(src)) throw new Error(`${label}: expected a JSON object`);
  const bad = keys.filter((k) => typeof src[k] !== "number" || !Number.isFinite(src[k]));
  if (bad.length) throw new Error(`${label}: missing or non-numeric ${bad.join(", ")}`);
  return Object.fromEntries(keys.map((k) => [k, src[k]]));
}

/**
 * @param {object} retrieval  `retrieval_v1.json` của rag_pipelines.eval.retrieval_eval: `{ "<mode>": {"hit_rate@1": ..}, n_queries, split, index }`
 * @param {object} [answers]  `answers_*.json`: ANSWER_KEYS (số 0..1) + `model?: string`
 * @param {object} [latency]  `latency.json`: LATENCY_KEYS (giây)
 * @param {string} [generatedAt] ISO 8601; script truyền giờ hiện tại
 * @returns {import("../src/content/eval-types").EvalContent}
 */
export function buildEvalContent(retrieval, answers, latency, generatedAt) {
  if (!isObj(retrieval)) throw new Error("retrieval: expected a JSON object");
  // Số trên split dev dùng để chỉnh tham số, chỉ split test mới được công bố.
  if (retrieval.split !== "test") throw new Error(`retrieval: split must be "test", got ${JSON.stringify(retrieval.split)}`);
  if (!Number.isInteger(retrieval.n_queries) || retrieval.n_queries <= 0) throw new Error("retrieval: n_queries must be a positive integer");
  const modes = MODES.filter((m) => m in retrieval);
  if (!modes.length) throw new Error(`retrieval: no mode found (expected one of ${MODES.join(", ")})`);

  const ablation = modes.map((mode) => {
    const m = pick(retrieval[mode], RETRIEVAL_KEYS, `retrieval.${mode}`);
    return { mode, ...Object.fromEntries(RETRIEVAL_KEYS.map((k) => [k.replace("@", "_at_"), m[k]])) };
  });

  const out = { status: "ready", ...(generatedAt && { generatedAt }), golden: { n_test: retrieval.n_queries }, ablation };
  if (answers !== undefined) {
    out.answers = pick(answers, ANSWER_KEYS, "answers");
    if (typeof answers.model === "string" && answers.model) out.model = answers.model;
  }
  if (latency !== undefined) out.latency = pick(latency, LATENCY_KEYS, "latency");
  return out;
}
