/**
 * Kiểu API dùng chung cho frontend. Nguồn sự thật: docs/api-contract.md
 * (stream: docs/ai-sdk-protocol.md, backend/app/stream.py).
 * Chỉ khai báo kiểu, không import gì.
 */

export const DOC_TYPES = ["luat", "bo_luat", "vbhn", "nghi_dinh", "thong_tu"] as const;
export type DocType = (typeof DOC_TYPES)[number];

export const DOC_STATUSES = ["con_hieu_luc", "chua_hieu_luc", "het_hieu_luc"] as const;
export type DocStatus = (typeof DOC_STATUSES)[number];

export const LLM_STATES = ["online", "offline"] as const;
export type LlmState = (typeof LLM_STATES)[number];

export const CHAT_MODES = ["rag", "offline", "refused"] as const;
export type ChatMode = (typeof CHAT_MODES)[number];

export const ARTICLE_KINDS = ["dieu", "phu_luc"] as const;
export type ArticleKind = (typeof ARTICLE_KINDS)[number];

/** Lỗi mọi endpoint (422/429/503/404/401): thông báo tiếng Việt. docs/api-contract.md#lỗi */
export interface ApiError {
  detail: string;
}

/** POST /api/chat. `messages` là UIMessage[] của AI SDK; tin cuối là user, 1-1000 ký tự, tối đa 10 tin. */
export interface ChatRequestBody<TMessage = unknown> {
  messages: TMessage[];
  /** YYYY-MM-DD; mặc định hôm nay. */
  as_of?: string;
}

/** data-status (docs/api-contract.md#các-part). */
export interface StatusData {
  llm: LlmState;
  mode: ChatMode;
}

/** data-trace: trace_id dùng cho FeedbackBody. */
export interface TraceData {
  trace_id: string;
}

/** data-citation-warning: id nguồn không hợp lệ / lệch nội dung. */
export interface CitationWarningData {
  invalid: string[];
  mismatch: string[];
}

/** GET /api/health (cache-control: no-store). */
export interface HealthResponse {
  llm: LlmState;
  db: "ok" | "down";
  index_version: number;
}

/** GET /api/docs (public, s-maxage=3600). `articles` chỉ đếm kind 'dieu'. */
export interface DocSummary {
  code: string;
  number: string | null;
  title: string | null;
  doc_type: DocType;
  /** YYYY-MM-DD */
  effective_from: string;
  /** YYYY-MM-DD */
  effective_to: string | null;
  status: DocStatus;
  articles: number;
}

/** `doc` trong GET /api/docs/{code}; 404 `{detail:"Không tìm thấy văn bản."}` nếu không có mã. */
export interface DocDetail extends Omit<DocSummary, "articles"> {
  issuer: string | null;
  /** YYYY-MM-DD */
  issued_on: string | null;
  replaced_by: string | null;
  amends: string[];
  source_url: string | null;
}

/** Phần tử `articles` trong GET /api/docs/{code}. Neo trang: `#D{number}` hoặc `#PL{number}`. */
export interface ArticleItem {
  /** vd "ND293-2025:D3" */
  id: string;
  number: number | null;
  suffix: string | null;
  title: string | null;
  chapter: string | null;
  content: string;
  kind: ArticleKind;
}

/** Body của GET /api/docs/{code}. */
export interface DocDetailResponse {
  doc: DocDetail;
  articles: ArticleItem[];
}

/** POST /api/feedback -> 204. */
export interface FeedbackBody {
  trace_id: string;
  score: 1 | -1;
  comment?: string;
}
