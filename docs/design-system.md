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
| `border` | `0.89 0.008 85` | trắng 12 % | Đường kẻ trang trí (không mang thông tin, không cần 3 : 1) |
| `input` | `0.62 0.015 255` | `0.55 0.02 255` | Viền ô nhập và nút outline (ranh giới điều khiển, cần 3 : 1) |
| `ring` | `0.5 0.1 255` | `0.7 0.08 255` | Vòng focus bàn phím |
| `destructive` | `0.5 0.19 27` | `0.7 0.18 25` | Lỗi |
| `cite`, `cite-foreground`, `cite-border` | `0.93 0.07 85`, `0.36 0.08 65`, `0.8 0.1 80` | `0.32 0.06 75`, `0.88 0.09 85`, `0.5 0.09 75` | **Chỉ** mã trích dẫn `[S1]`, số Điều, gạch chân mục đang xem. Không dùng cho nút hay trang trí |
| `status-online`, `status-offline`, `status-down` (+ `-foreground`) | xanh lá, xám, đỏ nhạt | tương ứng, tối | `StatusBadge` |

Tương tác tính từ chính các token trên (OKLCH sang sRGB, công thức WCAG):

| Cặp | Sáng | Tối |
|---|---|---|
| `foreground` / `background` | 16.6 | 15.5 |
| `muted-foreground` / `background` | 6.8 | 8.0 |
| `muted-foreground` / `muted` | 6.2 | 6.3 |
| `primary-foreground` / `primary` | 13.1 | 13.7 |
| `cite-foreground` / `cite` | 9.0 | 8.9 |
| `status-*-foreground` / `status-*` (online, offline, down) | 8.9, 7.5, 6.8 | 9.6, 7.8, 8.7 |
| `ring` / `background` (card) | 5.8 (5.9) | 6.9 (6.3) |
| `input` / `background` (card) | 3.5 (3.9 so với card) | 3.8 (3.5 so với card) |

Chữ thường đạt tối thiểu 6.2 : 1 (AA là 4.5 : 1), vòng focus và viền ô nhập đạt hơn 3 : 1 (WCAG 1.4.11). `border` chỉ khoảng 1.3 : 1 nên chỉ dùng để kẻ, không dùng làm ranh giới của điều khiển. `cite-border` (1.8 : 1 trên nền sáng) chỉ để trang trí khung trích dẫn có chữ đi kèm. Gạch chân mục đang xem dùng `cite-foreground`. Sáng/tối theo hệ thống, nút đổi lưu `localStorage` (`next-themes`, class `.dark` trên `<html>`).

Focus bàn phím: nút shadcn có ring riêng. Liên kết thường dùng `focusRing` từ `@/lib/utils` (outline 2 px đầy, cách 2 px, màu `ring`). Lớp nền `outline-ring/50` của shadcn có alpha, không dùng làm vòng focus.

## Chữ

Font `Be Vietnam Pro` (next/font, subset `vietnamese` + `latin`, trọng số 400/500/600/700), biến `--font-be-vietnam`, token Tailwind `--font-sans` = Be Vietnam Pro rồi `ui-sans-serif, system-ui, "Segoe UI", sans-serif`. Không có font mono riêng: dùng stack mặc định của Tailwind.

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

## Trang Hỏi đáp (Task 5.2)

- Trả lời của trợ lý là chữ trần trên nền trang, không bong bóng, đo dòng `--measure` (68ch). Chỉ tin của người dùng nằm trong bong bóng `secondary` bo nhỏ. Không avatar.
- `[S#]` là nút nhỏ nền `cite`, chữ `cite-foreground`, viền `cite-border`; nguồn đang xem gạch chân `cite-foreground`. Mã không có trong nguồn của tin đó là chữ `muted-foreground` thường, không phải nút.
- Huy hiệu hiệu lực dùng bộ `status-*` sẵn có: đang hiệu lực = `status-online`, chưa hiệu lực = `status-offline` (xám), hết hiệu lực = `status-down`. Luôn có chữ, không chỉ màu.
- Banner (ngoại tuyến, từ chối) là hộp `muted` viền `border`, chữ `muted-foreground`; chỉ lỗi dùng `destructive`. Cảnh báo trích dẫn là một dòng chữ phụ, không hộp.
- Bố cục: ≥ lg hai cột (câu trả lời, panel nguồn 18rem dính khi cuộn); dưới lg panel là sheet đáy mở bằng "Nguồn (n)" hoặc bấm `[S#]`. Ô nhập dính đáy trang.
- Thông báo cho trình đọc màn hình: vùng `role=status` chỉ đọc "Đã có câu trả lời mới." khi stream xong, nội dung đang stream không nằm trong vùng live (`aria-busy` trên danh sách).

## Trang Văn bản (Task 5.3)

- Danh sách: lưới 1 cột, `sm` trở lên 2 cột; mỗi văn bản là thẻ `rounded-md border bg-card` (không đổ bóng, không bo lớn): số hiệu (chữ phụ), tên là liên kết (`h2`), hàng meta gồm huy hiệu hiệu lực, loại, ngày hiệu lực, số Điều. Thứ tự: đang hiệu lực, chưa hiệu lực, hết hiệu lực; trong nhóm theo ngày hiệu lực mới nhất. `DocSummary` không có cơ quan/ngày ban hành nên thẻ không hiện hai trường này (có ở trang chi tiết).
- `EffectivenessBadge` (`src/components/effectiveness-badge.tsx`) dùng chung với chat; bộ `status-*` như mục Hỏi đáp.
- Chi tiết: đầu trang có liên kết quay lại, số hiệu, tên (`h1`), huy hiệu, "Được thay thế bởi {số hiệu}" (liên kết), meta `dl`, liên kết nguồn ngoài (chỉ http/https, `rel="noopener noreferrer"`). Thân bài ≥ lg hai cột: mục lục `16rem` dính (`sticky top-4`, cuộn riêng) và nội dung; dưới lg mục lục là `<details>` "Mục lục". Chương là `h2`, Điều là `h3` có `id` `D{n}` (Điều 12a: `D12a`), phụ lục `PL{n}`.
- Điều được trỏ tới (`:target`): viền trái 2 px và gạch chân tiêu đề bằng `cite-foreground`; thêm nền `cite` trong 3 giây (`data-active`, do `HashHighlight` đặt, kèm cuộn mượt, tắt khi `prefers-reduced-motion`). Nội dung điều là chữ trần `white-space: pre-line`, không markdown/HTML. `content-visibility: auto` trên từng Điều để văn bản dài (BLLĐ 220 Điều) không nặng.
- Render: cả hai trang `force-dynamic` (không gọi API lúc build, không đóng băng thẻ lỗi vào trang tĩnh); dữ liệu vẫn cache 1 giờ qua `fetch(..., { next: { revalidate: 3600 } })`. Gốc API phía server: `getApiBase()` trong `src/lib/api-server.ts`.

## Dependencies

- `cn` (npm, 0.5.2) thay cho `clsx` + `tailwind-merge`: giữ nguyên, vì đây là mặc định hiện tại của template shadcn. Đã kiểm tra chuỗi cung ứng: maintainer `shadcn`, repo `github.com/shadcn-ui/cn`, giấy phép MIT, không có script postinstall. Mã ứng dụng import `cn` từ `@/lib/utils` (file này re-export từ `"cn"`); các file sinh sẵn trong `components/ui/*` được phép import `"cn"` trực tiếp, không sửa tay.
- `@shadcn/react` (do CLI thêm cho `message-scroller`): maintainer `shadcn`, repo `shadcn-ui/ui`.
- `shadcn` (CLI) nằm ở devDependencies, chỉ cần lúc build cho `@import "shadcn/tailwind.css"`.
- `ai` 7 và `@ai-sdk/react` 4 (`useChat`, `DefaultChatTransport`), `react-markdown` + `remark-gfm` (không dùng `rehype-raw`). Dev: `@testing-library/user-event`.
- Node >= 22 (`engines`, `.nvmrc`), pnpm 11.22.0 (`packageManager`).

## Biến môi trường

- `API_ORIGIN`: đích rewrite `/api/*`. Khi chạy `next dev` mặc định `http://127.0.0.1:8000`. Ở production không đặt thì không có rewrite (`vercel.json`, Task 6.3, định tuyến). Logic ở `src/lib/api-rewrites.ts`.
- Gọi API từ server component (`/van-ban*`): `API_ORIGIN` -> `NEXT_PUBLIC_SITE_URL` -> `https://$VERCEL_URL` -> `http://127.0.0.1:8000` (chỉ `NODE_ENV=development`) -> lỗi rõ ràng.
- `NEXT_PUBLIC_MOCK_CHAT=1`: trang chat gọi `/api/mock/chat` (route dev, 404 khi `NODE_ENV=production`) thay cho `/api/chat`. Inlined lúc build.
- `NEXT_PUBLIC_REPO_URL`: liên kết GitHub ở footer, ẩn khi không đặt.
