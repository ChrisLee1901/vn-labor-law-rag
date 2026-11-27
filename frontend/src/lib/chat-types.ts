import type { UIMessage } from "ai";
import type { CitationWarningData, StatusData, TraceData } from "./api-types";

/** UIMessage với các data part tùy biến của backend (docs/api-contract.md). */
export type ChatMessage = UIMessage<
  unknown,
  { status: StatusData; trace: TraceData; "citation-warning": CitationWarningData }
>;

export interface SourceItem {
  id: string; // S1..Sn
  url: string; // /van-ban/{code}#D{n}
  title: string;
}

export interface MessageInfo {
  text: string;
  sources: SourceItem[];
  status?: StatusData;
  traceId?: string;
  warning?: CitationWarningData;
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

/** Dữ liệu có thể đến từ localStorage đã hỏng: bỏ qua mọi part không đúng hình dạng thay vì ném lỗi. */
export function messageInfo(m: ChatMessage): MessageInfo {
  const info: MessageInfo = { text: "", sources: [] };
  if (!Array.isArray(m?.parts)) return info;
  for (const p of m.parts as unknown[]) {
    if (!isObj(p)) continue;
    const data = isObj(p.data) ? p.data : undefined;
    if (p.type === "text" && typeof p.text === "string") info.text += p.text;
    else if (p.type === "source-url" && typeof p.sourceId === "string" && typeof p.url === "string")
      info.sources.push({ id: p.sourceId, url: p.url, title: typeof p.title === "string" ? p.title : p.url });
    else if (p.type === "data-status" && data && typeof data.llm === "string" && typeof data.mode === "string")
      info.status = data as unknown as StatusData;
    else if (p.type === "data-trace" && data && typeof data.trace_id === "string") info.traceId = data.trace_id;
    else if (p.type === "data-citation-warning" && data)
      info.warning = { invalid: strings(data.invalid), mismatch: strings(data.mismatch) };
  }
  return info;
}

export function isChatMessage(v: unknown): v is ChatMessage {
  return isObj(v) && typeof v.id === "string" && (v.role === "user" || v.role === "assistant" || v.role === "system") && Array.isArray(v.parts) && v.parts.every(isObj);
}

export const userText = (m: ChatMessage) => messageInfo(m).text;
