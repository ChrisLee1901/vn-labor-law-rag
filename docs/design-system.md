# Design system (Task 5.1)

Nguồn sự thật: `frontend/src/app/globals.css` (biến CSS) và `frontend/src/app/layout.tsx` (font). Task 5.2 đến 5.4 chỉ dùng các token dưới đây, không viết màu hoặc font trực tiếp trong component.

Hướng thiết kế: nghiêm túc, giống văn bản có đóng dấu. Giấy ngả kem, mực xanh đen, một điểm nhấn ấm chỉ dành cho trích dẫn pháp lý. Không gradient, không tím "AI".

## Màu (OKLCH, tên Tailwind: `bg-background`, `text-muted-foreground`, ...)

| Token | Sáng | Tối | Dùng cho |
|---|---|---|---|
| `background` / `foreground` | `0.985 0.004 85` / `0.22 0.03 255` | `0.19 0.02 255` / `0.94 0.008 85` | Nền trang, chữ chính |
| `card`, `popover` | `0.995 0.003 85` | `0.23 0.022 255` | Thẻ, popover, khung nguồn |
| `primary` / `primary-foreground` | `0.3 0.06 255` / giấy | `0.92 0.012 85` / mực | Nút chính (xanh mực) |
| `secondary`, `muted`, `accent` | giấy đậm hơn | mực nhạt hơn | Nền phụ, hover |
| `muted-foreground` | `0.46 0.02 255` | `0.74 0.015 255` | Chữ phụ (tương phản 6.8 : 1 sáng, 8.0 : 1 tối) |
| `border`, `input`, `ring` | `0.89`, `0.86`, `0.5 0.1 255` | trắng 12 %, 16 %, `0.7 0.08 255` | Viền, ô nhập, vòng focus |
| `destructive` | `0.5 0.19 27` | `0.7 0.18 25` | Lỗi |
| `cite`, `cite-foreground`, `cite-border` | `0.93 0.07 85`, `0.36 0.08 65`, `0.8 0.1 80` | `0.32 0.06 75`, `0.88 0.09 85`, `0.5 0.09 75` | **Chỉ** mã trích dẫn `[S1]`, số Điều, gạch chân mục đang xem. Không dùng cho nút hay trang trí |
| `status-online`, `status-offline`, `status-down` (+ `-foreground`) | xanh lá, xám, đỏ nhạt | tương ứng, tối | `StatusBadge` |

Mọi cặp chữ/nền ở trên đạt tối thiểu 6 : 1 (WCAG AA là 4.5 : 1), vòng focus đạt hơn 3 : 1. Sáng/tối theo hệ thống, nút đổi lưu `localStorage` (`next-themes`, class `.dark` trên `<html>`).

## Chữ

Font `Be Vietnam Pro` (next/font, subset `vietnamese` + `latin`, trọng số 400/500/600/700), biến `--font-sans`. Không có font mono riêng: dùng stack mặc định của Tailwind.

| Vai trò | Lớp Tailwind | Ghi chú |
|---|---|---|
| Tiêu đề trang | `text-2xl sm:text-3xl font-semibold` | `h1` đến `h3` đã mặc định 600, `tracking-tight`, `text-balance`, line-height 1.25 |
| Tiêu đề mục | `text-xl font-semibold` | |
| Nội dung | `text-base` (16 px), line-height 1.65 | Đoạn văn dài giới hạn `max-w-[var(--measure)]` (68ch) |
| Chữ phụ, nhãn | `text-sm text-muted-foreground` | |
| Huy hiệu, chú thích | `text-xs font-medium` | |

Tiêu đề luôn đứng thẳng (không italic).

## Hình khối và khoảng cách

- Bán kính: `--radius: 0.375rem` (6 px), phái sinh `rounded-sm/md/lg/xl`. Huy hiệu trạng thái dùng `rounded-full`. Không bo lớn.
- Khoảng cách: thang 4 px mặc định của Tailwind. Khung nội dung `max-w-5xl`, lề `px-4 sm:px-6`, đệm dọc trang `py-8`. Header dùng `py-2`, footer `py-5`.
- Chuyển động: chỉ `transform`/`opacity`, tắt khi `prefers-reduced-motion`. Không hiệu ứng trang trí.
- Hai điểm ngắt: dưới `md` (768 px) header xuống hai hàng, không cuộn ngang ở 320 px.

## Thành phần

- `src/components/ui/*`: shadcn (radix, preset vega) cùng các mảnh chat của shadcn (`message`, `message-scroller`, `bubble`, `input-group`, `trace`, `spinner`, `collapsible`).
- AI Elements bản shadcn không còn là gói riêng. `prompt-input`, `sources`, `inline-citation`, `suggestion` là mẫu ghép từ các thành phần trên: Task 5.2 tự ghép, nguồn mẫu ở https://ui.shadcn.com/docs/ai-elements/radix/<tên>.md.
- `StatusBadge`, `SiteHeader`, `SiteFooter`, `ThemeToggle` ở `src/components/`.

## Biến môi trường

- `API_ORIGIN` (mặc định `http://127.0.0.1:8000`): đích rewrite `/api/*` khi chạy `next dev`. Trên Vercel do `vercel.json` (Task 6.3) lo.
- `NEXT_PUBLIC_REPO_URL`: liên kết GitHub ở footer, ẩn khi không đặt.
