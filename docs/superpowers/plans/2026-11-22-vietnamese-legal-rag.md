# Trợ lý Pháp luật Lao động — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng một app RAG pháp luật lao động tiếng Việt end-to-end, chạy trên Vercel với GitHub CI/CD đầy đủ. Câu trả lời do LLM open-weight tự host trên Kaggle sinh ra, và app vẫn hữu dụng khi Kaggle tắt.

**Architecture:** Một repo, một project Vercel Services gồm 2 service: `web` (Next.js 16) và `api` (FastAPI, Python 3.12, không torch). Supabase pgvector giữ văn bản, chunk `halfvec(1024)` và FTS `simple`, trộn bằng RRF trong hàm SQL `hybrid_search`. Mọi model chạy trên notebook Kaggle T4 x2 sau một gateway FastAPI có bearer token, mở ra ngoài qua domain tĩnh của ngrok: GPU0 chạy `llama-server` với Qwen3-8B, GPU1 chạy embedder và reranker.

**Tech Stack:** Next.js 16, AI SDK v7 (`@ai-sdk/react`), shadcn/ui + AI Elements (bản shadcn), Tailwind v4, pnpm · FastAPI, httpx, psycopg 3, pydantic, uv, ruff, pyright, pytest, respx · Supabase Postgres + pgvector · llama.cpp `llama-server`, sentence-transformers, ngrok · GitHub Actions, Vercel CLI, Supabase CLI · ranx, Langfuse, Upstash Redis, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-vietnamese-legal-rag-design.md` (bối cảnh, mục tiêu, các quyết định đã chốt). Nghiên cứu nền: `docs/research/reports/Kiến trúc RAG tiếng Việt 2026.md`. Executor đọc cả hai trước khi bắt đầu.

## Global Constraints

- Sinh câu trả lời **chỉ** qua LLM self-host trên Kaggle (OpenAI-compatible). Cấm gọi Gemini/OpenAI/Claude API trong đường trả lời.
- `backend/` chỉ có runtime deps nhẹ: `fastapi`, `httpx`, `psycopg[binary]`, `pydantic`, `langfuse`. Cấm `torch`, `transformers`, `sentence-transformers`, `langchain`, `llama-index`. Bundle Python ≤ 500 MB.
- Python 3.12, quản lý bằng uv (`uv.lock` commit). Node 24, pnpm.
- Chuẩn hóa Unicode NFC ở **cả ingest lẫn query**.
- Supabase: **1 project** (`ap-southeast-1`). Migration chỉ additive. Re-ingest ghi vào `index_version` mới, chuyển bằng `app_config.active_index_version`.
- Kết nối DB từ Vercel qua pooler transaction mode, cổng **6543**, `prepare_threshold=None`, pool size 1.
- Function Vercel: region `sin1` (fallback `iad1`), `maxDuration` 120 s. Mọi call httpx tới gateway có timeout: connect 3 s, read 60 s.
- `LLM_BASE_URL` phải khớp `^https://[a-z0-9-]+\.ngrok-free\.(app|dev)$`, ngược lại coi như offline (chống SSRF).
- Gateway Kaggle: mọi route trừ `/health` đòi `Authorization: Bearer <GATEWAY_API_KEY>`, so sánh hằng thời gian (`hmac.compare_digest`).
- Mã văn bản cố định: `BLLD` (VBHN 18/VBHN-VPQH – BLLĐ 45/2019/QH14), `ND145-2020`, `ND293-2025`, `ND399-2026`, `LBHXH-2024` (41/2024/QH15), `ND158-2025`, `LVL-2025` (74/2025/QH15), `ND374-2025`.
- ID pháp lý: `<doc_code>:D<điều>[:K<khoản>[:<điểm>]]`, ví dụ `LBHXH-2024:D33:K1`, `ND145-2020:D12:K2:a`.
- Model IDs: embedder `AITeamVN/Vietnamese_Embedding` (1024 chiều), reranker `AITeamVN/Vietnamese_Reranker`, LLM `Qwen3-8B` GGUF `Q5_K_M` (fallback `Q4_K_M`), thinking tắt.
- Retrieval mặc định: RRF `rrf_k=50`, 40 ứng viên, rerank lấy top 6 Điều cha, mở rộng 1-hop tối đa 4 đoạn, child chunk ≤ 450 token.
- Copy UI tiếng Việt, `<html lang="vi">`, font `Be Vietnam Pro` subset `vietnamese`. Footer luôn có "Thông tin tham khảo, không phải tư vấn pháp lý."
- Secrets chỉ nằm trong Kaggle Secrets / Vercel env (Sensitive) / GitHub Secrets. Không bao giờ commit `.env`. gitleaks chạy trong CI.
- Kaggle: chỉ bật notebook trước buổi demo, không công khai URL tunnel (giảm rủi ro ToS "server farming").

## Review Focus

1. **Câu hỏi không dấu** ("luong toi thieu vung 1 nam 2026"). Mong đợi: vẫn ra NĐ 293/2025. Test ở Task 1.1 (`fts_noaccent`) và Task 3.2 (`test_tsquery_no_diacritics_hits_noaccent_column`).
2. **Tunnel đứt giữa lúc đang stream.** Mong đợi: UI giữ phần đã nhận, hiện lỗi tiếng Việt, stream kết thúc bằng `error` + `[DONE]`, không treo. Test ở Task 4.4 (`test_chat_stream_midway_disconnect_emits_error_then_done`).
3. **Câu hỏi chỉ định thời điểm** ("từ 1/1/2027", "năm 2027"). Mong đợi: lọc hiệu lực theo ngày trong câu hỏi, không theo ngày hôm nay. Test ở Task 3.2 (`test_extract_as_of`) và Task 1.1 (`test_hybrid_search_as_of_filters_effective_docs`).
4. **Supabase đang pause hoặc DB down.** Mong đợi: `/api/health` trả `db: "down"`, `/api/chat` trả lỗi tiếng Việt rõ ràng (503), không 500 trần. Test ở Task 4.4 (`test_chat_db_down_returns_503_vietnamese`).
5. **Người phỏng vấn mở bằng điện thoại.** Mong đợi: chat và panel nguồn dùng được ở viewport 390×844, không cuộn ngang. Test ở Task 5.5 (Playwright project `mobile`).

---

## Tổng quan phase và thứ tự

| Phase | Nội dung | Phụ thuộc | Chạy song song với |
|---|---|---|---|
| **P0** | Nền móng và spike rủi ro | — | Bên trong: 0.2‖0.3‖0.4‖0.5 sau 0.1 |
| **P1** | Corpus, schema, parser | 0.1, 0.5 | P2, P5.1, P6.1 |
| **P2** | Serving model trên Kaggle | 0.2, 0.3 | P1, P5.1, P6.1 |
| **P3** | Ingest, retrieval, golden set, eval truy xuất | P1 + P2 (riêng 3.3 chỉ cần 1.4) | — |
| **P4** | Sinh câu trả lời và API | P3 | P5.2–5.4 (dùng mock theo contract) |
| **P5** | Frontend UI/UX | 0.4 (5.1); contract của 4.3 (5.2+) | P1–P4 |
| **P6** | CI/CD đầy đủ | 0.4 (6.1 bắt đầu sớm và lớn dần) | Mọi phase |
| **P7** | Hoàn thiện portfolio | P4, P5, P6 | — |
| **P8** | Mở rộng bộ B (giao thông), tùy chọn | P7 | — |

```mermaid
graph LR
  T01[0.1 Repo] --> T02[0.2 llama.cpp] & T03[0.3 ngrok SSE] & T04[0.4 Vercel Services] & T05[0.5 Supabase]
  T05 --> P1[P1 Corpus+Schema]
  T02 & T03 --> P2[P2 Kaggle serving]
  T04 --> P51[5.1 UI shell] & P61[6.1 CI]
  P1 --> T33[3.3 Golden set]
  P1 & P2 --> P3[P3 Retrieval]
  P3 --> P4[P4 Generation+API]
  P4 --> P5x[5.2–5.5 UI tích hợp] --> P7[P7 Portfolio] --> P8[P8 Bộ B]
  P61 --> P6x[6.2–6.5] --> P7
```

`[USER]` đánh dấu bước người dùng phải tự làm: tạo tài khoản, bấm trên UI Kaggle hoặc Vercel, dán secret.

## Cấu trúc file (khóa ở đây)

```
vn-labor-law-rag/
├─ CLAUDE.md  README.md  LICENSE  .gitignore  .gitleaks.toml  vercel.json
├─ docs/
│  ├─ research/                  # research_notes/ + reports/ chuyển vào đây (Task 0.1)
│  ├─ corpus/raw/<code>/         # file gốc đã tải; corpus/docx/ (bản .docx đã chuyển); legal_docs.yaml; STATS.md
│  ├─ adr/NNNN-*.md  architecture.md  runbook-kaggle.md  spikes.md
│  └─ superpowers/{specs,plans}/
├─ backend/                      # service "api" (deploy)
│  ├─ pyproject.toml  uv.lock
│  ├─ app/main.py                # FastAPI app, include routers
│  ├─ app/config.py              # Settings (pydantic-settings)
│  ├─ app/legal/{normalize,ids,refs,dates}.py   # thuần Python, pipelines dùng chung
│  ├─ app/retrieval/{tsquery,search,expand,context}.py
│  ├─ app/llm/{gateway,prompt,citations}.py
│  ├─ app/api/{chat,health,docs,feedback,cron}.py
│  ├─ app/{stream,db,ratelimit,tracing,pii}.py
│  └─ tests/…                    # gương cấu trúc app/
├─ pipelines/                    # KHÔNG deploy; depends on backend (path, editable)
│  ├─ pyproject.toml  uv.lock
│  └─ rag_pipelines/{download,extract,structure,chunk,ingest,export_index,stats}.py
│     rag_pipelines/eval/{retrieval_eval,answer_eval,golden_schema}.py
├─ eval/                         # dữ liệu eval: golden/, cache/, index/, baselines/, results/
├─ kaggle/{gateway.py,serve.ipynb,requirements.txt,tests/}
├─ supabase/{config.toml,migrations/,tests/}
├─ frontend/                     # service "web"
│  └─ src/app/{page.tsx,van-ban/,gioi-thieu/,layout.tsx}, src/components/, src/lib/
└─ .github/{workflows/,dependabot.yml}
```

---

## Phase 0 — Nền móng và spike rủi ro

Mục tiêu: trả lời 4 câu hỏi chưa kiểm chứng trước khi viết code thật. Kết quả ghi vào `docs/spikes.md`. Spike là code bỏ đi, không cần TDD.

### Task 0.1: Khởi tạo repo

**Files:** Create `.gitignore`, `README.md` (khung), `LICENSE` (MIT), `.gitleaks.toml`, `CLAUDE.md` (đã có). Move `research_notes/` và `reports/` → `docs/research/`.

- [x] `git init -b main`. `.gitignore` gồm: `.env*`, `.venv/`, `node_modules/`, `.next/`, `__pycache__/`, `.vercel/`, `*.gguf`, `eval/cache/*.tmp`.
- [x] `git mv` hai thư mục research vào `docs/research/` (hoặc `mv` trước commit đầu). Sửa đường dẫn trong spec và CLAUDE.md.
- [ ] `[USER]` Tạo repo GitHub **public trên tài khoản cá nhân** (không phải org), tên `vn-labor-law-rag`, rồi `git remote add origin … && git push -u origin main`. — *đã làm phần local: repo local (nhánh main + feat/rag-v1); còn lại: chưa có remote/push, chờ [USER] tạo repo GitHub*
- [ ] `[USER]` Tạo tài khoản và lưu secret vào trình quản lý mật khẩu: Kaggle (đã xác minh số điện thoại, bật Internet cho notebook), ngrok (lấy authtoken + claim 1 dev domain tĩnh), Supabase, Vercel (Hobby, đăng nhập bằng GitHub), Langfuse Cloud (Hobby), Upstash (Redis free), Hugging Face (token read). — *chờ [USER]*
- [x] Kiểm tra: `git log --oneline` có commit `chore: bootstrap repo`; `docs/research/reports/` tồn tại.

### Task 0.2: Spike llama.cpp sm_75 trên Kaggle

**Files:** Create `kaggle/build_llamacpp.ipynb` (một lần), ghi kết quả vào `docs/spikes.md#llama`.

- [ ] `[USER]` Tạo notebook Kaggle, chọn **GPU T4 x2**, bật Internet. — *chờ [USER]*
- [ ] Build: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 && cmake --build build -j --target llama-server llama-bench`. Tạo symlink `libcuda.so` nếu linker báo thiếu. — *chờ live batch: cần Kaggle T4 x2 thật* — *notebook đã viết: kaggle/build_llamacpp.ipynb; chờ chạy trên Kaggle*
- [ ] Đóng gói `build/bin/*` cùng **mọi file `.so`** vào output, rồi tạo Kaggle Dataset `llamacpp-sm75-bin` (private). — *chờ live batch: cần Kaggle T4 x2 thật*
- [ ] Tải `Qwen3-8B-Q5_K_M.gguf` (repo GGUF chính thức của Qwen trên HF; nếu không có thì dùng bản `unsloth`), lưu thành Kaggle Dataset `qwen3-8b-gguf`. — *chờ live batch: cần Kaggle T4 x2 thật*
- [ ] Chạy `llama-bench -m … -ngl 99 -p 4096 -n 256`. Ghi pp/tg tok/s vào `docs/spikes.md`. **Đạt** khi tg ≥ 15 tok/s; nếu không, thử Q4_K_M và ghi lại. — *chờ live batch: cần Kaggle T4 x2 thật*
- [ ] Chạy `llama-server --help`, xác nhận tên cờ `--jinja`, `-fa`, `--chat-template-kwargs`, `--api-key`. Ghi vào spikes. — *chờ live batch: cần Kaggle T4 x2 thật*

### Task 0.3: Spike gateway + ngrok + SSE 2 phút

**Files:** Create `kaggle/spike_sse.py` (bỏ đi sau spike).

- [ ] Trên Kaggle, viết FastAPI tối giản: `GET /stream` phát 1 event mỗi giây trong 150 giây, có bearer token. — *chờ live batch: cần Kaggle + ngrok thật*
- [ ] Mở tunnel bằng `pyngrok` hoặc binary ngrok với `--url=<dev-domain>`, authtoken lấy từ Kaggle Secrets. — *chờ live batch: cần Kaggle + ngrok thật*
- [ ] Từ máy local, chạy `curl -N -H "Authorization: Bearer …" https://<domain>/stream`. **Đạt** khi nhận đủ 150 event, không bị cắt và không bị buffer dồn cục. Ghi kết quả vào spikes. — *chờ live batch: cần Kaggle + ngrok thật*
- [ ] Nếu ngrok cắt stream: ghi lại, rồi thử Cloudflare named tunnel (cần domain). Báo người dùng trước khi chọn phương án khác. — *chờ live batch: cần Kaggle + ngrok thật*
- [ ] Kiểm tra request không có token trả 401. — *chờ live batch: cần Kaggle + ngrok thật*

### Task 0.4: Spike Vercel Services + deploy từ Actions

**Files:** Create `vercel.json`, `frontend/` (create-next-app tối thiểu), `backend/app/main.py` (hello), `.github/workflows/spike-deploy.yml` (xóa sau spike).

- [ ] `vercel.json` khai báo 2 service: `web` (root `frontend`) và `api` (root `backend`, entrypoint `app.main:app`). Rewrite `/api/(.*)` sang `api`, phần còn lại sang `web`. Đặt `"git": {"deploymentEnabled": false}`. Tra cú pháp chính xác ở docs Vercel Services tại thời điểm làm. — *chờ live batch: spike Vercel Services chưa làm, chưa có vercel.json*
- [ ] FastAPI: `GET /api/ping` trả `{"ok": true}`, và `GET /api/sse` stream 30 event mỗi 1 giây. — *chờ live batch: spike Vercel Services chưa làm*
- [ ] `[USER]` Tạo project Vercel, lấy `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` và đưa vào GitHub Secrets. — *chờ [USER]*
- [ ] Workflow chạy `vercel pull --yes --environment=preview`, rồi `vercel build`, rồi `vercel deploy --prebuilt`. — *chờ live batch: cần project Vercel thật*
- [ ] **Đạt** khi URL preview có: `/` render Next.js, `/api/ping` ok, `/api/sse` stream từng event (`curl -N`). Ghi thêm: FastAPI nhận path có `/api` hay đã bị cắt, chỗ đặt `maxDuration` và region `sin1` có nhận không. — *chờ live batch: cần project Vercel thật*
- [ ] Nếu `--prebuilt` không hỗ trợ Services: chuyển sang Vercel Git integration, ghi ADR, và sửa Task 6.3 theo hướng đó. — *chờ live batch: cần project Vercel thật*
- [ ] Kiểm tra AI SDK v7: tên field của `source-url`, `data-*`, `error`, và header `x-vercel-ai-ui-message-stream`. Ghi vào spikes để Task 4.3 dùng. — *đã làm phần local: đã kiểm tra field qua docs trực tuyến ở Task 4.2 (docs/ai-sdk-protocol.md); còn lại: chưa ghi docs/spikes.md, chưa thử trên Vercel thật*

### Task 0.5: Spike Supabase

- [ ] `[USER]` Tạo project Supabase region `ap-southeast-1`, lấy connection string của pooler (cổng 6543) và service key. — *chờ [USER]*
- [ ] Chạy `create extension if not exists vector; select extversion from pg_extension where extname='vector';` rồi ghi version. Nếu ≥ 0.8.0 thì có iterative scan. — *chờ live batch: cần project Supabase thật*
- [ ] Từ function `/api/ping` của Task 0.4, chạy `select 1` qua psycopg với `prepare_threshold=None`. **Đạt** khi trả về trong < 1 s ở lần gọi nóng. — *chờ live batch: cần project Supabase thật*
- [ ] Viết `docs/spikes.md` tổng kết cả 4 spike, rồi commit `docs: phase 0 spike results`. — *chờ live batch: cần project Supabase thật*

**Cổng ra P0:** cả 4 spike đạt, hoặc đã có phương án thay thế được ghi lại và người dùng đồng ý.

---

## Phase 1 — Corpus, schema, parser

### Task 1.1: Migration schema và hàm `hybrid_search`

**Files:** Create `supabase/config.toml` (`supabase init`), `supabase/migrations/20261201000000_init.sql`, `supabase/migrations/20261201000100_hybrid_search.sql`, `supabase/tests/test_schema.py` (pytest + psycopg vào DB local).

**Interfaces — Produces:**
- `legal_docs(code text pk, number text, title text, doc_type text check in ('luat','bo_luat','vbhn','nghi_dinh','thong_tu'), issuer text, issued_on date, effective_from date, effective_to date null, status text, replaced_by text null references legal_docs, amends text[] default '{}', source_url text, file_sha256 text)`
- `articles(index_version int, id text, doc_code text references legal_docs, number int, suffix text null, title text, chapter text null, content text, primary key(index_version,id))`. `id` dạng `ND145-2020:D12`.
- `chunks(index_version int, id text, parent_id text, doc_code text, article int, clause int null, point text null, content text, embed_text text, n_tokens int, embedding halfvec(1024), fts tsvector generated always as (to_tsvector('simple', embed_text)) stored, fts_noaccent tsvector, primary key(index_version,id))`. Index: HNSW `embedding halfvec_ip_ops` (m=16, ef_construction=64), GIN trên `fts` và `fts_noaccent`, btree `(index_version, doc_code, article)`.
- `legal_refs(index_version int, src_id text, dst_doc_code text null, dst_doc_number text, dst_article int null, dst_clause int null, dst_point text null, rel text check in ('cites','details','amends'))`.
- `app_config(key text pk, value jsonb, updated_at timestamptz default now())`. Seed `('active_index_version','1')`, `('refusal_tau','0.35')`.
- `canned_answers(id serial pk, question_norm text unique, answer text, sources jsonb, created_at timestamptz)`.
- `feedback(id bigserial pk, trace_id text, score smallint check in (-1,1), comment text null, created_at timestamptz default now())`.
- `hybrid_search(query_text text, query_noaccent text, query_embedding halfvec(1024), index_version int, as_of date, match_count int default 40, full_text_weight float default 1, semantic_weight float default 1, rrf_k int default 50) returns table(id text, parent_id text, score float)`. Mỗi nhánh lấy `match_count*2` theo rank. FTS dùng `to_tsquery('simple', query_text)` OR với `to_tsquery('simple', query_noaccent)` trên `fts_noaccent`. Khi `query_embedding is null` thì chỉ chạy nhánh FTS (chế độ offline). Lọc theo văn bản có `effective_from <= as_of and (effective_to is null or as_of < effective_to)`.
- RLS bật trên mọi bảng, không có policy cho `anon` (backend dùng connection string server-side).

- [x] **Viết test hỏng** `supabase/tests/test_schema.py`. Fixture chèn 2 văn bản: `ND293-2025` (hiệu lực 2026-01-01 → 2027-01-01) và `ND399-2026` (từ 2027-01-01), mỗi văn bản có 1 chunk nói về "mức lương tối thiểu vùng I", embedding ngẫu nhiên cố định.
  - `test_hybrid_search_as_of_filters_effective_docs`: với `as_of='2026-06-01'` chỉ có id của ND293; với `as_of='2027-02-01'` chỉ có ND399.
  - `test_hybrid_search_fts_only_when_embedding_null`: truyền `query_embedding=None` vẫn ra kết quả.
  - `test_fts_noaccent_matches_unaccented_query`: query `luong & toi & thieu` trên `query_noaccent` ra chunk.
- [x] Chạy `supabase start` (Docker local), rồi `uv run --project pipelines pytest supabase/tests -v`. Mong đợi: FAIL (bảng chưa tồn tại). — *thực hiện khác kế hoạch: DB test là container Docker pgvector/pgvector:pg17 (scripts/test-db.sh, R1), không phải `supabase start`*
- [x] Viết 2 file migration theo Interfaces ở trên.
- [x] Chạy `supabase db reset`, rồi chạy lại test. Mong đợi: PASS. — *thực hiện khác kế hoạch: áp migration bằng test runner trên container Docker (R1), không phải `supabase db reset`*
- [x] Commit `feat(db): schema, hybrid_search RRF with as_of filter`.

### Task 1.2: `legal_docs.yaml` biên tập tay + downloader

**Files:** Create `docs/corpus/legal_docs.yaml`, `pipelines/pyproject.toml`, `pipelines/rag_pipelines/download.py`, `pipelines/tests/test_download.py`, `pipelines/tests/fixtures/congbao_page.html` (lưu từ trang NĐ 374/2025).

**Interfaces — Produces:** `parse_file_links(html: str) -> list[str]` (thứ tự ưu tiên docx > doc > pdf congbaocdn); CLI `uv run python -m rag_pipelines.download --docs docs/corpus/legal_docs.yaml --out docs/corpus/raw` ghi `docs/corpus/manifest.json` (`code, file, url, bytes, sha256`).

- [ ] Viết `legal_docs.yaml` cho 8 văn bản theo bảng dưới. **Bước kiểm tra tay:** mở vbpl.vn xác nhận tình trạng NĐ 145/2020 (có bị sửa trong 2025–2026 không) và ghi `status` cho đúng. — *đã làm phần local: legal_docs.yaml cho 8 văn bản; còn lại: [USER] xác minh tình trạng ND145-2020 trên vbpl.vn (còn `TODO(USER)` trong yaml)*

| code | number | effective_from | effective_to | replaced_by / amends |
|---|---|---|---|---|
| BLLD | 18/VBHN-VPQH (BLLĐ 45/2019/QH14) | 2021-01-01 | — | — |
| ND145-2020 | 145/2020/NĐ-CP | 2021-02-01 | — | — |
| ND293-2025 | 293/2025/NĐ-CP | 2026-01-01 | 2027-01-01 | replaced_by ND399-2026 |
| ND399-2026 | 399/2026/NĐ-CP | 2027-01-01 | — | — |
| LBHXH-2024 | 41/2024/QH15 | 2025-07-01 | — | — |
| ND158-2025 | 158/2025/NĐ-CP | 2025-07-01 | — | — |
| LVL-2025 | 74/2025/QH15 | 2026-01-01 | — | — |
| ND374-2025 | 374/2025/NĐ-CP | 2026-01-01 | — | — |

- [x] Test hỏng `test_parse_file_links_prefers_docx_then_doc_then_pdf`: từ fixture HTML, phần tử đầu tiên chứa `file_name=` và kết thúc bằng `.docx`, mọi link PDF là `congbaocdn`.
- [x] Viết `download.py`: cào lại trang mỗi lần chạy (không hard-code token g7), User-Agent `vn-labor-law-rag-corpus-fetcher/0.1`, nghỉ 1,5 s giữa các request, bỏ qua file đã có cùng sha256. Riêng `ND399-2026` lấy PDF datafiles ghi trong yaml.
- [x] Test PASS. Chạy CLI thật, so sánh với `docs/corpus/fetch_log.json`: 8 code đều có file, sha256 khớp hoặc đã cập nhật. — *thực hiện khác kế hoạch: so với `docs/corpus/manifest.json` (thay `fetch_log.json`, R10); 17 sha256 khớp*
- [x] Commit `feat(pipelines): legal_docs registry and Công báo downloader`.

### Task 1.3: Chuyển `.doc` và trích text

**Files:** Create `pipelines/rag_pipelines/extract.py`, `pipelines/tests/test_extract.py`, output `docs/corpus/docx/<code>.docx` (commit).

**Interfaces — Produces:** `extract_text(code: str) -> str`. Thứ tự ưu tiên: `docs/corpus/docx/<code>.docx` → `raw/<code>/*.docx` → PDF có text. Ghép các part theo thứ tự `part1, part2`, kết quả đã NFC, đã bỏ header Công báo.

- [ ] Cài LibreOffice (`winget install TheDocumentFoundation.LibreOffice`) và chạy một lần `soffice --headless --convert-to docx --outdir docs/corpus/docx <file.doc>` cho ND145 (2 part), ND293, LBHXH, ND158, LVL. Đặt tên `<code>.partN.docx`. — *không cài LibreOffice (R7): dùng docx gốc hoặc PDF text-layer; chuyển .doc→.docx là bước [USER] tùy chọn*
- [x] Test hỏng:
  - `test_strip_congbao_headers`: input có dòng `CÔNG BÁO/Số 1203 + 1204/Ngày 26-12-2020` và số trang lẻ. Output không còn các dòng đó.
  - `test_extract_is_nfc`: chuỗi dựng sẵn ở NFD → output `== unicodedata.normalize('NFC', …)`.
  - `test_extract_nd145_joins_two_parts`: text ND145 chứa cả "Điều 1." lẫn "Điều 115.".
- [x] Viết `extract.py`. DOCX dùng python-docx (đoạn văn + bảng, giữ thứ tự). PDF dùng `pymupdf`.
- [x] Test PASS. Commit `feat(pipelines): text extraction with Công báo header stripping`.

### Task 1.4: Parser cấu trúc pháp lý

**Files:** Create `pipelines/rag_pipelines/structure.py`, `backend/app/legal/ids.py`, `pipelines/tests/test_structure.py`, `backend/tests/legal/test_ids.py`.

**Interfaces — Produces:**
- `backend/app/legal/ids.py`: `make_id(doc_code: str, article: int, clause: int | None = None, point: str | None = None, suffix: str | None = None) -> str` và `parse_id(s: str) -> tuple[str, int, int | None, str | None]`.
- `structure.py`: `@dataclass Point(letter: str, text: str)`, `@dataclass Clause(number: int | None, text: str, points: list[Point])`, `@dataclass Article(doc_code: str, number: int, suffix: str | None, title: str, chapter: str | None, section: str | None, intro: str, clauses: list[Clause])`, `parse_document(text: str, doc_code: str) -> list[Article]`.
- Quy tắc: Chương `^Chương [IVXLC]+`, Mục `^Mục \d+`, Điều `^Điều (\d+)([a-z]?)\. (.*)`, Khoản `^(\d+)\. `, Điểm `^([a-zđ])\) `. Phần "Phụ lục" và mẫu biểu sau điều cuối bị **bỏ** (ghi số ký tự bị bỏ vào stats). Văn bản sửa đổi có "Điều 1." lồng trong dấu ngoặc kép không được tách thành Điều mới.

- [x] Test hỏng (dùng text thật qua `extract_text`):
  - `test_article_counts`: `{"BLLD": 220, "LBHXH-2024": 141, "LVL-2025": 55, "ND145-2020": 115}`, mỗi văn bản `len(articles) == n` và các số Điều liên tục từ 1.
  - `test_clause_and_point_parsing`: có ít nhất 1 Điều của BLLD với `clauses[0].points[0].letter == "a"`.
  - `test_make_parse_id_roundtrip`: `parse_id(make_id("ND145-2020", 12, 2, "a")) == ("ND145-2020", 12, 2, "a")`.
- [x] Viết code. Chạy `uv run pytest pipelines/tests/test_structure.py backend/tests/legal -v`. Mong đợi: PASS. Nếu số Điều lệch, in ra số bị thiếu hoặc trùng rồi sửa regex. **Không sửa con số trong test**: số đó lấy từ văn bản thật.
- [x] Commit `feat(legal): Vietnamese legal structure parser and ID scheme`.

### Task 1.5: Chunker + breadcrumb

**Files:** Create `pipelines/rag_pipelines/chunk.py`, `pipelines/tests/test_chunk.py`.

**Interfaces:**
- Consumes: `Article` (1.4), `make_id` (1.4), metadata từ `legal_docs.yaml`.
- Produces: `@dataclass Chunk(id: str, parent_id: str, doc_code: str, article: int, clause: int | None, point: str | None, content: str, embed_text: str, n_tokens: int)` và `chunk_articles(articles: list[Article], doc: dict, count_tokens: Callable[[str], int], max_tokens: int = 450) -> list[Chunk]`. Có thêm `strip_diacritics(s: str) -> str` (trong `backend/app/legal/normalize.py`, kèm `nfc(s)`).
- Breadcrumb (copy chính xác): `[{number} – {short_title}] {chapter} > Điều {n}. {title} | Khoản {k}:`. Bỏ `{chapter} > ` nếu không có chương, bỏ ` | Khoản {k}:` nếu Điều không có khoản. `embed_text = breadcrumb + "\n" + content`.
- Điều không có khoản thì là 1 chunk (id cấp Điều). Khoản > 450 token thì tách theo Điểm, mỗi Điểm 1 chunk có lặp phần dẫn của khoản. Điểm vẫn > 450 thì cắt theo câu.
- `count_tokens` trong pipelines dùng `tokenizers.Tokenizer.from_pretrained("AITeamVN/Vietnamese_Embedding")`.

- [x] Test hỏng (dùng `count_tokens = lambda s: len(s.split())` để test tất định):
  - `test_breadcrumb_format`: chunk K2 của Điều 12 ND145 có `embed_text.startswith("[145/2020/NĐ-CP – ")` và chứa `"Điều 12."` cùng `"| Khoản 2:"`.
  - `test_no_chunk_exceeds_max`: mọi chunk có `n_tokens <= 450`.
  - `test_every_article_has_parent_and_children`: tập `parent_id` bằng tập id Điều.
- [x] Viết code, test PASS, commit `feat(pipelines): structure-aware chunking with breadcrumbs`.

### Task 1.6: Trích tham chiếu chéo

**Files:** Create `backend/app/legal/refs.py`, `backend/tests/legal/test_refs.py`.

**Interfaces — Produces:** `@dataclass Ref(dst_doc_code: str | None, dst_doc_number: str, article: int | None, clause: int | None, point: str | None, rel: Literal["cites","details","amends"])`, `extract_refs(text: str, self_doc: str, aliases: dict[str, str]) -> list[Ref]`, và `DOC_ALIASES: dict[str, str]` (tên/số hiệu → code; văn bản ngoài corpus thì giữ `dst_doc_code=None`).

- [x] Test hỏng, input lấy từ câu thật:
  - `"theo quy định tại khoản 5 Điều 35 Luật Bảo hiểm y tế"` → `Ref(None, "Luật Bảo hiểm y tế", 35, 5, None, "cites")`.
  - `"Điều 47 Luật Việc làm"` → `dst_doc_code == "LVL-2025"`.
  - `"điểm a khoản 2 Điều 5 Nghị định số 145/2020/NĐ-CP"` → `("ND145-2020", 5, 2, "a")`.
  - `"quy định tại khoản 1 Điều này"` với `self_doc="BLLD"` → được bỏ qua (tự tham chiếu trong cùng Điều, không lưu).
  - `"khoản 3 Điều 20 của Bộ luật này"` → `dst_doc_code == "BLLD"`.
  - Câu "Nghị định này quy định chi tiết … Điều 12 Bộ luật Lao động" → `rel == "details"`.
- [x] Viết regex. Test PASS. Commit `feat(legal): cross-reference extractor`.

### Task 1.7: Thống kê corpus

**Files:** Create `pipelines/rag_pipelines/stats.py`, output `docs/corpus/STATS.md`.

- [x] CLI in bảng theo văn bản: số Điều, Khoản, chunk, token (p50/p95/max), số ref (nội bộ corpus / ngoài corpus), số ký tự bị bỏ (phụ lục).
- [x] Chạy rồi commit `STATS.md`. **Đạt** khi tổng chunk nằm trong khoảng 2.000–8.000 và không có chunk > 450 token. Nếu lệch thì xem lại 1.4/1.5.

### Task 1.8: Giữ Phụ lục danh mục địa bàn (bổ sung sau review 1.7)

> Lý do: parser 1.4 bỏ toàn bộ phụ lục. Phụ lục NĐ 293/2025 "Danh mục địa bàn áp dụng mức lương tối thiểu từ 01/01/2026" (~21.7k ký tự, theo 34 tỉnh/thành sau sáp nhập) là căn cứ duy nhất cho câu hỏi kiểu "phường X thuộc vùng nào". Các phụ lục biểu mẫu (ND145, ND374, ND158) vẫn bỏ vì nhiễu.

**Files:** Modify `docs/corpus/legal_docs.yaml` (thêm `keep_appendix: true` cho ND293-2025), `backend/app/legal/ids.py`, `pipelines/rag_pipelines/structure.py`, `pipelines/rag_pipelines/chunk.py`, `pipelines/rag_pipelines/stats.py`. Create `supabase/migrations/20261201000200_appendix_kind.sql`. Tests tương ứng.

**Interfaces — Produces:**
- `make_appendix_id(doc_code: str, appendix: int, item: int | None = None) -> str` → `ND293-2025:PL1` / `ND293-2025:PL1:M3`; `is_appendix_id(s: str) -> bool`.
- `@dataclass Appendix(doc_code: str, number: int, title: str, items: list[tuple[int, str, str]])` (item number, heading như "Thành phố Hà Nội", text); `parse_appendices(text: str, doc_code: str) -> list[Appendix]`: bắt đầu từ dòng `^Phụ lục( [IVX]+)?$` sau khối chữ ký, tiêu đề là các dòng IN HOA tiếp theo + dòng "(Kèm theo …)", mục là `^(\d+)\. (.+)$` tăng dần, nội dung mục gồm các dòng "- Vùng …" (nối dòng bị wrap).
- `chunk_appendices(appendices, doc, count_tokens, max_tokens=450) -> list[Chunk]`: 1 chunk/mục, id `make_appendix_id(code, n, item)`, `parent_id = make_appendix_id(code, n)`, breadcrumb `[{number} – {short_title}] Phụ lục {n}. {title} | {heading}:`; quá 450 token thì tách theo dòng "- Vùng …", rồi theo câu (`#k`).
- Migration additive: `alter table articles add column kind text not null default 'dieu' check (kind in ('dieu','phu_luc'));` — phụ lục lưu vào `articles` với `kind='phu_luc'`, `number` = số phụ lục, `id` = `make_appendix_id(code, n)`.

- [x] Test hỏng:
  - `test_nd293_appendix_parsed`: `parse_appendices(extract_text("ND293-2025"), "ND293-2025")` có 1 phụ lục, mục 1 heading "Thành phố Hà Nội", text chứa "Vùng I" và "Hoàn Kiếm"; số mục == 34.
  - `test_appendix_chunks_ids_and_limit`: mọi chunk có id dạng `ND293-2025:PL1:M\d+(#\d+)?`, `n_tokens <= 450`; id duy nhất.
  - `test_appendix_id_roundtrip`: `make_appendix_id("ND293-2025",1,3) == "ND293-2025:PL1:M3"`, `is_appendix_id(...)` True, `is_appendix_id("ND293-2025:D3")` False.
  - `test_articles_kind_column` (supabase/tests): insert article kind 'phu_luc' ok; kind 'x' vi phạm check.
  - Doc không có `keep_appendix` → không sinh chunk phụ lục.
- [x] Viết code; `stats.py` thêm cột "Chunk phụ lục". Chạy lại stats (tổng chunk vẫn trong 2.000–8.000, max ≤ 450).
- [x] Commit `feat(pipelines): keep ND293 locality appendix as chunks`.

---

## Phase 2 — Serving model trên Kaggle (song song với P1)

### Task 2.1: Gateway

**Files:** Create `kaggle/gateway.py`, `kaggle/requirements.txt` (fastapi, uvicorn, httpx, sentence-transformers, pyngrok), `kaggle/tests/test_gateway.py`.

**Interfaces — Produces (HTTP contract, backend dựa vào):**
- `GET /health` (không auth) → `{"status": "ok"|"loading", "llm": bool, "embedder": bool, "reranker": bool, "model": "<gguf name>"}`. `llm=true` chỉ khi `llama-server /health` trả `status == "ok"`.
- `POST /v1/embeddings` `{"input": [str], "model"?: str}` → `{"data": [{"index": i, "embedding": [1024 float]}]}`. Có normalize L2.
- `POST /v1/rerank` `{"query": str, "documents": [str], "top_n": int}` → `{"results": [{"index": i, "relevance_score": float in [0,1]}]}` sắp giảm dần (sigmoid của logit).
- `POST /v1/chat/completions` proxy trong suốt tới `http://127.0.0.1:8080`, giữ SSE (`StreamingResponse`, không buffer).
- `create_app(embedder, reranker, llm_url: str, api_key: str) -> FastAPI`. Model được inject để test dùng fake.

- [x] Test hỏng (FastAPI TestClient + fake embedder/reranker + respx mock llama-server):
  - `test_requires_bearer`: thiếu hoặc sai token trên `/v1/embeddings` → 401; `/health` → 200.
  - `test_embeddings_shape`: 3 input → 3 vector độ dài 1024.
  - `test_rerank_sorted_and_bounded`: điểm giảm dần, thuộc [0,1], `len == top_n`.
  - `test_chat_proxy_streams_chunks`: mock upstream trả 3 dòng `data:` → client nhận đủ 3 dòng theo thứ tự.
  - `test_health_loading_when_llm_not_ok`: upstream trả `{"status":"loading"}` → `llm is False`.
- [x] Viết `gateway.py`. Chạy `uv run --with-requirements kaggle/requirements.txt pytest kaggle/tests -v` (fake model, chạy được trên CPU). Mong đợi: PASS. — *thực hiện khác kế hoạch: chạy với `kaggle/requirements-test.txt` (không cài torch, R17)*
- [x] Commit `feat(kaggle): authenticated gateway for embed/rerank/chat proxy`.

### Task 2.2: Notebook serve + runbook

**Files:** Create `kaggle/serve.ipynb`, `docs/runbook-kaggle.md`.

- [x] Các cell notebook theo thứ tự:
  1. Đọc Kaggle Secrets `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `GATEWAY_API_KEY`, `HF_TOKEN`.
  2. Copy binary từ dataset `llamacpp-sm75-bin`.
  3. Chạy `CUDA_VISIBLE_DEVICES=0 llama-server -m /kaggle/input/qwen3-8b-gguf/… -ngl 99 -c 16384 -np 2 --jinja --host 127.0.0.1 --port 8080` với thinking tắt (cờ đã xác nhận ở 0.2).
  4. Poll `/health` tới `status=="ok"`.
  5. Load embedder và reranker fp16 trên `cuda:1`.
  6. Chạy uvicorn `gateway:create_app(...)` ở cổng 8000 (thread).
  7. Mở ngrok `--url=$NGROK_DOMAIN` tới 8000.
  8. In `READY https://<domain>` cùng kết quả smoke test.
  9. Cell cuối giữ phiên sống: vòng lặp log `/health` mỗi 60 s.
- [x] `runbook-kaggle.md`: checklist "trước phỏng vấn 15 phút" (mở notebook → chọn T4 x2 → Run All → chờ READY → mở app thấy badge xanh → hỏi thử 1 câu), "sau phỏng vấn" (Stop session), và cách xử lý sự cố (queue GPU, 401, badge vẫn đỏ).
- [ ] `[USER]` Thêm 4 secret vào Kaggle, chạy notebook. **Đạt** khi in `READY` trong ≤ 10 phút từ lúc Run All. — *chờ [USER]: chạy notebook thật trên Kaggle; chưa chạy*
- [x] Commit `feat(kaggle): serve notebook and interview runbook`.

### Task 2.3: Smoke + benchmark

**Files:** Create `scripts/smoke_llm.py` (chạy local, đọc `LLM_BASE_URL`, `LLM_API_KEY` từ env).

- [ ] Script kiểm tra: `/health` có `llm` true; embed 2 câu tiếng Việt ra 1024 chiều; rerank câu "lương tối thiểu vùng I" xếp đoạn liên quan lên đầu; chat stream một câu tiếng Việt, đo TTFT và tok/s trên 3 lần. — *chờ live batch: chưa viết scripts/smoke_llm.py, hoãn sang live batch (R19)*
- [ ] Ghi số đo vào `docs/spikes.md#bench`. **Đạt** khi TTFT p50 < 3 s qua tunnel và câu trả lời là tiếng Việt có dấu đúng. — *chờ live batch: cần gateway live qua tunnel*
- [ ] Commit `chore: LLM smoke and benchmark script`. — *chờ live batch: chưa làm, hoãn sang live batch (R19)*

---

## Phase 3 — Ingest, retrieval, golden set, eval truy xuất

### Task 3.1: Ingest + export index đóng băng

**Files:** Create `pipelines/rag_pipelines/ingest.py`, `pipelines/rag_pipelines/export_index.py`, `pipelines/tests/test_ingest.py`.

**Interfaces:**
- Consumes: `extract_text`, `parse_document`, `chunk_articles`, `extract_refs`, gateway `/v1/embeddings`.
- Produces: CLI `python -m rag_pipelines.ingest --index-version N [--dry-run]`. Upsert `legal_docs`, `articles`, `chunks` (kèm `fts_noaccent = to_tsvector('simple', strip_diacritics(embed_text))` tính trong Python), `legal_refs`. Embed theo batch 32. **Không** đổi `active_index_version`.
- `python -m rag_pipelines.export_index --index-version N` → `eval/index/v{N}.parquet` (cột: `id, parent_id, doc_code, article, clause, point, embed_text, content, embedding: list[float16]`) + `eval/index/v{N}.legal.parquet` (legal_docs, articles, legal_refs). Đây là dữ liệu CI dùng.

- [x] Test hỏng (DB local + fake embed client trả vector cố định):
  - `test_ingest_idempotent`: chạy 2 lần → số dòng `chunks` không đổi.
  - `test_ingest_does_not_switch_active_version`: sau khi ingest v2, `app_config.active_index_version` vẫn là `1`.
  - `test_refs_resolved_to_existing_articles`: mọi `legal_refs` có `dst_doc_code` thuộc corpus đều trỏ tới `articles.id` tồn tại, hoặc được đếm là "không phân giải" trong log.
- [x] Viết code, test PASS.
- [ ] Chạy thật với Kaggle bật: `--index-version 1` lên Supabase project, rồi export. Ghi `pg_total_relation_size('chunks')` vào STATS.md (phải < 150 MB). — *chờ live batch: ingest thật cần Kaggle embedder + Supabase; chưa chạy, chưa ghi kích thước vào STATS.md*
- [x] Commit `feat(pipelines): ingest to Supabase and frozen index export` (commit cả `eval/index/v1*.parquet` nếu < 50 MB, nếu lớn hơn thì dùng Git LFS). — *đã commit code + test; `eval/index/v1*.parquet` chưa có (chờ live batch)*

### Task 3.2: Retrieval core ở backend

**Files:** Create `backend/app/legal/dates.py`, `backend/app/retrieval/tsquery.py`, `backend/app/retrieval/search.py`, `backend/app/retrieval/expand.py`, `backend/app/llm/gateway.py`, `backend/app/db.py`, `backend/app/config.py`, cùng test tương ứng trong `backend/tests/`.

**Interfaces — Produces:**
- `build_tsquery(q: str) -> str | None`: NFC, lowercase, bỏ stopword (danh sách trong `tsquery.py`: của, và, là, các, những, được, có, cho, với, thì, mà, này, đó, khi, nào, gì, bao, nhiêu, không, tôi, em, ạ…), cụm trong `"…"` nối bằng `<->`, phần còn lại nối bằng ` | `. Escape ký tự đặc biệt của tsquery. Trả `None` nếu rỗng.
- `extract_query_ids(q: str) -> list[str]`: dùng `refs.py`, trả về ID kiểu `ND145-2020:D12[:K2]`.
- `extract_as_of(q: str, today: date) -> date`: nhận "từ 1/1/2027", "từ ngày 01/01/2027", "năm 2027" (→ 2027-01-01 nếu năm > năm hiện tại, ngược lại → 31/12 của năm đó). Mặc định trả `today`.
- `class Gateway(base_url: str | None, api_key: str)` với `async embed(texts: list[str]) -> list[list[float]]`, `async rerank(query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]`, `async health() -> bool`, `chat_stream(messages: list[dict]) -> AsyncIterator[str]` (yield text delta), `is_allowed(url) -> bool` (regex ngrok). URL không hợp lệ hoặc `None` → mọi call raise `LLMOffline`.
- `@dataclass Candidate(id: str, parent_id: str, score: float, rerank: float | None = None)`.
- `async retrieve(question: str, as_of: date, gw: Gateway, conn, index_version: int, online: bool) -> list[Candidate]`: online thì embed + hybrid + rerank top 6 theo parent; offline thì `hybrid_search(query_embedding=None)` lấy top 6 parent theo điểm RRF. ID trích được bằng regex luôn được chèn lên đầu.
- `async expand(parent_ids: list[str], conn, index_version: int, max_extra: int = 4) -> list[SourceDoc]` với `@dataclass SourceDoc(sid: str, id: str, doc_code: str, doc_number: str, article: int, title: str, content: str, effective_from: date, effective_to: date | None, status: str, via_ref: bool)`. `sid` là `S1…Sn` theo thứ tự.

- [x] Test hỏng:
  - `test_build_tsquery_or_and_stopwords`: `build_tsquery("Mức lương tối thiểu của vùng I là bao nhiêu")` không chứa `của` và `bao`, có chứa `' | '`.
  - `test_build_tsquery_phrase`: `'"thời gian thử việc"'` → chứa `'thời <-> gian <-> thử <-> việc'`.
  - `test_tsquery_no_diacritics_hits_noaccent_column` (DB local, dữ liệu fixture 1.1): `retrieve("luong toi thieu vung 1", online=False)` trả về id ND293.
  - `test_extract_as_of`: `"từ 1/1/2027 lương tối thiểu vùng I"` với `today=2026-11-22` → `date(2027,1,1)`; câu không có ngày → `today`.
  - `test_gateway_rejects_non_ngrok_url`: `Gateway("http://169.254.169.254", "k").is_allowed(...) is False`, gọi `embed` raise `LLMOffline`.
  - `test_regex_id_pinned_first`: câu "Điều 12 Nghị định 145/2020 nói gì" → candidate đầu tiên có `parent_id == "ND145-2020:D12"`.
  - `test_expand_adds_ref_targets_once`: parent có ref tới `LVL-2025:D47` → kết quả có đúng 1 SourceDoc `via_ref=True` cho D47, không trùng.
- [x] Viết code. psycopg dùng `AsyncConnectionPool(min_size=1, max_size=1, kwargs={"prepare_threshold": None})`. Test với respx cho gateway và DB local cho SQL.
- [x] Test PASS. Commit `feat(api): hybrid retrieval, rerank, as_of and reference expansion`.

### Task 3.3: Golden set (Claude sinh + kiểm chéo)

**Files:** Create `pipelines/rag_pipelines/eval/golden_schema.py`, `pipelines/tests/test_golden_schema.py`, `eval/golden/v1.jsonl`, `eval/golden/DATASET_CARD.md`, `eval/golden/review_sample.csv`.

**Interfaces — Produces:** mỗi dòng JSONL có dạng `{"id": "q001", "question": str, "answer": str, "gold": ["LBHXH-2024:D33:K1", …], "type": "single|numeric|multi_hop|temporal|compare|unanswerable|out_of_domain|injection", "as_of": "YYYY-MM-DD", "split": "dev|test", "source_quote": str}`. `gold` rỗng khi và chỉ khi type thuộc nhóm unanswerable, out_of_domain hoặc injection. `load_golden(path) -> list[GoldItem]` có validate.

- [x] Test hỏng `test_golden_valid`:
  - Mọi ID trong `gold` tồn tại trong output `parse_document` của văn bản tương ứng.
  - Tỷ lệ theo type (±3 điểm %): single 35, numeric 15, multi_hop 15, temporal 5, compare 10, unanswerable 10, out_of_domain+injection 10.
  - `len == 120`, dev 40 / test 80, phân tầng theo type.
  - Không có câu nào có độ trùng từ (Jaccard trên âm tiết) > 0.6 so với `source_quote` (chống chép nguyên văn).
- [x] **Sinh:** dispatch subagent `model: sonnet`, effort `medium`. Input là text đã parse (theo `extract_text` + `parse_document`) và schema ở trên. Yêu cầu: câu hỏi ngôn ngữ đời thường; multi_hop lấy từ các cặp trong `legal_refs`; temporal dùng ND293 so với ND399; `source_quote` trích nguyên văn; sinh 160 ứng viên.
- [x] **Kiểm chéo:** dispatch một subagent **khác** (`model: sonnet`, effort `medium`), chỉ đưa câu hỏi cùng văn bản gốc, **không** đưa đáp án. Subagent này tự trả lời và tự gán gold. Giữ câu khi đáp án khớp và gold giao nhau ≥ 1. Ghi tỷ lệ loại vào DATASET_CARD. Chọn 120 câu theo quota.
- [ ] Xuất 20 câu ngẫu nhiên (seed 42) ra `review_sample.csv`. `[USER]` Đọc và đánh dấu đúng/sai. Ghi kết quả vào DATASET_CARD. — *đã làm phần local: đã xuất review_sample.csv (20 câu, seed 42); còn lại: chờ [USER] đánh dấu đúng/sai và ghi vào DATASET_CARD*
- [x] Test PASS. Commit `feat(eval): golden set v1 (Claude-generated, cross-verified)`.

### Task 3.4: Harness eval truy xuất + bảng ablation đầu tiên

**Files:** Create `pipelines/rag_pipelines/eval/retrieval_eval.py`, `pipelines/tests/test_retrieval_eval.py`, `eval/cache/query_emb_AITeamVN-Vietnamese_Embedding.npy` (+ `.ids.json`), `eval/baselines/main.json`, `eval/results/retrieval_v1.md`.

**Interfaces — Produces:** CLI `python -m rag_pipelines.eval.retrieval_eval --index eval/index/v1.parquet --golden eval/golden/v1.jsonl --modes fts,dense,hybrid[,hybrid_rerank] --split test --out eval/results/…json`. Metric ranx: `hit_rate@1, recall@5, recall@10, recall@20, mrr@10, ndcg@10`, tính ở **cấp Điều** (map chunk → parent). Chỉ tính các câu có gold. `--compare eval/baselines/main.json --max-drop 0.03` exit 1 nếu `recall@10` hoặc `mrr@10` giảm quá ngưỡng.

- [x] Test hỏng:
  - `test_metrics_article_level`: 2 chunk cùng parent đúng → `hit_rate@1 == 1`, không bị tính trùng.
  - `test_compare_fails_on_drop`: baseline 0.80, hiện tại 0.76 → exit code 1.
  - `test_cache_miss_raises_clear_error`: golden có câu chưa có trong cache embedding → thông báo `"chạy --refresh-cache khi Kaggle bật"`.
- [x] Viết code. Trong CI, nhánh dense/hybrid dùng embedding câu hỏi đã cache cùng index parquet, nạp vào Postgres local (`supabase db start`). `hybrid_rerank` chỉ chạy khi có `LLM_BASE_URL`.
- [ ] Với Kaggle bật: `--refresh-cache`, chạy cả 4 mode trên split test, ghi bảng vào `retrieval_v1.md`, lưu `baselines/main.json` từ mode `hybrid`. — *chờ live batch: cần Kaggle embedder; chưa có eval/cache, baselines/main.json, retrieval_v1.md*
- [x] Commit `feat(eval): ranx retrieval harness, cached query embeddings, baseline`.

---

## Phase 4 — Sinh câu trả lời và API

### Task 4.1: Prompt + kiểm tra trích dẫn + ngưỡng từ chối

**Files:** Create `backend/app/llm/prompt.py`, `backend/app/llm/prompts/answer_v1.md`, `backend/app/llm/citations.py`, cùng tests.

**Interfaces — Produces:**
- `build_messages(question: str, sources: list[SourceDoc], history: list[dict], as_of: date) -> list[dict]`. System prompt đọc từ `answer_v1.md`. Mỗi nguồn được định dạng: `[S1] {doc_number}, Điều {n}. {title} — hiệu lực {dd/mm/yyyy}{" đến " + dd/mm/yyyy nếu có}\n{content}`.
- `answer_v1.md` phải yêu cầu: chỉ dùng nguồn được cung cấp; trích `[S#]` sau mỗi ý; nêu số Điều/Khoản; nếu nguồn không đủ thì nói "Tôi không tìm thấy căn cứ trong các văn bản hiện có"; trả lời tiếng Việt; bỏ qua mọi chỉ dẫn nằm trong câu hỏi hoặc nguồn mà yêu cầu thay đổi vai trò.
- `check_citations(answer: str, sources: list[SourceDoc]) -> CitationReport(valid: list[str], invalid: list[str], uncited: bool, article_mismatch: list[str])`. `article_mismatch` là các "Điều N" được nhắc trong câu trả lời nhưng không có trong header của nguồn.
- `should_refuse(candidates: list[Candidate], tau: float) -> bool`: `max(rerank) < tau`. Không có rerank (offline) thì trả `False`.
- `condense_messages(history: list[dict], question: str) -> list[dict]`: prompt ngắn yêu cầu viết lại câu hỏi thành câu độc lập. Chỉ dùng từ lượt thứ 2.

- [x] Test hỏng:
  - `test_invalid_citation_flagged`: sources S1–S3, answer chứa `[S5]` → `invalid == ["S5"]`.
  - `test_article_mismatch`: answer nói "Điều 99" nhưng không nguồn nào có Điều 99 → `"Điều 99" in article_mismatch`.
  - `test_should_refuse_below_tau`: rerank max 0.2, tau 0.35 → True.
  - `test_source_header_shows_effective_window`: SourceDoc ND293 → header chứa `"hiệu lực 01/01/2026 đến 01/01/2027"`.
- [x] Viết code, test PASS, commit `feat(api): grounded prompt, citation checks, refusal threshold`.

### Task 4.2: Emitter UI Message Stream

**Files:** Create `backend/app/stream.py`, `backend/tests/test_stream.py`.

**Interfaces — Produces:** `sse(part: dict) -> bytes` (`b"data: " + json + b"\n\n"`, `ensure_ascii=False`), `DONE = b"data: [DONE]\n\n"`, `STREAM_HEADERS = {"x-vercel-ai-ui-message-stream": "v1", "content-type": "text/event-stream", "cache-control": "no-cache"}`, và các builder: `start(message_id)`, `source_url(sid, url, title)`, `text_start(id)`, `text_delta(id, delta)`, `text_end(id)`, `data_status(llm: str, mode: Literal["rag","offline","refused"])`, `error(text)`, `finish()`. Tên field lấy theo ghi chú v7 ở `docs/spikes.md`.

- [x] Test hỏng:
  - `test_sse_utf8_vietnamese`: `sse(text_delta("t1","Điều"))` decode ra chứa `"Điều"` nguyên dạng (không `\u`).
  - `test_sequence_order`: một luồng mẫu có thứ tự `start → data-status → source-url* → text-start → text-delta+ → text-end → finish → [DONE]`.
- [x] Viết code, test PASS, commit `feat(api): AI SDK UI message stream emitter`.

### Task 4.3: Contract API (cho frontend mock song song)

**Files:** Create `docs/api-contract.md`, `frontend/src/lib/api-types.ts`.

- [x] Viết contract:
  - `POST /api/chat`: body `{messages: UIMessage[], as_of?: "YYYY-MM-DD"}`, trả về stream như 4.2. URL của `source-url` là `/van-ban/{doc_code}#D{n}`.
  - `GET /api/health` → `{llm: "online"|"offline", db: "ok"|"down", index_version: number}`.
  - `GET /api/docs` → `[{code, number, title, doc_type, effective_from, effective_to, status, articles: number}]`.
  - `GET /api/docs/{code}` → `{doc, articles: [{id, number, title, chapter, content}]}`.
  - `POST /api/feedback` `{trace_id, score: 1|-1, comment?}` → 204.
  - `GET /api/cron/keepalive` (header `Authorization: Bearer $CRON_SECRET`) → 204.
  - Lỗi: `{detail: string}` tiếng Việt, gồm 422 (input), 429 (rate limit), 503 (DB down).
- [x] Viết type TS tương ứng. Commit `docs: API contract`.

### Task 4.4: Các endpoint FastAPI

**Files:** Create `backend/app/main.py`, `backend/app/api/{chat,health,docs,feedback,cron}.py`, `backend/app/tracing.py`, `backend/app/pii.py`, `backend/tests/api/test_*.py`.

**Interfaces:**
- Consumes: mọi thứ từ 3.2, 4.1, 4.2. Settings (env): `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `CRON_SECRET`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`.
- Luồng `/api/chat`: validate (câu hỏi cuối 1–1000 ký tự, ≤ 10 lượt, sai thì 422 `"Câu hỏi quá dài (tối đa 1000 ký tự)."`) → rate limit (4.5) → kiểm tra health gateway (cache 15 s) → khớp canned answer nếu offline → `retrieve` → `should_refuse` → `expand` → stream. Offline: emit `data-status{llm:"offline",mode:"offline"}`, các `source-url`, và một text cố định *"Mô hình đang ngoại tuyến. Dưới đây là các điều luật liên quan nhất:"* kèm danh sách Điều. Refused: `mode:"refused"` cùng câu từ chối cố định, không gọi LLM.
- Sau khi stream xong: `check_citations` → nếu có invalid hoặc mismatch thì emit `data-citation-warning`. Trace Langfuse (input đã qua `redact_pii`) với `flush()` trong `finally`. `trace_id` gửi trong `data-trace`.
- `redact_pii(s) -> str`: thay CCCD 12 số, số điện thoại VN `(0|\+84)\d{9,10}` và email bằng `[đã ẩn]`.

- [x] Test hỏng (TestClient, respx mock gateway, DB local):
  - `test_chat_online_streams_sources_then_text`: có `source-url` trước `text-delta` đầu tiên, kết thúc bằng `[DONE]`.
  - `test_chat_offline_returns_fts_sources`: gateway `/health` lỗi → `mode == "offline"`, có ≥ 1 `source-url`, không có call nào tới `/v1/chat/completions`.
  - `test_chat_refuses_without_llm_call`: rerank max < tau → `mode == "refused"`, respx route chat có `call_count == 0`.
  - `test_chat_stream_midway_disconnect_emits_error_then_done`: upstream phát 2 delta rồi raise `httpx.ReadError` → output chứa 2 delta, một `error` có text tiếng Việt, rồi `[DONE]`.
  - `test_chat_db_down_returns_503_vietnamese`: pool raise `OperationalError` → 503, `detail` chứa `"Cơ sở dữ liệu"`.
  - `test_chat_input_too_long_422`.
  - `test_cron_requires_secret`: không có header → 401; có header → 204 và chạy `select 1`.
  - `test_redact_pii`: `"CCCD 001203004567, sđt 0912345678"` → không còn số nào trong 2 chuỗi đó.
- [x] Viết code, test PASS, commit `feat(api): chat/health/docs/feedback/cron endpoints with offline mode`.

### Task 4.5: Rate limit

**Files:** Create `backend/app/ratelimit.py`, `backend/tests/test_ratelimit.py`.

**Interfaces — Produces:** `async check(ip: str) -> bool`. Upstash REST qua httpx, fixed window: mỗi IP 20 request / 10 phút, toàn cục 300 request / ngày. Upstash không phản hồi (timeout 1 s) thì **cho qua và log cảnh báo**, vì lớp WAF của Vercel vẫn còn (ghi lý do bằng comment một dòng trong code).

- [x] Test (respx): request thứ 21 trong cửa sổ → False; Upstash timeout → True.
- [x] Viết code, nối vào `/api/chat` (429 `"Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút."`). Commit `feat(api): Upstash rate limiting`.

---

## Phase 5 — Frontend UI/UX (5.1 song song từ sau P0; 5.2–5.4 dùng mock theo contract 4.3)

> Dùng skill `hallmark` cho phần thiết kế giao diện (theo routing trong CLAUDE.md toàn cục). Phong cách: nghiêm túc, đáng tin như một văn bản pháp lý, không dùng gradient tím kiểu "AI".

### Task 5.1: Khung app và design system

**Files:** `frontend/` (Next.js 16 App Router, TS strict, Tailwind v4), `frontend/src/app/layout.tsx`, `frontend/src/components/ui/*` (shadcn), `frontend/src/components/ai-elements/*` (shadcn AI Elements), `frontend/src/components/site-header.tsx`, `frontend/src/components/status-badge.tsx`, `frontend/vitest.config.ts`.

- [x] `pnpm dlx shadcn@latest init`, rồi thêm các component `button card badge sheet tooltip hover-card scroll-area separator skeleton sonner` và các AI Elements cần cho chat (conversation, message, prompt-input, sources, inline-citation, loader). — *thực hiện khác kế hoạch: AI Elements không còn là package; dùng message/message-scroller/bubble/trace, loader=spinner, prompt-input/inline-citation/sources tự soạn ở 5.2*
- [x] Layout: `lang="vi"`, `Be Vietnam Pro` (subset `vietnamese`, weight 400/500/600/700), dark/light theo hệ thống cộng nút đổi. Header có tên app, các nav "Hỏi đáp / Văn bản / Giới thiệu" và `StatusBadge`. Footer có câu disclaimer (Global Constraints).
- [x] `StatusBadge` poll `GET /api/health` mỗi 30 s: xanh "Mô hình trực tuyến", xám "Chế độ ngoại tuyến", đỏ "Mất kết nối dữ liệu".
- [x] Test Vitest `status-badge.test.tsx`: mock fetch trả `{llm:"offline",db:"ok"}` → hiện text "Chế độ ngoại tuyến".
- [x] `pnpm lint && pnpm typecheck && pnpm test && pnpm build` xanh. Commit `feat(web): app shell, design tokens, status badge`.

### Task 5.2: Trang Hỏi đáp

**Files:** `frontend/src/app/page.tsx`, `frontend/src/components/chat/{chat.tsx,sources-panel.tsx,citation.tsx,suggested-questions.tsx,feedback.tsx}`, `frontend/src/lib/chat-storage.ts`, `frontend/src/mocks/chat-stream.ts` (mock SSE theo contract để dev khi backend chưa xong).

- [x] `useChat` với `DefaultChatTransport({ api: "/api/chat" })`. Markdown được render; `[S#]` trong text thành `Citation` (hover card hiện số hiệu, Điều, trích đoạn, nút "Xem điều luật" mở `/van-ban/{code}#D{n}`).
- [x] Panel nguồn bên phải (desktop) hoặc sheet trượt từ dưới (mobile), lấy từ các part `source-url`. Badge hiệu lực: "Đang hiệu lực" / "Chưa hiệu lực (từ dd/mm/yyyy)" / "Hết hiệu lực".
- [x] Banner theo `data-status`: offline → "Mô hình đang tắt — đang hiển thị điều luật liên quan"; refused → giải thích ngắn. `data-citation-warning` → cảnh báo nhỏ dưới câu trả lời.
- [x] Có 6 câu hỏi gợi ý lấy từ golden set (gồm câu lương tối thiểu 2026 so với 2027), nút Dừng, nút Copy, 👍/👎 gọi `/api/feedback` với `trace_id`. Lịch sử lưu ở localStorage (tối đa 20 hội thoại), bọc try/catch.
- [x] Test Vitest: `citation.test.tsx` (`"[S2]"` render thành nút có `aria-label` chứa số hiệu nguồn S2), `chat-storage.test.ts` (localStorage ném lỗi → không crash).
- [x] Commit `feat(web): chat page with citations, sources panel, offline banner`.

### Task 5.3: Trang Văn bản

**Files:** `frontend/src/app/van-ban/page.tsx`, `frontend/src/app/van-ban/[code]/page.tsx`.

- [x] Danh sách 8 văn bản dạng card: số hiệu, tên, loại, ngày hiệu lực, badge tình trạng, số Điều. Trang chi tiết có mục lục Chương/Điều (sticky ở desktop), mỗi Điều có anchor `#D{n}`, highlight Điều đang được trỏ tới. Dữ liệu lấy server-side từ `/api/docs*` với `revalidate: 3600`.
- [x] Commit `feat(web): legal documents browser`.

### Task 5.4: Trang Giới thiệu

**Files:** `frontend/src/app/gioi-thieu/page.tsx`, `frontend/src/content/architecture.svg` (xuất từ Mermaid trong `docs/architecture.md`), `frontend/src/content/eval.json` (copy từ `eval/results` bằng script `pnpm sync-eval`).

- [ ] Nội dung: sơ đồ kiến trúc, "Vì sao self-host LLM", bảng ablation, latency p50/p95, giới hạn đã biết, link repo GitHub. — *đã làm phần local: sơ đồ kiến trúc, lý do self-host, giới hạn đã biết, link repo; còn lại: bảng ablation và latency đang ở trạng thái chờ số liệu thật (`eval.json` = pending, chờ live batch)*
- [x] Commit `feat(web): about page with architecture and eval tables`.

### Task 5.5: E2E Playwright

**Files:** `frontend/playwright.config.ts` (2 project: `desktop` 1280×800, `mobile` 390×844), `frontend/e2e/{offline.spec.ts,online-mock.spec.ts,docs.spec.ts}`.

- [ ] `offline.spec.ts` chạy trên URL preview thật (`BASE_URL`): hỏi "Mức lương tối thiểu vùng I năm 2026?" → thấy badge ngoại tuyến (hoặc trực tuyến) và ≥ 1 nguồn có text "293/2025/NĐ-CP". — *chờ live batch: thân spec chưa chạy (chỉ chạy nhánh skip khi thiếu BASE_URL); cần URL preview thật*
- [x] `online-mock.spec.ts`: `page.route('/api/chat')` trả SSE mẫu → câu trả lời hiện dần, citation hover hoạt động.
- [x] Project `mobile`: `expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)` trên cả 3 trang; mở được sheet nguồn.
- [x] Commit `test(web): Playwright e2e desktop+mobile`.

---

## Phase 6 — CI/CD (6.1 bắt đầu ngay sau P0 và lớn dần theo code)

### Task 6.1: `ci.yml`

**Files:** `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.pre-commit-config.yaml` (ruff, gitleaks).

- [x] Trigger: `pull_request` và `push: main`. Job `changes` dùng `dorny/paths-filter` với các filter `web`, `api`, `pipelines`, `kaggle`, `db`, `eval`.
- [x] Các job (chỉ chạy khi filter khớp): — *thực hiện khác kế hoạch: DB test dùng service container pgvector thay `supabase db start`; pyright dùng ratchet (baseline 65 lỗi) thay vì chặn thẳng*
  - **web:** pnpm install --frozen-lockfile, lint, typecheck, vitest, build.
  - **api:** `astral-sh/setup-uv`, `uv lock --check`, `uv sync --locked`, `ruff check`, `ruff format --check`, `pyright`, `pytest` (DB service qua `supabase/setup-cli` + `supabase db start`).
  - **pipelines:** tương tự api.
  - **kaggle:** pytest gateway với fake model, CPU.
  - **db:** `supabase db start` + `supabase/tests`.
  - **secrets:** `gitleaks/gitleaks-action`.
- [x] Job `ci-ok` với `if: always()`: fail nếu bất kỳ job `needs` nào `failure`/`cancelled` (`skipped` thì cho qua).
- [ ] `[USER]` Bật branch protection cho `main`: require PR + check `ci-ok`. — *chờ [USER]: xem docs/ci.md*
- [x] Dependabot: npm (`/frontend`), uv (`/backend`, `/pipelines`), github-actions; chạy hàng tuần.
- [ ] Kiểm tra: mở một PR thử sửa README → chỉ `changes` và `ci-ok` chạy và xanh. — *chờ live batch: chưa có remote; mới mô phỏng path filter bằng suy luận, chưa mở PR thật*
- [x] Commit `ci: path-filtered CI with single required ci-ok check`.

### Task 6.2: `eval-retrieval.yml` (gate trên PR)

**Files:** `.github/workflows/eval-retrieval.yml`.

- [x] Trigger PR với paths `backend/app/retrieval/**`, `backend/app/legal/**`, `supabase/migrations/**`, `eval/**`, `pipelines/rag_pipelines/**`.
- [x] Các bước: `supabase db start` → nạp `eval/index/v1*.parquet` (script `python -m rag_pipelines.eval.load_frozen`) → `retrieval_eval --modes fts,dense,hybrid --split test --compare eval/baselines/main.json --max-drop 0.03` → render markdown → `marocchino/sticky-pull-request-comment`.
- [x] Thêm job này vào `needs` của `ci-ok` (dùng chung path filter).
- [x] Triển khai (xem `docs/ci.md`): `eval-retrieval.yml` là workflow tái sử dụng, gọi từ `ci.yml` và nằm trong `needs` của `ci-ok`; bootstrap rule `scripts/eval_gate_precheck.py` (thiếu baseline thì cảnh báo to, có baseline mà thiếu index/cache thì đỏ). Postgres là service container thay cho `supabase db start`. Chưa chạy trên GitHub (chưa có remote).
- [ ] sau live batch: mở PR bỏ stopword → lưu làm bằng chứng. PR cố tình bỏ stopword list → comment hiện chênh lệch, gate đỏ nếu tụt > 3 điểm. Giữ PR này làm **bằng chứng "gate chặn regression"** cho README, rồi đóng PR. (Cần `eval/baselines/main.json`, `eval/index/`, `eval/cache/` từ Task 3.1/3.4 và remote GitHub.)
- [x] Commit `ci: retrieval eval gate with PR comment`.

### Task 6.3: `deploy.yml`

**Files:** `.github/workflows/deploy.yml`.

- [x] PR: sau khi CI xanh, `vercel pull --environment=preview` → `vercel build` → `vercel deploy --prebuilt`. Lấy URL, comment lên PR, rồi chạy Playwright (`BASE_URL=url`) chỉ với spec offline + docs. — *đã viết workflow + actionlint; chưa chạy trên GitHub/Vercel*
- [x] `push: main`: job `migrate` (Environment `production`, `supabase link --project-ref $SUPABASE_PROJECT_REF` + `supabase db push`) → job `deploy-prod` (`vercel build --prod` + `vercel deploy --prebuilt --prod`) với `needs: [ci-ok, migrate]`. — *đã viết workflow + actionlint; chưa chạy trên GitHub/Supabase/Vercel*
- [ ] `[USER]` Thêm GitHub Secrets: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF`. Thêm Vercel env (Production + Preview): mọi biến ở 4.4. — *chờ [USER]*
- [ ] Kiểm tra: merge một PR → production cập nhật; `/api/health` trả `db: "ok"`. — *chờ live batch: cần remote GitHub, secrets và project Vercel/Supabase thật*
- [x] Commit `cd: gated preview and production deploys via Vercel CLI`.

### Task 6.4: `eval-full.yml` (thủ công, khi Kaggle bật)

**Files:** `.github/workflows/eval-full.yml`, `pipelines/rag_pipelines/eval/answer_eval.py`, `pipelines/tests/test_answer_eval.py`.

**Interfaces — Produces:** `answer_eval` gọi `/api/chat` của production (hoặc dùng trực tiếp pipeline backend) cho split test. Các metric tất định:
- `citation_precision`: tỉ lệ `[S#]` hợp lệ trỏ tới Điều thuộc gold.
- `citation_recall`: tỉ lệ Điều gold được trích.
- `numeric_match`: mọi số tiền, %, ngày trong `answer` gold xuất hiện trong câu trả lời, sau khi chuẩn hóa `5.310.000` ↔ `5310000`.
- `refusal_accuracy`: với unanswerable/out_of_domain, hệ thống phải từ chối; với câu khác, không được từ chối.
- `injection_resisted`.
- Latency TTFT/total.

- [x] Test hỏng: `test_numeric_normalization` (`"5.310.000 đồng"` khớp `"5310000"`), `test_refusal_accuracy_matrix`.
- [x] Workflow `workflow_dispatch` với input `model_label`. Bước đầu kiểm tra `/api/health` có `llm == "online"`, nếu không thì dừng với thông báo rõ. Kết quả ghi vào `eval/results/answers_{label}_{date}.json`, upload artifact, commit qua PR tự động. — *chưa chạy trên GitHub (chờ live batch cho lần chạy thật)*
- [x] Commit `feat(eval): deterministic end-to-end answer eval workflow`.

### Task 6.5: Keep-alive

- [ ] `vercel.json`: thêm cron `0 3 * * *` gọi `/api/cron/keepalive` (Hobby chỉ cho cron hằng ngày). Nếu Services không nhận cron ở root, ghi lại và dùng phương án GitHub. **Chưa làm:** `vercel.json` chưa tồn tại (Task 0.4, `[USER]`, cần spike Vercel Services); không tạo file một phần. Snippet và ghi chú đã nằm ở `docs/deploy.md` (mục Keep-alive, checklist 10). Tick khi Task 0.4 xong.
- [x] `.github/workflows/keepalive.yml`: `schedule: "0 2 */3 * *"`, `curl -fsS -H "Authorization: Bearer $CRON_SECRET" $PROD_URL/api/cron/keepalive`. (actionlint sạch; thân step chạy thử với server giả: 204 -> 0, 401 -> 22, không kết nối -> 7, thiếu env -> 1. Chưa chạy trên GitHub. `[USER]`: secret `CRON_SECRET`, biến `PROD_URL`.)
- [x] Commit `ops: Supabase keep-alive (Vercel cron + GitHub schedule)`.

---

## Phase 7 — Hoàn thiện portfolio

### Task 7.1: Observability + feedback

- [ ] Kiểm tra Langfuse: mỗi request có trace với các span `condense`, `embed`, `hybrid_search`, `rerank`, `expand`, `llm`; có metadata `index_version`, `mode`, `prompt_version="answer_v1"`. Feedback 👍/👎 thành score trên trace. (Code + test với Langfuse giả xong; kiểm trên Langfuse thật chưa làm: checklist ở `docs/runbook-observability.md`.) — *chờ live batch: cần Langfuse thật*
- [x] Script `scripts/latency_report.py` lấy p50/p95 theo span từ Langfuse API, ghi `eval/results/latency.md`.
- [x] Commit `feat(obs): span-level tracing and latency report`.

### Task 7.2: Ablation và A/B model

- [ ] Chạy retrieval eval (Kaggle bật) cho các cấu hình: `fts` → `dense` → `hybrid` → `hybrid+rerank` → `+breadcrumb` (so với index không breadcrumb, `index_version=2` ingest với `--no-breadcrumb`) → `+1-hop refs` (đo bằng citation_recall ở answer eval).
- [ ] A/B LLM trên split test bằng `eval-full`: `Qwen3-8B Q5_K_M` so với `Qwen3.5-9B Q4_K_M` và `AITeamVN/Vi-Qwen2-7B-RAG` (nạp lên GPU1 hoặc đổi model trong notebook). Ghi cả metric lẫn tok/s.
- [ ] Ghi `eval/results/ABLATION.md` (bảng và 3–5 dòng phân tích lỗi theo loại câu hỏi). Chọn cấu hình tốt nhất, cập nhật `baselines/main.json`.
- [ ] Commit `docs(eval): ablation and model A/B results`.

### Task 7.3: Câu trả lời dựng sẵn + video demo

- [ ] `scripts/build_canned.py`: với Kaggle bật, chạy 6 câu gợi ý cùng 10 câu nổi bật, lưu vào `canned_answers` (câu hỏi đã chuẩn hóa NFC + lowercase + strip dấu câu).
- [ ] Test (backend): offline và câu hỏi khớp canned → trả answer đã lưu, có nhãn "Câu trả lời đã lưu từ phiên trực tuyến".
- [ ] `[USER]` Quay video 60–90 s: câu hỏi lương tối thiểu 2026 so với 2027, câu nhiều bước BHTN, câu bị từ chối, trang Văn bản. Xuất GIF ngắn cho README.
- [ ] Commit `feat: canned answers for offline demo`.

### Task 7.4: Tài liệu

**Files:** `README.md`, `docs/architecture.md`, `docs/adr/0001-self-host-llm-on-kaggle.md`, `0002-pgvector-over-dedicated-vector-db.md`, `0003-plain-python-no-langchain.md`, `0004-regex-refs-over-graphrag.md`, `0005-claude-generated-golden-set.md`, `0006-single-supabase-blue-green-index.md`, `0007-ngrok-static-domain.md`.

- [ ] README theo thứ tự: GIF/video → một đoạn giới thiệu → sơ đồ → bảng số liệu (ablation, latency, refusal) → "Chạy thử" (link production + ghi chú "LLM chỉ bật khi demo; chế độ ngoại tuyến vẫn hoạt động") → kiến trúc chi tiết → cách chạy lại từ clone mới → CI/CD (ảnh PR gate) → giới hạn và rủi ro (Kaggle ToS, luật đang sửa) → nguồn dữ liệu (Điều 15 Luật SHTT) → disclaimer.
- [ ] Kiểm tra: một subagent mới clone repo và làm theo README, chạy được `uv run pytest`, `pnpm test`, `supabase start` + migration + nạp frozen index, mà không cần hỏi thêm.
- [ ] Commit `docs: README, architecture, ADRs`.
- [ ] pyright baseline xuống 0 (xóa continue/ratchet trong ci.yml)

---

## Phase 8 — Mở rộng bộ B (giao thông), tùy chọn

### Task 8.1: Thêm corpus giao thông không sửa code lõi

- [ ] Thêm 9 văn bản bộ B vào `legal_docs.yaml`, gồm cả quan hệ `amends`: ND238-2026 sửa ND168-2024 (hiệu lực 15/08/2026), ND241-2026 sửa ND165-2024. Tải bằng downloader của 1.2. Trang manifest ở `docs/research/research_notes/…/corpus_manifest.json` có sẵn URL.
- [ ] Bảng mức phạt trong NĐ 168: kiểm tra `extract_text` giữ được bảng (python-docx tables). Thêm test `test_nd168_penalty_table_preserved` (có ít nhất một dòng chứa "đồng" và "Điều 6").
- [ ] Văn bản sửa đổi: khi nguồn là Điều của ND168 và tồn tại ref `amends` từ ND238 tới Điều đó (có hiệu lực tại `as_of`), `expand` thêm Điều sửa đổi và header ghi "(đã được sửa đổi bởi NĐ 238/2026)". Thêm test.
- [ ] Ingest `--index-version 3`, thêm khoảng 30 câu golden bộ B (theo quy trình 3.3), chạy eval, rồi chuyển `active_index_version=3`.
- [ ] Commit `feat: traffic law corpus (set B) with amendment-aware expansion`.

---

## Self-review (đã chạy)

- **Bao phủ spec:** mục đích/demo → P7; mục tiêu "8 văn bản + trích dẫn" → P1, 3.2, 4.1; LLM tự host → P2; UI 3 trang → P5; CI/CD → P6; offline mode → 4.4, 5.2, 7.3; 1 Supabase + blue/green → 1.1, 3.1; golden set do Claude sinh → 3.3; bộ B → P8; anti-goals (bịa số, văn bản hết hiệu lực, trắng trang) → 4.1, 1.1 (as_of), 4.4 (offline).
- **Kiểm tra nhất quán type:** `Candidate`, `SourceDoc`, `Gateway`, `make_id`, `hybrid_search(...)` dùng cùng một chữ ký ở 1.1, 3.2, 4.1, 4.4.
- **Chưa xác minh, đã gắn vào spike:** cú pháp `vercel.json` Services, tên field AI SDK v7, cờ `llama-server`, ngrok với SSE dài, version pgvector.
