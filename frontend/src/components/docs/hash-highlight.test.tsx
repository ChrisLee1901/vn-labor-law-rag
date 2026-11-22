import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HashHighlight } from "./hash-highlight";

afterEach(() => {
  vi.useRealTimers();
  history.replaceState(null, "", "/");
  document.body.innerHTML = "";
});

describe("HashHighlight", () => {
  it("marks the targeted article active for a few seconds", () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<article id="D12"></article>';
    history.replaceState(null, "", "/van-ban/X#D12");
    const el = document.getElementById("D12")!;
    el.scrollIntoView = vi.fn();
    render(<HashHighlight />);
    expect(el.dataset.active).toBe("true");
    expect(el.scrollIntoView).toHaveBeenCalled();
    vi.advanceTimersByTime(3100);
    expect(el.dataset.active).toBeUndefined();
  });
  it("ignores unknown or malformed hashes", () => {
    history.replaceState(null, "", "/van-ban/X#%E0%A4%A");
    expect(() => render(<HashHighlight />)).not.toThrow();
  });
});
