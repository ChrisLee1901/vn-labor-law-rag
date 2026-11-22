import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DETAIL, DOCS } from "@/mocks/docs";

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

import { notFound } from "next/navigation";
import DocPage, { generateMetadata } from "./[code]/page";
import DocsPage from "./page";

const reply = (status: number, body?: unknown) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 22));
  vi.stubEnv("API_ORIGIN", "https://api.test");
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

describe("/van-ban", () => {
  it("renders a card per document with badge, type and article count, effective first", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, DOCS)));
    render(await DocsPage());
    const cards = screen.getAllByRole("listitem");
    expect(cards).toHaveLength(3);
    expect(cards.map((c) => within(c).getByRole("link").getAttribute("href"))).toEqual([
      "/van-ban/BLLD",
      "/van-ban/ND399-2026",
      "/van-ban/ND145-2020",
    ]);
    expect(within(cards[0]).getByText("Đang hiệu lực")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Văn bản hợp nhất")).toBeInTheDocument();
    expect(within(cards[0]).getByText(/220/)).toBeInTheDocument();
    expect(within(cards[1]).getByText("Chưa hiệu lực (từ 01/03/2027)")).toBeInTheDocument();
    expect(within(cards[2]).getByText("Hết hiệu lực")).toBeInTheDocument();
    expect(within(cards[2]).getByText("145/2020/NĐ-CP")).toBeInTheDocument();
  });

  it("shows a friendly error card with a retry link when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(await DocsPage());
    expect(screen.getByText("Không tải được danh sách văn bản. Vui lòng thử lại sau.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Thử lại" })).toHaveAttribute("href", "/van-ban");
  });

  it("shows a distinct message (not the error card) for an empty list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, [])));
    render(await DocsPage());
    expect(screen.getByText("Chưa có văn bản nào.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("/van-ban/[code]", () => {
  const params = (code: string) => ({ params: Promise.resolve({ code }) });

  it("renders articles with anchors that match chat source links, plus a TOC", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => (url.endsWith("/api/docs") ? reply(200, DOCS) : reply(200, DETAIL))));
    const { container } = render(await DocPage(params("ND145-2020")));
    for (const id of ["D1", "D12", "D12a", "D20", "PL1"]) expect(container.querySelector(`article#${id}`)).not.toBeNull();
    expect(container.querySelector("article#D12 h3")).toHaveTextContent("Điều 12. Hợp đồng lao động");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Quy định chi tiết một số điều của Bộ luật Lao động");
    expect(screen.queryByRole("heading", { name: "Chương II. Tiền lương", level: 2 })).toBeInTheDocument();
    const toc = screen.getAllByRole("navigation", { name: "Mục lục" })[0];
    expect(within(toc).queryAllByRole("heading")).toHaveLength(0);
    expect(within(toc).getByRole("link", { name: /Điều 20\. Tiền lương/ })).toHaveAttribute("href", "#D20");
    expect(within(toc).getByRole("link", { name: /Phụ lục 1/ })).toHaveAttribute("href", "#PL1");
    expect(within(toc).getByText("Chương II. Tiền lương")).toBeInTheDocument();
  });

  it("renders content as plain text, never as HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => (url.endsWith("/api/docs") ? reply(200, DOCS) : reply(200, DETAIL))));
    const { container } = render(await DocPage(params("ND145-2020")));
    expect(container.querySelector("article#D12 b")).toBeNull();
    expect(container.querySelector("article#D12")).toHaveTextContent("<b>không phải HTML</b> **không phải markdown**");
  });

  it("shows the badge, source link and the replacing document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) =>
        url.endsWith("/api/docs") ? reply(200, [...DOCS, { ...DOCS[0], code: "ND293-2025", number: "293/2025/NĐ-CP" }]) : reply(200, DETAIL),
      ),
    );
    render(await DocPage(params("ND145-2020")));
    expect(screen.getByText("Hết hiệu lực")).toBeInTheDocument();
    const src = screen.getByRole("link", { name: /Nguồn/ });
    expect(src).toHaveAttribute("href", "https://example.gov.vn/nd145");
    expect(src).toHaveAttribute("rel", "noopener noreferrer");
    const rep = screen.getByRole("link", { name: "293/2025/NĐ-CP" });
    expect(rep).toHaveAttribute("href", "/van-ban/ND293-2025");
    expect(screen.getByText(/Được thay thế bởi/)).toBeInTheDocument();
  });

  it("only offers an http(s) source link", async () => {
    const bad = { ...DETAIL, doc: { ...DETAIL.doc, source_url: "javascript:alert(1)" } };
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => (url.endsWith("/api/docs") ? reply(200, DOCS) : reply(200, bad))));
    render(await DocPage(params("ND145-2020")));
    expect(screen.queryByRole("link", { name: /Nguồn/ })).toBeNull();
  });

  it("calls notFound for a malformed code without fetching", async () => {
    const f = vi.fn();
    vi.stubGlobal("fetch", f);
    await expect(DocPage(params("a/../b"))).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalled();
    expect(f).not.toHaveBeenCalled();
  });

  it("calls notFound when the API answers 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(404, { detail: "Không tìm thấy văn bản." })));
    await expect(DocPage(params("NOPE"))).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("shows an error card (not a crash) when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    render(await DocPage(params("BLLD")));
    expect(screen.getByText(/Không tải được văn bản/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Thử lại" })).toHaveAttribute("href", "/van-ban/BLLD");
  });

  it("builds metadata from the document", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, DETAIL)));
    const m = await generateMetadata(params("ND145-2020"));
    expect(m.title).toBe("145/2020/NĐ-CP — Văn bản");
    expect(String(m.description)).toContain("Bộ luật Lao động");
  });
});
