# Kết quả spike (Phase 0 và benchmark)

Mỗi mục dưới đây do task tương ứng điền khi chạy thật. `TBD` nghĩa là **chưa có số đo**, không phải số ước lượng. Người chạy spike: dán khối kết quả vào đúng mục, đừng sửa số cho "đẹp".

| Mục | Task | Trạng thái |
|---|---|---|
| [#llama](#llama) | 0.2 | notebook đã viết, chưa chạy trên Kaggle |
| [#sse](#sse) | 0.3 | chưa chạy |
| [#vercel](#vercel) | 0.4 | chưa chạy |
| [#supabase](#supabase) | 0.5 | chưa chạy |
| [#bench](#bench) | 2.3 | chưa chạy |

---

<a id="llama"></a>

## llama: llama.cpp trên Kaggle T4 (sm_75), Task 0.2

**Mục đích.** Xác nhận llama.cpp build được cho T4 (compute capability 7.5), tạo hai Kaggle Dataset mà `kaggle/serve.ipynb` (Task 2.2) tiêu thụ, đo tốc độ Qwen3-8B và chốt tên các cờ `llama-server` đang được giả định.

**Notebook:** `kaggle/build_llamacpp.ipynb` (chạy một lần, không giữ phiên sống). Đã kiểm tra bằng test CPU (`kaggle/tests/test_build_llamacpp_notebook.py`): cú pháp, cờ cmake, hàm parse. **Chưa chạy trên Kaggle** nên mọi số bên dưới còn `TBD`.

**Đã tra cứu (2026-11-23), không phải số đo:**

- Tag llama.cpp `b12651` tồn tại, trỏ tới commit `f5e6915c28f10330885fcb9243a93ae98d3115ab` (GitHub API). Notebook ghim tag này (`LLAMA_CPP_REF`).
- `LLAMA_CURL` trong `CMakeLists.txt` hiện chỉ còn là cảnh báo deprecated (không còn `option`), và `LLAMA_OPENSSL` mặc định ON. Notebook không truyền `-DLLAMA_CURL=OFF`, mà truyền `-DLLAMA_OPENSSL=OFF`. (`kaggle/serve.ipynb` cell 2 vẫn truyền `-DLLAMA_CURL=OFF`: chỉ sinh cảnh báo khi build dự phòng, không lỗi.)
- Repo HF `Qwen/Qwen3-8B-GGUF` có cả `Qwen3-8B-Q5_K_M.gguf` (5,85 GB) và `Qwen3-8B-Q4_K_M.gguf` (5,03 GB). Bản `unsloth/Qwen3-8B-GGUF` cũng có hai file này; notebook chỉ dùng nó khi repo chính thức thiếu file.
- README `tools/server` của llama.cpp (master) ghi: `--jinja`, `-fa, --flash-attn [on|off|auto]` (mặc định `auto`), `--chat-template-kwargs STRING`, `--api-key KEY`, `--reasoning-budget N`, `-np, --parallel N`, `-c, --ctx-size N`, `--host`, `--port`. Đây là tài liệu của master, **chưa** phải `--help` của bản build trên Kaggle: bảng "Cờ" dưới đây vẫn `TBD`.

### Cách chạy (khớp [user-checklist.md](user-checklist.md) giai đoạn C1, bước 1 đến 6)

1. Kaggle: **New Notebook > File > Import Notebook**, chọn `kaggle/build_llamacpp.ipynb`. Settings: **Accelerator = GPU T4 x2**, **Internet = On**. Secret `HF_TOKEN` là tùy chọn (repo công khai); có thì tick "Attached".
2. **Run All**. Build mất khoảng 20 đến 30 phút, cell 4 không in gì giữa chừng. Notebook chạy xong là tự kết thúc.
3. Cell cuối in khối `RESULT`. Copy nguyên khối gửi cho trợ lý (hoặc dán vào bảng bên dưới).
4. **Save Version** và chọn **"Save & Run All (Commit)"**. Lưu ý chi phí: lựa chọn này **chạy lại toàn bộ notebook** trong một container mới (build khoảng 25 phút, tải khoảng 6 GB GGUF, rồi bench), tức là tốn thêm hạn mức GPU hằng tuần. Cần bước này vì chưa xác minh được phiên chạy tương tác (Run All) có để lại Output dùng được cho Dataset hay không. Notebook không có công tắc bỏ qua build, nên chỉ cần ghi nhận chi phí này; số đo dùng lần chạy nào cũng được (nên lấy khối `RESULT` của lần Commit, vì dataset cũng sinh từ đó). **Quick Save** có để lộ `/kaggle/working` thành Output hay không là **chưa xác minh**: đừng dựa vào nó. Tên nút và vị trí menu trên giao diện Kaggle trong mục này chưa xác minh (giao diện hay đổi): nếu khác, hãy làm theo ý nghĩa (lưu một phiên bản có Output).
5. Mở version vừa commit, tab **Output**, **New Dataset** để tạo hai Dataset private từ output (tên chính xác):
   - `llamacpp-sm75-bin` từ thư mục `llamacpp-sm75-bin/`
   - `qwen3-8b-gguf` từ thư mục `qwen3-8b-gguf/` (không chọn `qwen3-8b-gguf-q4-fallback/`, trừ khi Q5_K_M không đạt và bạn muốn dùng Q4_K_M)
   File `dataset-metadata.json` trong hai thư mục chỉ dùng nếu bạn upload bằng `kaggle datasets create -p <thư mục>`: khi đó thay `<KAGGLE_USERNAME>` bằng username Kaggle của bạn (placeholder này cố ý để trống, không commit username). Upload qua giao diện thì bỏ qua file đó.
6. **Stop session** (Session options > Stop session). Bật Kaggle chỉ trong lúc làm spike.

Bố cục dataset (đúng cái `serve.ipynb` tìm: `**/llama-server` dưới `/kaggle/input/llamacpp-sm75-bin`, và `**/*.gguf` dưới `/kaggle/input/qwen3-8b-gguf`):

```
llamacpp-sm75-bin/   llama-server, llama-bench, libllama*.so*, libggml*.so*, libmtmd*.so* (nếu có), MANIFEST.txt, dataset-metadata.json
qwen3-8b-gguf/       Qwen3-8B-Q5_K_M.gguf, dataset-metadata.json
```

Thư viện CUDA runtime (`libcudart`, `libcublas`...) không nằm trong dataset: image Kaggle có sẵn. `MANIFEST.txt` liệt kê chúng. Nếu serve.ipynb báo thiếu chúng, đặt `BUNDLE_CUDA_LIBS = True` ở cell 1 của notebook và chạy lại (dataset sẽ nặng hơn nhiều).

### Tiêu chí đạt

- Build xong, `llama-server --version` chạy được **từ thư mục đóng gói** với `LD_LIBRARY_PATH` trỏ vào đó (cell 5 tự kiểm tra bằng `ldd`, báo lỗi nếu thiếu `.so`).
- `llama-bench -m Qwen3-8B-Q5_K_M.gguf -ngl 99 -p 4096 -n 256` trên GPU 0: **tg >= 15 tok/s**. Không đạt (hoặc lỗi/OOM) thì notebook tự bench thêm `Q4_K_M`, ghi cả hai.
- Hai dataset private `llamacpp-sm75-bin` và `qwen3-8b-gguf` tồn tại.
- Mọi cờ ở bảng "Cờ cần xác nhận" có trong `--help`, hoặc đã ghi tên cờ đúng nếu khác.

### Kết quả (điền từ khối `RESULT`)

| Trường | Giá trị |
|---|---|
| Ngày chạy (UTC) | TBD — chờ chạy trên Kaggle |
| llama.cpp ref / commit | TBD — chờ chạy trên Kaggle (dự kiến `b12651` / `f5e6915c...`; giá trị thật in trong RESULT) |
| `llama-server --version` | TBD — chờ chạy trên Kaggle |
| CUDA toolkit | TBD — chờ chạy trên Kaggle |
| GPU (tên, VRAM, driver) | TBD — chờ chạy trên Kaggle |
| Thời gian build (phút) | TBD — chờ chạy trên Kaggle |
| Cần symlink `libcuda` stub? | TBD — chờ chạy trên Kaggle |
| Dung lượng `llamacpp-sm75-bin` (MB) | TBD — chờ chạy trên Kaggle |
| GGUF dùng (repo, MB) | TBD — chờ chạy trên Kaggle |
| Q5_K_M: pp4096 tok/s | TBD — chờ chạy trên Kaggle |
| Q5_K_M: tg256 tok/s | TBD — chờ chạy trên Kaggle |
| Q5_K_M đạt (tg >= 15)? | TBD — chờ chạy trên Kaggle |
| Q4_K_M: pp4096 / tg256 tok/s (chỉ khi Q5 không đạt) | TBD — chờ chạy trên Kaggle |
| Tên hai dataset đã tạo | TBD — chờ chạy trên Kaggle |

### Cờ cần xác nhận (`llama-server --help`)

Cột "giả định" là điều `kaggle/serve.ipynb` cell 3 hoặc plan đang dựa vào.

| Cờ | Giả định (nơi dùng) | Có trong `--help`? |
|---|---|---|
| `--jinja` | bật chat template Jinja, cần cho `--chat-template-kwargs` (serve cell 3) | TBD — chờ chạy trên Kaggle |
| `-fa` / `--flash-attn` | research note (`llm_serving_kaggle.md`) viết `-fa on`; README master ghi `-fa [on\|off\|auto]` (có giá trị), bản cũ là cờ không giá trị. Serve **chưa** dùng. Ghi lại dòng help chính xác | TBD — chờ chạy trên Kaggle |
| `--chat-template-kwargs` | `{"enable_thinking": false}` để tắt thinking của Qwen3 (serve cell 3) | TBD — chờ chạy trên Kaggle |
| `--api-key` | research note ví dụ `--api-key $LLM_KEY`; plan/serve **không** truyền cờ này (gateway đòi bearer, llama-server chỉ nghe 127.0.0.1) | TBD — chờ chạy trên Kaggle |
| `--reasoning-budget` | `--reasoning-budget 0` tắt thinking lớp thứ hai (serve cell 3) | TBD — chờ chạy trên Kaggle |
| `-np` | `-np 2` hai slot song song (serve cell 3) | TBD — chờ chạy trên Kaggle |
| `-c` | `-c 16384` (serve cell 3) | TBD — chờ chạy trên Kaggle |
| `--host`, `--port` | `127.0.0.1`, `8080` (serve cell 3) | TBD — chờ chạy trên Kaggle |

Nếu cờ nào "KHÔNG": ghi tên đúng ở đây, sửa `kaggle/gateway.py`/`kaggle/build_notebook.py` (cell 3), sinh lại `serve.ipynb`. Đừng sửa tay `serve.ipynb`.

### Nếu lỗi

- **Link lỗi `cannot find -lcuda`**: cell 4 tự tạo symlink stub (`/usr/local/cuda/lib64/stubs/libcuda.so`) rồi build lại, và in dòng `LINK FAILED on libcuda -> ...`. Stub chỉ dùng lúc build, không đóng gói. Vẫn lỗi thì gửi 60 dòng cuối cell in ra (log đầy đủ ở `/kaggle/working/build.log`).
- **Thiếu `.so` khi chạy** (`error while loading shared libraries`, hoặc cell 5 assert): mở `MANIFEST.txt`, so với `ldd` in ra ở cell 5. Thiếu lib nằm dưới `/usr/local/cuda` thì đặt `BUNDLE_CUDA_LIBS = True`.
- **OOM / bench lỗi**: cell 7 in 30 dòng cuối stderr và tự thử `Q4_K_M`. Bench chỉ dùng GPU 0 (`CUDA_VISIBLE_DEVICES=0`), GPU 1 dành cho embedder/reranker khi serve.
- **Repo HF không có file hoặc tải lỗi**: cell 6 tự thử `unsloth/Qwen3-8B-GGUF`. Thêm secret `HF_TOKEN` nếu bị giới hạn tốc độ.
- **Dataset**: nếu Kaggle không cho tạo dataset từ output, tải thư mục output về rồi **Datasets > New Dataset > Upload**, đặt đúng tên, **Private**.
- Chưa pin tag (đổi `LLAMA_CPP_REF` thành `"master"`): kết quả là UNPINNED, phải ghim lại commit in trong RESULT sau lần build thành công đầu tiên.

---

<a id="sse"></a>

## sse: gateway + ngrok + SSE 150 giây, Task 0.3

**Trạng thái: chưa chạy.** Kết quả: TBD — chờ chạy trên Kaggle.

Tiêu chí đạt (plan Task 0.3): `curl -N -H "Authorization: Bearer …" https://<domain>/stream` nhận đủ **150 event** (1 event/giây), không bị cắt, không bị buffer dồn cục. Request không có token trả **401**. Nếu ngrok cắt stream: ghi lại thời điểm, báo người dùng trước khi chọn phương án khác (ứng viên: Cloudflare named tunnel, cần domain riêng).

---

<a id="vercel"></a>

## vercel: Vercel Services + deploy từ Actions, Task 0.4

**Trạng thái: chưa chạy.** Kết quả: TBD — chờ chạy (cần project Vercel thật).

Tiêu chí đạt (plan Task 0.4): URL preview có `/` render Next.js, `/api/ping` trả `{"ok": true}`, `/api/sse` stream từng event (`curl -N`). Ghi thêm: FastAPI nhận path có `/api` hay đã bị cắt, chỗ đặt `maxDuration`, region `sin1` có nhận không, `--prebuilt` có hỗ trợ Services không (nếu không: Vercel Git integration + ADR), field AI SDK v7 (`source-url`, `data-*`, `error`, header `x-vercel-ai-ui-message-stream`).

---

<a id="supabase"></a>

## supabase: pgvector và kết nối pooler, Task 0.5

**Trạng thái: chưa chạy.** Kết quả: TBD — chờ chạy (cần project Supabase thật).

Tiêu chí đạt (plan Task 0.5): ghi `extversion` của `vector` (>= 0.8.0 thì có iterative scan); `select 1` qua psycopg (pooler 6543, `prepare_threshold=None`) từ `/api/ping` trả về **< 1 s** ở lần gọi nóng.

---

<a id="bench"></a>

## bench: smoke và benchmark LLM qua tunnel, Task 2.3

**Trạng thái: chưa chạy.** Kết quả: TBD — chờ gateway live qua tunnel (`scripts/smoke_llm.py` chưa viết).

Tiêu chí đạt (plan Task 2.3): **TTFT p50 < 3 s** qua tunnel (3 lần chat stream) và câu trả lời là tiếng Việt có dấu đúng; embed 2 câu ra 1024 chiều; rerank "lương tối thiểu vùng I" xếp đoạn liên quan lên đầu. Ghi cả tok/s.
