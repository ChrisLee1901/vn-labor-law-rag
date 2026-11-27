# Tiến độ dự án (cập nhật 2026-11-28)

Nguồn chi tiết: plan `docs/superpowers/plans/2026-11-22-vietnamese-legal-rag.md` (checkbox), checklist cho chủ repo `docs/user-checklist.md`, kết quả spike `docs/spikes.md`. File này chỉ là bản tóm tắt để theo dõi. Không ghi secret, tên miền tunnel hay ID tài khoản ở đây (repo public).

## 1. Hiện trạng một dòng
Code v1 xong và đã qua review toàn nhánh. PR #1 (`feat/rag-v1` → `main`) có CI xanh (`ci-ok`). Chưa merge. Phần chạy thật trên Kaggle đã qua 3 spike (build llama.cpp, SSE qua ngrok, smoke LLM). Còn spike Vercel và Supabase, ingest và eval thật, deploy.

## 2. Đã xong
| Mảng | Nội dung | Trạng thái |
|---|---|---|
| Corpus + schema | 8 văn bản, parser Điều/Khoản/Điểm, chunker (2.496 chunk, ≤450 token), tham chiếu chéo, schema + `hybrid_search` (RRF, as_of) | xong, test xanh |
| Backend (FastAPI) | retrieval, citation check, ngưỡng từ chối, stream AI SDK, rate limit, tracing Langfuse, feedback → score, canned-ready | xong, 300+ test, pyright ratchet 65 |
| Frontend (Next 16) | Chat, Văn bản, Giới thiệu, e2e Playwright, trang lỗi tiếng Việt | xong, 111 test |
| Kaggle | gateway bảo mật, notebook serve (vòng giữ phiên giới hạn 2 giờ), notebook build llama.cpp, spike SSE/ngrok, `scripts/smoke_llm.py` | **chạy live xong, 3 spike ĐẠT** (xem mục 3) |
| CI/CD | `ci.yml` + `ci-ok`, gate eval retrieval, `deploy.yml`, `eval-full.yml`, `keepalive.yml`, spike-deploy, Dependabot | CI xanh trên PR #1; deploy chưa chạy thật |
| Eval | golden 120 câu (dev 40 / test 80), harness retrieval + answer, build-eval cho trang Giới thiệu | code xong, chưa có số liệu thật (`eval.json` = pending) |
| Review toàn nhánh | 4 reviewer chia theo khu vực + 1 lượt sửa + 1 lượt re-review + sửa 2 lỗi as_of | xong |
| Repo / hạ tầng | repo GitHub public, PR #1; project Vercel đã tạo và link; Supabase project (org riêng) tạo ở Sydney; ngrok dev domain có sẵn; `VERCEL_TOKEN` trong GitHub Secrets; `DATABASE_URL` (Production + Preview) trong Vercel env | xong |

## 3. Spike live đã xong (2026-11-27)
- **0.2 build llama.cpp (ĐẠT):** `b12651`, CUDA 13.0, 2 x T4; build 34,5 phút nhờ libcuda compat; Qwen3-8B Q5_K_M pp4096 = 1063,6 tok/s, tg256 = 31,8 tok/s (ngưỡng 15); đủ 10 cờ `llama-server`. Dataset gộp `llamacpp-sm75-bin` (chứa cả bin và GGUF) đã tạo; `serve.ipynb` tìm GGUF ở mọi dataset đã gắn.
- **0.3 SSE qua ngrok (ĐẠT):** 150/150 event, không cắt, không dồn cục, 401 khi thiếu/sai token. `pyngrok` phải ghim `7.2.3` (bản 9.x không nhận `domain`).
- **2.3 smoke LLM live (ĐẠT):** TTFT p50 0,77 s, 36,5 tok/s, embed 1024 chiều, rerank đúng thứ tự, tiếng Việt có dấu đúng. `serve.ipynb` đã chạy tới READY.
- Còn lại của mục 0.x: spike Vercel (0.4) và Supabase (0.5) chưa chạy.

## 4. Việc của chủ repo (theo thứ tự)
1. Đặt `LLM_BASE_URL` (= `https://<NGROK_DOMAIN>`, không có `/v1`) và `LLM_API_KEY` (= `GATEWAY_API_KEY`) vào Vercel env (Production + Preview). Sau mỗi buổi dùng Kaggle: **Stop session**.
2. Lấy lại / đặt mật khẩu DB Supabase mới (đã quên mật khẩu cũ, project còn trống nên không ảnh hưởng) rồi cập nhật `DATABASE_URL` nếu đổi.
3. Giai đoạn E (spike Vercel Services), F (ingest thật, đọc thử 20 câu golden, xác minh NĐ 145/2020 trên vbpl.vn, eval thật), G (deploy production, WAF, keep-alive), H, I (video demo): xem checklist.
4. Chưa merge PR #1 trước giai đoạn G (merge sẽ kích hoạt `migrate`/`deploy-prod` khi chưa có secret).

## 5. Việc của trợ lý (không cần chủ repo)
- Task 7.2 (ablation: cờ `--no-breadcrumb` cho ingest, script sinh `ABLATION.md`, biến thể model A/B trong notebook).
- Task 7.3 (`scripts/build_canned.py`, đường trả lời dựng sẵn ở backend + test, nhãn trên UI).
- Task 7.4 (README, ADR, sửa lệch tài liệu còn lại, hạ pyright baseline 65 → 0).
- Chạy thử toàn đường ống với model giả (ingest → export → eval → backend + frontend + answer_eval) để bắt lỗi nối ghép trước khi tốn giờ GPU.
- Sau mỗi kết quả live do chủ repo dán: điền `docs/spikes.md`, tick plan.
- `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID`: đặt vào GitHub Secrets khi chủ repo xác nhận chạy spike Vercel (đặt sớm sẽ làm `deploy-preview` trên PR chạy thật và đỏ). **Đang chờ xác nhận.**

## 6. Quyết định đã chốt
- Kiến trúc: Next.js + FastAPI trên Vercel (Services), LLM/embedder/reranker tự host trên Kaggle qua ngrok, Supabase pgvector. Không dùng API LLM ngoài để sinh câu trả lời.
- Bộ văn bản A (lao động + BHXH + BHTN) trước; bộ B (giao thông) là phase tùy chọn.
- Chỉ 1 project Supabase cho dự án này; index đổi bằng `--index-version` (blue/green). Project Supabase nằm ở **Sydney (`ap-southeast-2`)**, nên region function của Vercel là **`syd1`** (đã đổi trong `vercel.json`, spec và tài liệu).
- Org Supabase riêng `vn-labor-law-rag` (org cũ bị giới hạn 2 project Free của một thành viên khác). Project `exe101` của chủ repo không được đụng tới.
- Lần ingest đầu (`--index-version 1`) cần `--force` (v1 active sẵn nhưng rỗng).
- Golden set do Claude sinh + kiểm chéo độc lập; chỉ báo số liệu trên split `test`.
- Kaggle chỉ bật khi demo/spike; mọi vòng giữ phiên đều có giới hạn thời gian.

## 7. Rủi ro / chưa kiểm chứng
- Vercel Services + `vercel deploy --prebuilt`, khóa `functions` trong `vercel.json`, Hobby 1 region với `syd1`, `--env` kèm `--prebuilt`.
- Qwen3 token/ký tự tiếng Việt so với slot 8.192 token (chưa đo `/tokenize`); `executemany`/`for share` qua pooler 6543 (kiểm ở lần ingest thật).
- Phụ lục địa bàn NĐ 399/2026 không lấy được từ Công báo → từ 01/01/2027 câu hỏi "phường X thuộc vùng nào" thiếu nguồn (đã ghi trong DATASET_CARD, trang Giới thiệu, `legal_docs.yaml`).
- `legal_docs.status` đang tĩnh: cần xử lý trước 01/01/2027 (ND293 vẫn báo còn hiệu lực).
- Chưa đo ảnh hưởng của sửa FTS (bỏ dấu) lên retrieval vì chưa có index đóng băng.
- Cổng Docker 54329 nằm trong dải loại trừ của Windows trên máy dev (agent đã dùng cổng khác qua `TEST_DATABASE_URL`).
- Nợ nhỏ còn trong sổ ghi chép (ledger nội bộ `.superpowers/`, không commit): ~40 mục Minor được phân loại FIX-LATER/WONTFIX.

## 8. Mốc kiểm tra
- PR #1: https://github.com/ChrisLee1901/vn-labor-law-rag/pull/1 — tất cả job `pass` (deploy-preview/prod được bỏ qua do chưa có đủ secret).
- Lịch sử commit gần nhất trên `feat/rag-v1`: `4bbbbae` (kết quả smoke LLM), `3f470e2` (SSE PASS), `98ece74` (GGUF tìm ở mọi dataset), `a9076bc` (kết quả 0.2), `b16caee` (notebook libcuda), `effa2b1` (as_of), `547d0c9` (CI xanh).
