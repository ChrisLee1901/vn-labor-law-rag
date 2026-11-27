import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourcesPanel } from "./sources-panel";

describe("SourcesPanel", () => {
  it("links only well-formed source urls", () => {
    render(
      <SourcesPanel
        sources={[
          { id: "S1", url: "/van-ban/ND293-2025#D3", title: "Hợp lệ" },
          { id: "S2", url: "javascript:alert(1)", title: "Tiêm mã" },
          { id: "S3", url: "//evil.com#D1", title: "Ngoài" },
          { id: "S4", url: "/van-ban/../admin#D1", title: "Đi lên" },
        ]}
      />,
    );
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/van-ban/ND293-2025#D3");
    expect(screen.getByText("Tiêm mã")).toBeInTheDocument();
  });
});
