"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import type { SourceItem } from "@/lib/chat-types";
import { isSafeSourceUrl } from "@/lib/docs-cache";
import { cn, focusRing } from "@/lib/utils";
import { SourceEffectiveness } from "./source-info";

/** Danh sách S1..Sn của câu trả lời đang chọn; mục đang xem có gạch chân màu cite. */
export function SourcesPanel({ sources, activeId }: { sources: SourceItem[]; activeId?: string }) {
  const activeRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  if (sources.length === 0)
    return <p className="text-sm text-muted-foreground">Nguồn trích dẫn của câu trả lời sẽ hiện ở đây.</p>;

  return (
    <ol className="space-y-3">
      {sources.map((s) => {
        const active = s.id === activeId;
        return (
          <li
            key={s.id}
            ref={active ? activeRef : undefined}
            aria-current={active ? "true" : undefined}
            className={cn("space-y-1.5 rounded-md border bg-card p-3 text-sm", active ? "border-cite-border" : "border-border")}
          >
            <p className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0 rounded-sm border border-cite-border bg-cite px-1 text-xs font-semibold leading-5 text-cite-foreground">
                {s.id}
              </span>
              <span className={cn("font-medium leading-snug", active && "underline decoration-cite-foreground decoration-2 underline-offset-4")}>
                {s.title}
              </span>
            </p>
            <SourceEffectiveness url={s.url} />
            {isSafeSourceUrl(s.url) && (
              <div>
                <Link href={s.url} className={cn("font-medium text-primary underline underline-offset-4", focusRing)}>
                  Xem điều luật
                </Link>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
