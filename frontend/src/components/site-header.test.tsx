import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SiteHeader } from "@/components/site-header";

vi.mock("next/navigation", () => ({ usePathname: () => "/van-ban/ND293-2025" }));
vi.mock("@/components/status-badge", () => ({ StatusBadge: () => <div role="status" /> }));

describe("SiteHeader", () => {
  it("hiển thị tên app và ba liên kết điều hướng", () => {
    render(<SiteHeader />);
    expect(screen.getByText("Trợ lý Pháp luật Lao động")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hỏi đáp" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Văn bản" })).toHaveAttribute("href", "/van-ban");
    expect(screen.getByRole("link", { name: "Giới thiệu" })).toHaveAttribute("href", "/gioi-thieu");
  });

  it("đánh dấu mục đang xem, kể cả trang con", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("link", { name: "Văn bản" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Hỏi đáp" })).not.toHaveAttribute("aria-current");
  });
});
