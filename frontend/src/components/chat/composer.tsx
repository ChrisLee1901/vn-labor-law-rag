"use client";

import { SendHorizontal, Square } from "lucide-react";
import { useState, type KeyboardEvent, type Ref } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MAX_QUESTION_CHARS } from "@/lib/chat-transport";

interface Props {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  inputRef?: Ref<HTMLTextAreaElement>;
}

/** Enter gửi, Shift+Enter xuống dòng. Bỏ qua Enter khi đang gõ tiếng Việt qua IME (Telex/VNI). */
export function Composer({ busy, onSend, onStop, inputRef }: Props) {
  const [value, setValue] = useState("");
  const trimmed = value.trim();

  function submit() {
    if (!trimmed || busy) return;
    onSend(trimmed);
    setValue("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // keyCode 229: Safari/Chrome cũ phát Enter của IME với isComposing=false.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-1"
    >
      <div className="flex items-end gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Câu hỏi
        </label>
        <Textarea
          id="chat-input"
          ref={inputRef}
          value={value}
          maxLength={MAX_QUESTION_CHARS}
          disabled={busy}
          rows={1}
          aria-describedby="chat-input-count"
          placeholder="Nhập câu hỏi về pháp luật lao động hoặc BHXH…"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          className="max-h-40 min-h-11 resize-none bg-background"
        />
        {busy ? (
          <Button type="button" size="lg" variant="outline" aria-label="Dừng" onClick={onStop} className="h-11 shrink-0">
            <Square className="fill-current" /> Dừng
          </Button>
        ) : (
          <Button type="submit" size="lg" aria-label="Gửi" disabled={!trimmed} className="h-11 shrink-0">
            <SendHorizontal /> <span className="hidden sm:inline">Gửi</span>
          </Button>
        )}
      </div>
      <div className="flex min-h-5 justify-between gap-4 text-xs text-muted-foreground">
        <span>Enter để gửi, Shift+Enter xuống dòng.</span>
        <span id="chat-input-count" className={value.length >= 800 ? undefined : "sr-only"}>
          {`${value.length}/${MAX_QUESTION_CHARS}`}
        </span>
      </div>
    </form>
  );
}
