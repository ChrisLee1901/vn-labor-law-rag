import { describe, expect, it } from "vitest";
import { friendlyError } from "./chat-transport";

const GENERIC = "Đã xảy ra lỗi, vui lòng thử lại.";
const NETWORK = "Kết nối bị gián đoạn, vui lòng thử lại.";

describe("friendlyError", () => {
  it("returns the backend detail only for a JSON body with a string detail", () => {
    expect(friendlyError(new Error('{"detail":"Bạn hỏi hơi nhanh."}'))).toBe("Bạn hỏi hơi nhanh.");
    expect(friendlyError(new Error('{"detail":42}'))).toBe(GENERIC);
  });

  it("maps network-like errors to a Vietnamese message", () => {
    for (const e of [new TypeError("network error"), new TypeError("terminated"), new TypeError("Failed to fetch"), new DOMException("x", "AbortError")])
      expect(friendlyError(e as Error)).toBe(NETWORK);
  });

  it("keeps Vietnamese stream error text and hides everything else", () => {
    expect(friendlyError(new Error("Mô hình trả lời quá lâu, vui lòng thử lại."))).toBe("Mô hình trả lời quá lâu, vui lòng thử lại.");
    expect(friendlyError(new Error("<html>502 Bad Gateway</html>"))).toBe(GENERIC);
    expect(friendlyError(new Error("Bad Gateway"))).toBe(GENERIC);
    expect(friendlyError(undefined)).toBe(GENERIC);
  });
});
