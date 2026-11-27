# Deploy (Task 6.3)

Workflow: `.github/workflows/deploy.yml` (tái sử dụng, `on: workflow_call`), do `ci.yml` gọi bằng hai job `deploy-preview` và `deploy-prod`. Cả hai `needs: ci-ok` và **không** nằm trong `needs` của `ci-ok`. Deploy bằng Vercel CLI (`vercel pull` / `build` / `deploy --prebuilt`) từ Actions; Vercel Git integration tắt.

> **CHƯA XÁC MINH.** Repo chưa có remote, chưa có project Vercel hay Supabase. Workflow mới qua actionlint, chưa chạy lần nào trên GitHub. Hai điểm mở nhất: (1) `--prebuilt` có hỗ trợ Vercel Services hay không (spike Task 0.4: `vercel.json` đã có, `docs/spikes.md#vercel` ghi cách chạy, chưa chạy lần nào); (2) định dạng đầu ra `supabase db push --dry-run` mà `scripts/migration_guard.py` đọc. Mục "Phương án dự phòng" bên dưới là lối thoát cho (1).

## Job nào chạy khi nào

| Sự kiện | `deploy-preview` | `deploy-prod` |
|---|---|---|
| PR từ nhánh cùng repo, `ci-ok` xanh | chạy: `gate` (thiếu secret Vercel thì bỏ qua kèm `::notice::`), rồi `preview` | bỏ qua (không phải `push`) |
| PR từ fork | bỏ qua (`head.repo != repo`, fork không có secret) | bỏ qua |
| PR của Dependabot | bỏ qua (secret Dependabot tách riêng, không có secret Vercel) | bỏ qua |
| `push` vào `main`, `ci-ok` xanh | bỏ qua | chạy: `migrate` rồi `deploy` (cả hai Environment `production`) |
| `ci-ok` đỏ | bỏ qua | bỏ qua |

`deploy-prod` có `concurrency: deploy-production`, `cancel-in-progress: false`: các lần push xếp hàng, không hủy deploy đang chạy giữa chừng. `migrate` và `deploy` nằm cùng workflow tái sử dụng (job của workflow khác không đưa vào `needs` của job gọi được), `deploy` có `needs: migrate` nên chỉ chạy khi migration xong.

### Preview

`vercel pull --environment=preview` -> kiểm tra Vercel có `API_ORIGIN` hoặc `NEXT_PUBLIC_SITE_URL` (đỏ sớm nếu thiếu, không in giá trị) -> `vercel build` -> `vercel deploy --prebuilt` -> URL vào job summary và sticky comment (`header: preview-url`, step này `continue-on-error`) -> Playwright với `BASE_URL=<url>` chỉ chạy `e2e/offline.spec.ts` và `e2e/docs.spec.ts`. Các spec còn lại (`online-mock`, `layout`) cần stub API cục bộ nên không chạy trên preview.

Deployment Protection của Vercel chặn request tự động tới URL preview (401). Đặt secret `VERCEL_AUTOMATION_BYPASS_SECRET` (Vercel: Settings, Deployment Protection, Protection Bypass for Automation) thì `playwright.config.ts` gửi header `x-vercel-protection-bypass` (chỉ khi có `BASE_URL`; chạy cục bộ không đổi). Không đặt thì Playwright nhận 401 và job đỏ. Vì header này nằm trong trace, bước Playwright chạy với `--trace off` và chỉ upload HTML report (3 ngày, không upload `test-results`): artifact không được che secret như log. Chạy cục bộ trace vẫn `retain-on-failure`.

### Production

1. `migrate` (Environment `production`; `deploy` cũng dùng Environment này): `supabase link`, rồi `supabase db push --dry-run` (in vào log và job summary), rồi `scripts/migration_guard.py`, rồi `supabase db push`.
2. `deploy`: `vercel pull --environment=production`, kiểm biến như trên, `vercel build --prod`, `vercel deploy --prebuilt --prod`.
3. Smoke: gọi `GET <url>/api/health` mỗi 5 s, tối đa 24 lần (~2 phút), **đỏ** nếu JSON không có `db == "ok"`. Không đòi `llm: "online"` (Kaggle thường tắt). URL deployment cũng bị Deployment Protection chặn, nên gần như bắt buộc phải có `VERCEL_AUTOMATION_BYPASS_SECRET` (header được gửi nếu secret có).

### Guard migration (luật 5: chỉ additive)

`scripts/migration_guard.py` đọc tên các migration sắp áp từ đầu ra `--dry-run`, bỏ comment SQL, và **fail** nếu gặp `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `DELETE FROM`. Cố ý thì thêm dòng `-- allow-destructive: <lý do>` vào chính file migration (hiện trong diff PR, nên được review). Không có tên migration và đầu ra cũng không phải câu "Remote database is up to date." (hằng `UP_TO_DATE`, wording chưa xác minh tới lần chạy thật) thì **fail** (fail closed), kèm hướng dẫn xem log dry-run rồi bổ sung wording hoặc `supabase db push` thủ công. Giới hạn đã biết (comment `shortcut:` trong script): bỏ comment bằng regex, `DROP INDEX/FUNCTION/POLICY` không bị chặn. Test: `pipelines/tests/test_migration_guard.py`.

Migration `20261201000300_function_search_path.sql` (ghim `search_path = public, extensions` cho `hybrid_search`, xử lý cảnh báo advisor `function_search_path_mutable`) nằm trước lần deploy production đầu tiên. Test `test_app_functions_pin_search_path` bắt hàm mới thiếu `set search_path`.

## Secrets và biến môi trường

Không có giá trị thật nào nằm trong repo.

**GitHub Secrets.** Secret cấp repo mà workflow của mọi PR cùng repo (người có quyền ghi) đọc được, vì PR chạy bản `deploy.yml` của chính nó. Vì vậy secret production nằm ở **Environment `production`** (chỉ cho nhánh `main`), còn secret preview phải ở cấp repo:

| Secret | Cấp | Dùng cho | Lấy ở đâu |
|---|---|---|---|
| `VERCEL_TOKEN` | repo (preview cần) | `vercel pull/build/deploy` | Vercel, Account Settings, Tokens |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | repo | chọn project | `.vercel/project.json` sau `vercel link` cục bộ |
| `SUPABASE_ACCESS_TOKEN` | **Environment `production`** | `supabase link/db push` | Supabase, Account, Access Tokens |
| `SUPABASE_DB_PASSWORD` | **Environment `production`** | `supabase db push` | mật khẩu database lúc tạo project |
| `SUPABASE_PROJECT_REF` | **Environment `production`** | `supabase link --project-ref` | Supabase, Project Settings, General |
| `VERCEL_AUTOMATION_BYPASS_SECRET` (tùy chọn nhưng nên có) | repo (preview cần) | Playwright trên preview, smoke production | Vercel, Deployment Protection, Protection Bypass for Automation |
| `CRON_SECRET` | repo | `keepalive.yml` (header `Authorization: Bearer`) | chuỗi ngẫu nhiên dài, **cùng giá trị** với biến Vercel `CRON_SECRET` |

Biến repository (không phải secret): `PROD_URL` = URL **https** gốc của production, không có đường dẫn (Task 6.4; `eval-full.yml` và `keepalive.yml` dùng; `keepalive.yml` từ chối `http://`).

Đánh đổi: `VERCEL_TOKEN` và bypass secret phải ở cấp repo vì job `preview` (không có Environment) cần chúng, nên một PR cùng repo của người có quyền ghi có thể đọc chúng. Giảm rủi ro bằng cách tạo Vercel token chỉ cho team/project này (không dùng token tài khoản), và coi quyền ghi vào repo là quyền deploy preview. Secret Supabase thì không lộ cho PR: Environment `production` chỉ chạy được từ `main`.

Job `migrate` và `deploy` đều có `environment: production`. Nếu bật Required reviewers thì **duyệt hai lần** (migrate, rồi deploy). Không muốn vậy thì để trống reviewers: giới hạn "Deployment branches" = `main` đã là lớp bảo vệ chính, reviewers chỉ là thêm.

**Vercel env** (Production **và** Preview; đánh dấu Sensitive cho khóa và token):

| Biến | Ghi chú |
|---|---|
| `DATABASE_URL` | pooler Supabase cổng 6543 |
| `LLM_BASE_URL`, `LLM_API_KEY` | gateway Kaggle qua ngrok domain tĩnh |
| `CRON_SECRET` | `/api/cron/keepalive` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | tracing |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | rate limit |
| `NEXT_PUBLIC_SITE_URL` | **bắt buộc** (xem dưới), có `https://` |
| `API_ORIGIN` | tùy chọn, xem cảnh báo dưới |

### `NEXT_PUBLIC_SITE_URL` và `API_ORIGIN` (ruling R32, Task 5.3)

Trang `/van-ban*` gọi API từ server (`frontend/src/lib/api-server.ts`): `API_ORIGIN` -> `NEXT_PUBLIC_SITE_URL` -> `VERCEL_PROJECT_PRODUCTION_URL` -> `VERCEL_URL`. URL deployment (`VERCEL_URL`) bị Deployment Protection trả 401, nên phải đặt tường minh. Workflow đỏ sớm nếu Vercel thiếu cả hai (đọc `.vercel/.env.<môi trường>.local` sau `vercel pull`; biến loại Sensitive không được pull nên đừng đánh Sensitive cho hai biến này).

- **Production:** `NEXT_PUBLIC_SITE_URL=https://<tên miền production công khai>`. Lấy ở Vercel, Project, Domains.
- **Preview:** cũng `https://<tên miền production>` (URL preview khác nhau mỗi lần deploy và bị protection chặn). Hệ quả: `/van-ban` trên preview đọc API của production (cùng một Supabase nên dữ liệu như nhau).
- **Không nên đặt `API_ORIGIN` ở production/preview** trừ khi spike chứng minh an toàn: khi có `API_ORIGIN`, `next.config` bật rewrite `/api/:path*` tới origin đó (`src/lib/api-rewrites.ts`). Trỏ nó về chính deployment thì có nguy cơ vòng lặp rewrite; trỏ về production thì API của preview bị bỏ qua. Vì thế bản này dùng `NEXT_PUBLIC_SITE_URL` (không bật rewrite). Lệch nhẹ so với ruling "đặt cả hai", ghi lại ở đây. Kiểm tra ở lần deploy đầu: `/van-ban` render và `/api/health` trả từ function `api`.

## Checklist `[USER]` (theo thứ tự)

1. Tạo project Vercel; `vercel link` cục bộ để lấy `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`. Tắt Git integration (spike Task 0.4 đặt `"git": {"deploymentEnabled": false}` trong `vercel.json`). Chạy xong spike Task 0.4 và ghi kết quả vào `docs/spikes.md` trước.
2. Tạo Vercel Token. Đặt toàn bộ **Vercel env** ở bảng trên cho cả Production và Preview.
3. Vercel, Deployment Protection: tạo Protection Bypass for Automation, lấy secret.
4. GitHub, Settings, Environments: tạo `production`, mục Deployment branches chọn "Selected branches" và chỉ cho `main`. Required reviewers tùy chọn (có thì duyệt hai lần, xem trên).
5. Thêm secret: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF` **trong Environment `production`**; `VERCEL_TOKEN` (nên là token chỉ cho project này), `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_AUTOMATION_BYPASS_SECRET` ở Settings, Secrets and variables, Actions (cấp repo).
6. Vercel, Project, Firewall: tạo WAF rate-limit (mục dưới).
7. Lần đầu: nếu project Supabase đã có bảng tạo tay trước khi dùng CLI thì `supabase db push` sẽ đụng, khi đó dùng `supabase migration repair` cho các migration đã áp. Merge một PR vào `main` và xem job `migrate` + `deploy`.
8. Kiểm tra cuối (chưa làm, cần live batch): merge một PR -> production cập nhật, `/api/health` trả `db: "ok"`.
9. Keep-alive (Task 6.5): thêm secret repo `CRON_SECRET` (cùng giá trị với biến Vercel `CRON_SECRET`) và đặt biến repository `PROD_URL` (phải là `https://...`, không có đường dẫn). Chạy tay `keepalive` bằng Actions, Run workflow, phải xanh.
10. Sau khi spike Task 0.4 đạt, thêm cron Vercel vào `vercel.json` (mục Keep-alive bên dưới); `vercel.json` đã có nhưng chưa có `crons`.

## Keep-alive Supabase (Task 6.5)

Supabase free pause project sau 7 ngày không hoạt động. `GET /api/cron/keepalive` (backend/app/api/cron.py) trả **204** khi `Authorization: Bearer $CRON_SECRET` đúng, **401** khi sai hoặc thiếu; bên trong chạy `select 1` qua pooler, tính là hoạt động DB. Hai cơ chế:

1. **Chính: GitHub schedule** `.github/workflows/keepalive.yml`, `cron: "0 2 */3 * *"` (mỗi 3 ngày, UTC) và `workflow_dispatch`. `curl --proto '=https'` (không `-f`, không `-L`) rồi kiểm mã HTTP **đúng 204**: 2xx khác, redirect (308 của `http://`) hay 401 đều đỏ, bearer token không bao giờ bị theo redirect hay gửi qua http. Secret và `PROD_URL` chỉ qua `env:`. Thiếu `CRON_SECRET`, thiếu `PROD_URL` hoặc `PROD_URL` không bắt đầu bằng `https://` thì job **đỏ** kèm thông báo (bỏ qua im lặng thì Supabase bị pause mà không ai biết). `PROD_URL` là URL https gốc, không có đường dẫn (dấu `/` cuối được cắt). Hệ quả: repo mới chưa cấu hình sẽ đỏ theo lịch cho đến khi làm checklist mục 9.
2. **Phụ: Vercel Cron** hằng ngày. `vercel.json` đã có (Task 0.4) nhưng **chưa** có `crons`: tài liệu Vercel không nói cron cấp cao nhất có chạy với Services hay không. Thêm vào `vercel.json` sau khi spike đạt (cấp cao nhất, cạnh `services`):
   ```json
   {"crons":[{"path":"/api/cron/keepalive","schedule":"0 3 * * *"}]}
   ```
   Hobby chỉ cho cron hằng ngày. Khi biến môi trường `CRON_SECRET` được đặt, Vercel tự gửi `Authorization: Bearer $CRON_SECRET`. Nếu Vercel Services không nhận cron ở root `vercel.json`, ghi vào `docs/spikes.md` và chỉ dựa vào GitHub schedule.

Giới hạn đã biết: GitHub **tự tắt workflow theo lịch** sau 60 ngày repo không có hoạt động (chủ repo phải bật lại ở tab Actions hoặc đẩy một commit). 60 ngày dài hơn 7 ngày rất nhiều, nên Vercel Cron mới là lớp bảo hiểm thật sự khi đã có. Trong lúc đó, nhớ bật lại workflow nếu repo yên 60 ngày. Chưa chạy trên GitHub, Vercel hay Supabase lần nào; endpoint được kiểm bằng `backend/tests/api/test_misc_endpoints.py`.

## WAF rate limit (ruling R29, Task 4.5) `[USER]`

Vercel, Project, Firewall, Custom Rules: một rule, điều kiện Request Path bằng `/api/chat`, hành động Rate Limit theo IP (gợi ý: cửa sổ 60 s, 20 request, trả 429; app tự giới hạn 20 request / 10 phút / IP và 300 request / ngày toàn cục trong `backend/app/ratelimit.py`, nên WAF chỉ là lớp thứ hai chặn bùng nổ trước khi function chạy). Giới hạn số rule theo gói Vercel chưa kiểm chứng. Rule cấu hình trong dashboard, không nằm trong repo.

## Đã biết, chưa xử lý

- **`statement_timeout`:** backend chưa đặt timeout cho câu SQL. Pooler Supabase ở transaction mode (6543) có thể không nhận startup option (`options=-c statement_timeout=...`). Hướng sửa khi cần: `SET LOCAL statement_timeout` trong mỗi transaction. Hiện chấp nhận: ngân sách `/api/chat` 100 s và `maxDuration` 120 s của function đã chặn trần. Chưa đổi code ở task này.
- **`vercel build` chạy cục bộ trên runner** với service Python có thể cần Python hoặc `uv` trên runner (ubuntu-latest có Python 3.12). Nếu build báo thiếu, thêm `astral-sh/setup-uv` vào job `preview` và `deploy`.
- **Region (Hobby chỉ 1 region, chưa xác minh):** `vercel.json` ghim `syd1` cho service `api` trong khi `web` ở region mặc định; deploy có thể lỗi vì số region. Cách xử lý (đặt Function Region ở cấp project, bỏ `regions` khỏi `functions`) ở `docs/spikes.md#vercel`, cây quyết định.
- Preview nào cũng chạy khi PR cùng repo xanh, kể cả PR chỉ sửa tài liệu (không lọc theo path), tốn quota deploy của Vercel.

## Thất bại và rollback

- Deploy production hỏng (smoke đỏ hoặc bản mới lỗi): Vercel, Deployments, chọn bản trước đó, **Promote to Production** (hoặc `vercel rollback`). Không cần chạy lại CI.
- Dữ liệu: rollback bằng đổi con trỏ `app_config.active_index_version` về index cũ (blue/green trong một DB). Migration chỉ additive nên không có down-migration; guard ở trên chặn migration phá dữ liệu.
- `migrate` đỏ thì `deploy` không chạy, production giữ bản cũ. Một migration đã áp xong mà `deploy` đỏ vẫn an toàn vì migration additive và `hybrid_search` giữ nguyên chữ ký.

## Phương án dự phòng: Vercel Git integration `[chưa xác minh, dùng nếu spike cho thấy --prebuilt không hỗ trợ Services]`

1. Vercel, Project, Settings, Git: kết nối repo GitHub; bỏ `"git": {"deploymentEnabled": false}` khỏi `vercel.json`. Production deploy theo `main`, preview theo PR; Vercel tự build.
2. `.github/workflows/ci.yml`: xóa job `deploy-preview`; giữ `deploy-prod` nhưng chỉ để chạy `migrate`.
3. `.github/workflows/deploy.yml`: xóa các job `gate`, `preview`, `deploy` (giữ `migrate`); các secret `VERCEL_*` trong GitHub không còn dùng thì xóa.
4. Mất: Playwright trên preview và smoke `/api/health` trong CI, và thứ tự "migrate xong mới deploy" (Vercel deploy song song). Chấp nhận được vì migration additive; muốn giữ thứ tự thì đặt Vercel Ignored Build Step chờ `migrate`.
5. Ghi ADR theo Task 0.4 và sửa lại mục này.
