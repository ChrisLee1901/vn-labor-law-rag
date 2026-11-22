"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { FeedbackBody } from "@/lib/api-types";

/** 👍/👎 cho một câu trả lời. Chưa có trace_id thì vô hiệu; mỗi tin chỉ bình chọn một lần. */
export function Feedback({ traceId }: { traceId?: string }) {
  const [vote, setVote] = useState<1 | -1 | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(score: 1 | -1) {
    if (!traceId || busy || vote) return;
    setBusy(true);
    try {
      const body: FeedbackBody = { trace_id: traceId, score };
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(String(res.status));
      setVote(score);
    } catch {
      toast.error("Không gửi được đánh giá, vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }

  const disabled = !traceId || busy || vote !== null;
  return (
    <>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Câu trả lời hữu ích" aria-pressed={vote === 1} disabled={disabled} onClick={() => send(1)}>
        <ThumbsUp className={vote === 1 ? "fill-current" : undefined} />
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="Câu trả lời chưa tốt" aria-pressed={vote === -1} disabled={disabled} onClick={() => send(-1)}>
        <ThumbsDown className={vote === -1 ? "fill-current" : undefined} />
      </Button>
    </>
  );
}
