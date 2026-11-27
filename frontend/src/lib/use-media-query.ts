import { useSyncExternalStore } from "react";

/** false khi SSR hoặc môi trường không có matchMedia. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia?.(query);
      m?.addEventListener("change", cb);
      return () => m?.removeEventListener("change", cb);
    },
    () => window.matchMedia?.(query).matches ?? false,
    () => false,
  );
}
