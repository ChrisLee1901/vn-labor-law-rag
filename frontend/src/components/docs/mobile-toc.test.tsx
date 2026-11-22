import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MobileToc } from "./mobile-toc";

describe("MobileToc", () => {
  it("closes after a link is clicked", async () => {
    const { container } = render(
      <MobileToc>
        <a href="#D1">Điều 1</a>
      </MobileToc>,
    );
    const details = container.querySelector("details")!;
    details.open = true;
    await userEvent.click(screen.getByRole("link", { name: "Điều 1" }));
    expect(details.open).toBe(false);
  });
});
