import type { ArticleItem, DocDetailResponse, DocSummary } from "./api-types";

/** Cache module-level cho GET /api/docs và GET /api/docs/{code}; gộp request đang bay, bỏ cache khi lỗi để lần sau thử lại. */
let docsPromise: Promise<DocSummary[]> | null = null;
const detailPromises = new Map<string, Promise<DocDetailResponse>>();

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function getDocs(): Promise<DocSummary[]> {
  if (!docsPromise) {
    docsPromise = getJson<DocSummary[]>("/api/docs");
    docsPromise.catch(() => (docsPromise = null));
  }
  return docsPromise;
}

export function getDocDetail(code: string): Promise<DocDetailResponse> {
  let p = detailPromises.get(code);
  if (!p) {
    p = getJson<DocDetailResponse>(`/api/docs/${encodeURIComponent(code)}`);
    p.catch(() => detailPromises.delete(code));
    detailPromises.set(code, p);
  }
  return p;
}

export function resetDocsCache() {
  docsPromise = null;
  detailPromises.clear();
}

export interface SourceRef {
  code: string;
  kind: "D" | "PL";
  n: number;
}

/** `/van-ban/ND293-2025#D3` -> {code, kind: "D", n: 3}; phụ lục `#PL2`. */
export function parseSourceUrl(url: string): SourceRef | null {
  const m = /^\/van-ban\/([^#/?]+)#(D|PL)(\d+)$/.exec(url);
  return m ? { code: decodeURIComponent(m[1]), kind: m[2] as "D" | "PL", n: Number(m[3]) } : null;
}

export type EffectivenessTone = "active" | "future" | "expired";
export interface Effectiveness {
  label: string;
  tone: EffectivenessTone;
  tooltip?: string;
}

const vnDate = (iso: string) => iso.split("-").reverse().join("/");
const isoToday = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Cùng quy ước với truy hồi: hiệu lực khi from <= hôm nay < to. */
export function effectiveness(doc: Pick<DocSummary, "effective_from" | "effective_to">, now = new Date()): Effectiveness {
  const today = isoToday(now);
  if (doc.effective_from > today)
    return { label: `Chưa hiệu lực (từ ${vnDate(doc.effective_from)})`, tone: "future" };
  if (doc.effective_to && doc.effective_to <= today)
    return { label: "Hết hiệu lực", tone: "expired", tooltip: `Hết hiệu lực từ ${vnDate(doc.effective_to)}` };
  return {
    label: "Đang hiệu lực",
    tone: "active",
    tooltip: doc.effective_to ? `Hết hiệu lực từ ${vnDate(doc.effective_to)}` : undefined,
  };
}

export function articleFor(articles: ArticleItem[], ref: SourceRef): ArticleItem | undefined {
  const kind = ref.kind === "D" ? "dieu" : "phu_luc";
  return articles.find((a) => a.kind === kind && a.number === ref.n);
}

export function excerpt(content: string, max = 300): string {
  const t = content.replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max).trimEnd()}…` : t;
}
