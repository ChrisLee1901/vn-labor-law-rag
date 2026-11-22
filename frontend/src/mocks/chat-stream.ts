/** Stream SSE giả theo docs/api-contract.md, dùng cho test và `NEXT_PUBLIC_MOCK_CHAT=1`. */
export type MockKind = "rag" | "offline" | "refused" | "error";

type Chunk = Record<string, unknown>;

const S1 = {
  type: "source-url",
  sourceId: "S1",
  url: "/van-ban/ND293-2025#D3",
  title: "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu",
};
const S2 = {
  type: "source-url",
  sourceId: "S2",
  url: "/van-ban/BLLD#D25",
  title: "45/2019/QH14, Điều 25. Thử việc",
};
const text = (id: string, delta: string): Chunk[] => [
  { type: "text-start", id },
  ...delta.match(/[\s\S]{1,24}/g)!.map((d) => ({ type: "text-delta", id, delta: d })),
  { type: "text-end", id },
];

function chunks(kind: MockKind): Chunk[] {
  const start = { type: "start", messageId: `mock-${kind}` };
  switch (kind) {
    case "rag":
      return [
        start,
        { type: "data-status", data: { llm: "online", mode: "rag" } },
        S1,
        S2,
        ...text(
          "t1",
          "Mức lương tối thiểu vùng I năm 2026 là **5.310.000 đồng/tháng** [S1]. Thời gian thử việc tối đa với vị trí yêu cầu trình độ cao đẳng trở lên là 60 ngày [S2][S9].",
        ),
        { type: "data-citation-warning", data: { invalid: ["S9"], mismatch: [] } },
        { type: "data-trace", data: { trace_id: "trace-rag-1" } },
        { type: "finish" },
      ];
    case "offline":
      return [
        start,
        { type: "data-status", data: { llm: "offline", mode: "offline" } },
        S1,
        ...text("t1", "Mô hình đang ngoại tuyến. Dưới đây là các điều luật liên quan nhất:\n\n- [S1] 293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu"),
        { type: "data-trace", data: { trace_id: "trace-offline-1" } },
        { type: "finish" },
      ];
    case "refused":
      return [
        start,
        { type: "data-status", data: { llm: "online", mode: "refused" } },
        ...text("t1", "Tôi không tìm thấy căn cứ trong các văn bản hiện có."),
        { type: "data-trace", data: { trace_id: "trace-refused-1" } },
        { type: "finish" },
      ];
    case "error":
      return [
        start,
        { type: "data-status", data: { llm: "online", mode: "rag" } },
        S1,
        ...text("t1", "Mức lương tối thiểu vùng I"),
        { type: "error", errorText: "Kết nối tới mô hình bị gián đoạn, vui lòng thử lại." },
      ];
  }
}

export function mockChatResponse(kind: MockKind): Response {
  const body =
    chunks(kind)
      .map((c) => `data: ${JSON.stringify(c)}\n\n`)
      .join("") + "data: [DONE]\n\n";
  return new Response(body, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      "x-vercel-ai-ui-message-stream": "v1",
    },
  });
}

/** Chọn kịch bản theo nội dung câu hỏi (dùng khi dev): chứa "offline"/"từ chối"/"lỗi" thì ra kịch bản tương ứng. */
export function mockKindFor(question: string): MockKind {
  const q = question.toLowerCase();
  if (q.includes("offline")) return "offline";
  if (q.includes("từ chối") || q.includes("nấu")) return "refused";
  if (q.includes("lỗi")) return "error";
  return "rag";
}
