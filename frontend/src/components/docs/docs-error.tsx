import { cn, focusRing } from "@/lib/utils";

/** Thẻ lỗi thân thiện; "Thử lại" là liên kết thường để tải lại trang (server fetch chạy lại). */
export function DocsError({ message, retryHref }: { message: string; retryHref: string }) {
  return (
    <div role="alert" className="max-w-[var(--measure)] space-y-3 rounded-md border bg-card p-4">
      <p>{message}</p>
      <a href={retryHref} className={cn("inline-block font-medium text-primary underline underline-offset-4", focusRing)}>
        Thử lại
      </a>
    </div>
  );
}
