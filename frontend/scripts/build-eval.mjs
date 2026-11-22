// Biến kết quả eval (Python) thành `src/content/eval.json`. Hàm thuần, dùng chung cho sync-eval.mjs và test.

export const MODES = ["fts", "dense", "hybrid", "hybrid_rerank"];
const RETRIEVAL_KEYS = ["hit_rate@1", "recall@5", "recall@10", "recall@20", "mrr@10", "ndcg@10"];
export const ANSWER_KEYS = ["citation_precision", "citation_recall", "numeric_match", "refusal_accuracy", "injection_resisted"];
export const ANSWERS_SCHEMA_VERSION = 1;

const isObj = (v) => typeof v === "object" && v !== null && !Array.isArray(v);

function pick(src, keys, label) {
  if (!isObj(src)) throw new Error(`${label}: expected a JSON object`);
  const bad = keys.filter((k) => typeof src[k] !== "number" || !Number.isFinite(src[k]));
  if (bad.length) throw new Error(`${label}: missing or non-numeric ${bad.join(", ")}`);
  return Object.fromEntries(keys.map((k) => [k, src[k]]));
}

// Số trên split dev dùng để chỉnh tham số, chỉ split test mới được công bố. Áp cho cả hai file.
function checkTest(src, label) {
  if (!isObj(src)) throw new Error(`${label}: expected a JSON object`);
  if (src.split !== "test") throw new Error(`${label}: split must be "test", got ${JSON.stringify(src.split)}`);
  if (!Number.isInteger(src.n_queries) || src.n_queries <= 0) throw new Error(`${label}: n_queries must be a positive integer`);
}

/**
 * @param {object} retrieval  `retrieval_v1.json` của rag_pipelines.eval.retrieval_eval: `{ "<mode>": {"hit_rate@1": ..}, n_queries, split, index }`
 * @param {object} [answers]  `answers_<label>_<date>.json` của rag_pipelines.eval.answer_eval (schema trong docstring của module đó):
 *   `schema_version: 1`, `split: "test"`, `n_queries`, `n_failed`, `label`, `metrics`/`denominators` (ANSWER_KEYS),
 *   `latency: {n, ttft_ms: {p50, p95}, total_ms: {p50, p95}}` (mili giây; ở đây đổi sang giây)
 * @param {string} [generatedAt] ISO 8601; script truyền giờ hiện tại
 * @returns {import("../src/content/eval-types").ReadyEval}
 */
export function buildEvalContent(retrieval, answers, generatedAt) {
  checkTest(retrieval, "retrieval");
  const modes = MODES.filter((m) => m in retrieval);
  if (!modes.length) throw new Error(`retrieval: no mode found (expected one of ${MODES.join(", ")})`);

  const ablation = modes.map((mode) => {
    const m = pick(retrieval[mode], RETRIEVAL_KEYS, `retrieval.${mode}`);
    return { mode, ...Object.fromEntries(RETRIEVAL_KEYS.map((k) => [k.replace("@", "_at_"), m[k]])) };
  });

  const out = { status: "ready", ...(generatedAt && { generatedAt }), retrieval: { n_queries: retrieval.n_queries }, ablation };
  if (answers !== undefined) {
    checkTest(answers, "answers");
    if (answers.schema_version !== ANSWERS_SCHEMA_VERSION) throw new Error(`answers: schema_version must be ${ANSWERS_SCHEMA_VERSION}, got ${JSON.stringify(answers.schema_version)}`);
    const lat = answers.latency;
    if (!isObj(lat) || !Number.isInteger(lat.n) || lat.n <= 0) throw new Error("answers.latency: n must be a positive integer");
    const ttft = pick(lat.ttft_ms, ["p50", "p95"], "answers.latency.ttft_ms");
    const total = pick(lat.total_ms, ["p50", "p95"], "answers.latency.total_ms");
    if (!Number.isInteger(answers.n_failed) || answers.n_failed < 0 || answers.n_failed > answers.n_queries) throw new Error("answers: n_failed must be an integer in 0..n_queries");
    if (typeof answers.label !== "string" || !answers.label) throw new Error("answers: label must be a non-empty string");
    out.model = answers.label;
    out.answers = {
      n_queries: answers.n_queries,
      n_failed: answers.n_failed,
      ...pick(answers.metrics, ANSWER_KEYS, "answers.metrics"),
      denominators: pick(answers.denominators, ANSWER_KEYS, "answers.denominators"),
    };
    out.latency = { n_queries: lat.n, ttft_p50_s: ttft.p50 / 1000, ttft_p95_s: ttft.p95 / 1000, total_p50_s: total.p50 / 1000, total_p95_s: total.p95 / 1000 };
  }
  return out;
}
