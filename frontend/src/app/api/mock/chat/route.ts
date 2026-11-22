import { mockChatResponse, mockKindFor } from "@/mocks/chat-stream";
import type { ChatMessage } from "@/lib/chat-types";
import { userText } from "@/lib/chat-types";

/** Chỉ dùng khi dev với NEXT_PUBLIC_MOCK_CHAT=1; production trả 404. */
export async function POST(req: Request) {
  if (process.env.NODE_ENV === "production") return new Response("Not found", { status: 404 });
  const body = (await req.json().catch(() => ({}))) as { messages?: ChatMessage[] };
  const last = body.messages?.at(-1);
  return mockChatResponse(mockKindFor(last ? userText(last) : ""));
}
