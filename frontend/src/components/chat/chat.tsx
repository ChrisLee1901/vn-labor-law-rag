"use client";

import { useChat } from "@ai-sdk/react";
import { Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { saveChat, newChatId, type StoredChat } from "@/lib/chat-storage";
import { CHAT_API, STALL_ERROR, createChatTransport, friendlyError } from "@/lib/chat-transport";
import { messageInfo, userText, type ChatMessage } from "@/lib/chat-types";
import { useMediaQuery } from "@/lib/use-media-query";
import { Composer } from "./composer";
import { HistorySheet } from "./history-sheet";
import { AssistantMessage, UserMessage } from "./message-view";
import { SourcesPanel } from "./sources-panel";
import { SuggestedQuestions } from "./suggested-questions";

/** Không có chunk nào trong ngần này thời gian khi đang stream thì coi là treo. */
export const STALL_MS = 45_000;

interface Selection {
  messageId: string;
  sourceId?: string;
}

/** Vỏ chọn hội thoại: đổi hội thoại = dựng lại phiên với id mới (key). */
export function Chat() {
  const [session, setSession] = useState<{ id: string; messages: ChatMessage[] }>(() => ({ id: newChatId(), messages: [] }));
  return (
    <ChatSession
      key={session.id}
      id={session.id}
      initialMessages={session.messages}
      onOpen={(c: StoredChat) => setSession({ id: c.id, messages: c.messages })}
      onNew={() => setSession({ id: newChatId(), messages: [] })}
    />
  );
}

interface SessionProps {
  id: string;
  initialMessages: ChatMessage[];
  onOpen: (c: StoredChat) => void;
  onNew: () => void;
}

function ChatSession({ id, initialMessages, onOpen, onNew }: SessionProps) {
  const transport = useMemo(() => createChatTransport(CHAT_API), []);
  const { messages, sendMessage, status, stop, regenerate, error } = useChat<ChatMessage>({
    id,
    messages: initialMessages,
    transport,
  });
  const busy = status === "submitted" || status === "streaming";
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const [selection, setSelection] = useState<Selection | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [stalled, setStalled] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true); // đang ở cuối trang thì tự cuộn theo stream
  const dirty = useRef(false); // chỉ lưu lịch sử khi người dùng đã hỏi trong phiên này
  const wasBusy = useRef(false);

  // Nguồn của tin được chọn (mặc định: tin trả lời mới nhất có nguồn).
  const lastWithSources = [...messages].reverse().find((m) => m.role === "assistant" && messageInfo(m).sources.length > 0);
  const selected = messages.find((m) => m.id === selection?.messageId) ?? lastWithSources;
  const sources = selected ? messageInfo(selected).sources : [];
  const activeSourceId = selected && selection?.messageId === selected.id ? selection.sourceId : undefined;

  useEffect(() => {
    if (busy || !dirty.current || messages.length === 0) return;
    const first = messages.find((m) => m.role === "user");
    saveChat({ id, title: (first ? userText(first) : "Cuộc hội thoại").slice(0, 60), updatedAt: Date.now(), messages });
  }, [busy, messages, id]);

  // Đồng hồ treo: dựng lại mỗi khi `messages` đổi (mỗi part mới) hoặc trạng thái đổi.
  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => {
      stop();
      setStalled(true);
    }, STALL_MS);
    return () => clearTimeout(t);
  }, [busy, messages, stop]);

  useEffect(() => {
    const onScroll = () => {
      stick.current = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (stick.current) endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, status]);

  // Ô nhập bị khóa khi stream nên mất focus: trả focus về khi xong, nếu người dùng chưa chuyển đi nơi khác.
  useEffect(() => {
    if (wasBusy.current && !busy && (!document.activeElement || document.activeElement === document.body)) inputRef.current?.focus();
    wasBusy.current = busy;
  }, [busy]);

  function send(text: string) {
    dirty.current = true;
    stick.current = true;
    setStalled(false);
    setSelection(null);
    void sendMessage({ text });
  }

  function retry() {
    dirty.current = true;
    setStalled(false);
    setSelection(null);
    void regenerate();
  }

  const last = messages.at(-1);
  const empty = messages.length === 0;
  const finished = !busy && !error && last?.role === "assistant";

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-8">
      <div className="flex min-w-0 flex-col">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          {empty ? (
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold sm:text-3xl">Hỏi đáp pháp luật lao động</h1>
              <p className="max-w-(--measure) text-muted-foreground">
                Đặt câu hỏi về hợp đồng, tiền lương, thời giờ làm việc, kỷ luật và bảo hiểm xã hội. Mỗi câu trả lời dẫn tới điều luật cụ thể để bạn đối chiếu.
              </p>
            </div>
          ) : (
            <h1 className="sr-only">Hỏi đáp pháp luật lao động</h1>
          )}
          <div className="ml-auto flex shrink-0 gap-2">
            <HistorySheet disabled={busy} currentId={id} onOpen={onOpen} onDeleted={(deleted) => deleted === id && onNew()} />
            <Button type="button" variant="outline" size="sm" disabled={empty || busy} onClick={onNew}>
              <Plus /> Cuộc hội thoại mới
            </Button>
          </div>
        </div>

        {empty ? (
          <div className="space-y-4 pb-6">
            <SuggestedQuestions onPick={send} />
            <p className="max-w-(--measure) text-sm text-muted-foreground">
              Mô hình trả lời được chạy tạm thời và có thể ngoại tuyến ngoài giờ demo; khi đó hệ thống chỉ hiển thị các điều luật liên quan nhất.
            </p>
          </div>
        ) : (
          <div className="space-y-8 pb-6" aria-busy={busy}>
            {messages.map((m, i) =>
              m.role === "user" ? (
                <UserMessage key={m.id} message={m} />
              ) : (
                <AssistantMessage
                  key={m.id}
                  message={m}
                  pending={busy && i === messages.length - 1}
                  activeSourceId={selected?.id === m.id ? activeSourceId : undefined}
                  onSelectSource={(messageId, sourceId) => {
                    setSelection({ messageId, sourceId });
                    if (!isDesktop) setSheetOpen(true);
                  }}
                  onOpenSources={(messageId) => {
                    setSelection({ messageId });
                    setSheetOpen(true);
                  }}
                />
              ),
            )}
            {busy && last?.role === "user" && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner /> Đang tìm điều luật liên quan…
              </p>
            )}
            {(error || stalled) && !busy && (
              <div role="alert" className="flex max-w-(--measure) flex-wrap items-center gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <span className="min-w-0 flex-1">{stalled ? STALL_ERROR : friendlyError(error)}</span>
                <Button type="button" size="sm" variant="outline" onClick={retry}>
                  Thử lại
                </Button>
              </div>
            )}
            <div ref={endRef} className="scroll-mb-48" />
          </div>
        )}

        <p role="status" aria-live="polite" className="sr-only">
          {finished ? "Đã có câu trả lời mới." : ""}
        </p>

        <div className="sticky bottom-0 mt-auto bg-background pt-2 pb-4">
          <Composer busy={busy} onSend={send} onStop={stop} inputRef={inputRef} />
        </div>
      </div>

      <aside aria-label="Nguồn trích dẫn" className="hidden lg:block">
        <div className="sticky top-6 space-y-3">
          <h2 className="text-base font-semibold">Nguồn{sources.length > 0 && ` (${sources.length})`}</h2>
          <SourcesPanel sources={sources} activeId={activeSourceId} />
        </div>
      </aside>

      <Sheet open={sheetOpen && !isDesktop} onOpenChange={setSheetOpen}>
        <SheetContent side="bottom" className="max-h-[75vh]">
          <SheetHeader>
            <SheetTitle>Nguồn ({sources.length})</SheetTitle>
          </SheetHeader>
          <div className="min-h-0 overflow-y-auto px-4 pb-4">
            <SourcesPanel sources={sources} activeId={activeSourceId} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
