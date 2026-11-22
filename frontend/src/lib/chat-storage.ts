import { isChatMessage, type ChatMessage } from "./chat-types";

/** Lịch sử hội thoại trong localStorage. Mọi truy cập bọc try/catch: chế độ riêng tư hoặc đầy bộ nhớ thì không lưu, không lỗi. */
export const CHATS_KEY = "rag.chats.v1";
export const MAX_CHATS = 20;

export interface StoredChat {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
}

const isChat = (v: unknown): v is StoredChat => {
  const c = v as StoredChat | null;
  return !!c && typeof c.id === "string" && typeof c.title === "string" && typeof c.updatedAt === "number" && Array.isArray(c.messages) && c.messages.every(isChatMessage);
};

/** Mới nhất trước. */
export function loadChats(): StoredChat[] {
  try {
    const raw = localStorage.getItem(CHATS_KEY);
    const data: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(data) ? data.filter(isChat).sort((a, b) => b.updatedAt - a.updatedAt) : [];
  } catch {
    return [];
  }
}

function write(chats: StoredChat[]) {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
  } catch {
    // không lưu được: bỏ qua
  }
}

export function saveChat(chat: StoredChat) {
  write([chat, ...loadChats().filter((c) => c.id !== chat.id)].sort((a, b) => b.updatedAt - a.updatedAt));
}

export function deleteChat(id: string) {
  write(loadChats().filter((c) => c.id !== id));
}

export function clearChats() {
  try {
    localStorage.removeItem(CHATS_KEY);
  } catch {
    // bỏ qua
  }
}

export function newChatId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
