"use client";

import { useEffect } from "react";

/** Cuộn tới phần tử theo `#hash` và đặt `data-active` vài giây (nền nhấn nhẹ); `:target` giữ viền cố định. */
export function HashHighlight() {
  useEffect(() => {
    let current: HTMLElement | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const clear = () => {
      clearTimeout(timer);
      if (current) delete current.dataset.active;
      current = null;
    };
    const run = () => {
      clear();
      let id = "";
      try {
        id = decodeURIComponent(location.hash.slice(1));
      } catch {
        // hash hỏng: coi như không có
      }
      const el = id ? document.getElementById(id) : null;
      if (!el) return;
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
      el.dataset.active = "true";
      current = el;
      timer = setTimeout(clear, 3000);
    };
    run();
    window.addEventListener("hashchange", run);
    return () => {
      window.removeEventListener("hashchange", run);
      clear();
    };
  }, []);
  return null;
}
