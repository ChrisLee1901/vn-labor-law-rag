import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearChats, deleteChat, loadChats, newChatId, saveChat, type StoredChat } from "./chat-storage";

const chat = (id: string, updatedAt: number): StoredChat => ({
  id,
  title: `Chat ${id}`,
  updatedAt,
  messages: [{ id: "m", role: "user", parts: [{ type: "text", text: "hi" }] }],
});

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("chat-storage", () => {
  it("saves, loads newest first, replaces by id and deletes", () => {
    saveChat(chat("a", 1));
    saveChat(chat("b", 2));
    saveChat({ ...chat("a", 3), title: "A2" });
    expect(loadChats().map((c) => c.id)).toEqual(["a", "b"]);
    expect(loadChats()[0].title).toBe("A2");
    deleteChat("a");
    expect(loadChats().map((c) => c.id)).toEqual(["b"]);
    clearChats();
    expect(loadChats()).toEqual([]);
  });

  it("keeps at most 20 conversations, dropping the oldest", () => {
    for (let i = 1; i <= 25; i++) saveChat(chat(`c${i}`, i));
    const all = loadChats();
    expect(all).toHaveLength(20);
    expect(all[0].id).toBe("c25");
    expect(all[19].id).toBe("c6");
  });

  it("does not crash when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(loadChats()).toEqual([]);
    expect(() => saveChat(chat("a", 1))).not.toThrow();
    expect(() => deleteChat("a")).not.toThrow();
    expect(() => clearChats()).not.toThrow();
  });

  it("ignores corrupt stored data", () => {
    localStorage.setItem("rag.chats.v1", "{not json");
    expect(loadChats()).toEqual([]);
    localStorage.setItem("rag.chats.v1", JSON.stringify([{ id: 1 }, null, "x"]));
    expect(loadChats()).toEqual([]);
  });

  it("silently drops chats whose messages are malformed", () => {
    const good = chat("good", 5);
    const bad = [
      { ...chat("b1", 4), messages: [null] },
      { ...chat("b2", 3), messages: [{ id: "m", role: "robot", parts: [] }] },
      { ...chat("b3", 2), messages: [{ id: "m", role: "user", parts: "x" }] },
      { ...chat("b4", 1), messages: [{ role: "user", parts: [] }] },
    ];
    localStorage.setItem("rag.chats.v1", JSON.stringify([good, ...bad]));
    expect(loadChats().map((c) => c.id)).toEqual(["good"]);
  });

  it("generates distinct ids", () => {
    expect(newChatId()).not.toBe(newChatId());
  });
});
