# Runbook eval câu trả lời (`answer_eval`)

Đo chất lượng trả lời đầu-cuối trên split `test` (80 câu) qua `POST /api/chat`, không dùng LLM làm giám khảo. Chỉ số, mẫu số và trường hợp biên: docstring của `pipelines/rag_pipelines/eval/answer_eval.py` (bản đọc được cho người dùng cuối nằm ở bảng giải nghĩa trên trang `/gioi-thieu`). Chưa có lần chạy thật nào: `frontend/src/content/eval.json` vẫn là `{"status":"pending"}` cho tới khi có kết quả.

Cần Kaggle bật (LLM online). Tắt notebook ngay sau khi xong ([runbook-kaggle.md](runbook-kaggle.md)).

## Giới hạn tần suất của API production

`/api/chat` có giới hạn theo IP (20 lượt / 10 phút) và toàn cục (300 lượt / ngày), cộng một rule WAF dự kiến (docs/deploy.md). 80 câu chạy liền sẽ chạm trần, nên:

- `--delay-s` mặc định 31 s giữa hai câu (80 câu mất khoảng 41 phút cộng thời gian trả lời).
- Gặp 429: đợi `Retry-After` (backend hiện không gửi header này nên mặc định 200 s, tối đa 600 s), thử lại tối đa 3 lần. Hết lượt chờ thì **dừng cả lần chạy với exit 3 và không ghi file kết quả** (kết quả dở không bao giờ thành file chính thức). Trần theo ngày thì chỉ chạy lại được hôm sau hoặc chạy local.
- Dừng (exit 3) tương tự khi LLM chuyển offline giữa chừng hoặc 5 câu liên tiếp lỗi.
- Câu lỗi lẻ (part `error`, stream đứt giữa chừng, HTTP lỗi) không làm hỏng cả lần chạy: được tính là **sai** và đếm ở `n_failed` trong file kết quả. Không có chế độ tiếp tục: chạy lại là chạy từ đầu.
- Không có và sẽ không thêm cơ chế bỏ qua giới hạn (header hay secret) vào backend.

## Chạy qua GitHub Actions (production)

Workflow `eval-full` (Actions, Run workflow): điền `model_label` (vd `Qwen3-8B-Q5_K_M`), `base_url` tùy chọn (mặc định biến repository `PROD_URL`). Bước đầu gọi `/api/health` và dừng nếu `llm != "online"`. Kết quả thành artifact và PR tự động; xem [ci.md](ci.md) (mục eval-full) về việc `ci-ok` không tự chạy trên PR đó.

## Chạy tay trên máy bạn

```bash
cd pipelines && uv sync
export EVAL_BASE_URL=https://<host-production>        # hoặc --base-url
uv run python -m rag_pipelines.eval.answer_eval --label Qwen3-8B-Q5_K_M --markdown ../answers-summary.md
# ghi eval/results/answers_<nhãn>_<ngày>.json
```

Thoát 0 = đủ 80 câu; 2 = tham số sai (chỉ chấp nhận `--split test`); 3 = dừng giữa chừng, không có file.

## Chạy trên backend local (tránh trần production)

Không có `UPSTASH_REDIS_REST_*` thì backend không giới hạn tần suất, nên dùng `--delay-s 0`. Cần DB local có chỉ mục đang hoạt động và gateway Kaggle online:

```bash
bash scripts/test-db.sh                                # Postgres pgvector local, cổng 54329
for f in supabase/migrations/*.sql; do psql postgresql://postgres:postgres@localhost:54329/postgres -v ON_ERROR_STOP=1 -q -f "$f"; done
# nạp chỉ mục: uv run --project pipelines python -m rag_pipelines.eval.load_frozen --index eval/index/v1.parquet --database-url postgresql://postgres:postgres@localhost:54329/postgres
#   (eval/index/ chỉ có sau lần ingest thật đầu tiên; nếu chưa có thì ingest vào DB local, xem CLAUDE.md)
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:54329/postgres \
LLM_BASE_URL=https://<domain>.ngrok-free.dev LLM_API_KEY=<GATEWAY_API_KEY> \
uv run fastapi dev app/main.py                          # :8000 (secret chỉ ở env của shell này, không commit)
# terminal khác:
cd pipelines && uv run python -m rag_pipelines.eval.answer_eval --base-url http://localhost:8000 --delay-s 0 --label Qwen3-8B-Q5_K_M
```

File kết quả có `base_url_kind: "local"` (URL không bao giờ được ghi). Số liệu của backend local và production cùng cấu hình thì so sánh được; độ trễ thì không (khác đường mạng và máy).

## Đưa lên trang web

Sau khi file `eval/results/answers_*.json` đã vào nhánh chính: `cd frontend && pnpm sync-eval` (cần thêm `eval/results/retrieval_v1.json` từ `retrieval_eval ... --out eval/results/retrieval_v1.json`), rồi review diff của `src/content/eval.json`.
