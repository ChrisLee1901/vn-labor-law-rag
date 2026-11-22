import type { ArticleItem, DocDetailResponse, DocSummary } from "@/lib/api-types";

/** Dữ liệu mẫu cho test trang Văn bản. Mốc "hôm nay" của test: 2026-11-22. */
export const DOCS: DocSummary[] = [
  {
    code: "ND145-2020",
    number: "145/2020/NĐ-CP",
    title: "Quy định chi tiết một số điều của Bộ luật Lao động",
    doc_type: "nghi_dinh",
    effective_from: "2021-02-14",
    effective_to: "2026-01-01",
    status: "het_hieu_luc",
    articles: 74,
  },
  {
    code: "ND399-2026",
    number: "399/2026/NĐ-CP",
    title: "Văn bản chưa có hiệu lực",
    doc_type: "nghi_dinh",
    effective_from: "2027-03-01",
    effective_to: null,
    status: "chua_hieu_luc",
    articles: 12,
  },
  {
    code: "BLLD",
    number: "18/VBHN-VPQH",
    title: "Bộ luật Lao động (văn bản hợp nhất)",
    doc_type: "vbhn",
    effective_from: "2021-01-01",
    effective_to: null,
    status: "con_hieu_luc",
    articles: 220,
  },
];

const art = (over: Partial<ArticleItem> & Pick<ArticleItem, "id" | "number">): ArticleItem => ({
  suffix: null,
  title: null,
  chapter: null,
  content: "",
  kind: "dieu",
  ...over,
});

export const DETAIL: DocDetailResponse = {
  doc: {
    code: "ND145-2020",
    number: "145/2020/NĐ-CP",
    title: "Quy định chi tiết một số điều của Bộ luật Lao động",
    doc_type: "nghi_dinh",
    effective_from: "2021-02-14",
    effective_to: "2026-01-01",
    status: "het_hieu_luc",
    issuer: "Chính phủ",
    issued_on: "2020-12-14",
    replaced_by: "ND293-2025",
    amends: [],
    source_url: "https://example.gov.vn/nd145",
  },
  articles: [
    art({ id: "ND145-2020:D1", number: 1, title: "Phạm vi điều chỉnh", chapter: "Chương I. Quy định chung", content: "Nghị định này quy định\nchi tiết." }),
    art({ id: "ND145-2020:D12", number: 12, title: "Hợp đồng lao động", chapter: "Chương I. Quy định chung", content: "<b>không phải HTML</b> **không phải markdown**" }),
    art({ id: "ND145-2020:D12a", number: 12, suffix: "a", title: "Điều bổ sung", chapter: "Chương II. Tiền lương", content: "Nội dung 12a." }),
    art({ id: "ND145-2020:D20", number: 20, title: "Tiền lương", chapter: "Chương II. Tiền lương", content: "Nội dung 20." }),
    art({ id: "ND145-2020:PL1", number: 1, kind: "phu_luc", title: "Danh mục", content: "Phụ lục một." }),
  ],
};
