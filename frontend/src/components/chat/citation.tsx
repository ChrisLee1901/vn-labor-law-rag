"use client";

import Link from "next/link";
import { createContext, useContext } from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { SourceItem } from "@/lib/chat-types";
import { isSafeSourceUrl } from "@/lib/docs-cache";
import { cn, focusRing } from "@/lib/utils";
import { SourceEffectiveness, SourceExcerpt } from "./source-info";

export interface CitationContextValue {
  sources: SourceItem[];
  activeId?: string;
  onSelect?: (id: string) => void;
}
export const CitationContext = createContext<CitationContextValue>({ sources: [] });

/** Nút `[S#]` trong câu trả lời: hover/focus hiện thẻ xem trước, bấm mở panel nguồn. Mã lạ hiện chữ nhạt. */
export function Citation({ id }: { id: string }) {
  const { sources, activeId, onSelect } = useContext(CitationContext);
  const source = sources.find((s) => s.id === id);
  if (!source) return <span className="text-muted-foreground">[{id}]</span>;

  return (
    <HoverCard openDelay={120} closeDelay={80}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          aria-label={`Nguồn ${id}: ${source.title}`}
          onClick={() => onSelect?.(id)}
          className={cn(
            "mx-0.5 inline-flex min-w-6 items-center justify-center rounded-sm border border-cite-border bg-cite px-1 align-baseline text-xs font-semibold leading-5 text-cite-foreground",
            focusRing,
            activeId === id && "underline decoration-2 underline-offset-2",
          )}
        >
          {id}
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80 max-w-[calc(100vw-2rem)] space-y-2">
        <p className="font-medium leading-snug">{source.title}</p>
        <SourceEffectiveness url={source.url} />
        <SourceExcerpt url={source.url} />
        {isSafeSourceUrl(source.url) && (
          <Link href={source.url} className={cn("inline-block text-sm font-medium text-primary underline underline-offset-4", focusRing)}>
            Xem điều luật
          </Link>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}
