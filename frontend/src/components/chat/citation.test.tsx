import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetDocsCache } from "@/lib/docs-cache";
import type { SourceItem } from "@/lib/chat-types";
import { AnswerMarkdown } from "./markdown";
import { CitationContext } from "./citation";

const sources: SourceItem[] = [
  { id: "S1", url: "/van-ban/ND293-2025#D3", title: "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu" },
  { id: "S2", url: "/van-ban/ND145-2020#D12", title: "145/2020/NĐ-CP, Điều 12. Hợp đồng lao động" },
];

beforeEach(() => {
  resetDocsCache();
  vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
});

const renderText = (text: string, onSelect = vi.fn()) =>
  render(
    <CitationContext.Provider value={{ sources, onSelect }}>
      <AnswerMarkdown text={text} />
    </CitationContext.Provider>,
  );

describe("Citation", () => {
  it('renders "[S2]" as a button labelled with the source number and title', () => {
    renderText("[S2]");
    const btn = screen.getByRole("button", { name: /145\/2020\/NĐ-CP, Điều 12/ });
    expect(btn).toHaveTextContent("S2");
    expect(btn).toHaveAccessibleName(expect.stringContaining("S2"));
  });

  it("renders an unknown source as plain muted text", () => {
    renderText("Xem [S9] thêm");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("[S9]")).toBeInTheDocument();
  });

  it("splits adjacent and comma lists into separate buttons", () => {
    renderText("a [S1][S2] b [S1, S2]");
    expect(screen.getAllByRole("button")).toHaveLength(4);
  });

  it("selects the source on click", async () => {
    const onSelect = vi.fn();
    renderText("Mức lương [S1].", onSelect);
    await userEvent.click(screen.getByRole("button", { name: /293\/2025/ }));
    expect(onSelect).toHaveBeenCalledWith("S1");
  });

  it("opens the hover card on keyboard focus with the article link", async () => {
    renderText("[S1]");
    await userEvent.tab();
    const link = await screen.findByRole("link", { name: /Xem điều luật/ });
    expect(link).toHaveAttribute("href", "/van-ban/ND293-2025#D3");
  });
});

describe("AnswerMarkdown safety", () => {
  it("renders markdown but never images or raw HTML, and hardens external links", () => {
    const { container } = renderText(
      "**đậm** ![x](http://evil/x.png) <script>alert(1)</script> [ngoài](https://example.com) [trong](/van-ban/BLLD#D1) [js](javascript:alert(1))",
    );
    expect(container.querySelector("strong")).toHaveTextContent("đậm");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    const ext = screen.getByRole("link", { name: "ngoài" });
    expect(ext).toHaveAttribute("target", "_blank");
    expect(ext).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "trong" })).toHaveAttribute("href", "/van-ban/BLLD#D1");
    expect(screen.queryByRole("link", { name: "js" })).toBeNull();
  });
});
