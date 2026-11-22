// Stub FastAPI cho e2e cục bộ (không có backend thật). Next rewrite /api/* về đây qua API_ORIGIN, nên cả
// server component (fetchDocs) lẫn trình duyệt (health, excerpt nguồn, chat) đều gọi vào đây.
// POST /api/chat phát SSE theo từng đoạn và dừng giữa chừng tới khi test gọi POST /__release (kiểm tra "hiện dần" không phụ thuộc đồng hồ).
import { createServer } from "node:http";

const doc = (code, number, title, over = {}) => ({
  code, number, title, doc_type: "nghi_dinh", effective_from: "2026-01-01", effective_to: null, status: "con_hieu_luc", ...over,
});
const art = (id, number, title, content) => ({ id, number, suffix: null, title, chapter: "Chương I. Quy định chung", content, kind: "dieu" });

const DETAILS = {
  "ND293-2025": {
    doc: { ...doc("ND293-2025", "293/2025/NĐ-CP", "Quy định mức lương tối thiểu"), issuer: "Chính phủ", issued_on: "2025-11-10", replaced_by: null, amends: [], source_url: null },
    articles: [
      art("ND293-2025:D1", 1, "Phạm vi điều chỉnh", "Nghị định này quy định mức lương tối thiểu."),
      art("ND293-2025:D3", 3, "Mức lương tối thiểu", "Mức lương tối thiểu tháng vùng I là 5.310.000 đồng/tháng."),
    ],
  },
  BLLD: {
    doc: { ...doc("BLLD", "18/VBHN-VPQH", "Bộ luật Lao động (văn bản hợp nhất)", { doc_type: "vbhn", effective_from: "2021-01-01" }), issuer: "Văn phòng Quốc hội", issued_on: "2023-07-10", replaced_by: null, amends: [], source_url: null },
    articles: [art("BLLD:D25", 25, "Thử việc", "Thời gian thử việc tối đa 60 ngày.")],
  },
};
const LIST = Object.values(DETAILS).map(({ doc: d, articles }) => ({ ...d, articles: articles.length }));

const sources = [
  { type: "source-url", sourceId: "S1", url: "/van-ban/ND293-2025#D3", title: "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu" },
  { type: "source-url", sourceId: "S2", url: "/van-ban/BLLD#D25", title: "45/2019/QH14, Điều 25. Thử việc" },
];
const PART1 = "Mức lương tối thiểu vùng I năm 2026 là ";
const PART2 = "**5.310.000 đồng/tháng** [S1]. Thử việc tối đa 60 ngày [S2].";

let waiting = [];
const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

createServer((req, res) => {
  const { pathname } = new URL(req.url, "http://x");
  if (pathname === "/api/health") return json(res, 200, { llm: "online", db: "ok", index_version: 1 });
  if (pathname === "/api/docs") return json(res, 200, LIST);
  if (pathname.startsWith("/api/docs/")) {
    const d = DETAILS[decodeURIComponent(pathname.slice(10))];
    return d ? json(res, 200, d) : json(res, 404, { detail: "Không tìm thấy văn bản." });
  }
  if (pathname === "/__release") {
    waiting.forEach((r) => r());
    waiting = [];
    return json(res, 200, { ok: true });
  }
  if (pathname === "/api/chat" && req.method === "POST") {
    req.resume();
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache, no-transform", "x-vercel-ai-ui-message-stream": "v1" });
    const send = (c) => res.write(`data: ${JSON.stringify(c)}\n\n`);
    [{ type: "start", messageId: "stub-1" }, { type: "data-status", data: { llm: "online", mode: "rag" } }, ...sources, { type: "text-start", id: "t1" }, { type: "text-delta", id: "t1", delta: PART1 }].forEach(send);
    new Promise((r) => waiting.push(r)).then(() => {
      [{ type: "text-delta", id: "t1", delta: PART2 }, { type: "text-end", id: "t1" }, { type: "data-trace", data: { trace_id: "stub-trace" } }, { type: "finish" }].forEach(send);
      res.end("data: [DONE]\n\n");
    });
    return;
  }
  json(res, 404, { detail: "Không tìm thấy." });
}).listen(Number(process.env.E2E_STUB_PORT ?? 8787), "127.0.0.1");
