import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EvalContent } from "@/content/eval-types";

const state = vi.hoisted(() => ({ value: { status: "pending" } as EvalContent }));
vi.mock("@/content/eval.json", () => ({
  get default() {
    return state.value;
  },
}));

import { ArchitectureDiagram } from "@/components/about/architecture-diagram";
import AboutPage from "./page";

const READY: EvalContent = {
  status: "ready",
  generatedAt: "2026-12-01T00:00:00.000Z",
  model: "Qwen3-8B Q5_K_M",
  retrieval: { n_queries: 68 },
  ablation: [
    { mode: "fts", hit_rate_at_1: 0.2, recall_at_5: 0.3, recall_at_10: 0.4, recall_at_20: 0.5, mrr_at_10: 0.25, ndcg_at_10: 0.3 },
    { mode: "hybrid", hit_rate_at_1: 0.41234, recall_at_5: 0.6, recall_at_10: 0.7, recall_at_20: 0.8, mrr_at_10: 0.5, ndcg_at_10: 0.55 },
  ],
  answers: {
    n_queries: 80,
    n_failed: 2,
    citation_precision: 0.9,
    citation_recall: 0.8,
    numeric_match: 0.7,
    refusal_accuracy: 0.95,
    injection_resisted: 1,
    denominators: { citation_precision: 143, citation_recall: 64, numeric_match: 17, refusal_accuracy: 76, injection_resisted: 4 },
  },
  latency: { n_queries: 40, ttft_p50_s: 1.234, ttft_p95_s: 2.5, total_p50_s: 8, total_p95_s: 15.75 },
};

afterEach(() => {
  state.value = { status: "pending" };
  vi.unstubAllEnvs();
});

describe("/gioi-thieu", () => {
  it("shows the pending note, the methodology and no table or number while results are pending", () => {
    render(<AboutPage />);
    expect(screen.getByText("Kết quả đánh giá sẽ được công bố sau lần chạy đầu tiên khi mô hình trực tuyến.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    // answer/latency metric definitions are provisional: hidden until real results carry them
    for (const t of [/Độ chính xác trích dẫn/, /Khớp số liệu/, /Từ chối đúng/, /Chống injection/, /TTFT là thời gian/]) expect(screen.queryByText(t)).toBeNull();
    expect(screen.getByText(/Tỷ lệ Điều đúng \(gold\) nằm trong k kết quả đầu/)).toBeInTheDocument();
    expect(screen.getByText(/Bộ câu hỏi vàng gồm 120 câu/)).toBeInTheDocument();
    expect(screen.getByText(/chưa có người kiểm/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Kết quả đánh giá" })).toBeInTheDocument();
  });

  it("renders every section as a heading", () => {
    render(<AboutPage />);
    const names = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(names).toEqual([
      "Mục tiêu",
      "Kiến trúc",
      "Vì sao tự host LLM trên Kaggle",
      "Chế độ ngoại tuyến",
      "Kết quả đánh giá",
      "Giới hạn đã biết",
      "Mã nguồn và tài liệu",
    ]);
  });

  it("renders the ablation table with 3-decimal numbers and the latency and answer blocks when ready", () => {
    state.value = READY;
    render(<AboutPage />);
    expect(screen.queryByText(/sẽ được công bố sau/)).toBeNull();
    const ablation = screen.getByRole("table", { name: /Ablation/ });
    const rows = within(ablation).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[2]).getAllByRole("cell").map((c) => c.textContent)).toEqual(["0.412", "0.600", "0.700", "0.800", "0.500", "0.550"]);
    expect(within(rows[2]).getByRole("rowheader")).toHaveTextContent("Hybrid RRF");
    const latency = screen.getByRole("table", { name: /Độ trễ/ });
    expect(within(latency).getByText("1.23 s")).toBeInTheDocument();
    expect(within(latency).getByText("15.75 s")).toBeInTheDocument();
    const answers = screen.getByRole("table", { name: /Chất lượng câu trả lời/ });
    expect(within(answers).getByText("0.950")).toBeInTheDocument();
    // mỗi khối ghi số câu của chính nó, truy xuất chỉ đếm câu có gold
    expect(within(ablation).getByText(/68 câu có đáp án \(gold\) trong split test/)).toBeInTheDocument();
    expect(within(answers).getByText(/80 câu trong split test/)).toBeInTheDocument();
    expect(within(latency).getByText(/40 câu trong split test/)).toBeInTheDocument();
    expect(within(answers).getByText(/2 câu lỗi tính là sai/)).toBeInTheDocument();
    const injection = within(answers).getByRole("row", { name: /Chống prompt injection/ });
    expect(within(injection).getAllByRole("cell").map((c) => c.textContent)).toEqual(["1.000", "4"]);
    expect(within(within(answers).getByRole("row", { name: /Khớp số liệu/ })).getAllByRole("cell").map((c) => c.textContent)).toEqual(["0.700", "17"]);
    expect(screen.getByText(/mọi mã \[S#\] mà câu trả lời nêu ra/)).toBeInTheDocument();
    expect(screen.getByText(/cận trên của khả năng chống injection/)).toBeInTheDocument();
    expect(screen.getByText(/TTFT là thời gian từ lúc gửi câu hỏi/)).toBeInTheDocument();
    expect(screen.getByText(/Mô hình sinh câu trả lời: Qwen3-8B Q5_K_M/)).toBeInTheDocument();
  });

  it("omits the answer and latency blocks when the run had no such data", () => {
    state.value = { status: "ready", retrieval: { n_queries: 68 }, ablation: READY.ablation };
    render(<AboutPage />);
    expect(screen.getAllByRole("table")).toHaveLength(1);
    // retrieval-only run: no glossary rows for metrics that were not produced
    expect(screen.getByText(/Tỷ lệ Điều đúng \(gold\) nằm trong k kết quả đầu/)).toBeInTheDocument();
    expect(screen.queryByText(/Độ chính xác trích dẫn/)).toBeNull();
    expect(screen.queryByText(/TTFT là thời gian/)).toBeNull();
  });

  it("links to the repo only when NEXT_PUBLIC_REPO_URL is set", () => {
    vi.stubEnv("NEXT_PUBLIC_REPO_URL", "");
    const { unmount } = render(<AboutPage />);
    expect(screen.queryByRole("link", { name: /GitHub/ })).toBeNull();
    unmount();
    vi.stubEnv("NEXT_PUBLIC_REPO_URL", "https://github.com/x/real_rag");
    render(<AboutPage />);
    expect(screen.getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", "https://github.com/x/real_rag");
    expect(screen.getByRole("link", { name: "Văn bản pháp luật" })).toHaveAttribute("href", "/van-ban");
    expect(screen.getByRole("link", { name: /congbao\.chinhphu\.vn/ })).toHaveAttribute("href", "https://congbao.chinhphu.vn");
  });
});

describe("ArchitectureDiagram", () => {
  it("has an accessible name and description", () => {
    render(<ArchitectureDiagram />);
    const img = screen.getByRole("img", { name: /Sơ đồ kiến trúc/ });
    expect(img).toHaveAccessibleDescription(/Supabase/);
  });
});
