# Kết quả spike (Phase 0 và benchmark)

Mỗi mục dưới đây do task tương ứng điền khi chạy thật. `TBD` nghĩa là **chưa có số đo**, không phải số ước lượng. Người chạy spike: dán khối kết quả vào đúng mục, đừng sửa số cho "đẹp".

| Mục | Task | Trạng thái |
|---|---|---|
| [#llama](#llama) | 0.2 | build + bench xong 2026-11-27 (Q5_K_M tg 31,8 tok/s, đạt); còn tạo 2 dataset |
| [#sse](#sse) | 0.3 | code đã viết (`kaggle/spike_sse.py`, `scripts/spike_sse_check.py`), chưa chạy trên Kaggle |
| [#vercel](#vercel) | 0.4 | code đã viết (`vercel.json`, `backend/app/api/spike.py`, `spike-deploy.yml`, `scripts/spike_vercel_check.py`), chưa chạy với project Vercel thật |
| [#supabase](#supabase) | 0.5 | chưa chạy |
| [#bench](#bench) | 2.3 | code đã viết (`scripts/smoke_llm.py`), chưa chạy với gateway live |

---

<a id="llama"></a>

## llama: llama.cpp trên Kaggle T4 (sm_75), Task 0.2

**Mục đích.** Xác nhận llama.cpp build được cho T4 (compute capability 7.5), tạo hai Kaggle Dataset mà `kaggle/serve.ipynb` (Task 2.2) tiêu thụ, đo tốc độ Qwen3-8B và chốt tên các cờ `llama-server` đang được giả định.

**Notebook:** `kaggle/build_llamacpp.ipynb` (chạy một lần, không giữ phiên sống). Đã kiểm tra bằng test CPU (`kaggle/tests/test_build_llamacpp_notebook.py`): cú pháp, cờ cmake, hàm parse. Đã chạy thật trên Kaggle ngày 2026-11-27 (lần thứ 3), số liệu ở bảng bên dưới.

**Đã tra cứu (2026-11-23), không phải số đo:**

- Tag llama.cpp `b12651` tồn tại, trỏ tới commit `f5e6915c28f10330885fcb9243a93ae98d3115ab` (GitHub API). Notebook ghim tag này (`LLAMA_CPP_REF`).
- `LLAMA_CURL` trong `CMakeLists.txt` hiện chỉ còn là cảnh báo deprecated (không còn `option`), và `LLAMA_OPENSSL` mặc định ON. Notebook không truyền `-DLLAMA_CURL=OFF`, mà truyền `-DLLAMA_OPENSSL=OFF`. (`kaggle/serve.ipynb` cell 2 cũng đã đổi sang `-DLLAMA_OPENSSL=OFF` và dùng cùng cách tìm stub libcuda.)
- Repo HF `Qwen/Qwen3-8B-GGUF` có cả `Qwen3-8B-Q5_K_M.gguf` (5,85 GB) và `Qwen3-8B-Q4_K_M.gguf` (5,03 GB). Bản `unsloth/Qwen3-8B-GGUF` cũng có hai file này; notebook chỉ dùng nó khi repo chính thức thiếu file.
- README `tools/server` của llama.cpp (master) ghi: `--jinja`, `-fa, --flash-attn [on|off|auto]` (mặc định `auto`), `--chat-template-kwargs STRING`, `--api-key KEY`, `--reasoning-budget N`, `-np, --parallel N`, `-c, --ctx-size N`, `--host`, `--port`. Đây là tài liệu của master, **chưa** phải `--help` của bản build trên Kaggle: bảng "Cờ" dưới đây đã đối chiếu với `--help` thật (2026-11-27).

### Cách chạy (khớp [user-checklist.md](user-checklist.md) giai đoạn C1, bước 1 đến 6)

1. Kaggle: **New Notebook > File > Import Notebook**, chọn `kaggle/build_llamacpp.ipynb`. Settings: **Accelerator = GPU T4 x2**, **Internet = On**. Secret `HF_TOKEN` là tùy chọn (repo công khai); có thì tick "Attached".
2. **Run All**. Build mất khoảng 20 đến 30 phút, cell 4 không in gì giữa chừng. Notebook chạy xong là tự kết thúc.
3. Cell cuối in khối `RESULT`. Lần Run All tương tác này chỉ là smoke test: khối `RESULT` gửi lại cho trợ lý là khối in ra ở lần chạy **Commit (Save & Run All)** ở bước 4, không phải khối này.
4. **Save Version** và chọn **"Save & Run All (Commit)"**. Lưu ý chi phí: lựa chọn này **chạy lại toàn bộ notebook** trong một container mới (build khoảng 25 phút, tải khoảng 6 GB GGUF, rồi bench), tức là tốn thêm hạn mức GPU hằng tuần. Cần bước này vì chưa xác minh được phiên chạy tương tác (Run All) có để lại Output dùng được cho Dataset hay không. Notebook không có công tắc bỏ qua build, nên chỉ cần ghi nhận chi phí này; khối `RESULT` cần gửi lại là khối in trong log/output của lần **Commit (Save & Run All)** này (dataset cũng sinh từ lần chạy đó). **Quick Save** có để lộ `/kaggle/working` thành Output hay không là **chưa xác minh**: đừng dựa vào nó. Tên nút và vị trí menu trên giao diện Kaggle trong mục này chưa xác minh (giao diện hay đổi): nếu khác, hãy làm theo ý nghĩa (lưu một phiên bản có Output).
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
| Ngày chạy (UTC) | 2026-11-27 10:22 |
| llama.cpp ref / commit | `b12651` (ghim) / `f5e6915c28f10330885fcb9243a93ae98d3115ab` |
| `llama-server --version` | version: 1.0.0-dev (build 1, commit f5e6915), GNU 13.3.0, Linux x86_64 |
| CUDA toolkit | 13.0 (cmake 3.31.10) |
| GPU (tên, VRAM, driver) | 2 x Tesla T4, 15360 MiB, driver 580.178.04, cc 7.5 |
| Thời gian build (phút) | 34,5 (nproc=4) |
| `stub_dir`, `stub_file`, `configure_variant` (libcuda stub) | `/tmp/cuda-stub`, `/usr/local/cuda-13.0/compat/libcuda.so.580.126.20` (compat của toolkit), `cmake-library-path` |
| Dung lượng `llamacpp-sm75-bin` (MB) | 215 |
| GGUF dùng (repo, MB) | `Qwen/Qwen3-8B-GGUF`, `Qwen3-8B-Q5_K_M.gguf`, 5851 |
| Q5_K_M: pp4096 tok/s | 1063,6 |
| Q5_K_M: tg256 tok/s | 31,8 |
| Q5_K_M đạt (tg >= 15)? | ĐẠT |
| Q4_K_M: pp4096 / tg256 tok/s (chỉ khi Q5 không đạt) | không cần (Q5 đạt) |
| Tên hai dataset đã tạo | chờ chủ repo tạo từ tab Output (TBD) |

### Cờ cần xác nhận (`llama-server --help`)

Cột "giả định" là điều `kaggle/serve.ipynb` cell 3 hoặc plan đang dựa vào.

| Cờ | Giả định (nơi dùng) | Có trong `--help`? |
|---|---|---|
| `--jinja` | bật chat template Jinja, cần cho `--chat-template-kwargs` (serve cell 3) | CÓ (xác nhận 2026-11-27) |
| `-fa` / `--flash-attn` | research note (`llm_serving_kaggle.md`) viết `-fa on`; README master ghi `-fa [on\|off\|auto]` (có giá trị), bản cũ là cờ không giá trị. Serve **chưa** dùng. Ghi lại dòng help chính xác | CÓ (xác nhận 2026-11-27) |
| `--chat-template-kwargs` | `{"enable_thinking": false}` để tắt thinking của Qwen3 (serve cell 3) | CÓ (xác nhận 2026-11-27) |
| `--api-key` | research note ví dụ `--api-key $LLM_KEY`; plan/serve **không** truyền cờ này (gateway đòi bearer, llama-server chỉ nghe 127.0.0.1) | CÓ (xác nhận 2026-11-27) |
| `--reasoning-budget` | `--reasoning-budget 0` tắt thinking lớp thứ hai (serve cell 3) | CÓ (xác nhận 2026-11-27) |
| `-np` | `-np 2` hai slot song song (serve cell 3) | CÓ (xác nhận 2026-11-27) |
| `-c` | `-c 16384` (serve cell 3) | CÓ (xác nhận 2026-11-27) |
| `--host`, `--port` | `127.0.0.1`, `8080` (serve cell 3) | CÓ (xác nhận 2026-11-27) |

Nếu cờ nào "KHÔNG": ghi tên đúng ở đây, sửa `kaggle/gateway.py`/`kaggle/build_notebook.py` (cell 3), sinh lại `serve.ipynb`. Đừng sửa tay `serve.ipynb`.

### Nếu lỗi

- **Configure lỗi `Target "ggml-cuda" links to: CUDA::cuda_driver but the target was not found`** (gặp ở lần chạy đầu: llama.cpp `b12651`, GCC 13.3.0, CUDA 13.0.88, `CMAKE_CUDA_ARCHITECTURES=75` được nhận là `75-real`): FindCUDAToolkit không thấy stub `libcuda`. Image CUDA 13 để stub ở `/usr/local/cuda/targets/x86_64-linux/lib/stubs/libcuda.so` (CUDA 12: `lib64/stubs`). Cell 4 giờ **tìm stub trước khi configure** (`/usr/local/cuda*/**/stubs/libcuda.so*`), in ra những gì tìm thấy (không thấy thì in nội dung các thư mục CUDA để biết bố cục), tạo thư mục riêng chứa symlink `libcuda.so`/`libcuda.so.1`, **luôn** truyền `-DCMAKE_LIBRARY_PATH=<stub_dir>` khi configure, và đặt `LIBRARY_PATH`/`LD_LIBRARY_PATH` chỉ cho tiến trình build. Nếu configure vẫn báo `cuda_driver`, thử lại một lần với `-DCUDAToolkit_ROOT`, `-DCUDA_cuda_driver_LIBRARY`, `-DCUDA_DRIVER_LIBRARY` trỏ thẳng tới file stub (tên biến khác nhau giữa các bản CMake, nên đặt cả hai). Lỗi configure không còn làm cell dừng trước khi thử lại; thất bại cuối cùng in 60 dòng cuối, phiên bản cmake và danh sách stub. Stub không được vào `LD_LIBRARY_PATH` lúc chạy hay vào gói (cell 5 assert nếu `ldd` thấy đường dẫn `stubs`). **Chưa chạy trên Kaggle**, chờ chủ repo chạy lại.
- **Lần chạy thứ hai vẫn lỗi `CUDA::cuda_driver`, `libcuda stubs found: none`** (cmake 3.31.10, CUDA 13.0.88): image không có `stubs/libcuda.so` đâu cả, và có thể phiên chưa bật GPU. Cell 2 giờ chạy `nvidia-smi -L` **đầu tiên**; không thấy GPU thì dừng ngay với "Notebook chưa bật GPU: Session options → Accelerator = GPU T4 x2, rồi Run All lại", và luôn in `ldconfig -p | grep -i libcuda` (cho biết thư viện driver thật nằm đâu). Cell 4 tìm libcuda theo thứ tự (a) `stubs/libcuda.so*`, (b) `/usr/local/cuda*/compat/libcuda.so*`, (c) `ldconfig -p`, (d) `find` giới hạn ở `/usr/lib /usr/lib64 /lib /usr/local/nvidia /opt` (timeout 30 s), in mọi ứng viên, dùng cái đầu tiên. Link với thư viện driver thật hoặc compat lúc build là được (binary tìm `libcuda.so.1` động lúc chạy); chỉ đường dẫn có `stubs` hoặc thư mục stub riêng mới bị coi là rò rỉ. Không thấy gì: in `find / -xdev -name 'libcuda*'` (tối đa 30 dòng) rồi báo lỗi "không tìm thấy libcuda"; dán các dòng đó. **Chưa chạy trên Kaggle.**
- **Link lỗi `cannot find -lcuda`**: stub nói ở trên cũng đi vào `LIBRARY_PATH` lúc build. Vẫn lỗi thì gửi 60 dòng cuối cell in ra (log đầy đủ ở `/kaggle/working/build.log`).
- **Thiếu `.so` khi chạy** (`error while loading shared libraries`, hoặc cell 5 assert): mở `MANIFEST.txt`, so với `ldd` in ra ở cell 5. Thiếu lib nằm dưới `/usr/local/cuda` thì đặt `BUNDLE_CUDA_LIBS = True`.
- **OOM / bench lỗi**: cell 7 in 30 dòng cuối stderr và tự thử `Q4_K_M`. Bench chỉ dùng GPU 0 (`CUDA_VISIBLE_DEVICES=0`), GPU 1 dành cho embedder/reranker khi serve.
- **Repo HF không có file hoặc tải lỗi**: cell 6 tự thử `unsloth/Qwen3-8B-GGUF`. Thêm secret `HF_TOKEN` nếu bị giới hạn tốc độ.
- **Dataset**: nếu Kaggle không cho tạo dataset từ output, tải thư mục output về rồi **Datasets > New Dataset > Upload**, đặt đúng tên, **Private**.
- Chưa pin tag (đổi `LLAMA_CPP_REF` thành `"master"`): kết quả là UNPINNED, phải ghim lại commit in trong RESULT sau lần build thành công đầu tiên.

---

<a id="sse"></a>

## sse: gateway + ngrok + SSE 150 giây, Task 0.3

**Trạng thái: code đã viết, chưa chạy trên Kaggle.** Mọi số bên dưới còn `TBD — chờ chạy`.

**Gồm:** `kaggle/spike_sse.py` (server FastAPI tối giản + launcher; **xóa sau spike**) và `scripts/spike_sse_check.py` (checker chạy trên máy bạn, chỉ dùng thư viện chuẩn). Test: `kaggle/tests/test_spike_sse.py` (server), `pipelines/tests/test_spike_sse_check.py` (checker, theo tiền lệ `test_migration_guard.py`). Đã chạy thử cục bộ với `--no-tunnel` (10 event x 0,2 s: PASS); **chưa chạy qua ngrok thật**.

Server: `GET /stream` đòi bearer (sai hoặc thiếu: 401 JSON `{"detail": ...}`), phát 150 event, mỗi giây 1 event (`id: n` + `data: {"n": n, "t": <epoch>}`), kết thúc bằng `event: done`. `GET /health` không cần token. Launcher mở tunnel đúng như `serve.ipynb` cell 7 (`pyngrok`: `ngrok.set_auth_token(...)`, `ngrok.connect(port, "http", domain=NGROK_DOMAIN)`), in `READY https://<domain>`, tự thoát sau `--duration-min` (mặc định 10, tối đa 30), không có vòng giữ sống. Dừng sớm bằng Ctrl-C hoặc Stop session.

### Cách chạy

**Kaggle** (notebook mới, Internet **On**, không cần GPU; Add-ons > Secrets thêm 3 secret `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` (không kèm `https://`), `GATEWAY_API_KEY`, tick "Attached"). Dùng đúng domain và key của production để spike thử đúng thứ sẽ chạy thật. Tắt notebook `serve` nếu đang chạy (một domain chỉ giữ được một tunnel).

Cell 1 (cần repo đã push công khai, xem [user-checklist.md](user-checklist.md) giai đoạn A):

```python
!git clone -b feat/rag-v1 --depth 1 https://github.com/<TÀI-KHOẢN>/vn-labor-law-rag  # đến khi merge vào main (main không có kaggle/)
!pip install -q pyngrok==7.2.3 fastapi==0.115.6 uvicorn==0.34.0
```

Chưa push repo: tải `kaggle/spike_sse.py` lên làm Dataset rồi `!cp /kaggle/input/<dataset>/spike_sse.py .`, hoặc dán nội dung file vào một cell bắt đầu bằng `%%writefile spike_sse.py` (rồi dùng `spike_sse.py` thay cho đường dẫn ở cell 2).

Cell 2:

```python
!python vn-labor-law-rag/kaggle/spike_sse.py --duration-min 10
```

Chờ dòng `READY https://<domain>` rồi sang máy bạn. Launcher tự thoát sau 10 phút (in `STOPPED`). Xong thì **Stop session**.

**Máy bạn** (Git Bash; PowerShell: `$env:GATEWAY_API_KEY="..."`). Đặt key trong shell, đừng dán vào chat:

```bash
export GATEWAY_API_KEY=<GATEWAY_API_KEY>
python scripts/spike_sse_check.py --url https://<NGROK_DOMAIN>/stream --token-env GATEWAY_API_KEY --expect 150
```

Mất khoảng 2,5 phút. Mã thoát: 0 PASS, 1 FAIL, 2 lỗi dùng/kết nối. Script in khối `=== RESULT spike_sse ===` (đã che nhãn đầu của domain, không in token): dán nguyên khối đó vào chat và vào bảng dưới. Thử cục bộ không cần Kaggle: `python kaggle/spike_sse.py --no-tunnel --count 10 --interval 0.2 --port 8765` (cần `fastapi`, `uvicorn`, `GATEWAY_API_KEY` trong env), rồi `python scripts/spike_sse_check.py --url http://127.0.0.1:8765/stream --token-env GATEWAY_API_KEY --expect 10 --interval 0.2`.

Tùy chọn: `curl -N -H "Authorization: Bearer $GATEWAY_API_KEY" https://<NGROK_DOMAIN>/stream` để tận mắt thấy event chạy từng giây. Đừng dán URL đầy đủ ở nơi công khai: nó là domain production.

### Tiêu chí đạt (plan Task 0.3)

Checker in `PASS` khi **tất cả** đúng:

- Request không có token và request token sai đều trả **401**.
- Stream HTTP 200, `content-type: text/event-stream` (không phải trang HTML cảnh báo của ngrok).
- Nhận đủ **150 event** theo thứ tự `n = 1..150`, không hụt số, có `event: done` (không bị cắt sớm).
- Không dồn cục: p95 khoảng cách giữa hai event nằm trong **[0,5 s; 2 s]** (interval server 1 s), không quá **3** event đến cách event trước **< 50 ms**, khoảng cách dài nhất **<= 5 s**. Ngưỡng là hằng số đặt tên ở đầu `scripts/spike_sse_check.py`; nếu bạn thấy ngưỡng sai, nói trước khi sửa, đừng nới ngưỡng để "đạt".

### Kết quả (điền từ khối `RESULT`)

| Trường | Giá trị |
|---|---|
| Ngày chạy (UTC) | TBD — chờ chạy |
| `verdict` | TBD — chờ chạy |
| `no_token_status` / `wrong_token_status` | TBD — chờ chạy |
| `stream_http_status` | TBD — chờ chạy |
| `headers` (content-type, cache-control, x-accel-buffering, transfer-encoding, server, header `ngrok-*`) | TBD — chờ chạy |
| `events` (x/150), `done_event`, `cut` | TBD — chờ chạy |
| `wall_time_s` | TBD — chờ chạy |
| inter-arrival min / median / p95 / max (longest gap), giây | TBD — chờ chạy |
| `clumped_events` | TBD — chờ chạy |
| Thời điểm bị cắt (nếu có), tính từ event đầu | TBD — chờ chạy |

### Đã tra cứu (2026-11-23), không phải số đo

- Trang giới hạn gói free của ngrok: interstitial hiện "in front of all HTML browser traffic on the free tier", không ảnh hưởng client lập trình, bỏ qua được bằng header `ngrok-skip-browser-warning` hoặc `User-Agent` tùy biến. Checker gửi cả hai. Domain `.ngrok-free.dev` là gói free, nên nếu `content-type` trả về `text/html` thì đây là nghi phạm đầu tiên.
- Cùng trang: free **1 GB/tháng** data transfer out; "Free endpoints have no timeout—they can stay online indefinitely". Trang **không** nêu giới hạn thời lượng hay idle timeout của một request HTTP, nên việc 150 s có bị cắt hay không **chưa xác minh** (đó là mục tiêu của spike). 150 event nhỏ chỉ vài chục KB, không đáng kể so với 1 GB.
- `ERR_NGROK_334`: "The endpoint <URL> is already online" (domain đang được tunnel khác giữ).
- `ERR_NGROK_4018`: "ngrok requires an account and a valid credential to start a session" (thiếu hoặc sai authtoken).
- `ERR_NGROK_105`: authtoken không đúng định dạng (theo kết quả tìm kiếm trên trang tham chiếu lỗi ngrok, chưa mở trang gốc).
- Mã lỗi khi hết băng thông 1 GB: **chưa xác minh** (trang không nêu).

### Nếu ngrok cắt stream

1. **Ghi lại** (không sửa số): khối `RESULT` đầy đủ, số event nhận được, dòng `cut:` do checker in, giây thứ mấy bị cắt, và log cell Kaggle (launcher có in lỗi không).
2. Chạy lại một lần để phân biệt lỗi ngẫu nhiên và lỗi hệ thống.
3. **Dừng và báo người dùng** kèm số liệu. **Không** tự chuyển sang Cloudflare named tunnel (cần domain riêng, đổi regex SSRF của `LLM_BASE_URL`, đổi kiến trúc): plan yêu cầu báo trước khi chọn phương án khác. Ứng viên để bàn: Cloudflare named tunnel.
4. Nếu **dồn cục** (đủ event nhưng đến cùng lúc, `clumped_events` cao): cũng ghi và báo; thử thêm `curl -N` để loại trừ lỗi checker.

### Nếu lỗi

- `ERR_NGROK_334` / "domain already in use" lúc launcher mở tunnel: phiên cũ (notebook `serve` hoặc phiên spike trước) vẫn giữ domain. Stop session cũ hoặc đóng endpoint ở dashboard ngrok (Endpoints), rồi chạy lại.
- Launcher in `ngrok setup failed: <TênLỗi> [ERR_NGROK_nnn]` rồi thoát mã 3: chỉ in tên lỗi và mã (authtoken bị loại khỏi log). Mã `ERR_NGROK_...` ở dòng này đối chiếu với các mục dưới.
- `ERR_NGROK_4018` hoặc `ERR_NGROK_105`: sai `NGROK_AUTHTOKEN` (copy thiếu ký tự, hoặc secret chưa tick "Attached").
- Launcher in `... missing (env var or Kaggle Secret)`: chưa Add hoặc chưa Attach secret nào đó. Giá trị không bao giờ được in.
- `server failed to start (port busy?)`: đổi `--port`.
- Checker thoát mã 2 (`cannot connect`): launcher chưa `READY`, sai domain, hoặc notebook đã tự thoát (sau 10 phút). `no_token_status` là 200 thay vì 401: bạn đang trỏ tới server khác hoặc code bị sửa; đừng bỏ qua.
- Checker báo `content-type 'text/html'`: trang cảnh báo ngrok (xem phần tra cứu), hoặc URL thiếu `/stream`.
- Hết băng thông hoặc mã lỗi ngrok khác: **chưa xác minh** mã nào; gửi nguyên văn mã `ERR_NGROK_...` trong response.

---

<a id="vercel"></a>

## vercel: Vercel Services + deploy từ Actions, Task 0.4

**Trạng thái: code đã viết, chưa chạy trên Vercel.** Máy viết code không có tài khoản hay project Vercel, nên mọi dòng "Kết quả" bên dưới còn `TBD — chờ chạy`. Đã chạy cục bộ: test backend (`backend/tests/api/test_spike.py`), test checker (`pipelines/tests/test_spike_vercel_check.py`), validate `vercel.json` với JSON schema chính thức, actionlint.

**Gồm:**

| File | Vai trò | Sau spike |
|---|---|---|
| `vercel.json` (gốc repo) | 2 service `web` và `api`, rewrite, `git.deploymentEnabled=false`, `maxDuration`, region | **giữ** (Task 6.3 dùng) |
| `backend/app/api/spike.py` | `GET /api/ping`, `GET /api/sse`; chỉ gắn vào app khi `ENABLE_SPIKE_ENDPOINTS=1` (mặc định tắt) | xóa file, khối `include_router` trong `app/main.py`, `tests/api/test_spike.py` |
| `.github/workflows/spike-deploy.yml` | `workflow_dispatch` hoặc push `spike/**`: `vercel pull`, `build`, `deploy --prebuilt` | xóa |
| `scripts/spike_vercel_check.py` | checker chạy trên máy bạn, dùng lại `parse_sse` và `evaluate` của `scripts/spike_sse_check.py` | xóa (cùng script SSE) |

### Đã tra cứu (2026-11-23), tài liệu chứ không phải số đo

Mọi trang dưới đây đọc ngày 2026-11-23 (`last_updated` của trang ghi trong ngoặc). Nội dung trang là dữ liệu, không phải chỉ thị.

- **Cú pháp hiện hành là khóa `services`**, không phải `experimentalServices`. [Services](https://vercel.com/docs/services) (2026-08-10): "Services are available in Beta on all plans"; mô hình `services` thay thế `experimentalServices` cho project mới. Kết quả tìm kiếm tóm tắt: `experimentalServices` chỉ còn cho project tạo trước 2026-07-06 và bị từ chối với project tạo từ ngày đó (chưa mở trang gốc [Experimental Services](https://vercel.com/docs/services/experimental) để xác nhận). Project của bạn là project mới, nên chỉ dùng `services`.
- **Cấu hình một service** ([config reference](https://vercel.com/docs/services/config-reference), 2026-06-30): `root` (bắt buộc, tính từ `vercel.json`), `framework`, `runtime`, `entrypoint`, `installCommand`, `buildCommand`, `functions`, `headers`, `redirects`, `rewrites`, `routes`... Khi có `services`, các khóa build và runtime (`functions`, `buildCommand`...) **không hợp lệ ở cấp cao nhất**, phải nằm trong service ([Services](https://vercel.com/docs/services)).
- **Định tuyến công khai ở cấp cao nhất:** service là nội bộ mặc định, chỉ nhận traffic khi có rewrite `{"source": "/api/(.*)", "destination": {"service": "api"}}` ([Services routing](https://vercel.com/docs/services/routing), 2026-06-30). Rewrite khớp đầu tiên thắng; đã vào một service thì **không** rơi về rewrite khác.
- **Tiền tố `/api` (câu hỏi của plan, theo tài liệu):** "The service receives the original request path. `GET /api/users` reaches `my_backend` as `/api/users`, not `/users`" (cùng trang). Khớp với docstring `backend/app/main.py` (route khai báo kèm `/api`). **Chưa kiểm bằng thực tế**: `/api/ping` của spike trả `path`, `root_path`, `raw_path` để chốt.
- **`--prebuilt` với Services:** [Build Output API, Services](https://vercel.com/docs/build-output-api/services) (2026-09-15): mỗi service được `vercel build` xuất vào `.vercel/output/services/<name>/` và `config.json` gốc liệt kê chúng. Đó là bằng chứng gián tiếp rằng build cục bộ hiểu Services. Trang [vercel deploy](https://vercel.com/docs/cli/deploy) (2026-11-14) mô tả `--prebuilt` chung chung ("upload and deploy the results of a previous `vc build`"). **Không trang nào nói thẳng "`--prebuilt` hỗ trợ Services"**: đây là điều spike phải trả lời.
- **Ràng buộc Services** (trang Build Output API): không Middleware trong service, không Edge runtime, tối đa 100 service, tên service chỉ gồm chữ thường, `-`, `_`. Frontend của repo không có `middleware` hay `proxy` (đã kiểm `frontend/` và `frontend/src/`).
- **FastAPI** ([FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), 2026-11-14; [Python runtime](https://vercel.com/docs/functions/runtimes/python), 2026-08-12): entrypoint tự nhận gồm `app/main.py` (biến `app`) hoặc `tool.vercel.entrypoint` trong `pyproject.toml`; trong `services`, `entrypoint` là `module:variable` như `app.main:app`. Phụ thuộc: "`pyproject.toml` (with or without a `uv.lock`), `requirements.txt`, or a `Pipfile`", nên **không cần `requirements.txt`** vì `backend/` có `pyproject.toml` và `uv.lock`. Python mặc định 3.12 (khớp `requires-python = ">=3.12,<3.13"`). Bundle chuẩn tối đa 500 MB. Streaming bằng `StreamingResponse` được hỗ trợ.
- **`maxDuration` và region:** [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi): cấu hình hàm bằng `functions` trong `vercel.json`, **khóa là file entrypoint đã resolve** (`"app/main.py": {"maxDuration": 60}`). [vercel.json](https://vercel.com/docs/project-configuration/vercel-json): `regions` cấp cao nhất (mặc định `iad1`) hoặc `regions` ngay trong từng mục `functions`. Cách đặt trong service (`services.api.functions`) suy ra từ config reference (`functions` nằm trong service) và JSON schema; **chưa có ví dụ chính thức**, và chưa rõ khóa glob tính từ `root` của service (`app/main.py`) hay từ gốc repo (`backend/app/main.py`).
- **Cron:** `crons` là khóa cấp cao nhất trong [vercel.json](https://vercel.com/docs/project-configuration/vercel-json) và schema; [Cron Jobs](https://vercel.com/docs/schedules/cron-jobs) (2026-09-16) gọi `GET` vào URL production với `path`, và ghi cron là tính năng cũ sẽ chuyển sang "Schedules". Không trang nào nói cron có chạy ở chế độ Services hay không. **Vì vậy `vercel.json` chưa có `crons`** (xem dưới).
- **CLI trong CI:** [Global options](https://vercel.com/docs/cli/global-options) (2026-11-14): `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` đọc từ env, khuyến nghị cho CI vì không lộ token trong argv. [deploy](https://vercel.com/docs/cli/deploy): stdout của `vercel deploy` là URL deployment; `--env KEY=VALUE` đặt env **lúc chạy**, `--build-env` đặt env lúc build; với `--prebuilt` thì System Environment Variables không có lúc build.
- **Deployment Protection:** [Protection Bypass for Automation](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation) (2026-09-16): header (hoặc query) `x-vercel-protection-bypass: <secret>`; secret cũng có trong env `VERCEL_AUTOMATION_BYPASS_SECRET` của deployment.
- **`x-vercel-id`:** [Response headers](https://vercel.com/docs/headers/response-headers) (2026-08-11) chỉ nói header chứa danh sách region mà request đi qua cùng region function chạy. **Định dạng chính xác không được tài liệu hóa.** Checker tách theo `::` và lấy các mã dạng `syd1`, **luôn in kèm giá trị gốc**; đọc bằng mắt, đừng tin phần tách.
- **Dự phòng (không cần nếu spike đạt):** nếu Services không biểu diễn được thì dùng hai project riêng, hoặc Next.js `rewrites` tới Python Function gốc. Tài liệu hiện có Services nên đã chọn Services.

**JSON schema.** Schema chính thức `https://openapi.vercel.sh/vercel.json` (Draft-04, tải 2026-11-23) **có** `services` (đánh dấu `private: true`; mỗi service: `root` bắt buộc, `framework`, `runtime`, `entrypoint`, `functions`, `headers`, `rewrites`...), `rewrites[].destination` dạng `{"service": ...}`, `git.deploymentEnabled`, `crons`, `regions`; `experimentalServices` vẫn còn. `vercel.json` hiện tại **hợp lệ** theo schema (`uv run --no-project --with jsonschema`; đối chứng âm: thêm khóa lạ vào service, hoặc `maxDuration: 0`, đều bị từ chối). Schema **không** kiểm: khóa `functions` trong service tính từ đâu, region có được nhận khi `--prebuilt`, service có build được trên runner, và ngữ nghĩa lúc chạy nói chung.

### Cấu trúc đã chọn

`vercel.json` ở gốc repo (khóa `services`, **không** dùng `experimentalServices`):

- `web`: `root: "frontend/"`, `framework: "nextjs"`.
- `api`: `root: "backend/"`, `framework: "fastapi"`, `entrypoint: "app.main:app"`, `functions: {"app/main.py": {"maxDuration": 120, "regions": ["syd1"]}}`.
- `rewrites`: `/api/(.*)` sang service `api`; `/(.*)` sang service `web`.
- `git.deploymentEnabled: false` (tắt Git integration; deploy từ Actions).

Lý do: (1) Services là cách tài liệu hiện hành mô tả Next.js + FastAPI trong một project, một domain; (2) `maxDuration: 120` khớp luật của repo (function dừng ở 120 s): ngân sách tổng `CHAT_BUDGET_S = 100` cộng 20 s dư cho khởi động và đóng stream, vẫn dưới trần 300 s của spec; (3) region `syd1` được thử đặt riêng cho `api` vì Supabase ở `ap-southeast-2`, còn `web` ở region mặc định của project (`iad1` với project mới). **Có thể không hợp lệ trên Hobby**: gói này chỉ cho một region ([Configuring regions](https://vercel.com/docs/functions/configuring-functions/region), 2026-08-11: "Hobby: Single region"; deploy quá số region của gói thì lỗi trước bước build), nên hai service ở hai region có thể làm deploy lỗi, hoặc một service chạy sai region. Tài liệu không chứng minh hình dạng hiện tại là sai, nên `vercel.json` giữ nguyên và hai biến thể được thử trong cùng một lần spike (xem cây quyết định). Nếu thật sự chỉ một region: các trang Next SSR như `/van-ban` cũng chạy ở region đó và gọi API qua URL công khai; đo ở lần chạy thật; (4) `api` thuần Python, không `torch` (luật 2). Production **không** đặt `API_ORIGIN` (rewrite `/api` của `next.config` chỉ bật khi có biến này hoặc `next dev`); đừng đặt nó cho Preview của spike.

**Chưa có `crons`.** Tài liệu không nói cron cấp cao nhất có chạy với Services hay không, nên không thêm. Snippet và quy trình ở [deploy.md](deploy.md) mục Keep-alive giữ nguyên. Nếu spike đạt: thêm snippet đó, deploy lại và xem Project, Settings, Cron Jobs có hiện job không; không hiện thì chỉ dựa vào GitHub schedule và ghi vào đây.

### Điều chưa xác minh (spike phải trả lời)

1. `vercel build` và `vercel deploy --prebuilt` với Services chạy được trên runner Ubuntu (cần Python hoặc `uv` trên runner?).
2. `services.api.functions["app/main.py"]` có khớp hàm không (hay phải là `backend/app/main.py`), `maxDuration` và `regions` có được áp (dashboard, Deployment, Functions).
3. Project có cần Framework Preset "Services" không (một guide của Vercel nhắc `vercel project update --framework services`, trang đó không nói rõ khi nào cần). Nếu `vercel pull` hoặc `build` báo thiếu preset thì chạy lệnh đó hoặc đặt trong Project Settings.
4. `vercel deploy --env ENABLE_SPIKE_ENDPOINTS=1` có tới runtime của service khi dùng `--prebuilt`. Không tới thì `/api/ping` trả 404 JSON (checker nhận ra: "FastAPI trả lời nhưng không có route"); khi đó đặt biến cho Preview trong dashboard rồi chạy lại.
5. Định dạng `x-vercel-id` và chỗ nó cho biết region của function.
6. Cron ở chế độ Services (xem trên).
7. **Hobby chỉ cho một region** ([Configuring regions](https://vercel.com/docs/functions/configuring-functions/region), 2026-08-11): `api` ghim `syd1` theo từng hàm còn `web` ở mặc định `iad1` thì deploy có thể lỗi vì số region, hoặc một service chạy sai region. Chưa rõ Vercel đếm region thế nào khi có `services`.

### Cách chạy (khớp [user-checklist.md](user-checklist.md) giai đoạn E)

1. `npm i -g vercel@66.6.0`, `vercel login`, `vercel link` trong thư mục repo (project mới). Lấy `orgId`, `projectId` từ `.vercel/project.json`.
2. GitHub, Settings, Secrets and variables, Actions (cấp repo): `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`. Không dán giá trị vào chat.
3. Tùy chọn: Vercel, Project, Deployment Protection, tạo Protection Bypass for Automation; trên máy bạn `export VERCEL_AUTOMATION_BYPASS_SECRET=...` (PowerShell: `$env:VERCEL_AUTOMATION_BYPASS_SECRET="..."`). Spike **không cần DB hay LLM**, nên chưa cần đặt env Vercel nào khác.
4. Đẩy nhánh spike: `git push origin feat/rag-v1:spike/vercel` (workflow `spike-deploy` chạy khi đẩy `spike/**`; **Run workflow** chỉ hiện khi workflow nằm trên nhánh mặc định, mà `main` chưa có workflow). URL preview nằm ở job summary.
5. Trên máy bạn:

   ```bash
   python scripts/spike_vercel_check.py --url https://<preview>.vercel.app --bypass-env VERCEL_AUTOMATION_BYPASS_SECRET
   ```

   Bỏ `--bypass-env` nếu Protection tắt. Mất khoảng 40 giây. Mã thoát: 0 PASS, 1 FAIL, 2 lỗi dùng hoặc kết nối. Secret không bao giờ được in và không bị gửi sang host khác (checker không theo redirect). Dán nguyên khối `=== RESULT spike_vercel ===` vào chat và vào bảng dưới (nhãn đầu của URL đã được che).
6. Xem tay: `curl -N https://<preview>/api/sse` (thêm `-H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET"` nếu có bảo vệ). Vercel, Project, Deployments, deployment vừa tạo, Functions: ghi **region** và **max duration** của hàm `api`.
7. Gửi lại: khối RESULT, link run Actions hoặc 20 dòng cuối log khi lỗi, kết quả mục 6, và xác nhận đã thêm 3 secret `VERCEL_*` (có hoặc không).

### Tiêu chí đạt (plan Task 0.4)

Checker in `PASS` khi **tất cả** đúng:

- `/` trả 200 HTML và nhìn giống app Next.js (có `<title>` và marker `__next` hoặc `/_next/`).
- `/api/ping` trả JSON `ok: true` và FastAPI thấy `path == "/api/ping"`.
- `/api/sse` trả 200 `text/event-stream`, đủ **30 event** đúng thứ tự, có `event: done`, không dồn cục (cùng ngưỡng spike 0.3: p95 khoảng cách trong [0,5 s; 2 s], không quá 3 event cách nhau dưới 50 ms, khoảng cách dài nhất tối đa 5 s).

Ghi thêm (không làm FAIL): FastAPI nhận path có `/api` hay không (`fastapi_sees_api_prefix`), region của function (`function_region` so với `syd1`, kèm `x_vercel_id_regions`), header `server`, `cache-control`, `x-vercel-cache`, `x-vercel-id`. "Chỗ đặt `maxDuration`" trả lời bằng `vercel.json` (trong service `api`, khóa `functions`) cộng bước 6.

Deployment Protection chặn (401 HTML "Authentication Required", hoặc redirect tới vercel.com): checker dừng sớm, in `protection: BLOCKED` và hướng dẫn dùng `--bypass-env`.

### Kết quả (điền từ khối `RESULT`)

| Trường | Giá trị |
|---|---|
| Ngày chạy (UTC) | TBD — chờ chạy |
| Link run Actions, hoặc lỗi nếu có | TBD — chờ chạy |
| `vercel build` và `deploy --prebuilt` với Services chạy được? | TBD — chờ chạy |
| `verdict` | TBD — chờ chạy |
| `protection` | TBD — chờ chạy |
| `/`: status, content-type | TBD — chờ chạy |
| `/api/ping`: status và `ping_facts` (`path`, `root_path`, `raw_path`, `python`) | TBD — chờ chạy |
| `fastapi_sees_api_prefix` | TBD — chờ chạy |
| `function_region` (mong đợi `syd1`) và `x_vercel_id_regions` | TBD — chờ chạy |
| Giá trị thô `x-vercel-id` | TBD — chờ chạy |
| `/api/sse`: `events` (x/30), `done_event`, `cut` | TBD — chờ chạy |
| `wall_time_s`, inter-arrival min/median/p95/max, `clumped_events` | TBD — chờ chạy |
| `server`, `cache-control`, `x-vercel-cache` | TBD — chờ chạy |
| `maxDuration` và region hiển thị ở dashboard (Functions) | TBD — chờ chạy |
| `ENABLE_SPIKE_ENDPOINTS` qua `--env` có tới runtime? | TBD — chờ chạy |
| Cần Framework Preset Services, hoặc Python/uv trên runner? | TBD — chờ chạy |

### Nếu lỗi và cây quyết định

- **`vercel build` báo thiếu Python hoặc `uv`:** thêm `astral-sh/setup-uv` vào `spike-deploy.yml` (về sau cả `deploy.yml`), chạy lại.
- **`/api/ping` trả 404 HTML (đi vào Next.js):** rewrite hoặc Services không áp. Gửi `vercel.json` và log `vercel build`.
- **`/api/ping` trả 404 JSON:** FastAPI trả lời nhưng không có route, tức `ENABLE_SPIKE_ENDPOINTS` chưa tới runtime. Đặt biến cho Preview trong dashboard, chạy lại (không phải lỗi Services).
- **`path` là `/ping` (tiền tố bị cắt):** trái với tài liệu. Ghi lại và báo trước khi sửa route, vì mọi route trong `backend/app/api/*` khai báo `/api/...`.
- **`/api/sse` dồn cục hoặc bị cắt:** ghi số event và giây bị cắt. Đây là lỗi ảnh hưởng chat, **không tự đổi**, báo lại.
- **`--prebuilt` không hỗ trợ Services:** chuyển sang Vercel Git integration theo [deploy.md](deploy.md) mục "Phương án dự phòng" (các bước đã ghi ở đó, không lặp lại). Ghi ADR và sửa `ci.yml`, `deploy.yml` chỉ **sau khi bạn báo kết quả**; chưa có ADR nào.
- **Region không phải `syd1`, hoặc deploy lỗi vì số region:** Hobby chỉ cho 1 region: nếu deploy lỗi vì số region, đặt Project → Settings → Functions → Function Region = `syd1` (đặt cho cả project, cả `web` lẫn `api`) và xóa `regions` khỏi `functions` trong `vercel.json`; thử cả hai biến thể (giữ `regions` trong `functions`, và đặt ở cấp project) trong cùng một lần spike. Ghi giá trị region thật, nơi đã cấu hình và biến thể nào chạy được; fallback của repo là `iad1`.

### Kiểm tra AI SDK v7 (mục cuối của plan Task 0.4)

- **Đã kiểm ở Task 4.2** (2026-11-22, [ai-sdk-protocol.md](ai-sdk-protocol.md)): hình dạng chunk `start`, `text-*`, `source-url` (`sourceId`, `url`), `data-*` (`data-status`, `data-trace`, `data-citation-warning`), `error` (`errorText`), `finish`, `[DONE]` và header `x-vercel-ai-ui-message-stream: v1`, đối chiếu với tài liệu trực tuyến của AI SDK. Backend phát đúng header này (`backend/app/stream.py`).
- **Chưa làm, cố ý:** kiểm header và stream thật trên Vercel. `/api/chat` cần DB và LLM nên spike này không dựng bản giả. Bước đó nằm ở lần deploy thật đầu tiên (smoke Task 6.3 và `frontend/e2e/offline.spec.ts`): header `x-vercel-ai-ui-message-stream: v1` của `/api/chat` phải đi qua được proxy Vercel. Còn nằm trong mục "Unverified" của ai-sdk-protocol.md: `title` trên `source-url`, `transient`, hành vi `useChat` thật.

### Dọn sau spike

Xóa `.github/workflows/spike-deploy.yml`, `backend/app/api/spike.py`, `backend/tests/api/test_spike.py`, khối gắn trong `backend/app/main.py`, `scripts/spike_vercel_check.py`, `pipelines/tests/test_spike_vercel_check.py` (và các file SSE của spike 0.3). **Giữ `vercel.json`.** Rồi: thêm cron vào `vercel.json` nếu được, tick plan Task 0.4 và 6.5, sửa mục "CHƯA XÁC MINH" của `deploy.md`.

---

<a id="supabase"></a>

## supabase: pgvector và kết nối pooler, Task 0.5

**Trạng thái: chưa chạy.** Kết quả: TBD — chờ chạy (cần project Supabase thật).

Tiêu chí đạt (plan Task 0.5): ghi `extversion` của `vector` (>= 0.8.0 thì có iterative scan); `select 1` qua psycopg (pooler 6543, `prepare_threshold=None`) từ `/api/ping` trả về **< 1 s** ở lần gọi nóng.

---

<a id="bench"></a>

## bench: smoke và benchmark LLM qua tunnel, Task 2.3

**Trạng thái: code đã viết (`scripts/smoke_llm.py`, test `pipelines/tests/test_smoke_llm.py` với gateway giả), chưa chạy với gateway live.** Mọi số bên dưới còn `TBD — chờ chạy`.

**Mục đích.** Từ máy bạn, qua tunnel ngrok thật, kiểm gateway Kaggle đủ dùng: `/health` báo LLM sẵn sàng; embed ra 1024 chiều; rerank xếp đúng đoạn lên đầu; chat stream tiếng Việt có dấu đúng, đo TTFT và tok/s. Script chỉ dùng thư viện chuẩn, không ghi file, không in key (host bị che nhãn đầu).

### Cách chạy

Notebook `kaggle/serve.ipynb` phải **READY** trước (cell 8 in `READY https://<domain>`, xem [runbook-kaggle.md](runbook-kaggle.md)). Đặt key trong shell, đừng dán vào chat.

```bash
# Git Bash
export LLM_BASE_URL=https://<NGROK_DOMAIN>
export LLM_API_KEY=<GATEWAY_API_KEY>
python scripts/smoke_llm.py            # tùy chọn: --runs 3 (mặc định), --timeout 60
```

```powershell
# PowerShell
$env:LLM_BASE_URL="https://<NGROK_DOMAIN>"
$env:LLM_API_KEY="<GATEWAY_API_KEY>"
python scripts/smoke_llm.py
```

Mã thoát: 0 PASS, 1 FAIL, 2 lỗi dùng, kết nối hoặc 401. Mất khoảng 1 đến 2 phút. Script in từng bước `[a_health]`... rồi khối `=== RESULT smoke_llm ===` (bảng markdown theo từng lần chat, p50/p95 TTFT, tok/s, cosine, thứ tự rerank, 200 ký tự đầu của câu trả lời lần 1, thời điểm UTC): dán **nguyên khối** đó vào chat và vào bảng dưới. `LLM_BASE_URL` không khớp regex ngrok của backend thì script chỉ cảnh báo (backend sẽ coi gateway là offline).

Các bước và cách đo:

| Bước | Kiểm | Nguồn field |
|---|---|---|
| a. `GET /health` (không cần token) | `llm` là true; in `status`, `embedder`, `reranker`, `model` | `kaggle/gateway.py` `health()` |
| b. `POST /v1/embeddings` hai câu | đúng 2 vector, mỗi vector **1024** chiều, số hữu hạn, hai vector khác nhau; in cosine; gọi hai lần để lấy thời gian lần đầu và lần lặp | `data[].index/embedding` |
| c. `POST /v1/rerank` truy vấn "lương tối thiểu vùng I" với 3 đoạn (nấu ăn, lương tối thiểu vùng, thai sản) | đoạn lương tối thiểu xếp **đầu**, điểm trong [0, 1] (đã qua sigmoid) và giảm dần | `results[].index/relevance_score` |
| d. `POST /v1/chat/completions` stream, `max_tokens=128`, system+user, không gửi tham số thinking (thinking tắt ở cờ `llama-server`, giống backend) | SSE đủ tới `[DONE]`; câu trả lời không rỗng, có dấu tiếng Việt, không U+FFFD, không mojibake, không `<think>` hay `reasoning_content`; ghi NFC hay không | SSE `choices[0].delta.content` |
| e. Kết luận | TTFT p50 < `TTFT_P50_MAX_S = 3.0` s | |

Công thức: **TTFT** = từ lúc gửi request (gồm bắt tay TCP/TLS qua ngrok) tới delta nội dung không rỗng đầu tiên. **tok/s** = số token / (tổng thời gian - TTFT), tức tốc độ decode. Số token lấy từ `usage.completion_tokens` nếu stream có (script gửi `stream_options.include_usage`); không có thì đếm số chunk nội dung và cột "nguồn token" ghi "xấp xỉ theo số chunk". p50/p95 nội suy tuyến tính. tok/s **không gate**, chỉ cảnh báo nếu median < 10. Script gửi thêm `stream_options` so với backend (backend không gửi): chỉ để lấy `usage`.

### Tiêu chí đạt (plan Task 2.3)

- **TTFT p50 < 3 s** qua tunnel (3 lần chat stream).
- Câu trả lời là **tiếng Việt có dấu đúng** (các kiểm tra ở bước d).
- Embed 1024 chiều, rerank đúng thứ tự, `/health` có `llm` true.
- Ghi cả tok/s (chỉ để biết). Ngưỡng là hằng số đặt tên ở đầu `scripts/smoke_llm.py`: nếu bạn thấy ngưỡng sai, nói trước khi sửa, đừng nới ngưỡng để "đạt".

### Kết quả (điền từ khối `RESULT`)

| Trường | Giá trị |
|---|---|
| Ngày chạy (UTC) | TBD — chờ chạy |
| `verdict` | TBD — chờ chạy |
| `health` (status, llm, embedder, reranker, model) | TBD — chờ chạy |
| Embeddings: chiều, cosine, ms lần đầu / lần lặp | TBD — chờ chạy |
| Rerank: thứ tự, điểm | TBD — chờ chạy |
| TTFT từng lần (s) | TBD — chờ chạy |
| TTFT p50 / p95 (s) | TBD — chờ chạy |
| tok/s từng lần và median, nguồn token (usage hay xấp xỉ) | TBD — chờ chạy |
| 200 ký tự đầu của câu trả lời lần 1, có dấu đúng? NFC? | TBD — chờ chạy |
| Cấu hình lúc đo (quant Q5_K_M hay Q4_K_M, `-ngl`, `-c`, vùng ngrok) | TBD — chờ chạy |

### Nếu lỗi

- **Thoát mã 2, "401 unauthorized"**: `LLM_API_KEY` không trùng secret `GATEWAY_API_KEY` trong Kaggle (hoặc secret chưa tick "Attached" khi notebook chạy). Kiểm shell có đúng key, không có dấu cách hay xuống dòng thừa.
- **Thoát mã 2, "không kết nối được"**: notebook chưa READY, đã hết phiên, sai domain, hoặc mất mạng.
- **`a_health` FAIL `llm=False`**: llama-server chưa tải xong model hoặc đã chết; xem log cell serve (runbook).
- **HTTP 502/504 (kèm `ngrok ERR_NGROK_...` nếu có)**: gateway hoặc llama-server chưa sẵn sàng, hoặc tunnel đang đứt. Chờ vài chục giây rồi chạy lại một lần.
- **"phản hồi không phải JSON" hoặc content-type `text/html`**: trang cảnh báo ngrok hoặc URL sai (xem phần ngrok ở mục [sse](#sse)).
- **TTFT p50 >= 3 s**: xem cell serve có đẩy đủ lớp lên GPU không (`-ngl`) và `CUDA_VISIBLE_DEVICES` (llama-server GPU 0, embedder/reranker GPU 1, tranh GPU làm chậm); prompt dài hơn dự kiến; vùng ngrok xa Việt Nam; lần đầu sau khi khởi động có thể chậm hơn, chạy lại để so. Ghi số thật, không nới ngưỡng.
- **Chiều embedding khác 1024**: sai model embedder (phải là `AITeamVN/Vietnamese_Embedding`).
- **Thiếu dấu, `<think>`, U+FFFD, mojibake**: kiểm cờ `--reasoning-budget 0` và `--chat-template-kwargs` (mục [llama](#llama)), template Jinja, và mã hóa ở tunnel.
- **Luồng bị cắt / không có `[DONE]`**: liên quan spike [sse](#sse); ghi lại lần thứ mấy và sau bao lâu.
