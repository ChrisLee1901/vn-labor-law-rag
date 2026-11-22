import { render, screen, waitFor, within } from "@testing-library/react";
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
