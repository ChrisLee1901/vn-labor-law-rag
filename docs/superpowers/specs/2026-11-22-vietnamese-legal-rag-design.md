# Thiết kế: RAG pháp luật lao động tiếng Việt end-to-end

*Ngày: 2026-11-22 · Trạng thái: chờ duyệt · Nghiên cứu nền: `docs/research/reports/Kiến trúc RAG tiếng Việt 2026.md` (nguồn và số liệu ở đó, file này không lặp lại).*

## 1. Mục đích và lý do

- **Để làm gì:** một project portfolio cho CV, chứng minh người làm tự dựng được RAG end-to-end, không chỉ gọi API Gemini/GPT/Claude.
- **Ai dùng:** người phỏng vấn, xem trong buổi phỏng vấn. Trước buổi đó, chủ project bật notebook Kaggle ở nhà để có API LLM.
- **Thế nào là thành công:** demo chạy mượt trong 1–2 giờ. Repo GitHub nhìn chuyên nghiệp, kể được kiến trúc bằng số liệu (bảng ablation, eval gate). Khi Kaggle tắt, app vẫn có ích.

## 2. Mục tiêu / Không làm / Thất bại dù chạy được

| Mục tiêu | Không làm (non-goals) | Thất bại dù chạy được (anti-goals) |
|---|---|---|
| Hỏi đáp tiếng Việt trên 8 văn bản lao động – BHXH – BHTN, trích dẫn Điều/Khoản | Tài khoản người dùng, lưu lịch sử trên server | Trả lời bịa số liệu hoặc số Điều không có trong văn bản |
| LLM open-weight tự host trên Kaggle, gọi qua API | Gọi Gemini/GPT/Claude để **sinh câu trả lời** | App trắng trang hoặc lỗi khi Kaggle tắt |
| UI/UX chỉn chu trên Vercel, GitHub CI/CD đầy đủ | Chạy 24/7, SLA, nhiều người dùng đồng thời | Trả lời theo văn bản hết hiệu lực mà không cảnh báo |
| Eval có số liệu, ablation, eval gate trên PR | Fine-tune model | Demo chỉ đẹp với một câu chọn sẵn |
| Mở rộng sang bộ B (giao thông) mà không sửa code | GraphRAG/Neo4j (chỉ ghi là future work) | |

## 3. Ràng buộc

- **Chi phí:** chỉ dùng gói miễn phí: Kaggle T4 x2 (~30 GPU-giờ/tuần, phiên ≤ 12 giờ), Vercel Hobby, Supabase Free (500 MB, 2 project, pause sau 7 ngày), ngrok free (1 domain tĩnh, 20k request/tháng), Langfuse Hobby, Upstash free.
- **Kaggle ToS:** cấm "server farming". Chỉ bật trước phỏng vấn, dùng bearer token, không công khai URL. App phải coi LLM là thành phần **có thể vắng mặt**.
- **Vercel:** function Python ≤ 500 MB, ≤ 300 s kể cả thời gian stream. Không cài torch hay model nào trên Vercel.
- **Máy dev:** Windows 11, Python 3.12. Repo GitHub cá nhân, public.

## 4. Các cách đã cân nhắc

| Cách | Đánh đổi | Kết quả |
|---|---|---|
| A. Next.js + API TypeScript | Một ngôn ngữ, ít code; nhưng RAG viết bằng TS không phải thứ phỏng vấn AI/ML muốn xem | Loại |
| **B. Next.js UI + FastAPI (Python), một repo, một project Vercel** | Ingest, retrieval và eval dùng chung codebase Python; tốn thêm công thiết lập 2 runtime và CI | **Người dùng chọn** |
| C. Mọi thứ chạy trên Kaggle, Vercel chỉ làm UI | Đơn giản nhất nhưng gần như không có kiến trúc để kể; Kaggle tắt thì chết hết | Loại |

Lưu vector: **Supabase pgvector** (dữ liệu bền, mở bảng cho người phỏng vấn xem được). Kaggle chỉ chạy model. Không dùng FAISS trong RAM của Kaggle.

## 5. Những gì người dùng đã quyết

1. Kiến trúc B.
2. Corpus: **bộ A** (8 văn bản) làm trước; **bộ B** giao thông là phase mở rộng.
3. Giữ Kaggle, kèm **chế độ offline** và **video demo** dự phòng.
4. Tunnel: **ngrok free với domain tĩnh**.
5. Tải tài liệu ngay. ✅ Đã xong: `docs/corpus/raw/` (17 file, log tại `docs/corpus/fetch_log.json`).

## 6. Thiết kế

### 6.1 Thành phần

```
Trình duyệt ── Next.js 16 (Vercel, service "web")
                 │  /api/* (rewrite, cùng domain)
                 ▼
             FastAPI (Vercel Python, service "api", sin1)
               ├── Supabase Postgres (ap-southeast-1): legal_docs, chunks (halfvec 1024 + tsvector),
               │     legal_refs, app_config, feedback, canned_answers; hàm hybrid_search (RRF)
               └── httpx ──► ngrok domain tĩnh ──► Kaggle notebook (T4 x2)
                               gateway FastAPI (bearer): /health, /v1/embeddings, /v1/rerank,
                               proxy SSE /v1/chat/completions ──► llama-server (GPU0)
                               embedder + reranker fp16 (GPU1)
```

### 6.2 Luồng một câu hỏi (online)

1. Chuẩn hóa NFC. Từ lượt thứ hai trở đi, condense câu hỏi bằng lịch sử hội thoại.
2. Regex trích số hiệu văn bản / Điều / Khoản.
3. Tự dựng tsquery theo kiểu OR, sau khi bỏ stopword.
4. Embed câu hỏi ở gateway, rồi gọi `hybrid_search`: RRF k=50, lấy 40 ứng viên, mặc định lọc văn bản còn hiệu lực tại ngày hỏi.
5. Rerank, giữ top 5–8 Điều cha.
6. Mở rộng 1 hop theo `legal_refs`.
7. Nếu điểm rerank cao nhất < τ thì **từ chối, không gọi LLM**.
8. Prompt với các nguồn `[S#]`. Stream câu trả lời theo AI SDK UI Message Stream v1 (`source-url`, `text-delta`, `data-status`).
9. Kiểm tra hậu kỳ: chỉ được trích các `[S#]` đã cung cấp, và số Điều phải khớp với header.
10. Gửi trace lên Langfuse.

### 6.3 Chế độ offline (Kaggle tắt)

`/api/health` báo `llm: offline`, UI hiện badge. Câu hỏi đi qua FTS cộng tra cứu ID bằng regex (không cần embedding), trả về danh sách Điều liên quan để đọc trực tiếp. Câu hỏi khớp câu mẫu thì trả **câu trả lời dựng sẵn** (lưu trong `canned_answers`, sinh từ lần chạy online, có nhãn "trả lời đã lưu"). README có video demo 60–90 giây.

### 6.4 Dữ liệu

- `legal_docs` **biên tập tay**: số hiệu, loại, cơ quan, ngày ban hành, ngày hiệu lực, tình trạng, `replaced_by`, `amends`, URL nguồn.
- **Chunk:** Điều là parent, Khoản là child (≤ 450 token; vượt thì tách theo Điểm). Thêm breadcrumb `[số hiệu – tên] Chương > Điều N. tiêu đề | Khoản M`. Lưu riêng `content` và `embed_text`.
- **Nguồn parse:** ưu tiên `.docx`; `.doc` → `.docx` bằng LibreOffice headless. Fallback là PDF có lớp text (PyMuPDF), bỏ header "CÔNG BÁO". Mọi văn bản bộ A đều có PDF text, **không cần OCR**.
- Model: embedder `AITeamVN/Vietnamese_Embedding`, reranker `AITeamVN/Vietnamese_Reranker`, LLM `Qwen3-8B` GGUF Q5_K_M (tắt thinking). Các phương án A/B nằm trong báo cáo.

### 6.5 Hạ tầng và CI/CD

- **Repo layout:** `frontend/`, `backend/`, `pipelines/` (không deploy), `kaggle/`, `supabase/migrations/`, `eval/`, `docs/`, `.github/workflows/`.
- **Supabase:** **1 project duy nhất** (người dùng chốt, vì free tier). An toàn nhờ: CI và test chạy Postgres tạm trên runner (`supabase db start`), không chạm project thật; migration chỉ cộng thêm (additive); re-ingest ghi vào `index_version` mới rồi đổi con trỏ `app_config.active_index_version` (blue/green trong 1 DB, rollback bằng cách đổi lại con trỏ).
- **CI (`ci.yml`):** path filter, chạy các job web / api / db / eval-retrieval. Job tổng `ci-ok` là check bắt buộc duy nhất.
- **CD:** chạy từ Actions bằng `vercel pull/build/deploy --prebuilt`, `needs: ci-ok`. Fallback là Vercel Git integration nếu spike P0 cho thấy `--prebuilt` không hỗ trợ Services.
- **Eval:** `eval-retrieval` (PR, không cần GPU: cache embedding + index đóng băng + ranx). `eval-full` (dispatch khi Kaggle bật).
- **Vận hành:** keep-alive cron hằng ngày. Chống lạm dụng bằng WAF 1 rule, Upstash và giới hạn input.

## 7. Giao cho người build tự quyết

Tên biến, cấu trúc module bên trong mỗi thư mục, style UI chi tiết trong khuôn shadcn, prompt cụ thể (có version trong git), giá trị τ và chunk size (chốt bằng eval), thứ tự task trong cùng một phase.

## 8. Các quyết định do Claude tự chốt (người dùng kiểm tra lại)

- Tên hiển thị của app: **"Trợ lý Pháp luật Lao động"**. Repo: `vn-labor-law-rag`.
- UI gồm 3 trang: **Chat** (khung chat + panel nguồn + badge online/offline + câu hỏi gợi ý), **Văn bản** (danh sách 8 văn bản với tình trạng hiệu lực, xem từng Điều), **Giới thiệu** (sơ đồ kiến trúc + bảng eval).
- Không có đăng nhập. Lịch sử chat chỉ lưu ở localStorage.
- ~~2 project Supabase~~ → người dùng chốt 1 project (xem 6.5). Dev local trỏ vào project đó, chỉ đọc hoặc ghi vào `index_version` thử nghiệm.
- Ingest gọi embedding qua chính gateway Kaggle, để query và corpus dùng cùng một model và cùng cách chạy.
- **Golden set (người dùng chốt):** do Claude (subagent `model: sonnet`, effort `medium`) sinh trực tiếp từ văn bản đã tải trong `docs/corpus/raw/`. Không gọi API ngoài, không tốn quota. Claude khác họ với Qwen nên giảm thiên vị. Quy trình: một lượt sinh theo quota loại câu → một lượt Claude **độc lập** kiểm tra lại từng đáp án và nhãn Điều/Khoản với văn bản gốc, câu nào không khớp thì bỏ → người dùng chỉ đọc thử khoảng 20 câu ngẫu nhiên. README ghi trung thực "Claude sinh + tự kiểm chéo + N câu người kiểm". Chỉ dùng cho eval, không nằm trong đường trả lời.
- Thư mục `research_notes/` và `reports/` chuyển vào `docs/research/` ở Phase 0.
