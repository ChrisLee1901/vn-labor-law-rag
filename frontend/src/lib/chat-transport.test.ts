import { describe, expect, it } from "vitest";
import type { ChatMessage } from "./chat-types";
import { toRequestMessages } from "./chat-transport";

const user = (i: number): ChatMessage => ({ id: `u${i}`, role: "user", parts: [{ type: "text", text: `q${i}` }] });
const bot = (i: number): ChatMessage => ({
  id: `a${i}`,
  role: "assistant",
  parts: [
    { type: "data-status", data: { llm: "online", mode: "rag" } },
    { type: "source-url", sourceId: "S1", url: "/van-ban/BLLD#D1", title: "t" },
    { type: "text", text: `r${i}` },
  ],
});

describe("toRequestMessages", () => {
  it("keeps only text parts and caps to the last 10 messages", () => {
    const msgs = Array.from({ length: 8 }, (_, i) => [user(i), bot(i)]).flat().concat(user(9));
    const out = toRequestMessages(msgs);
    expect(out).toHaveLength(10);
    expect(out.at(-1)?.role).toBe("user");
    expect(out.every((m) => m.parts.every((p) => p.type === "text"))).toBe(true);
  });

  it("drops a trailing assistant message and empty assistant shells", () => {
    const shell: ChatMessage = { id: "s", role: "assistant", parts: [{ type: "data-status", data: { llm: "online", mode: "rag" } }] };
    expect(toRequestMessages([user(1), shell]).map((m) => m.id)).toEqual(["u1"]);
    expect(toRequestMessages([user(1), bot(1)]).map((m) => m.id)).toEqual(["u1"]);
  });
});
