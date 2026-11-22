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

export const GENERIC_ERROR = "Đã xảy ra lỗi, vui lòng thử lại.";
export const NETWORK_ERROR = "Kết nối bị gián đoạn, vui lòng thử lại.";
export const STALL_ERROR = "Mô hình phản hồi quá lâu. Bạn có thể thử lại.";

/**
 * Chỉ trả văn bản tiếng Việt cho người dùng:
 * - body HTTP JSON có `detail` là chuỗi (SDK đưa body vào error.message) -> detail của backend;
 * - lỗi mạng/ngắt stream (TypeError, AbortError, "network error", "terminated"...) -> thông báo kết nối;
 * - `errorText` của part `error` do backend phát (ngắn, có chữ tiếng Việt) -> giữ nguyên;
 * - còn lại (HTML của proxy, văn bản tiếng Anh...) -> thông báo chung, không lộ nội dung thô.
 */
export function friendlyError(error: Error | undefined): string {
  const raw = (error?.message ?? "").trim();
  try {
    const detail = (JSON.parse(raw) as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return GENERIC_ERROR;
  } catch {
    // không phải JSON
  }
  if (error instanceof TypeError || error?.name === "AbortError" || /network|fetch|terminated|socket|econn|aborted/i.test(raw))
    return NETWORK_ERROR;
  if (raw && raw.length <= 200 && !raw.includes("<") && /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i.test(raw)) return raw;
  return GENERIC_ERROR;
}
