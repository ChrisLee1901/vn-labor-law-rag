# Checklist việc bạn tự làm (theo thứ tự)

Phần code đã xong và đã review ở local. Những gì còn lại cần tài khoản, secret, GPU Kaggle, remote GitHub, Vercel, Supabase, Langfuse hoặc quyết định của bạn. File này xếp chúng theo thứ tự phụ thuộc. Quy trình chung cho mỗi bước:

1. Làm các bước đánh số trong một **Giai đoạn**.
2. Đối chiếu **Dấu hiệu thành công**. Lỗi thì xem **Nếu lỗi**.
3. Dán khối **Gửi lại cho trợ lý** vào chat. Trợ lý sẽ tick plan (`docs/superpowers/plans/2026-11-22-vietnamese-legal-rag.md`) rồi làm tiếp.

Nhắc an toàn (luật cứng trong `CLAUDE.md`):

- **Không bao giờ dán token, mật khẩu, authtoken, API key, chuỗi `DATABASE_URL` có mật khẩu vào chat.** Chỉ dán đúng các giá trị "không bí mật" ghi trong khối gửi lại (số đo, tên domain công khai, tên biến, ảnh chụp đã che).
- Secret chỉ nằm ở: trình quản lý mật khẩu, Kaggle Secrets, Vercel env, GitHub Secrets. Không commit `.env`.
- **Kaggle chỉ bật khi đang làm việc hoặc demo**, xong là *Stop session* (không chỉ ngắt kernel). Không viết gì để giữ notebook chạy mãi. Không công khai URL tunnel.
- Supabase chỉ có **1 project**. Migration chỉ additive. Không xóa hay ghi đè index đang active.
- Trợ lý không tự commit hay push. Bạn yêu cầu thì mới làm.
- Ký hiệu: `<TÊN>` là chỗ bạn thay bằng giá trị thật, không dán giá trị đó vào chat. Lệnh viết cho Git Bash; PowerShell thì thay `export X=...` bằng `$env:X="..."`.
- Trên Windows, phòng khi stdout không phải console UTF-8 (Git Bash, hoặc ghi ra pipe/file), hãy đặt `PYTHONUTF8=1` (Git Bash: `export PYTHONUTF8=1`; PowerShell: `$env:PYTHONUTF8=1`) trước các lệnh Python in tiếng Việt. `scripts/smoke_llm.py` đã tự đặt UTF-8 cho stdout/stderr; một số script khác (ví dụ `answer_eval`, `latency_report`) cũng in thông báo tiếng Việt và chưa tự đặt, nên cứ đặt biến này cho chắc (smoke, ingest, retrieval_eval, eval).

## Trạng thái hiện tại (đã kiểm tra)

- Nhánh là `feat/rag-v1` (63 commit), chưa có remote. `main` local chỉ là commit `a3407a3` (import tài liệu và corpus raw, **chưa có workflow**). Plan viết `main` vì plan có trước nhánh này.
- Chưa có: `vercel.json`, `eval/index/`, `eval/cache/`, `eval/baselines/`, `eval/results/`. Các file này do trợ lý viết khi bạn nhắn đúng câu ở từng giai đoạn dưới đây.
- Có sẵn: `kaggle/serve.ipynb` (sinh từ `kaggle/build_notebook.py`), `kaggle/build_llamacpp.ipynb` (spike 0.2, đã viết, chưa chạy), `docs/spikes.md` (khung, chưa có số), `docs/runbook-kaggle.md`, `docs/deploy.md`, `docs/ci.md`, `docs/runbook-eval.md`, `docs/runbook-observability.md`, 4 migration trong `supabase/migrations/`.

## Thứ tự và thời gian ước tính

| Giai đoạn | Việc | Ước tính | Cần Kaggle bật? |
|---|---|---|---|
| A | Repo GitHub, push, CI chạy lần đầu, bảo vệ nhánh | 45 phút | không |
| B | Tạo tài khoản, gom secret | 1 đến 1,5 giờ | không |
| C | Kaggle: spike 0.2, 0.3, notebook serve 2.2, smoke 2.3 | 2 đến 4 giờ | có |
| D | Supabase: spike 0.5, áp migration lần đầu | 45 phút | không |
| E | Vercel: spike 0.4 | 1 đến 2 giờ | không |
| F | Xác minh ND145, ingest thật, duyệt golden, eval truy xuất thật | 3 đến 4 giờ | có (ingest, eval) |
| G | Deploy production, WAF, keep-alive | 1 đến 1,5 giờ | không |
| H | Eval đầy đủ, Langfuse, A/B model, bằng chứng gate | 3 đến 5 giờ | có |
| I | Quay video demo | 1 đến 2 giờ | có |

Phụ thuộc: A, B làm trước. C, D, E độc lập nhau sau B (nhưng G cần E và D). F cần C (embedding) và D. H cần G, C, F. I cần G và trợ lý đã viết xong Task 7.3.

---

## Giai đoạn A: GitHub repo và push

**Khuyến nghị:** đẩy `main` (chỉ có `a3407a3`) lên trước, rồi đẩy `feat/rag-v1` và mở PR. Đừng đổi tên nhánh thành `main`.

Lý do (đọc từ `.github/workflows/ci.yml`, `deploy.yml`, `keepalive.yml`):

- `main` ở `a3407a3` **không có workflow nào**, nên đẩy nó không kích hoạt gì. Nó chỉ tạo nhánh gốc và nhánh mặc định cho repo.
- PR `feat/rag-v1` -> `main` chạy `ci.yml`. Các job `web`, `api`, `pipelines`, `kaggle`, `db`, `eval-retrieval`, `secrets`, `ci-ok` chạy (đều không cần secret của bạn). `eval-retrieval` sẽ **xanh kèm cảnh báo** "Gate inactive" vì chưa có `eval/baselines/main.json` (đúng thiết kế). `deploy-preview` tự bỏ qua kèm `::notice::` khi chưa có secret Vercel.
- **Merge PR vào `main` là lúc `push: main` kích hoạt `deploy-prod`**: job `migrate` (Environment `production`) rồi `deploy`. Chưa có secret Supabase và Vercel thì job này **đỏ**. Ngoài ra `keepalive.yml` (chạy theo lịch từ nhánh mặc định) sẽ **đỏ** mỗi 3 ngày khi thiếu `CRON_SECRET` hoặc `PROD_URL`. Vì vậy: **đừng merge PR này vào `main` cho tới khi xong Giai đoạn G** (hoặc chấp nhận vài lần đỏ).

Các bước:

1. Trên GitHub, tạo repo **public**, tài khoản cá nhân, tên `vn-labor-law-rag`, **không** tick README/.gitignore/license (repo đã có).
2. Trong thư mục repo:
   ```bash
   git remote add origin https://github.com/<TÀI-KHOẢN>/vn-labor-law-rag.git
   git push -u origin main
   git push -u origin feat/rag-v1
   ```
3. Settings, Actions, General:
   - Actions permissions: cho phép actions.
   - Workflow permissions: tick **"Allow GitHub Actions to create and approve pull requests"** (cần cho `eval-full`, nếu không bước mở PR lỗi 403).
4. Mở PR `feat/rag-v1` -> `main` (chưa merge). Chờ CI chạy xong lần đầu. Phải thấy check tên `ci-ok`.
5. **Sau khi `ci-ok` đã chạy ít nhất một lần**: Settings, Branches (hoặc Rulesets), thêm quy tắc cho `main` ([docs/ci.md](ci.md)):
   - Require a pull request before merging.
   - Require status checks to pass: thêm đúng một check `ci-ok`.
   - Require branches to be up to date (khuyến nghị).
6. Bật Dependabot: file `.github/dependabot.yml` đã có; vào Settings, Code security, bật Dependabot alerts và version updates nếu GitHub chưa tự bật.
7. Khuyến nghị bắt buộc review cho các file làm lỏng gate (chưa có CODEOWNERS vì chưa biết username của bạn): `eval/baselines/**`, `scripts/eval_gate_precheck.py`, `.github/workflows/eval-retrieval.yml`. Cách nhanh: ruleset thứ hai, "Restrict file paths" hoặc thêm `.github/CODEOWNERS` dòng `eval/baselines/ @<TÀI-KHOẢN>` và bật "Require review from Code Owners". Nếu làm một mình thì tự review không được, nên bước này có thể bỏ và chấp nhận rủi ro; ghi lại quyết định.

**Dấu hiệu thành công:** tab Actions có run `ci` cho PR, `ci-ok` xanh. `eval-retrieval` xanh với annotation vàng "Gate inactive". `deploy-preview` skipped hoặc notice "Bỏ qua preview".

**Nếu lỗi:**

- `lfs: true` hoặc job `secrets` (gitleaks) đỏ: mở log job, gửi 20 dòng cuối. Gitleaks đỏ nghĩa là có chuỗi giống secret trong lịch sử; không bỏ qua, gửi tên file và dòng (không gửi giá trị).
- `web`/`api` đỏ do khác môi trường Windows/Linux: gửi log, trợ lý sửa. CI chưa chạy lần nào trên GitHub nên có thể có lỗi nhỏ.
- Check `ci-ok` không hiện trong danh sách khi thêm branch protection: chưa có run nào xong. Chờ CI chạy xong rồi tải lại trang.

**Gửi lại cho trợ lý** (task 0.1 mục remote, 6.1 `[USER]`):

- Link repo và link PR (public, không bí mật).
- Ảnh chụp tab Checks của PR (hoặc dán danh sách job và trạng thái).
- Với job đỏ: tên job và 20 dòng cuối của log.
- Xác nhận đã bật branch protection (có/không), và quyết định về review bắt buộc.

---

## Giai đoạn B: Tài khoản và kho secret

Tạo theo thứ tự này. Lưu mọi giá trị vào trình quản lý mật khẩu. **Không dán giá trị vào chat.**

| # | Tạo gì | Chi tiết | Biến / tên | Đặt ở đâu | Bắt buộc? |
|---|---|---|---|---|---|
| 1 | Kaggle | Xác minh số điện thoại. Khi tạo notebook bật **Internet** | không | n/a | có |
| 2 | Hugging Face | Settings, Access Tokens, loại **Read** | `HF_TOKEN` | Kaggle Secrets | có |
| 3 | ngrok | Lấy authtoken. Dashboard, Domains, claim **1 dev domain tĩnh** `<ten>.ngrok-free.dev` | `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` (không kèm `https://`) | Kaggle Secrets | có |
| 4 | Chuỗi gateway key | Tự sinh chuỗi ngẫu nhiên dài, ví dụ `python -c "import secrets;print(secrets.token_urlsafe(48))"` | `GATEWAY_API_KEY` (Kaggle) và `LLM_API_KEY` (Vercel, và env local khi chạy lệnh): **cùng giá trị** | Kaggle Secrets + Vercel env | có |
| 5 | Supabase | Project mới, region **ap-southeast-2** (Sydney). Lưu mật khẩu DB. Connect, **Transaction pooler** cổng 6543 | `DATABASE_URL`; `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF`; Account, Access Tokens: `SUPABASE_ACCESS_TOKEN` | Vercel env (`DATABASE_URL`); GitHub Environment `production` (3 secret Supabase) | có |
| 6 | Vercel | Hobby, đăng nhập bằng GitHub. Account Settings, Tokens: tạo token riêng cho project này | `VERCEL_TOKEN` | GitHub Secrets cấp repo | có |
| 7 | Upstash | Redis free | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | Vercel env | tùy chọn (thiếu thì backend không giới hạn tần suất; nên có trước khi công khai) |
| 8 | Langfuse Cloud | Hobby. Chọn vùng; project mới; lấy khóa | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (ví dụ `https://cloud.langfuse.com`, đúng vùng) | Vercel env | tùy chọn (thiếu thì tracing tắt, app vẫn chạy); cần cho Giai đoạn H |
| 9 | Chuỗi cron | Tự sinh chuỗi ngẫu nhiên dài | `CRON_SECRET`: **cùng giá trị** ở Vercel env và GitHub Secrets cấp repo | Vercel env + GitHub Secrets | có (keep-alive) |
| 10 | Deployment Protection bypass | Tạo ở Vercel (Giai đoạn G) | `VERCEL_AUTOMATION_BYPASS_SECRET` | GitHub Secrets cấp repo | gần như bắt buộc (smoke production và Playwright preview nhận 401 nếu thiếu) |

Biến không bí mật đặt ở GitHub, Settings, Secrets and variables, **Variables**: `PROD_URL` = URL https gốc của production, không có đường dẫn (đặt ở Giai đoạn G). Vercel env còn cần `NEXT_PUBLIC_SITE_URL` (Giai đoạn G). Bảng đầy đủ: [deploy.md](deploy.md) mục "Secrets và biến môi trường". Kaggle Secrets cần đúng 4 cái: `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `GATEWAY_API_KEY`, `HF_TOKEN`.

**Dấu hiệu thành công:** bạn có đủ 10 mục trong trình quản lý mật khẩu; `https://dashboard.ngrok.com` hiện domain tĩnh; Supabase project ở trạng thái Healthy.

**Nếu lỗi:** ngrok chỉ cho 1 domain tĩnh miễn phí; domain phải khớp `^https://[a-z0-9-]+\.ngrok-free\.(app|dev)$` (backend chặn SSRF bằng regex này), domain `.ngrok-free.dev` hợp lệ. Kaggle không cho bật Internet nếu chưa xác minh điện thoại.

**Gửi lại cho trợ lý:** chỉ cần ghi "Giai đoạn B xong" kèm: tên domain ngrok (công khai, ví dụ `abc-def.ngrok-free.dev`), region Supabase (ap-southeast-2?), vùng Langfuse (EU/US), mục nào bỏ qua (Upstash? Langfuse?). **Không** gửi khóa.

---

## Giai đoạn C: Kaggle (spike 0.2, 0.3, notebook serve 2.2, smoke 2.3)

Bật Kaggle chỉ trong lúc làm giai đoạn này. Hạn mức GPU Kaggle theo tuần có hạn (T4 x2): làm liền một buổi, dừng session khi xong.

### C1. Spike 0.2 (llama.cpp sm_75) và 0.3 (ngrok + SSE)

`kaggle/build_llamacpp.ipynb` (spike 0.2) **đã viết**: Import vào Kaggle rồi Run All, bước 2 đến 6 bên dưới do notebook làm (chi tiết và cách xử lý lỗi: `docs/spikes.md#llama`). `kaggle/spike_sse.py` + `scripts/spike_sse_check.py` (spike 0.3) **đã viết**, chưa chạy thật (chi tiết, ngưỡng đạt và cách xử lý lỗi: `docs/spikes.md#sse`).

Nội dung cần làm (theo plan Task 0.2, 0.3):

1. Tạo notebook Kaggle mới (Import `kaggle/build_llamacpp.ipynb`), Settings: **GPU T4 x2**, **Internet bật**. Add Secrets (`HF_TOKEN`, `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `GATEWAY_API_KEY`), tick "Attached".
2. Build: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 && cmake --build build -j --target llama-server llama-bench` (khoảng 26 phút). Linker báo thiếu `libcuda.so` thì tạo symlink.
3. Đóng gói `build/bin/*` và **mọi file `.so`** thành output, rồi **Save Version > "Save & Run All (Commit)"** (chạy lại toàn bộ notebook, khoảng 25 phút build + 6 GB tải + bench, tốn thêm hạn mức GPU; Quick Save có lộ Output hay không là chưa xác minh; tên nút trên giao diện Kaggle chưa xác minh), rồi tạo Dataset private **`llamacpp-sm75-bin`** từ tab Output của version đó (New Dataset). Chi tiết: `docs/spikes.md#llama`.
4. Tải `Qwen3-8B-Q5_K_M.gguf` (repo GGUF của Qwen; không có thì bản `unsloth`), lưu thành Dataset private **`qwen3-8b-gguf`**.
5. `llama-bench -m <gguf> -ngl 99 -p 4096 -n 256`. Ghi pp và tg tok/s. **Đạt** khi tg >= 15 tok/s (không đạt: thử Q4_K_M và ghi lại).
6. `llama-server --help`: xác nhận các cờ `--jinja`, `-fa`, `--chat-template-kwargs`, `--api-key`, `--reasoning-budget`. Đây là điểm **chưa xác minh**: `kaggle/serve.ipynb` đang dùng `--jinja --reasoning-budget 0 --chat-template-kwargs {"enable_thinking": false}`; nếu bản build không nhận cờ nào, ghi tên cờ đúng.
7. Spike SSE (notebook Kaggle riêng, không cần GPU, 3 secret `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `GATEWAY_API_KEY`; tắt notebook `serve` trước vì một domain chỉ giữ một tunnel). Cell 1: `!git clone https://github.com/<TÀI-KHOẢN>/vn-labor-law-rag` rồi `!pip install -q pyngrok fastapi uvicorn` (cần đã push, giai đoạn A). Cell 2: `!python vn-labor-law-rag/kaggle/spike_sse.py --duration-min 10`, chờ dòng `READY https://<NGROK_DOMAIN>` (tự thoát sau 10 phút). Trên máy bạn: `export GATEWAY_API_KEY=<GATEWAY_API_KEY>` rồi `python scripts/spike_sse_check.py --url https://<NGROK_DOMAIN>/stream --token-env GATEWAY_API_KEY --expect 150`. **Đạt** khi checker in `verdict: PASS` (đủ 150 event, không bị cắt, không dồn cục, không token và token sai đều 401).

**Dấu hiệu thành công:** hai dataset private tồn tại; tg >= 15 tok/s; 150 event đủ qua curl.

**Nếu lỗi:** ngrok cắt stream giữa chừng (**chưa xác minh**, đây là mục tiêu của spike): ghi lại thời điểm bị cắt, **đừng tự chọn phương án khác**, báo trợ lý (plan nêu Cloudflare named tunnel, cần domain riêng). Build lỗi thiếu `.so` hoặc VRAM: gửi 30 dòng cuối log build.

**Gửi lại cho trợ lý** (task 0.2, 0.3):

- `pp` và `tg` tok/s của llama-bench (số), quant đã dùng.
- Danh sách cờ `llama-server` xác nhận có/không: `--jinja`, `-fa`, `--chat-template-kwargs`, `--api-key`, `--reasoning-budget`.
- Spike SSE: dán nguyên khối `=== RESULT spike_sse ===` của checker (đã che domain, không chứa token).
- Tên hai dataset đã tạo (xác nhận).

Trợ lý ghi vào `docs/spikes.md#llama` (khung đã có, còn trống số liệu). Khối `RESULT` ở cell cuối của notebook đã gom sẵn mọi số trên: dán nguyên khối in ra ở lần chạy **Commit (Save & Run All)** (lần Run All tương tác chỉ là smoke test).

### C2. Notebook serve thật (Task 2.2)

Làm theo [runbook-kaggle.md](runbook-kaggle.md) mục "Thiết lập một lần" (Import `kaggle/serve.ipynb`, Add Input hai dataset, 4 secret, Settings), rồi **Run All** và bấm giờ.

**Dấu hiệu thành công:** cell 8 in `READY https://<domain>` kèm smoke test (embedding 1024 chiều, rerank, một câu trả lời tiếng Việt, không có `<think>`) trong **<= 10 phút** từ lúc bấm Run All (có sẵn hai dataset; hàng đợi GPU không tính). Mở `https://<domain>/health` trên trình duyệt thấy `"status":"ok"` (trình duyệt chỉ đọc được `/health`, các endpoint khác đòi bearer).

**Nếu lỗi:** bảng "Sự cố thường gặp" trong runbook-kaggle (401, badge đỏ, `ERR_NGROK_334`, thiếu `.so`). Đã biết (ledger): smoke test trong notebook gọi `127.0.0.1`, không phải tunnel; process con thừa hưởng biến môi trường chứa secret. Gặp gì lạ thì gửi log cell.

### C3. Smoke và benchmark (Task 2.3)

`scripts/smoke_llm.py` đã viết (chưa chạy với gateway live). Với notebook đang READY, chạy trên máy bạn:

```bash
export LLM_BASE_URL=https://<NGROK_DOMAIN>
export LLM_API_KEY=<GATEWAY_API_KEY>     # chỉ trong shell này
python scripts/smoke_llm.py              # PowerShell: $env:LLM_BASE_URL="..."; $env:LLM_API_KEY="..."
```

Script kiểm: `/health` có `llm` true, embed 2 câu ra 1024 chiều, rerank đúng thứ tự, chat stream 3 lần đo TTFT và tok/s. **Đạt** khi TTFT p50 < 3 s qua tunnel và câu trả lời tiếng Việt có dấu đúng.

Việc nhỏ trong phiên này (ledger Task 4.1): đo thật số ký tự trên token của Qwen3 với văn bản luật tiếng Việt qua `llama-server` `/tokenize` để chỉnh `max_context_chars` (hiện 18000 ký tự, giả định ~6k token). Nhờ trợ lý đưa lệnh đo khi bạn làm C3.

**Gửi lại cho trợ lý** (task 2.2, 2.3):

- Thời gian từ Run All tới `READY` (phút), có dùng dataset không.
- Nguyên khối `=== RESULT smoke_llm ===` do script in (không chứa key, host đã che nhãn đầu): gồm TTFT p50/p95, tok/s, embed 1024 chiều, thứ tự rerank, đoạn đầu câu trả lời. Chi tiết và cách đọc: [spikes.md#bench](spikes.md#bench).
- Ảnh chụp cell 8 (che URL nếu muốn; domain ngrok không phải bí mật nhưng đừng công khai URL tunnel).

**Giữ notebook bật nếu sắp làm tiếp Giai đoạn F** (ingest cần embedding). Không thì Stop session.

---

## Giai đoạn D: Supabase (spike 0.5 và migration lần đầu)

Chưa cần Kaggle.

1. Cài Supabase CLI (chưa có trên máy; ledger R1 dùng `npx supabase`): thay `supabase` bằng `npx supabase` trong các lệnh dưới nếu không cài global.
2. Spike pgvector (Supabase, SQL Editor):
   ```sql
   create extension if not exists vector;
   select extversion from pg_extension where extname = 'vector';
   ```
   >= 0.8.0 thì có iterative scan.
3. Đo `select 1` qua pooler 6543 (lần gọi nóng) từ máy bạn:
   ```bash
   export DATABASE_URL='<chuỗi pooler cổng 6543>'
   python -c "import os,time,psycopg;c=psycopg.connect(os.environ['DATABASE_URL'],prepare_threshold=None);t=time.time();c.execute('select 1');t=time.time()-t;t2=time.time();c.execute('select 1');print('lan1',round(t,3),'lan2 (nong)',round(time.time()-t2,3))"
   ```
   (Từ máy bạn ở Việt Nam, số này không đại diện Vercel `syd1`; số đo đúng từ function Vercel sẽ lấy ở Giai đoạn E/G qua `/api/health`.)
4. **Áp migration lần đầu thủ công, không để CI làm**:
   ```bash
   supabase login                                  # trình duyệt, không dán token vào chat
   supabase link --project-ref <SUPABASE_PROJECT_REF>
   supabase db push --dry-run                      # xem danh sách migration sắp áp
   supabase db push
   ```
   Lý do khuyến nghị: lần đầu bạn tự thấy log, và `scripts/migration_guard.py` đọc đầu ra `--dry-run` của CLI mà **wording "Remote database is up to date." chưa xác minh** (guard fail closed nếu không nhận ra). Sau lần push này, chạy lại `supabase db push --dry-run` và gửi đúng câu CLI in ra để trợ lý khớp hằng `UP_TO_DATE`.
   Phải thấy 4 migration (`20261201000000_init`, `..0100_hybrid_search`, `..0200_appendix_kind`, `..0300_function_search_path`). Migration chỉ additive; không tạo bảng tay trước khi push (nếu đã tạo thì dùng `supabase migration repair`, xem deploy.md checklist mục 7).
5. Kiểm tra bảng: SQL Editor `select key, value from app_config;` phải thấy `active_index_version = 1`, `refusal_tau = 0.35`.

**Dấu hiệu thành công:** `extversion` in ra; `select 1` nóng < 1 s; 4 migration áp xong; `app_config` có 2 dòng.

**Nếu lỗi:** `db push` hỏi mật khẩu thì dùng mật khẩu DB (nhập tại terminal, không dán chat). Pooler báo prepared statement: chắc chắn đã dùng `prepare_threshold=None` và cổng 6543. Lỗi extension: bật `vector` ở Database, Extensions.

**Gửi lại cho trợ lý** (task 0.5; một phần 6.3 mục 7):

- `extversion` của pgvector.
- Thời gian `select 1` lần 1 và lần nóng (giây).
- Danh sách tên migration `db push` đã áp, và câu CLI in ra ở `--dry-run` lần thứ hai.
- Kết quả `select key, value from app_config;`.

---

## Giai đoạn E: Vercel (spike 0.4: Services + `--prebuilt`)

Đây là điểm rủi ro lớn nhất, **chưa xác minh**: Vercel Services có chạy với `vercel build` + `vercel deploy --prebuilt` hay không. Kết quả quyết định cả `deploy.yml`. Cũng chưa xác minh: tên field AI SDK v7 cho `source-url`, `data-*`, `error` và header `x-vercel-ai-ui-message-stream` (docs/ai-sdk-protocol.md đã ghi phần đã kiểm).

Frontend (`frontend/`) và backend (`backend/app/main.py`, có `/api/health`) **đã tồn tại**, plan 0.4 giả định chỉ có bản "hello"; spike sẽ dùng bản thật. Code đã viết: `vercel.json` (2 service `web` root `frontend` và `api` root `backend` entrypoint `app.main:app`, rewrite `/api/(.*)`, `"git": {"deploymentEnabled": false}`), endpoint `/api/ping` và `/api/sse` (30 event) tạm thời trong `backend/app/api/spike.py` (chỉ bật khi `ENABLE_SPIKE_ENDPOINTS=1`), `.github/workflows/spike-deploy.yml` và checker `scripts/spike_vercel_check.py`. Quy trình chi tiết: [spikes.md](spikes.md#vercel).

Phần bạn làm:

1. `npm i -g vercel` rồi `vercel login`. Trong thư mục repo: `vercel link` (tạo project mới). Lệnh này tạo `.vercel/project.json` (đã trong `.gitignore`) chứa `orgId` và `projectId` (không bí mật, nhưng chỉ cần cho GitHub Secrets).
2. Thêm GitHub Secrets cấp repo: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (Settings, Secrets and variables, Actions).
3. Không cần đặt env Vercel nào cho spike (`/api/ping` chưa gọi DB, đó là việc của Task 0.5; workflow tự truyền `ENABLE_SPIKE_ENDPOINTS=1`). Tùy chọn: tạo Protection Bypass for Automation (Deployment Protection) và `export VERCEL_AUTOMATION_BYPASS_SECRET=...` trên máy bạn.
4. Đẩy nhánh lên GitHub rồi chạy workflow `spike-deploy` (tab Actions, Run workflow; `vercel pull --yes --environment=preview` -> `vercel build` -> `vercel deploy --prebuilt`). URL preview nằm ở job summary. Chạy `vercel build` trên Windows với service Python **chưa xác minh**; nếu cần thì dùng workflow (Linux) hoặc WSL.
5. Chạy checker trên máy bạn: `python scripts/spike_vercel_check.py --url https://<preview>.vercel.app --bypass-env VERCEL_AUTOMATION_BYPASS_SECRET` (bỏ `--bypass-env` nếu không bật Protection). Dán nguyên khối `=== RESULT spike_vercel ===`. Nó kiểm các mục sau (xem tay nếu muốn: `curl -N` thêm `-H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET"` khi có Protection):
   - `/` hiển thị trang Next.js.
   - `/api/ping` trả `{"ok": true, ...}` kèm `path`, `root_path`, `raw_path`, `vercel_region` (chưa có `select 1`, việc của Task 0.5).
   - `curl -N https://<preview>/api/sse` nhận từng event cách nhau ~1 giây (không dồn cục).
   - Checker in: FastAPI nhận path **có** `/api` hay đã bị cắt, region của function so với `syd1`. Tự ghi thêm từ dashboard (Deployment, Functions): `maxDuration` và region hiển thị. Header `x-vercel-ai-ui-message-stream` không kiểm ở spike này (`/api/chat` cần DB và LLM): kiểm ở lần deploy thật đầu tiên.
6. Nếu `--prebuilt` không hỗ trợ Services: dùng phương án dự phòng (Vercel Git integration) trong [deploy.md](deploy.md) mục "Phương án dự phòng". Trợ lý sẽ ghi ADR và sửa `ci.yml`, `deploy.yml`.

**Dấu hiệu thành công:** ba mục `/`, `/api/ping`, `/api/sse` đạt trên URL preview, và `vercel deploy --prebuilt` không báo lỗi Services.

**Nếu lỗi:** `vercel build` thiếu Python hoặc `uv`: thêm `astral-sh/setup-uv` vào job (đã dự đoán trong deploy.md). `/api/*` trả 404 hoặc vào nhầm Next.js: sai rewrite, gửi `vercel.json` và log `vercel build`. `/api/sse` dồn cục: ghi lại, đây là lỗi ảnh hưởng chat; không tự đổi. Checker báo `/api/ping returned HTTP 404 JSON: FastAPI answered but the route is absent, so ENABLE_SPIKE_ENDPOINTS=1 did not reach the function` (cờ chưa tới runtime; việc workflow "tự truyền" biến này qua `--env` + `--prebuilt` + Services là **chưa xác minh**): đặt `ENABLE_SPIKE_ENDPOINTS=1` cho môi trường Preview trong Vercel (Project, Settings, Environment Variables) rồi chạy lại workflow (xem [spikes.md](spikes.md#vercel), mục "Điều chưa xác minh" số 4). Deploy lỗi vì số region: Hobby chỉ cho 1 region, đặt Project, Settings, Functions, Function Region = `syd1` cho cả project và xóa `regions` khỏi `functions` trong `vercel.json`; thử cả hai biến thể trong cùng một lần spike và báo biến thể nào chạy được.

**Gửi lại cho trợ lý** (task 0.4, 0.5, 6.5 cron, một phần 6.3):

- Kết quả từng URL: `/` có render không; `/api/ping` nội dung; `/api/sse` có stream từng event không (số event và có dồn cục không).
- FastAPI thấy path có `/api` hay không; `maxDuration` đặt chỗ nào; region `syd1` nhận hay không.
- Header `x-vercel-ai-ui-message-stream`: để lần deploy thật đầu tiên (không thuộc spike này).
- Thời gian `select 1` từ function Vercel (lần nóng): thuộc Task 0.5, chưa có trong `/api/ping` của spike này.
- `--prebuilt` hỗ trợ Services: có/không, kèm thông báo lỗi (nếu có).
- Link run Actions (công khai nếu repo public) hoặc 20 dòng cuối log khi lỗi.
- Xác nhận đã thêm 3 secret `VERCEL_*` (có/không), không gửi giá trị.

Trợ lý sẽ sau đó thêm cron `{"crons":[{"path":"/api/cron/keepalive","schedule":"0 3 * * *"}]}` vào `vercel.json` (nếu Services nhận) và viết `docs/spikes.md` tổng kết 4 spike, rồi commit (khi bạn yêu cầu). Xóa `spike-deploy.yml` sau spike.

---

## Giai đoạn F: Ingest thật, duyệt golden, eval truy xuất thật

Làm theo thứ tự F1 -> F2 -> F3 -> F4. F1 và F2 làm được trước mà không cần Kaggle.

### F1. Xác minh tình trạng ND145/2020 (ghi trong `docs/corpus/legal_docs.yaml`)

Dòng 19 của `legal_docs.yaml` còn `TODO(USER)`: tra web chỉ thấy dự thảo sửa đổi 2026, chưa thấy nghị định sửa đổi được ban hành. Làm **trước ingest** vì `status`, `effective_to` đi vào DB.

1. Vào https://vbpl.vn, tìm "145/2020/NĐ-CP". Mở trang văn bản, xem:
   - **Tình trạng hiệu lực** (Còn hiệu lực / Hết hiệu lực một phần / toàn bộ).
   - Tab **Lược đồ** hoặc **Văn bản liên quan**: có nghị định nào **sửa đổi, bổ sung, thay thế** ND145/2020 đã ban hành không (số hiệu, ngày ban hành, ngày hiệu lực).
   - Điều bị sửa nếu hết hiệu lực một phần.
2. Hiện YAML ghi `status: con_hieu_luc`, `effective_to: null`, `replaced_by: null`. Nếu khác, đó là thay đổi cần làm trước ingest (và nếu có văn bản mới thì phải thêm vào `legal_docs.yaml` rồi ingest; xem phần "Rủi ro đã biết" trong `CLAUDE.md`).

**Gửi lại cho trợ lý** (task 1.2):

- Tình trạng hiệu lực chữ nguyên văn trên vbpl.vn, ngày bạn tra.
- Có/không văn bản sửa đổi hoặc thay thế; nếu có: số hiệu, ngày ban hành, ngày hiệu lực.
- Ảnh chụp màn hình trang vbpl.vn.

Trợ lý sửa `legal_docs.yaml` và bỏ dòng `TODO(USER)`.

### F2. Duyệt tay 20 câu golden (`eval/golden/review_sample.csv`)

File có 20 dòng, cột `id,type,question,answer,gold,ok`, cột `ok` đang trống. Mở bằng Excel hoặc VS Code. Với mỗi dòng, đọc `question`, `answer`, `gold` (id Điều/Khoản; gold rỗng với câu `unanswerable`, `out_of_domain`, `injection` vì đáp án đúng là **từ chối**), rồi mở văn bản luật tương ứng (ví dụ trang congbao hoặc `docs/corpus/raw/<mã>/`) và kiểm tra.

Điền cột `ok`: `1` = đúng, `0` = sai. Đánh **sai** khi:

- `answer` mâu thuẫn với điều luật gold (sai số tiền, số ngày, tỷ lệ, điều kiện).
- `gold` trỏ tới Điều/Khoản không chứa căn cứ của đáp án (hoặc thiếu một Điều cần thiết cho câu nhiều bước).
- Câu `temporal` chọn sai văn bản theo ngày (ND293 hết hiệu lực từ 2027-01-01, ND399 thay thế).
- Câu được gắn `unanswerable`/`out_of_domain` nhưng thực ra trả lời được từ corpus (hoặc ngược lại).
- Câu hỏi nhập nhằng đến mức không có đáp án duy nhất.

Ghi ngắn lý do cho từng dòng `0` (một câu). Phần trăm sai của mẫu dùng để nói về chất lượng nhãn: trợ lý ghi vào `eval/golden/DATASET_CARD.md` (dòng "Kiểm tra thủ công 20 câu ... đang chờ"). Làm **trước** F4: nếu phát hiện nhãn sai hàng loạt, sửa golden trước rồi mới tính cache embedding và baseline.

**Gửi lại cho trợ lý** (task 3.3 `[USER]`):

- 20 giá trị `ok` kèm `id` (ví dụ `q082=1, q015=1, q004=0 (lý do)...`) hoặc dán nguyên file CSV đã điền (không bí mật).
- Ghi chú về lỗi lặp lại (nếu có), ví dụ `q007` loại `multi_hop` nhưng chỉ một văn bản (ledger đã ghi mục này, đáng xem cả 18 câu `multi_hop`).

### F3. Ingest thật (Task 3.1, cần Kaggle bật)

Bật notebook serve (C2), chờ `READY`. Trên máy bạn, trong thư mục repo:

```bash
export DATABASE_URL='<pooler Supabase cổng 6543>'      # chỉ trong shell này
export LLM_BASE_URL=https://<NGROK_DOMAIN>
export LLM_API_KEY=<GATEWAY_API_KEY>
cd pipelines && uv sync
uv run python -m rag_pipelines.ingest --index-version 1 --dry-run   # không chạm DB, in 2496 chunk
uv run python -m rag_pipelines.ingest --index-version 1 --force
uv run python -m rag_pipelines.export_index --index-version 1
```

Lưu ý quan trọng (lệch giữa tài liệu): migration `init` đặt sẵn `active_index_version = 1`, mà `ingest` **từ chối** ghi version đang active nếu thiếu `--force`. Lần đầu index còn **rỗng** nên `--force` an toàn. Từ index thứ hai (`--index-version 2`) thì **không** dùng `--force`, ingest xong rồi mới đổi `app_config.active_index_version` (luật 5). Tài liệu (`CLAUDE.md`, plan) chưa nhắc `--force` cho lần đầu; trợ lý sẽ sửa ở Task 7.4.

Embedding 2496 chunk, lô 32 (khoảng 78 lần gọi): vài phút đến mười mấy phút. Đo kích thước trong SQL Editor của Supabase:

```sql
select pg_size_pretty(pg_total_relation_size('chunks')), pg_total_relation_size('chunks');
select count(*) from chunks where index_version = 1;   -- mong đợi 2496 (có thể lệch nếu YAML đổi ở F1)
select count(*) from articles where index_version = 1;
```

Phải **< 150 MB** (giới hạn trong plan). `export_index` ghi `eval/index/v1.parquet` cùng `v1.legal_docs.parquet`, `v1.articles.parquet`, `v1.legal_refs.parquet`. Nếu `v1.parquet` > 50 MB thì dùng Git LFS (nói trợ lý).

**Dấu hiệu thành công:** ingest in số chunk, số ref giữ lại (~1250) và "không phân giải"; 4 file parquet có trong `eval/index/`; kích thước bảng < 150 MB.

**Nếu lỗi:** `ActiveVersionError` (exit 2): thiếu `--force` lần đầu. 429 hoặc timeout khi embed: gateway hết hạn hoặc ngrok rớt, kiểm `https://<domain>/health`; ingest có retry 3 lần và idempotent nên chạy lại được. Lỗi `prepared statement` hoặc `for share`/`executemany` qua pooler: **chưa kiểm** (ledger Task 3.1); gửi traceback đầy đủ (đã che mật khẩu).

**Gửi lại cho trợ lý** (task 3.1): output cuối của ingest (số chunk/ref), kết quả 3 câu SQL ở trên (số byte, số dòng), danh sách file trong `eval/index/` kèm kích thước (`ls -l eval/index`). Trợ lý ghi vào STATS và tick.

### F4. Eval truy xuất thật và baseline (Task 3.4, cần Kaggle bật)

Cần Docker (Postgres local `pgvector`, cổng 54329; **không** chạm Supabase thật).

```bash
bash scripts/test-db.sh
for f in supabase/migrations/*.sql; do
  docker exec -i rag-pg psql -U postgres -v ON_ERROR_STOP=1 -q < "$f"
done
export LLM_BASE_URL=https://<NGROK_DOMAIN>
export LLM_API_KEY=<GATEWAY_API_KEY>
cd pipelines
uv run python -m rag_pipelines.eval.retrieval_eval \
  --index ../eval/index/v1.parquet --golden ../eval/golden/v1.jsonl \
  --modes fts,dense,hybrid,hybrid_rerank --split test --refresh-cache \
  --out ../eval/results/retrieval_v1.json --markdown ../eval/results/retrieval_v1.md
```

(Nếu máy bạn có sẵn `psql` thì dùng vòng lặp trong [runbook-eval.md](runbook-eval.md).) `--refresh-cache` gọi gateway để embed các câu hỏi golden và ghi `eval/cache/query_emb_AITeamVN-Vietnamese_Embedding.npy` cùng `.ids.json` (CI dùng để chạy gate mà không cần Kaggle). Chỉ báo số trên split **test** (80 câu).

Sau đó nhờ trợ lý tạo `eval/baselines/main.json` từ mode `hybrid` và kiểm tra gate chạy nghiêm ngặt (các artefact phải có đủ: baseline, 4 file index, hai file cache; thiếu một là CI **đỏ**, xem bootstrap rule trong [ci.md](ci.md)). Khi `eval/baselines/main.json` được commit, quy tắc bootstrap tự chuyển sang nghiêm ngặt.

**Dấu hiệu thành công:** bảng markdown có 4 dòng mode với `hit_rate@1`, `recall@5/10/20`, `mrr@10`, `ndcg@10`; `hybrid` >= `fts` và `dense` (nếu không, đó là phát hiện đáng ghi, đừng tự chỉnh số); các file `eval/cache/*` và `eval/results/retrieval_v1.*` tồn tại.

**Nếu lỗi:** `skip hybrid_rerank: LLM_BASE_URL chưa đặt hoặc gateway không sẵn sàng`: notebook chưa READY hoặc sai key. `ensure_local` từ chối DB: bạn trỏ nhầm DB không phải localhost (đừng dùng `--allow-remote` trên Supabase thật, lệnh này ghi đè và đổi active version). Lỗi "chạy --refresh-cache khi Kaggle bật": cache thiếu id (golden đã đổi sau F2).

**Gửi lại cho trợ lý** (task 3.4): dán nguyên `eval/results/retrieval_v1.md` (không bí mật), và báo đã chạy xong để trợ lý commit artefact. Nếu `hybrid` kém hơn kỳ vọng, gửi kèm 3 câu sai nặng nhất để trợ lý phân tích (không chỉnh trên split test; chỉnh τ và prompt trên split `dev`).

Xong F4 và chưa làm gì khác với Kaggle thì **Stop session**.

---

## Giai đoạn G: Deploy production (Task 6.3, 6.5)

Chỉ làm sau E (biết Services chạy hay phải dùng phương án dự phòng) và D, F3 (DB đã có dữ liệu). Đọc [deploy.md](deploy.md) mục "Checklist `[USER]`" và "Secrets và biến môi trường"; dưới đây là bản rút gọn theo thứ tự.

1. **Vercel env** (Project, Settings, Environment Variables, đặt cho cả **Production và Preview**; đánh Sensitive cho khóa/token, **trừ** `NEXT_PUBLIC_SITE_URL` và `API_ORIGIN` nếu có): `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `CRON_SECRET`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, và `NEXT_PUBLIC_SITE_URL=https://<tên miền production công khai>` (**bắt buộc**; lấy ở Project, Domains). **Không đặt `API_ORIGIN`** (nguy cơ vòng lặp rewrite, giải thích trong deploy.md). `LLM_BASE_URL` phải khớp regex ngrok.
2. Vercel, Deployment Protection: tạo **Protection Bypass for Automation**, lấy secret -> GitHub Secret `VERCEL_AUTOMATION_BYPASS_SECRET` (cấp repo).
3. GitHub, Settings, **Environments**, tạo `production`, Deployment branches = "Selected branches" chỉ `main`. Required reviewers tùy chọn (có thì phải duyệt **hai lần**: `migrate` rồi `deploy`; làm một mình thì bỏ trống).
4. GitHub Secrets **trong Environment `production`**: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF`. Cấp repo (Settings, Secrets and variables, Actions): `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_AUTOMATION_BYPASS_SECRET`, `CRON_SECRET` (cùng giá trị với Vercel).
5. Vercel, Project, Firewall, Custom Rules: một rule, Request Path bằng `/api/chat`, Rate Limit theo IP (gợi ý cửa sổ 60 s, 20 request, trả 429). Giới hạn số rule theo gói **chưa kiểm chứng**. Rule nằm trong dashboard, không nằm trong repo.
6. **Deploy lần đầu**: merge PR `feat/rag-v1` -> `main` (đây là lúc `push: main` chạy `deploy-prod`). Xem job `migrate` (nếu đã `db push` ở D thì dry-run báo "đã cập nhật"), rồi `deploy`, rồi smoke.
7. Đặt biến repository `PROD_URL` (Settings, Secrets and variables, **Variables**) = `https://<tên miền production>` (không đường dẫn, không `http://`). Chạy tay workflow `keepalive` (Actions, Run workflow).

**Dấu hiệu thành công:**

- Job `migrate` và `deploy` xanh; smoke `/api/health` trong log.
- `curl https://<production>/api/health` (nếu Deployment Protection chặn thì thêm header bypass) trả JSON có **`"db": "ok"`**. Khi Kaggle **tắt**, `"llm": "offline"` là **bình thường và đúng**.
- Mở trang chủ: badge trạng thái LLM màu đỏ (offline) và hỏi một câu vẫn ra kết quả FTS kèm nhãn ngoại tuyến. `/van-ban` render danh sách văn bản.
- `keepalive` chạy tay **xanh** (HTTP 204).

**Nếu lỗi:**

- `migrate` đỏ ở guard: gửi dòng log của guard (nó fail closed khi không nhận ra đầu ra dry-run, bước D4 đã chuẩn bị chuyện này).
- Smoke 401: thiếu `VERCEL_AUTOMATION_BYPASS_SECRET`.
- Workflow đỏ sớm "thiếu `API_ORIGIN` hoặc `NEXT_PUBLIC_SITE_URL`": biến chưa đặt cho đúng môi trường, hoặc bạn lỡ đánh Sensitive (không pull được).
- `/api/health` có `db: "down"`: sai `DATABASE_URL` (phải cổng 6543) hoặc pooler; kiểm tra `app_config` đã có dữ liệu.
- Production hỏng: Vercel, Deployments, bản trước, **Promote to Production** (rollback không cần chạy lại CI).
- Keepalive đỏ: log nói rõ thiếu secret/variable hay mã HTTP khác 204.

**Gửi lại cho trợ lý** (task 6.3, 6.5, 6.4 phần `PROD_URL`):

- URL production công khai (đã có `https://`).
- Output JSON của `/api/health` (không bí mật).
- Link run `ci` trên `main` và trạng thái `migrate` / `deploy` / smoke; log lỗi nếu đỏ.
- Link run `keepalive` (xanh hay đỏ).
- Ảnh chụp trang chủ với badge và một câu trả lời ngoại tuyến.
- Xác nhận đã làm: Environment `production` + giới hạn nhánh, WAF rule, `PROD_URL`, "Allow Actions to create PRs" (có/không từng mục).

---

## Giai đoạn H: Eval đầy đủ, Langfuse, A/B model, bằng chứng gate

Bật Kaggle ở đầu giai đoạn này (runbook-kaggle) và chờ `READY`, badge xanh trên production. Làm gọn trong một buổi, xong Stop session.

### H1. Langfuse thật (Task 7.1)

Làm theo checklist cuối [runbook-observability.md](runbook-observability.md) ("Kiểm thật lần đầu có LLM online"):

1. `LANGFUSE_*` đã đặt trên Vercel (Giai đoạn G). Hỏi **một cuộc hội thoại hai lượt** (lượt hai mới có `condense`).
2. Lấy `trace_id` từ part `data-trace` (DevTools, Network, response của `/api/chat`), tìm trên Langfuse: phải thấy **6 span** `condense`, `embed`, `hybrid_search`, `rerank`, `expand`, `llm`; span gốc `chat` có metadata `index_version`, `mode=rag`, `prompt_version=answer_v1`.
3. Tắt notebook, hỏi lượt đầu: chỉ còn `chat`, `hybrid_search`, `expand`, `mode=offline`.
4. Bấm 👍/👎: trace có score `user-feedback` (1 hoặc -1) và comment đã che số điện thoại. Gõ một số điện thoại vào câu hỏi: không thấy nó ở input/output của trace.
5. `LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... LANGFUSE_HOST=... python scripts/latency_report.py --days 1` (đặt biến trong shell, không dán chat): bảng có số liệu, `n` khớp số request vừa hỏi.

Điểm **chưa xác minh** (ghi trong runbook): metadata nằm ở span gốc `chat`, chưa biết có hiện ở khung metadata trace trên UI không; BackgroundTask flush trên Vercel; Langfuse Cloud gói Hobby có cho gọi API `v2/observations` không.

**Gửi lại cho trợ lý** (task 7.1): ảnh chụp trace (che nội dung nếu muốn) thấy đủ 6 span và metadata; ảnh trace offline; ảnh score feedback; bảng `latency_report` (dán markdown, không chứa khóa); ghi rõ mục nào không đạt. Trợ lý tick 7.1.

### H2. Eval trả lời đầy đủ (Task 6.4, `eval-full`)

1. Kiểm tra `curl <PROD_URL>/api/health` trả `"llm": "online"`. Workflow dừng nếu không.
2. Actions, workflow **eval-full**, Run workflow: `model_label` = `Qwen3-8B-Q5_K_M` (khớp `^[A-Za-z0-9._-]{1,40}$`, không dấu cách), `base_url` để trống (dùng `PROD_URL`). Chạy 80 câu giãn cách 31 s: khoảng **45 đến 60 phút** (giữ Kaggle bật suốt thời gian đó).
3. Kết quả: artifact và một PR tự động nhánh `eval/answers-<nhãn>-<ngày>` thêm `eval/results/answers_<nhãn>_<ngày>.json`.
4. **`ci-ok` không tự chạy trên PR đó** (GitHub không kích hoạt workflow từ PR tạo bằng `GITHUB_TOKEN`): đẩy một commit rỗng lên nhánh đó (`git fetch; git checkout eval/answers-...; git commit --allow-empty -m "ci: trigger"; git push`) hoặc đóng rồi mở lại PR, rồi merge.
5. Muốn tránh trần 20 lượt/10 phút và 300 lượt/ngày: chạy trên backend local (xem runbook-eval.md).

**Nếu lỗi:** exit 3 (429 hết lượt chờ, LLM chuyển offline giữa chừng, 5 câu liên tiếp lỗi): **không có file kết quả**, chạy lại từ đầu (không có chế độ tiếp tục); trần ngày thì chờ hôm sau hoặc chạy local. 403 khi mở PR: chưa bật "Allow GitHub Actions to create and approve pull requests". Chạy quá hạn mức: Kaggle session hết hạn giữa chừng.

**Gửi lại cho trợ lý** (task 6.4): link run và link PR; phần tóm tắt trong job summary (dán markdown: citation precision/recall, numeric_match, refusal_accuracy, injection_resisted, TTFT/total p50/p95, `n_failed`). Sau khi merge PR, nhờ trợ lý chạy `pnpm sync-eval` (cần cả `eval/results/retrieval_v1.json` từ F4) để cập nhật trang `/gioi-thieu`.

### H3. A/B model và ablation (Task 7.2, phần cần Kaggle)

Trợ lý viết trước phần không cần Kaggle (xem mục cuối); nhắn **"bắt đầu Task 7.2"** để biết bạn cần chạy gì. Phần của bạn:

- **Ablation truy xuất**: `index_version=2` ingest với `--no-breadcrumb` (cần trợ lý thêm cờ nếu chưa có), **không dùng `--force`**, **không** đổi `active_index_version` trên production. Chạy `retrieval_eval` cho `fts`, `dense`, `hybrid`, `hybrid_rerank` trên mỗi index rồi gửi bảng.
- **A/B LLM**: `Qwen3-8B Q5_K_M` (đã có) so với `Qwen3.5-9B Q4_K_M` và `AITeamVN/Vi-Qwen2-7B-RAG`. Trong notebook: đổi đường dẫn GGUF ở cell 3 (`-m /kaggle/input/<dataset>/<file>.gguf`), thêm dataset model tương ứng vào Input, giữ `-ngl 99 -c 16384 -np 2`, **kiểm cờ tắt thinking** (mô hình khác có thể cần cờ khác), rồi Run All. Chạy `eval-full` với `model_label` khác nhau (ví dụ `Qwen3.5-9B-Q4_K_M`). Ghi tok/s của từng model từ `llama-bench` hoặc `smoke_llm.py`. Sửa notebook thì chạy `python kaggle/build_notebook.py` rồi import lại bản mới.

**Gửi lại cho trợ lý**: các bảng retrieval theo cấu hình, link PR `eval-full` của từng model, tok/s mỗi model. Trợ lý viết `eval/results/ABLATION.md` (bảng và 3 đến 5 dòng phân tích lỗi theo loại câu hỏi), chọn cấu hình tốt nhất, cập nhật `baselines/main.json`.

### H4. Bằng chứng "gate chặn regression" (Task 6.2 mục cuối)

Cần baseline, index và cache đã commit và có trên `main` (F4 và G).

1. Nhờ trợ lý hoặc tự tạo nhánh `exp/drop-stopwords`: bỏ danh sách stopword trong `backend/app/retrieval/tsquery.py` (hoặc nơi trợ lý chỉ), push, mở PR vào `main`.
2. Chờ `eval-retrieval`. Kỳ vọng: sticky comment `eval-retrieval` hiện bảng chênh lệch, gate **đỏ** nếu `recall@10` hoặc `mrr@10` của `hybrid` tụt hơn 0.03 (tuyệt đối).
3. Chụp màn hình comment và tab Checks (đỏ). **Giữ nguyên PR** cho tới khi trợ lý lưu ảnh vào README, rồi đóng PR (không merge).

Nếu gate vẫn xanh: stopword không đủ ảnh hưởng, hỏi trợ lý đổi thay đổi cố ý làm hỏng khác (ví dụ giảm `rrf_k`).

**Gửi lại cho trợ lý**: link PR, ảnh chụp comment và checks. Trợ lý tick 6.2.

---

## Giai đoạn I: Tài sản demo (Task 7.3)

**Chưa làm được ngay.** `scripts/build_canned.py` và đường canned-answer ở backend chưa được viết (bảng `canned_answers` chưa có migration). Thứ tự:

1. Nhắn trợ lý **"bắt đầu Task 7.3"** (code `build_canned.py`, migration additive cho `canned_answers`, đường offline trả câu trả lời đã lưu với nhãn "Câu trả lời đã lưu từ phiên trực tuyến", test).
2. Khi trợ lý yêu cầu: **bật Kaggle** (READY), chạy `python scripts/build_canned.py` (6 câu gợi ý và 10 câu nổi bật, cần `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY` trong shell). Tắt Kaggle sau đó.
3. Quay video **60 đến 90 giây** trên production (Kaggle bật, badge xanh):
   - Câu lương tối thiểu vùng: đáp án khác nhau giữa 2026 (ND293) và 2027 (ND399), thể hiện chọn văn bản theo `as_of`.
   - Một câu BHTN nhiều bước (có trích dẫn, bấm trích dẫn thấy nguồn).
   - Một câu bị từ chối (ngoài phạm vi hoặc thiếu căn cứ).
   - Trang **Văn bản** (`/van-ban`).
4. Xuất GIF ngắn (< 10 MB, ~15 đến 25 giây, ví dụ 800 px rộng) cho README, và giữ video gốc làm video demo dự phòng nếu Kaggle bị khóa (rủi ro ToS trong `CLAUDE.md`).

**Gửi lại cho trợ lý** (task 7.3 `[USER]`): đường dẫn file GIF/video trong repo (đặt vào `docs/assets/`), hoặc link video; xác nhận canned chạy được khi Kaggle tắt (ảnh chụp câu trả lời đã lưu).

---

## Bảng gửi lại nhanh

| Mục plan còn mở | Việc của bạn | Gửi lại (không bí mật) | Trợ lý làm gì |
|---|---|---|---|
| 0.1 remote, 6.1 branch protection | A | link repo/PR, trạng thái Checks, xác nhận đã bật `ci-ok` | tick 0.1 remote và 6.1 |
| 0.1 tài khoản | B | "B xong", domain ngrok, region Supabase/Langfuse, mục bỏ qua | tick 0.1 |
| 0.2 | C1 | pp/tg tok/s, cờ `llama-server`, tên dataset | viết `docs/spikes.md#llama`, tick |
| 0.3 | C1 | số event/150, bị cắt/dồn cục, 401 không token | ghi spikes, tick (hoặc đề xuất đường thay) |
| 2.2 | C2 | thời gian tới `READY`, ảnh cell 8 | tick 2.2 |
| 2.3 | C3 | khối `RESULT smoke_llm` (TTFT p50, tok/s) | ghi `spikes.md#bench`, tick |
| 0.5 | D | `extversion`, thời gian `select 1`, tên migration, `app_config` | ghi spikes, tick; khớp `UP_TO_DATE` |
| 0.4 | E | kết quả `/`, `/api/ping`, `/api/sse`, path `/api`, header AI SDK, `--prebuilt` | viết `vercel.json`, spikes, ADR hoặc phương án dự phòng, cron 6.5 |
| 1.2 (ND145) | F1 | tình trạng vbpl.vn, có/không văn bản sửa đổi | sửa `legal_docs.yaml` |
| 3.3 `[USER]` | F2 | 20 giá trị `ok` + lý do cho dòng sai | cập nhật `DATASET_CARD.md`, tick |
| 3.1 (live) | F3 | output ingest, 3 câu SQL, `ls -l eval/index` | ghi STATS, tick |
| 3.4 (live) | F4 | `eval/results/retrieval_v1.md` | tạo `baselines/main.json`, commit, tick |
| 6.3, 6.5 (live) | G | URL prod, JSON `/api/health`, link run, ảnh badge | tick 6.3, 6.5 |
| 6.4 (live) | H2 | link run/PR, markdown tóm tắt | `pnpm sync-eval`, tick |
| 7.1 (live) | H1 | ảnh trace/score, bảng latency | tick 7.1 |
| 7.2 | H3 | bảng ablation, link PR theo model, tok/s | viết `ABLATION.md`, cập nhật baseline |
| 6.2 (cuối) | H4 | link PR, ảnh comment/Checks đỏ | lưu ảnh cho README, tick |
| 7.3 `[USER]` | I | file GIF/video, ảnh canned offline | tick 7.3 |

## Việc trợ lý sẽ làm tiếp (không cần bạn)

- **Task 7.2 (phần không cần Kaggle):** khung ablation (cờ `--no-breadcrumb` cho ingest nếu chưa có, script gom bảng, mẫu `ABLATION.md`).
- **Task 7.3 (code):** `scripts/build_canned.py`, migration additive cho `canned_answers`, đường canned-answer ở backend + test (mất LLM, câu khớp canned thì trả câu đã lưu kèm nhãn). Phần chạy thật cần Kaggle bật, trợ lý sẽ báo khi nào bạn bật.
- **Task 7.4 (tài liệu):** `README.md` (GIF, bảng số liệu, hướng dẫn chạy lại, giới hạn và rủi ro), ADR 0001 đến 0007 (`docs/adr/`), sửa lệch tài liệu đã gom lại (ví dụ `fetch_log.json`, tên `A1_...` trong plan/spec, `--force` lần ingest đầu, `curl -fsS` trong plan 6.5), kéo `pyright` baseline từ 65 về 0.
- **Rà soát cả nhánh lần cuối** (`requesting-code-review`): gom các minor trì hoãn trong ledger (ví dụ 413 thiếu `no-store`, double flush Langfuse khi ngắt kết nối, `isChatMessage` không kiểm từng part).
- **Task 8.1 (giao thông, tùy chọn):** chỉ làm nếu bạn muốn mở rộng corpus sau khi xong các phần trên.
- Mỗi khi bạn gửi kết quả: tick checkbox trong plan, cập nhật `docs/spikes.md`, sửa tài liệu bị lệch, và khi bạn yêu cầu thì commit (trên nhánh) và mở PR.
