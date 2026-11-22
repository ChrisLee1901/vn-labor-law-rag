import { DefaultChatTransport } from "ai";
import type { ChatMessage } from "./chat-types";

export const MAX_HISTORY_MESSAGES = 10;
export const MAX_QUESTION_CHARS = 1000;

/** Body backend cần: chỉ `messages` (tối đa 10, chỉ part văn bản, tin cuối là user). `as_of` bỏ trống = hôm nay. */
export function toRequestMessages(messages: ChatMessage[]) {
  const slim = messages
    .map((m) => ({
      id: m.id,
      role: m.role,
      parts: m.parts.flatMap((p) => (p.type === "text" ? [{ type: "text" as const, text: p.text }] : [])),
    }))
    .filter((m) => m.role === "user" || m.parts.length > 0);
  while (slim.length && slim[slim.length - 1].role !== "user") slim.pop();
  return slim.slice(-MAX_HISTORY_MESSAGES);
}

export function createChatTransport(api: string) {
  return new DefaultChatTransport<ChatMessage>({
    api,
    prepareSendMessagesRequest: ({ messages }) => ({ body: { messages: toRequestMessages(messages) } }),
  });
}

export const CHAT_API = process.env.NEXT_PUBLIC_MOCK_CHAT === "1" ? "/api/mock/chat" : "/api/chat";

/** Lỗi HTTP có body `{detail}` được SDK đưa vào error.message dạng JSON: lấy `detail` cho người dùng. */
export function friendlyError(error: Error | undefined): string {
  const raw = error?.message ?? "";
  try {
    const detail = (JSON.parse(raw) as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  } catch {
    // không phải JSON
  }
  return raw || "Đã xảy ra lỗi, vui lòng thử lại.";
}
