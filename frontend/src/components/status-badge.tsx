"use client";

import { useEffect, useState } from "react";
import type { HealthResponse } from "@/lib/api-types";
import { cn } from "@/lib/utils";

type State = "checking" | "online" | "offline" | "down";

const POLL_MS = 30_000;

const VIEW: Record<State, { label: string; box: string; dot: string }> = {
  checking: { label: "Đang kiểm tra…", box: "bg-status-offline text-status-offline-foreground", dot: "bg-current opacity-40" },
  online: { label: "Mô hình trực tuyến", box: "bg-status-online text-status-online-foreground", dot: "bg-current" },
  offline: { label: "Chế độ ngoại tuyến", box: "bg-status-offline text-status-offline-foreground", dot: "bg-current" },
  down: { label: "Mất kết nối dữ liệu", box: "bg-status-down text-status-down-foreground", dot: "bg-current" },
};

async function readState(signal: AbortSignal): Promise<State> {
  const res = await fetch("/api/health", { cache: "no-store", signal });
  if (!res.ok) return "down";
  const h = (await res.json()) as HealthResponse;
  if (h.db !== "ok") return "down";
  return h.llm === "online" ? "online" : "offline";
}

export function StatusBadge({ className }: { className?: string }) {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    let ctrl: AbortController | undefined;

    const check = async () => {
      ctrl?.abort();
      const c = (ctrl = new AbortController());
      try {
        const next = await readState(c.signal);
        if (!c.signal.aborted) setState(next);
      } catch {
        if (!c.signal.aborted) setState("down");
      }
    };
    const stop = () => clearInterval(timer);
    const start = () => {
      stop();
      void check();
      timer = setInterval(check, POLL_MS);
    };
    const onVisibility = () => (document.hidden ? stop() : start());

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
      ctrl?.abort();
    };
  }, []);

  const v = VIEW[state];
  return (
    <span
      role="status"
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", v.box, className)}
    >
      <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", v.dot)} />
      {v.label}
    </span>
  );
}
