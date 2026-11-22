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
| `api` | `backend/**`, `supabase/migrations/**`, `docs/api-contract.md`, `scripts/pyright_ratchet.py`, `ruff.toml` | `uv lock --check`, ruff, pyright ratchet, pytest + Postgres pgvector |
| `pipelines` | `pipelines/**`, `backend/**`, `supabase/migrations/**`, `docs/corpus/legal_docs.yaml`, `eval/golden/**`, `scripts/eval_gate_precheck.py`, `scripts/migration_guard.py`, `ruff.toml` | như `api`, ruff lấy từ backend |
| `kaggle` | `kaggle/**`, `ruff.toml` | ruff, pytest gateway với model giả (CPU) |
| `db` | `supabase/**`, `pipelines/pyproject.toml`, `ruff.toml` | pytest `supabase/tests` trên Postgres pgvector |
| `eval-retrieval` | `backend/app/retrieval/**`, `backend/app/legal/**`, `supabase/migrations/**`, `eval/**`, `pipelines/rag_pipelines/**`, lockfile, `scripts/eval_gate_precheck.py`, `ruff.toml`, `ci.yml`, `eval-retrieval.yml` | gate truy xuất (workflow tái sử dụng `eval-retrieval.yml`), xem dưới |
| `secrets` | luôn | gitleaks quét toàn bộ lịch sử |
| `ci-ok` | luôn | tổng hợp |
| `deploy-preview` | PR cùng repo (không fork, không Dependabot), sau `ci-ok` xanh | workflow tái sử dụng `deploy.yml`: Vercel preview, comment URL, Playwright offline + docs. Không nằm trong `needs` của `ci-ok` |
| `deploy-prod` | `push` vào `main`, sau `ci-ok` xanh | `deploy.yml`: `migrate` (Environment `production`, guard migration) rồi `deploy` (Vercel `--prod`, smoke `/api/health`). Không nằm trong `needs` của `ci-ok` |
| `keepalive` (workflow riêng) | `schedule` `0 2 */3 * *` và `workflow_dispatch`, không chạy trên PR/push | `curl` `/api/cron/keepalive` trên production giữ Supabase không bị pause; thiếu `CRON_SECRET`/`PROD_URL` thì đỏ. GitHub tự tắt workflow theo lịch sau 60 ngày repo không hoạt động. Xem [deploy.md](deploy.md) |

Sửa `.github/workflows/ci.yml` thì mọi filter đều khớp.

## Gate eval truy xuất (`eval-retrieval`)

`.github/workflows/eval-retrieval.yml` là workflow tái sử dụng (`on: workflow_call`), `ci.yml` gọi nó như job `eval-retrieval` và job này nằm trong `needs` của `ci-ok`. (Job của workflow khác không thể nằm trong `needs`, nên file không có trigger `pull_request` riêng: sẽ chạy đôi và không bị `ci-ok` chặn.)

Các bước: Postgres `pgvector/pgvector:pg17` (service container, `TEST_DATABASE_URL`, không chạm Supabase thật) → áp `supabase/migrations/*.sql` → `retrieval_eval --index eval/index/v1.parquet --modes fts,dense,hybrid --split test --compare eval/baselines/main.json --max-drop 0.03` (tự nạp index qua `load_frozen`, dùng embedding câu hỏi đã cache trong `eval/cache/`, không cần Kaggle) → markdown vào `$GITHUB_STEP_SUMMARY` và sticky comment (`marocchino/sticky-pull-request-comment`, `header: eval-retrieval`, cập nhật tại chỗ). Gate đỏ khi `recall@10` hoặc `mrr@10` của mode `hybrid` giảm quá 0.03 (tuyệt đối); comment vẫn được đăng khi đỏ. Số liệu chỉ trên split `test`. PR từ fork có token read-only: step comment `continue-on-error`, nội dung vẫn có trong job summary.

### Bootstrap rule (`scripts/eval_gate_precheck.py`)

Chưa có dữ liệu đóng băng thì gate không được xanh âm thầm:

| Trạng thái | Kết quả |
|---|---|
| `eval/baselines/main.json` **vắng** | job xanh nhưng có annotation `::warning::`, summary và comment ghi "Gate inactive: no frozen baseline committed yet (run the live batch, see runbook)" |
| baseline **có**, thiếu `eval/index/v1{,.legal_docs,.articles,.legal_refs}.parquet` hoặc `eval/cache/query_emb_AITeamVN-Vietnamese_Embedding.{npy,ids.json}` | job **đỏ**, comment nêu file thiếu |
| đủ cả | chạy gate nghiêm ngặt |

Chống xóa lách gate: trên PR, precheck so với nhánh base (workflow `git fetch` ref base, `GITHUB_BASE_REF` qua env). Nếu `eval/baselines/main.json` hoặc `eval/index/v1.parquet` có trên base mà PR xóa (hoặc baseline rỗng / không phải JSON object) thì job **đỏ**; chỉ khi base cũng chưa có baseline mới là "inactive". Push vào `main` bỏ qua kiểm tra base. Không canh `eval/cache/` (shortcut: chỉ baseline + index; nâng cấp nếu cần). Base ref không fetch được thì cũng đỏ (fail closed).

Giới hạn còn lại: PR vẫn có thể sửa con số bên trong `eval/baselines/main.json` (thấy trong diff) để nới ngưỡng. **[USER]** Bắt buộc review cho `eval/baselines/**` (CODEOWNERS hoặc ruleset yêu cầu review file đó; chưa thêm CODEOWNERS vì chưa biết username GitHub chủ repo).

Cách gỡ bootstrap: commit `eval/baselines/main.json` (cùng `eval/index/` và `eval/cache/`) sau live batch (Task 3.1/3.4). Từ lúc đó quy tắc tự nghiêm ngặt, không cần sửa code. Index lớn hơn 50 MB thì dùng Git LFS (checkout đã bật `lfs: true`).

## Deploy

Hai job `deploy-*` chạy sau `ci-ok` và gọi `.github/workflows/deploy.yml` (không có trigger riêng, giống `eval-retrieval.yml`). Secrets, checklist `[USER]`, WAF, rollback và phương án dự phòng: [deploy.md](deploy.md). Chưa chạy trên GitHub lần nào.

## Eval câu trả lời đầu-cuối (`eval-full`, thủ công)

`.github/workflows/eval-full.yml`: chỉ `workflow_dispatch`, không bao giờ chạy theo lịch, push hay PR (Kaggle ToS: chỉ chạy khi chủ repo tự bật notebook). Input: `model_label` (bắt buộc, kiểm tra `^[A-Za-z0-9._-]{1,40}$` trong một step, qua env) và `base_url` (tùy chọn; trống thì lấy biến repository `PROD_URL`, không phải secret; thiếu cả hai thì job đỏ với thông báo rõ).

Các bước: kiểm tra input → `GET <base>/api/health`, bắt buộc `llm == "online"` (không thì job đỏ, chưa có kết quả nào) → `rag_pipelines.eval.answer_eval` trên split `test` (80 câu, giãn cách 31 s để không chạm giới hạn 20 lượt / 10 phút theo IP, mất khoảng 45 đến 60 phút) → `eval/results/answers_<nhãn>_<ngày>.json` → job summary, artifact (`actions/upload-artifact`) → PR tự động (`peter-evans/create-pull-request`, nhánh `eval/answers-<nhãn>-<ngày>`). Quyền: `contents: write`, `pull-requests: write` ở cấp job; không dùng secret nào ngoài `GITHUB_TOKEN`. Định nghĩa chỉ số và schema: docstring của `pipelines/rag_pipelines/eval/answer_eval.py`; cách chạy tay và chạy trên backend local: [runbook-eval.md](runbook-eval.md).

- **`ci-ok` không chạy trên PR này.** PR mở bằng `GITHUB_TOKEN` không kích hoạt workflow khác (quy tắc của GitHub, chống đệ quy). **[USER]** Trước khi merge: đẩy một commit rỗng lên nhánh `eval/answers-*` (`git commit --allow-empty`) hoặc đóng rồi mở lại PR, hoặc cấu hình PAT cho `create-pull-request` (khi đó thêm secret, ngoài phạm vi hiện tại).
- **[USER]** Bật Settings, Actions, General, Workflow permissions, "Allow GitHub Actions to create and approve pull requests", nếu không bước mở PR lỗi 403. Đặt biến repository `PROD_URL` (Settings, Secrets and variables, Variables) là URL https gốc của deployment production.
- 429 (giới hạn theo IP hoặc 300 lượt/ngày toàn cục) hết lượt chờ thì job đỏ và KHÔNG có file kết quả. Nếu chạy lại nhiều lần trong ngày, tổng số lượt có thể chạm trần toàn cục: dùng backend local (runbook-eval.md).
- Kết quả đã merge vào `eval/results/` được đưa lên trang `/gioi-thieu` bằng `pnpm sync-eval` (xem design-system.md). Chạy tay, không có bước tự động.

## Ghi chú

- Postgres cho test và cho gate eval là service container `pgvector/pgvector:pg17` trên runner, truyền qua `TEST_DATABASE_URL`. CI không dùng secret và không chạm project Supabase thật.
- Ruff dùng chung `ruff.toml` gốc, bản ruff khóa trong `backend/uv.lock`. `kaggle/serve.ipynb` bị loại (file sinh ra, chạy `python kaggle/build_notebook.py` sau khi sửa `kaggle/gateway.py`).
- `pyright` ở job `api` chạy dạng ratchet (`scripts/pyright_ratchet.py`): đếm lỗi, so với `backend/pyright-baseline.txt` (hiện 65), đỏ nếu nhiều hơn baseline, in gợi ý hạ baseline khi ít hơn. Việc tiếp theo: đưa baseline về 0 rồi đổi step thành `uv run pyright` (plan Task 7.4).
- Hook cục bộ: `pre-commit install` (ruff check, ruff format, gitleaks).
