"use client";

import { useRef, type ReactNode } from "react";
import { cn, focusRing } from "@/lib/utils";

/** Mục lục thu gọn dưới lg: cuộn riêng khi dài, tự đóng sau khi bấm một liên kết. */
export function MobileToc({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  return (
    <details
      ref={ref}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("a") && ref.current) ref.current.open = false;
      }}
      className="mb-6 rounded-md border bg-card p-3 lg:hidden"
    >
      <summary className={cn("cursor-pointer font-medium", focusRing)}>Mục lục</summary>
      <nav aria-label="Mục lục" className="mt-3 max-h-[60dvh] overflow-y-auto">
        {children}
      </nav>
    </details>
  );
}
