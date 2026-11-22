import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadChats } from "@/lib/chat-storage";
import { resetDocsCache } from "@/lib/docs-cache";
import { mockChatResponse, type MockKind } from "@/mocks/chat-stream";
import { Chat } from "./chat";

const docs = [
  { code: "ND293-2025", number: "293/2025/NĐ-CP", title: "Lương tối thiểu", doc_type: "nghi_dinh", effective_from: "2026-01-01", effective_to: null, status: "con_hieu_luc", articles: 8 },
  { code: "BLLD", number: "45/2019/QH14", title: "Bộ luật Lao động", doc_type: "bo_luat", effective_from: "2021-01-01", effective_to: null, status: "con_hieu_luc", articles: 220 },
];

type Handler = (call: number, signal?: AbortSignal | null) => Response;
let chatCalls: { body: Record<string, unknown> }[];
let feedbackBodies: unknown[];

function stubFetch(chat: MockKind | Handler) {
  chatCalls = [];
  feedbackBodies = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
      if (url.endsWith("/api/chat")) {
        chatCalls.push({ body: JSON.parse(String(init?.body)) });
        return typeof chat === "function" ? chat(chatCalls.length, init?.signal) : mockChatResponse(chat);
      }
      if (url.endsWith("/api/feedback")) {
        feedbackBodies.push(JSON.parse(String(init?.body)));
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/docs")) return Response.json(docs);
      if (url.includes("/api/docs/")) return Response.json({ doc: docs[0], articles: [] });
      throw new Error(`unexpected fetch ${url}`);
    }),
  );
}

async function ask(question = "Lương tối thiểu vùng I?") {
  const user = userEvent.setup();
  render(<Chat />);
  await user.type(screen.getByRole("textbox", { name: "Câu hỏi" }), `${question}{Enter}`);
  return user;
}

beforeEach(() => {
  localStorage.clear();
  resetDocsCache();
});
afterEach(() => vi.unstubAllGlobals());

describe("Chat", () => {
  it("shows the empty state with 6 suggested questions that send on click", async () => {
    stubFetch("rag");
    const user = userEvent.setup();
    render(<Chat />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Câu hỏi gợi ý" });
    expect(within(list).getAllByRole("button")).toHaveLength(6);
    await user.click(within(list).getAllByRole("button")[0]);
    expect(await screen.findByText(/5\.310\.000/)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Câu hỏi gợi ý" })).toBeNull();
  });

  it("streams the answer with citations, sources panel and a minimal request body", async () => {
    stubFetch("rag");
    await ask();
    expect(await screen.findByText(/5\.310\.000/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Nguồn S1: 293\/2025/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nguồn S2: 45\/2019/ })).toBeInTheDocument();
    expect(screen.getByText("[S9]")).toBeInTheDocument(); // nguồn lạ
    const panel = screen.getByRole("complementary", { name: "Nguồn trích dẫn" });
    expect(within(panel).getAllByRole("listitem")).toHaveLength(2);
    expect(await within(panel).findAllByText("Đang hiệu lực")).toHaveLength(2);
    expect(within(panel).getAllByRole("link", { name: /Xem điều luật/ })[0]).toHaveAttribute("href", "/van-ban/ND293-2025#D3");

    expect(Object.keys(chatCalls[0].body)).toEqual(["messages"]);
    expect(chatCalls[0].body.messages).toEqual([
      { id: expect.any(String), role: "user", parts: [{ type: "text", text: "Lương tối thiểu vùng I?" }] },
    ]);
  });

  it("marks the clicked citation's source as active", async () => {
    stubFetch("rag");
    // desktop: panel cố định bên phải, không mở sheet (sheet modal sẽ ẩn phần còn lại khỏi cây trợ năng)
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} }));
    const user = await ask();
    await user.click(await screen.findByRole("button", { name: /Nguồn S2:/ }));
    const panel = screen.getByRole("complementary", { name: "Nguồn trích dẫn" });
    expect(within(panel).getAllByRole("listitem")[1]).toHaveAttribute("aria-current", "true");
  });

  it("persists the conversation to localStorage", async () => {
    stubFetch("rag");
    await ask();
    await screen.findByText(/5\.310\.000/);
    await waitFor(() => expect(loadChats()).toHaveLength(1));
    expect(loadChats()[0].title).toContain("Lương tối thiểu");
  });

  it("shows the offline banner", async () => {
    stubFetch("offline");
    await ask();
    expect(await screen.findByText("Mô hình đang tắt — đang hiển thị điều luật liên quan")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nguồn S1:/ })).toBeInTheDocument();
  });

  it("explains a refusal", async () => {
    stubFetch("refused");
    await ask("Công thức bún bò?");
    expect(await screen.findByText(/Không tìm thấy căn cứ đủ liên quan/)).toBeInTheDocument();
  });

  it("warns about invalid citations and lists them", async () => {
    stubFetch("rag");
    await ask();
    const warning = await screen.findByText(/Một số trích dẫn có thể chưa chính xác/);
    expect(warning.parentElement).toHaveTextContent("S9");
  });

  it("sends feedback with the trace_id once", async () => {
    stubFetch("rag");
    const user = await ask();
    const up = await screen.findByRole("button", { name: "Câu trả lời hữu ích" });
    await waitFor(() => expect(up).toBeEnabled());
    await user.click(up);
    await waitFor(() => expect(feedbackBodies).toEqual([{ trace_id: "trace-rag-1", score: 1 }]));
    expect(up).toBeDisabled();
    expect(screen.getByRole("button", { name: "Câu trả lời chưa tốt" })).toBeDisabled();
  });

  it("shows Stop while streaming and stops", async () => {
    stubFetch((_n, signal) => {
      const enc = new TextEncoder();
      const stream = new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(enc.encode('data: {"type":"start","messageId":"m"}\n\n'));
          c.enqueue(enc.encode('data: {"type":"text-start","id":"t"}\n\n'));
          c.enqueue(enc.encode('data: {"type":"text-delta","id":"t","delta":"Đang"}\n\n'));
          signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(stream, { headers: { "content-type": "text/event-stream", "x-vercel-ai-ui-message-stream": "v1" } });
    });
    const user = await ask();
    const stop = await screen.findByRole("button", { name: "Dừng" });
    expect(screen.getByRole("textbox", { name: "Câu hỏi" })).toBeDisabled();
    await user.click(stop);
    expect(await screen.findByRole("button", { name: "Gửi" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Câu hỏi" })).toBeEnabled();
  });

  it("shows an inline error with Thử lại that regenerates", async () => {
    stubFetch((n) => mockChatResponse(n === 1 ? "error" : "rag"));
    const user = await ask();
    expect(await screen.findByText(/Kết nối tới mô hình bị gián đoạn/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText(/5\.310\.000/)).toBeInTheDocument();
    expect(chatCalls).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Thử lại" })).toBeNull();
  });

  it("limits input to 1000 characters and shows a counter near the limit", async () => {
    stubFetch("rag");
    render(<Chat />);
    const box = screen.getByRole("textbox", { name: "Câu hỏi" });
    expect(box).toHaveAttribute("maxlength", "1000");
    await userEvent.setup().click(box);
    await userEvent.paste("a".repeat(900));
    expect(screen.getByText("900/1000")).toBeInTheDocument();
  });
});

const sse = (...chunks: object[]) => chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`).join("");
const SSE_HEADERS = { "content-type": "text/event-stream", "x-vercel-ai-ui-message-stream": "v1" };
const openingChunks = sse(
  { type: "start", messageId: "m" },
  { type: "text-start", id: "t" },
  { type: "text-delta", id: "t", delta: "Phần trả lời dở" },
);

describe("Chat errors", () => {
  it("shows Vietnamese text for a dropped stream, keeps the partial answer and retries", async () => {
    stubFetch((n) => {
      if (n > 1) return mockChatResponse("rag");
      const enc = new TextEncoder();
      let sent = false;
      const stream = new ReadableStream<Uint8Array>({
        async pull(c) {
          if (sent) {
            await new Promise((r) => setTimeout(r, 50)); // để các chunk đã nhận kịp đi qua pipeline trước khi lỗi
            c.error(new TypeError("network error"));
          } else {
            c.enqueue(enc.encode(openingChunks));
            sent = true;
          }
        },
      });
      return new Response(stream, { headers: SSE_HEADERS });
    });
    const user = await ask();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Kết nối bị gián đoạn, vui lòng thử lại.");
    expect(alert).not.toHaveTextContent(/network/i);
    expect(screen.getByText("Phần trả lời dở")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText(/5\.310\.000/)).toBeInTheDocument();
    expect(screen.queryByText("Phần trả lời dở")).toBeNull();
  });

  it.each([
    [429, "Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút."],
    [503, "Cơ sở dữ liệu tạm thời không khả dụng, vui lòng thử lại sau."],
  ])("shows the backend detail for HTTP %i", async (status, detail) => {
    stubFetch(() => Response.json({ detail }, { status }));
    await ask();
    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });

  it("does not leak an HTML proxy error body", async () => {
    stubFetch(() => new Response("<html><body>502 Bad Gateway</body></html>", { status: 502 }));
    await ask();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Đã xảy ra lỗi, vui lòng thử lại.");
    expect(alert).not.toHaveTextContent(/Bad Gateway|html/i);
  });

  it("stops and offers a retry when no chunk arrives for 45 s, resetting on each chunk", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const enc = new TextEncoder();
      let controller!: ReadableStreamDefaultController<Uint8Array>;
      stubFetch((n, signal) => {
        if (n > 1) return mockChatResponse("rag");
        const stream = new ReadableStream<Uint8Array>({
          start(c) {
            controller = c;
            c.enqueue(enc.encode(openingChunks));
            signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
          },
        });
        return new Response(stream, { headers: SSE_HEADERS });
      });
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<Chat />);
      await user.type(screen.getByRole("textbox", { name: "Câu hỏi" }), "Hỏi{Enter}");
      await screen.findByText("Phần trả lời dở");
      await act(() => vi.advanceTimersByTimeAsync(40_000));
      expect(screen.queryByRole("alert")).toBeNull();
      controller.enqueue(enc.encode(sse({ type: "text-delta", id: "t", delta: " thêm" })));
      await screen.findByText(/thêm/);
      await act(() => vi.advanceTimersByTimeAsync(40_000)); // 80 s tổng nhưng chunk giữa chừng reset đồng hồ
      expect(screen.queryByRole("alert")).toBeNull();
      await act(() => vi.advanceTimersByTimeAsync(6_000));
      expect(await screen.findByRole("alert")).toHaveTextContent("Mô hình phản hồi quá lâu. Bạn có thể thử lại.");
      expect(screen.getByRole("button", { name: "Gửi" })).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Thử lại" }));
      expect(await screen.findByText(/5\.310\.000/)).toBeInTheDocument();
      expect(screen.queryByRole("alert")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("disables history and new conversation while streaming", async () => {
    stubFetch((_n, signal) => {
      const stream = new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(new TextEncoder().encode(openingChunks));
          signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(stream, { headers: SSE_HEADERS });
    });
    const user = await ask();
    await screen.findByRole("button", { name: "Dừng" });
    expect(screen.getByRole("button", { name: /Lịch sử/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Cuộc hội thoại mới/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Dừng" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Lịch sử/ })).toBeEnabled());
    expect(screen.getByRole("button", { name: /Cuộc hội thoại mới/ })).toBeEnabled();
  });

  it("ignores Enter while an IME composition is active", async () => {
    stubFetch("rag");
    render(<Chat />);
    const box = screen.getByRole("textbox", { name: "Câu hỏi" });
    fireEvent.change(box, { target: { value: "xin chào" } });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229 });
    fireEvent.keyDown(box, { key: "Enter", isComposing: true });
    expect(chatCalls).toHaveLength(0);
    fireEvent.keyDown(box, { key: "Enter" });
    await waitFor(() => expect(chatCalls).toHaveLength(1));
  });

  it("links the counter to the textarea without a live region", async () => {
    stubFetch("rag");
    render(<Chat />);
    const box = screen.getByRole("textbox", { name: "Câu hỏi" });
    const counter = document.getElementById(box.getAttribute("aria-describedby")!)!;
    expect(counter).not.toHaveAttribute("aria-live");
    await userEvent.setup().click(box);
    await userEvent.paste("a".repeat(850));
    expect(counter).toHaveTextContent("850/1000");
  });
});
