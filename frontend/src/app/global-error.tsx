"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="vi">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "3rem 1rem", maxWidth: "40rem", margin: "0 auto" }}>
        <h1>Đã xảy ra lỗi</h1>
        <p>Ứng dụng gặp sự cố. Hãy tải lại trang hoặc thử lại.</p>
        <button type="button" onClick={reset}>
          Thử lại
        </button>
      </body>
    </html>
  );
}
