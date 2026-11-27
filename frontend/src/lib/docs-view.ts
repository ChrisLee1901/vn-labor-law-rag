import type { ArticleItem, DocSummary, DocType } from "./api-types";
import { effectiveness } from "./docs-cache";

export const DOC_TYPE_LABEL: Record<DocType, string> = {
  luat: "Luật",
  bo_luat: "Bộ luật",
  vbhn: "Văn bản hợp nhất",
  nghi_dinh: "Nghị định",
  thong_tu: "Thông tư",
};

const RANK = { active: 0, future: 1, expired: 2 } as const;

/** Đang hiệu lực trước, rồi chưa hiệu lực, rồi hết hiệu lực; trong mỗi nhóm ngày hiệu lực mới nhất trước. */
export function sortDocs(docs: DocSummary[], now = new Date()): DocSummary[] {
  return docs
    .map((d) => ({ d, r: RANK[effectiveness(d, now).tone] }))
    .sort((a, b) => a.r - b.r || (a.d.effective_from < b.d.effective_from ? 1 : a.d.effective_from > b.d.effective_from ? -1 : 0))
    .map((x) => x.d);
}

export interface ChapterGroup {
  chapter: string | null;
  articles: ArticleItem[];
}

/** Gom các Điều liền nhau cùng Chương (giữ thứ tự API). Phụ lục không thuộc chương nào nên bỏ ra ngoài. */
export function groupByChapter(articles: ArticleItem[]): ChapterGroup[] {
  const groups: ChapterGroup[] = [];
  for (const a of articles) {
    if (a.kind !== "dieu") continue;
    const last = groups.at(-1);
    if (last && last.chapter === a.chapter) last.articles.push(a);
    else groups.push({ chapter: a.chapter, articles: [a] });
  }
  return groups;
}

/** id phần tử: `D{n}` / `PL{n}` (khớp liên kết nguồn của chat), thêm hậu tố cho Điều 12a. */
export function articleAnchor(a: ArticleItem): string {
  if (a.number == null) return a.id.replace(/[^A-Za-z0-9-]/g, "-");
  return `${a.kind === "dieu" ? "D" : "PL"}${a.number}${a.suffix ?? ""}`;
}

export function articleHeading(a: ArticleItem): string {
  const head = `${a.kind === "dieu" ? "Điều" : "Phụ lục"} ${a.number ?? ""}${a.suffix ?? ""}`.trim();
  return a.title ? `${head}. ${a.title}` : head;
}

export const isValidDocCode = (code: string) => /^[A-Za-z0-9-]+$/.test(code);
