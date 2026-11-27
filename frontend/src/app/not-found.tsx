import Link from "next/link";

export default function NotFound() {
  return (
    <div className="space-y-3 py-12">
      <h1 className="text-2xl font-semibold">Không tìm thấy trang</h1>
      <p className="text-muted-foreground">Trang bạn mở không tồn tại hoặc đã được chuyển đi.</p>
      <Link href="/" className="underline underline-offset-4">
        Về trang hỏi đáp
      </Link>
    </div>
  );
}
