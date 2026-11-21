# Runbook Kaggle: bật LLM trước buổi phỏng vấn

Notebook `kaggle/serve.ipynb` chạy ba thứ sau một cổng xác thực (gateway, cổng 8000) và đưa ra internet qua ngrok:

- `llama-server` với Qwen3-8B GGUF Q5_K_M trên GPU 0 (thinking tắt)
- embedder `AITeamVN/Vietnamese_Embedding` và reranker `AITeamVN/Vietnamese_Reranker` (fp16) trên GPU 1

Chỉ bật notebook trước buổi demo và tắt ngay sau đó. Không công khai URL tunnel (Kaggle ToS: không chạy server liên tục).

## Thiết lập một lần

1. Tạo Kaggle Notebook mới, **Import** file `kaggle/serve.ipynb`.
2. **Add Input** (Add data), gắn hai Dataset private:
   - `llamacpp-sm75-bin`: binary `llama-server` build sẵn cho T4 (sm_75) cùng mọi file `.so`.
   - `qwen3-8b-gguf`: file `Qwen3-8B-Q5_K_M.gguf`.
   Thiếu dataset thì notebook vẫn chạy: GGUF tải từ Hugging Face (`Qwen/Qwen3-8B-GGUF`), còn `llama-server` phải build từ mã nguồn mất khoảng 26 phút (xem bảng sự cố).
3. **Add-ons > Secrets**, thêm 4 secret và bật "Attached" cho notebook này:

   | Secret | Giá trị |
   | --- | --- |
   | `NGROK_AUTHTOKEN` | authtoken ngrok |
   | `NGROK_DOMAIN` | domain tĩnh dạng `ten-cua-ban.ngrok-free.dev` (không kèm `https://`) |
   | `GATEWAY_API_KEY` | chuỗi ngẫu nhiên dài, trùng với `LLM_API_KEY` trong env Vercel |
   | `HF_TOKEN` | token Hugging Face (tải embedder, reranker và GGUF dự phòng) |

4. **Settings**: bật **Internet**, **Accelerator = GPU T4 x2**, Persistence = không cần.

Sửa `kaggle/gateway.py` thì sinh lại notebook rồi import lại bản mới lên Kaggle:

```
python kaggle/build_notebook.py
```

Notebook nhúng nguyên văn `gateway.py` (cell `%%writefile gateway.py`). Test `kaggle/tests/test_notebook.py` báo lỗi nếu `serve.ipynb` lệch so với `gateway.py`.

## Trước phỏng vấn 15 phút

- [ ] Mở notebook trên Kaggle, kiểm tra Accelerator là **GPU T4 x2**, Internet đang bật.
- [ ] **Run All**. Hàng đợi GPU có thể mất vài phút, nên bắt đầu sớm.
- [ ] Theo dõi cell 6: in `/health` mỗi 10 giây tới khi `status: ok`. Mục tiêu: dưới 10 phút từ lúc bấm Run All (khi có sẵn hai dataset).
- [ ] Chờ cell 8 in `READY https://<domain>` kèm kết quả smoke test (embedding 1024 chiều, rerank, một câu trả lời tiếng Việt, không có `<think>`).
- [ ] Mở app (Vercel): badge trạng thái LLM chuyển **xanh**.
- [ ] Hỏi thử một câu, ví dụ "Thời gian thử việc tối đa là bao lâu?", kiểm tra có trích dẫn.

Cell 9 giữ phiên sống và ghi `/health` mỗi 60 giây. Cell này chạy vô hạn, đó là bình thường.

## Sau phỏng vấn

- [ ] Kaggle: **Session options > Stop session** (hoặc nút tắt phiên). Chỉ ngắt kernel là chưa đủ, phải dừng phiên để trả GPU.
- [ ] Badge trên app chuyển đỏ (offline) là đúng.

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
| --- | --- | --- |
| Run All đứng ở "Waiting for GPU" lâu | Hàng đợi GPU T4 x2 của Kaggle | Bắt đầu sớm hơn, thử lại vài phút sau. Quota GPU hằng tuần còn không? Có thể thử phiên khác sau ít phút. |
| App báo 401 / `unauthorized` | `GATEWAY_API_KEY` trên Kaggle khác `LLM_API_KEY` trong env Vercel | Đặt lại hai giá trị giống nhau (Vercel: Sensitive), redeploy Vercel, chạy lại notebook. Thử nhanh: `curl -H "Authorization: Bearer $KEY" https://<domain>/v1/rerank ...`. |
| Notebook đã `READY` nhưng badge vẫn đỏ | `LLM_BASE_URL` sai, hoặc `/health` chưa `ok`, hoặc tunnel chưa mở | Mở `https://<domain>/health` trên trình duyệt, cần thấy `"status":"ok"`. Kiểm tra `LLM_BASE_URL` khớp `^https://[a-z0-9-]+\.ngrok-free\.(app\|dev)$` (domain `.ngrok-free.dev` hợp lệ). Nếu `llm` là `false`, xem `/kaggle/working/llama.log`. |
| ngrok: "domain already in use" / `ERR_NGROK_334` | Phiên cũ vẫn còn giữ domain | Stop session ở phiên cũ trên Kaggle, hoặc đóng endpoint tại dashboard ngrok (Endpoints), rồi chạy lại cell 7. |
| Cell 6 hết 15 phút, `llm: false` | `llama-server` chết (thiếu `.so`, hết VRAM) | Đọc phần cuối `llama.log` do cell in ra. Kiểm tra dataset `llamacpp-sm75-bin` có đủ file `.so`. |
| Thiếu dataset, cell 2 build mất rất lâu | Fallback build từ mã nguồn (`-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75`) chạy khoảng 26 phút | Chấp nhận chờ, hoặc gắn dataset `llamacpp-sm75-bin` rồi chạy lại (nên làm trước buổi demo, không làm lúc gần giờ). |
| Chat trả lời có `<think>...</think>` | Cờ tắt thinking không được build llama.cpp chấp nhận | Xem cảnh báo ở cell 8, kiểm tra `llama.log` và cờ `--reasoning-budget 0` / `--chat-template-kwargs` trong cell 3. |
| `kaggle_secrets` báo thiếu secret | Secret chưa bật "Attached" cho notebook | Add-ons > Secrets, tick cả 4 secret. |
