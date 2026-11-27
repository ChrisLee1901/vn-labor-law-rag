"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="space-y-3 py-12">
      <h1 className="text-2xl font-semibold">Đã xảy ra lỗi</h1>
      <p className="text-muted-foreground">Không tải được trang này. Hãy thử lại sau ít phút.</p>
      <button type="button" onClick={reset} className="underline underline-offset-4">
        Thử lại
      </button>
    </div>
  );
}
