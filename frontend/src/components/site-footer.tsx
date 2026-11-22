import { cn, focusRing } from "@/lib/utils";

export function SiteFooter() {
  const repoUrl = process.env.NEXT_PUBLIC_REPO_URL;
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-5 text-sm text-muted-foreground sm:px-6">
        <p>Thông tin tham khảo, không phải tư vấn pháp lý.</p>
        {repoUrl ? (
          <a href={repoUrl} target="_blank" rel="noreferrer" className={cn("underline underline-offset-4 hover:text-foreground", focusRing)}>
            Mã nguồn trên GitHub<span className="sr-only"> (mở tab mới)</span>
          </a>
        ) : null}
      </div>
    </footer>
  );
}
