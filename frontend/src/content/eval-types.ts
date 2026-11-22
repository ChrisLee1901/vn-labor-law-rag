export type AblationRow = {
  mode: string;
  hit_rate_at_1: number;
  recall_at_5: number;
  recall_at_10: number;
  recall_at_20: number;
  mrr_at_10: number;
  ndcg_at_10: number;
};

export type EvalContent = {
  /** `pending`: chưa có lần chạy eval trực tuyến nào, trang chỉ hiện mô tả phương pháp. */
  status: "pending" | "ready";
  generatedAt?: string;
  /** LLM sinh câu trả lời khi chạy eval. */
  model?: string;
  golden?: { n_test: number };
  ablation?: AblationRow[];
  answers?: {
    citation_precision: number;
    citation_recall: number;
    numeric_match: number;
    refusal_accuracy: number;
    injection_resisted: number;
  };
  latency?: { ttft_p50_s: number; ttft_p95_s: number; total_p50_s: number; total_p95_s: number };
};
