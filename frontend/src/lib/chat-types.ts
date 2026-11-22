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

export function messageInfo(m: ChatMessage): MessageInfo {
  const info: MessageInfo = { text: "", sources: [] };
  for (const p of m.parts) {
    if (p.type === "text") info.text += p.text;
    else if (p.type === "source-url") info.sources.push({ id: p.sourceId, url: p.url, title: p.title ?? p.url });
    else if (p.type === "data-status") info.status = p.data;
    else if (p.type === "data-trace") info.traceId = p.data.trace_id;
    else if (p.type === "data-citation-warning") info.warning = p.data;
  }
  return info;
}

export const userText = (m: ChatMessage) => messageInfo(m).text;
