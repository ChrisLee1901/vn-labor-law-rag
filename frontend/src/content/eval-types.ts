export type AblationRow = {
  mode: string;
  hit_rate_at_1: number;
  recall_at_5: number;
  recall_at_10: number;
  recall_at_20: number;
  mrr_at_10: number;
  ndcg_at_10: number;
};

/** `n_queries` của mỗi khối là số câu của chính lần chạy đó (truy xuất chỉ đếm câu có gold), không suy ra từ nhau. Mọi khối chỉ trên split test. */
export type AnswersBlock = {
  n_queries: number;
  citation_precision: number;
  citation_recall: number;
  numeric_match: number;
  refusal_accuracy: number;
  injection_resisted: number;
};
export type LatencyBlock = { n_queries: number; ttft_p50_s: number; ttft_p95_s: number; total_p50_s: number; total_p95_s: number };

export type ReadyEval = Extract<EvalContent, { status: "ready" }>;

export type EvalContent =
  /** Chưa có lần chạy eval trực tuyến nào: trang chỉ hiện mô tả phương pháp. */
  | { status: "pending" }
  | {
      status: "ready";
      generatedAt?: string;
      /** LLM sinh câu trả lời khi chạy eval. */
      model?: string;
      retrieval: { n_queries: number };
      ablation: AblationRow[];
      answers?: AnswersBlock;
      latency?: LatencyBlock;
    };
