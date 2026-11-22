import { cache } from "react";
import type { DocDetailResponse, DocSummary } from "./api-types";

type Env = Record<string, string | undefined>;

/**
 * Gốc URL của API khi gọi từ server component. Thứ tự:
 * API_ORIGIN -> NEXT_PUBLIC_SITE_URL -> https://$VERCEL_URL (API cùng project trên Vercel)
 * -> http://127.0.0.1:8000 (chỉ khi NODE_ENV=development) -> ném lỗi.
 */
export function getApiBase(env: Env = process.env): string {
  const base =
    env.API_ORIGIN ||
    env.NEXT_PUBLIC_SITE_URL ||
    (env.VERCEL_URL ? `https://${env.VERCEL_URL}` : "") ||
    (env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "");
  if (!base) throw new Error("Thiếu API_ORIGIN (hoặc NEXT_PUBLIC_SITE_URL / VERCEL_URL) để gọi API từ server.");
  return base.replace(/\/+$/, "");
}

const OPTS = { next: { revalidate: 3600 } };

/** Danh sách văn bản. Ném lỗi khi API hỏng hoặc trả sai dạng. */
export async function fetchDocs(): Promise<DocSummary[]> {
  const res = await fetch(`${getApiBase()}/api/docs`, OPTS);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body: unknown = await res.json();
  if (!Array.isArray(body)) throw new Error("Phản hồi /api/docs không phải mảng");
  return body as DocSummary[];
}

/** Chi tiết văn bản; `null` nếu mã không tồn tại (404). Dùng chung giữa metadata và trang trong một request. */
export const fetchDocDetail = cache(async (code: string): Promise<DocDetailResponse | null> => {
  const res = await fetch(`${getApiBase()}/api/docs/${encodeURIComponent(code)}`, OPTS);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as DocDetailResponse;
  if (!body?.doc || !Array.isArray(body.articles)) throw new Error("Phản hồi /api/docs/{code} sai dạng");
  return body;
});
