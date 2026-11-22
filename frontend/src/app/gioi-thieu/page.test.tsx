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
  golden: { n_test: 80 },
  ablation: [
    { mode: "fts", hit_rate_at_1: 0.2, recall_at_5: 0.3, recall_at_10: 0.4, recall_at_20: 0.5, mrr_at_10: 0.25, ndcg_at_10: 0.3 },
    { mode: "hybrid", hit_rate_at_1: 0.41234, recall_at_5: 0.6, recall_at_10: 0.7, recall_at_20: 0.8, mrr_at_10: 0.5, ndcg_at_10: 0.55 },
  ],
  answers: { citation_precision: 0.9, citation_recall: 0.8, numeric_match: 0.7, refusal_accuracy: 0.95, injection_resisted: 1 },
  latency: { ttft_p50_s: 1.234, ttft_p95_s: 2.5, total_p50_s: 8, total_p95_s: 15.75 },
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
    expect(screen.getByText(/80 câu thuộc split test/)).toBeInTheDocument();
    expect(screen.getByText(/mô hình sinh câu trả lời Qwen3-8B Q5_K_M/)).toBeInTheDocument();
  });

  it("omits the answer and latency blocks when the run had no such data", () => {
    state.value = { status: "ready", golden: { n_test: 80 }, ablation: READY.ablation };
    render(<AboutPage />);
    expect(screen.getAllByRole("table")).toHaveLength(1);
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
