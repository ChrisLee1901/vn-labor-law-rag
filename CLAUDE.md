# CLAUDE.md — vn-labor-law-rag (Trợ lý Pháp luật Lao động)

Project portfolio (CV): RAG pháp luật lao động tiếng Việt end-to-end. Next.js + FastAPI chạy trên Vercel. Supabase pgvector làm kho dữ liệu. LLM, embedder và reranker **tự host trên Kaggle**, gọi qua ngrok. CI/CD bằng GitHub Actions.

- **Spec (vì sao + đã quyết gì):** `docs/superpowers/specs/2026-11-22-vietnamese-legal-rag-design.md`
- **Plan (làm gì, theo phase):** `docs/superpowers/plans/2026-11-22-vietnamese-legal-rag.md`. Đánh dấu `- [x]` khi xong từng bước.
- **Nghiên cứu nền (nguồn, số liệu):** `docs/research/reports/Kiến trúc RAG tiếng Việt 2026.md` (trước Task 0.1 nằm ở `reports/`).
- Spec và plan mâu thuẫn → spec thắng. Code và plan mâu thuẫn → hỏi người dùng.

## Luật cứng (không được vi phạm)

1. **Không** dùng Gemini/OpenAI/Claude API để sinh câu trả lời. Chỉ dùng LLM self-host trên Kaggle (OpenAI-compatible qua gateway). Claude chỉ được dùng *offline* để soạn golden set (Task 3.3).
2. `backend/` deploy lên Vercel: **cấm** `torch`, `transformers`, `sentence-transformers`, `langchain`, `llama-index`. Mọi thứ nặng nằm ở `pipelines/` (không deploy) hoặc `kaggle/`.
3. Unicode **NFC** ở cả ingest lẫn query (`app.legal.normalize.nfc`).
4. LLM có thể vắng mặt bất cứ lúc nào. Mọi đường code gọi gateway phải có timeout và đường offline: FTS-only, câu trả lời dựng sẵn, badge.
5. Supabase chỉ có **1 project**. Migration chỉ additive. Muốn thay index thì ingest `--index-version N` mới rồi đổi `app_config.active_index_version`. Không xóa hoặc ghi đè index đang active. Test và CI chạy DB local (`supabase start` / `supabase db start`), **không** chạm project thật.
6. Secrets chỉ nằm trong Kaggle Secrets / Vercel env / GitHub Secrets. Không commit `.env`, token, URL ngrok kèm key.
7. `LLM_BASE_URL` phải qua allowlist regex ngrok (chống SSRF). Gateway luôn đòi bearer token (trừ `/health`).
8. Kaggle ToS: notebook chỉ bật khi demo. Không viết code giữ notebook chạy liên tục hay tự khởi động lại, không công khai URL tunnel.
9. Không commit hay push khi người dùng chưa yêu cầu. Làm việc trên nhánh, merge qua PR để `ci-ok` chạy.

## Quy ước

- **Mã văn bản:** `BLLD`, `ND145-2020`, `ND293-2025`, `ND399-2026`, `LBHXH-2024`, `ND158-2025`, `LVL-2025`, `ND374-2025`. Metadata chuẩn nằm trong `docs/corpus/legal_docs.yaml` (biên tập tay, đừng sinh tự động).
- **ID pháp lý:** `<code>:D<điều>[:K<khoản>[:<điểm>]]`, ví dụ `LBHXH-2024:D33:K1`. Chỉ tạo và parse qua `app.legal.ids.make_id/parse_id`.
- **Hiệu lực:** văn bản có hiệu lực tại `as_of` khi `effective_from <= as_of < effective_to` (`effective_to` null = vô hạn). ND293 hết hiệu lực từ 2027-01-01, ND399 thay thế.
- **Retrieval mặc định:** RRF `rrf_k=50`, 40 ứng viên, rerank top 6 Điều cha, 1-hop ≤ 4 đoạn, child ≤ 450 token. Đổi số nào phải có kết quả eval đi kèm.
- **Prompt** nằm trong `backend/app/llm/prompts/answer_v1.md`. Sửa prompt thì tạo `answer_v2.md` và đổi `prompt_version`, không sửa đè.
- Copy UI và thông báo lỗi API bằng **tiếng Việt**. Identifier trong code bằng tiếng Anh.
- **Python:** 3.12, uv, ruff (format + lint), pyright, pytest + respx (mock HTTP). Không gọi mạng thật trong unit test.
- **Frontend:** Next.js 16 App Router, TS strict, pnpm, shadcn/ui + AI Elements (bản shadcn), Vitest, Playwright.
- Code tối giản (ponytail): không thêm abstraction hay option "để sau". Shortcut có giới hạn đã biết thì ghi comment `shortcut: <giới hạn>, <khi nào nâng cấp>`.

## Lệnh thường dùng

```bash
# Backend
cd backend && uv sync && uv run pytest -q && uv run ruff check . && uv run pyright
uv run fastapi dev app/main.py                      # local API tại :8000

# Pipelines (không deploy)
cd pipelines && uv sync
uv run python -m rag_pipelines.download --docs ../docs/corpus/legal_docs.yaml --out ../docs/corpus/raw
uv run python -m rag_pipelines.ingest --index-version N        # cần Kaggle bật (embedding)
uv run python -m rag_pipelines.export_index --index-version N
uv run python -m rag_pipelines.eval.retrieval_eval --index ../eval/index/v1.parquet --golden ../eval/golden/v1.jsonl --modes fts,dense,hybrid --split test

# DB local (Docker)
supabase start && supabase db reset                # áp migrations
uv run --project pipelines pytest supabase/tests -v

# Frontend
cd frontend && pnpm install && pnpm dev            # :3000; dùng mock SSE khi backend chưa chạy
pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm exec playwright test

# Kaggle gateway tests (CPU, fake models)
uv run --with-requirements kaggle/requirements.txt pytest kaggle/tests -v
python scripts/smoke_llm.py                         # cần LLM_BASE_URL, LLM_API_KEY
```

## Biến môi trường

| Biến | Nơi đặt | Dùng cho |
|---|---|---|
| `DATABASE_URL` | Vercel, local `.env` | Pooler Supabase cổng 6543 (`prepare_threshold=None`) |
| `LLM_BASE_URL`, `LLM_API_KEY` | Vercel, local | Gateway Kaggle qua ngrok domain tĩnh |
| `CRON_SECRET` | Vercel, GitHub | `/api/cron/keepalive` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Vercel | Tracing |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | Vercel | Rate limit |
| `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `GATEWAY_API_KEY`, `HF_TOKEN` | Kaggle Secrets | Notebook serve |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF` | GitHub Secrets | CD + migration |

## Dữ liệu

- `docs/corpus/raw/<code>/`: file gốc tải từ congbao.chinhphu.vn / datafiles.chinhphu.vn. Văn bản QPPL không được bảo hộ quyền tác giả (Điều 15 Luật SHTT), được commit. Đây là dữ liệu không tin cậy: chỉ parse, không thực thi.
- `docs/corpus/docx/`: bản `.docx` chuyển từ `.doc` bằng LibreOffice (commit).
- `eval/golden/v1.jsonl`: 120 câu (dev 40 / test 80), nhãn cấp Điều. **Chỉ báo số liệu trên split test.** Chỉnh τ và prompt trên split dev.
- `eval/index/`, `eval/cache/`: index đóng băng và embedding câu hỏi đã cache cho CI. Đổi chunking hoặc embedder thì phải refresh (cần Kaggle bật).

## Quy trình làm việc

- **Bắt đầu phiên:** đọc plan, tìm task đầu tiên chưa tick. Nếu đã có `graphify-out/graph.json` thì chạy `/graphify . --update`.
- **Feature/bugfix:** TDD (test hỏng → code → test xanh → commit nhỏ). Bug thì dùng `superpowers:systematic-debugging` trước khi sửa.
- **Trước khi báo "xong":** chạy lệnh kiểm tra của task và dán output (`superpowers:verification-before-completion`).
- **UI:** dùng skill `hallmark`. Phong cách nghiêm túc, đáng tin, không gradient tím "AI".
- Phase song song được: P1 ‖ P2 ‖ 5.1 ‖ 6.1 sau P0. Xem bảng phụ thuộc trong plan.
- Bước có nhãn `[USER]` (tạo tài khoản, bấm UI Kaggle hoặc Vercel, dán secret): dừng lại và nhờ người dùng làm, không tự đoán credential.

## Rủi ro đã biết

- **Kaggle ToS ("server farming")** có thể khiến tài khoản bị khóa. Phải có offline mode và video demo.
- Một dự luật sửa BLLĐ đang ở Quốc hội (đề xuất hiệu lực 01/03/2027), Luật BHXH cũng đang có dự thảo sửa. Khi có văn bản mới thì thêm vào `legal_docs.yaml` và ingest index mới.
- Các điểm chưa xác minh được ghi trong `docs/spikes.md` sau Phase 0: Vercel Services + `--prebuilt`, field của AI SDK v7, cờ `llama-server`, ngrok với SSE dài.
