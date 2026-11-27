"use client";

import { AlertTriangle, BookOpen, Copy, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import { Message, MessageContent } from "@/components/ui/message";
import { Spinner } from "@/components/ui/spinner";
import { messageInfo, type ChatMessage } from "@/lib/chat-types";
import { AnswerMarkdown } from "./markdown";
import { CitationContext } from "./citation";
import { Feedback } from "./feedback";

export function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <Message align="end">
      <MessageContent>
        <Bubble variant="secondary" align="end" className="max-w-[90%] sm:max-w-[80%]">
          <BubbleContent className="rounded-md px-3 py-2 text-base whitespace-pre-wrap">{messageInfo(message).text}</BubbleContent>
        </Bubble>
      </MessageContent>
    </Message>
  );
}

function Banner({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <p className="flex max-w-(--measure) items-start gap-2 rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
      <span aria-hidden className="mt-0.5 shrink-0">
        {icon}
      </span>
      <span>{children}</span>
    </p>
  );
}

interface AssistantProps {
  message: ChatMessage;
  /** Đang chờ hoặc đang nhận stream của tin này. */
  pending: boolean;
  activeSourceId?: string;
  onSelectSource: (messageId: string, sourceId: string) => void;
  onOpenSources: (messageId: string) => void;
}

export function AssistantMessage({ message, pending, activeSourceId, onSelectSource, onOpenSources }: AssistantProps) {
  const { text, sources, status, traceId, warning } = messageInfo(message);
  const invalid = warning ? [...new Set([...warning.invalid, ...warning.mismatch])] : [];

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Đã sao chép câu trả lời.");
    } catch {
      toast.error("Không sao chép được, hãy chọn và sao chép thủ công.");
    }
  }

  return (
    <Message>
      <MessageContent className="gap-3">
        {status?.mode === "offline" && (
          <Banner icon={<WifiOff className="size-4" />}>Mô hình đang tắt — đang hiển thị điều luật liên quan</Banner>
        )}
        {status?.mode === "refused" && (
          <Banner icon={<AlertTriangle className="size-4" />}>
            Không tìm thấy căn cứ đủ liên quan trong các văn bản hiện có. Hãy thử diễn đạt khác hoặc nêu rõ Điều/văn bản.
          </Banner>
        )}
        <CitationContext.Provider
          value={{ sources, activeId: activeSourceId, onSelect: (id) => onSelectSource(message.id, id) }}
        >
          {text ? <AnswerMarkdown text={text} /> : null}
        </CitationContext.Provider>
        {pending && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> {text ? "Đang trả lời…" : "Đang tìm điều luật liên quan…"}
          </p>
        )}
        {!pending && warning && (
          <p className="max-w-(--measure) text-sm text-muted-foreground">
            <span className="font-medium">Một số trích dẫn có thể chưa chính xác</span> — hãy kiểm tra lại với văn bản gốc.
            {invalid.length > 0 && <> (Không khớp: {invalid.join(", ")}.)</>}
          </p>
        )}
        {!pending && (
          <div className="-ml-2 flex flex-wrap items-center gap-1">
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Sao chép câu trả lời" onClick={copy}>
              <Copy />
            </Button>
            <Feedback traceId={traceId} />
            {sources.length > 0 && (
              <Button type="button" variant="ghost" size="sm" className="lg:hidden" onClick={() => onOpenSources(message.id)}>
                <BookOpen /> Nguồn ({sources.length})
              </Button>
            )}
          </div>
        )}
      </MessageContent>
    </Message>
  );
}
