# CI

Workflow: `.github/workflows/ci.yml` (chạy trên `pull_request` và `push` vào `main`). Job `changes` (dorny/paths-filter) quyết định job nào chạy. Job nào bị bỏ qua (`skipped`) thì không chặn merge.

## Check bắt buộc: `ci-ok`

`ci-ok` luôn chạy (`if: always()`), đỏ khi có job `failure` hoặc `cancelled`, xanh khi các job còn lại `success` hoặc `skipped`. Đây là check bắt buộc duy nhất.

**[USER] Bật branch protection cho `main`** (sau khi repo đã có trên GitHub và `ci-ok` đã chạy ít nhất một lần):

1. Settings, Branches, Add branch ruleset (hoặc Add classic branch protection rule), áp cho `main`.
2. Bật "Require a pull request before merging".
3. Bật "Require status checks to pass", thêm đúng một check: `ci-ok`.
4. Bật "Require branches to be up to date before merging" (khuyến nghị).

## Job và filter

| Job | Chạy khi đổi | Việc chính |
|---|---|---|
| `changes` | luôn | tính filter `web`, `api`, `pipelines`, `kaggle`, `db`, `eval` |
| `web` | `frontend/**` | pnpm install, lint, typecheck, vitest, build |
| `e2e` | `frontend/**`, sau `web` xanh | Playwright (chromium), upload `playwright-report` khi lỗi |
| `api` | `backend/**`, `supabase/migrations/**`, `docs/api-contract.md`, `ruff.toml` | `uv lock --check`, ruff, pyright (chưa chặn), pytest + Postgres pgvector |
| `pipelines` | `pipelines/**`, `backend/**`, `supabase/migrations/**`, `docs/corpus/legal_docs.yaml`, `eval/golden/**`, `ruff.toml` | như `api`, ruff lấy từ backend |
| `kaggle` | `kaggle/**`, `ruff.toml` | ruff, pytest gateway với model giả (CPU) |
| `db` | `supabase/**`, `pipelines/pyproject.toml`, `ruff.toml` | pytest `supabase/tests` trên Postgres pgvector |
| `secrets` | luôn | gitleaks quét toàn bộ lịch sử |
| `ci-ok` | luôn | tổng hợp |

Sửa `.github/workflows/ci.yml` thì mọi filter đều khớp. Filter `eval` (`pipelines/**`, `backend/app/**`, `eval/**`, `docs/corpus/**`, `supabase/migrations/**`) dành cho job eval-retrieval ở Task 6.2.

## Ghi chú

- Postgres cho test là service container `pgvector/pgvector:pg17` trên runner, truyền qua `TEST_DATABASE_URL`. CI không dùng secret và không chạm project Supabase thật.
- Ruff dùng chung `ruff.toml` gốc, bản ruff khóa trong `backend/uv.lock`. `kaggle/serve.ipynb` bị loại (file sinh ra, chạy `python kaggle/build_notebook.py` sau khi sửa `kaggle/gateway.py`).
- `pyright` ở job `api` đang `continue-on-error` vì còn 65 lỗi kiểu có sẵn. Sửa hết rồi bỏ cờ này.
- Hook cục bộ: `pre-commit install` (ruff check, ruff format, gitleaks).
