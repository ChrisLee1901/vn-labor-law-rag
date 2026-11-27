import { describe, expect, it } from "vitest";
import { messageInfo, type ChatMessage } from "./chat-types";

const msg = (parts: unknown[]) => ({ id: "m", role: "assistant", parts }) as unknown as ChatMessage;

describe("messageInfo", () => {
  it("tolerates null, odd and half-formed parts", () => {
    const info = messageInfo(
      msg([
        null,
        "x",
        { type: "text" },
        { type: "text", text: 5 },
        { type: "source-url", sourceId: "S1" },
        { type: "source-url", sourceId: "S2", url: "/van-ban/BLLD#D1" },
        { type: "data-status", data: null },
        { type: "data-trace", data: {} },
        { type: "data-citation-warning", data: { invalid: "S9" } },
        { type: "text", text: "ok" },
      ]),
    );
    expect(info.text).toBe("ok");
    expect(info.sources).toEqual([{ id: "S2", url: "/van-ban/BLLD#D1", title: "/van-ban/BLLD#D1" }]);
    expect(info.status).toBeUndefined();
    expect(info.traceId).toBeUndefined();
    expect(info.warning).toEqual({ invalid: [], mismatch: [] });
  });

  it("returns an empty info when parts is not an array", () => {
    expect(messageInfo({ id: "m", role: "user", parts: undefined } as unknown as ChatMessage)).toEqual({ text: "", sources: [] });
  });
});
