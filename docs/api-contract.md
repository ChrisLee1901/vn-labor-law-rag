# API contract (Task 4.3)

Hợp đồng giữa frontend và backend FastAPI. Frontend dựng trên mock song song với backend (Task 4.4). Kiểu TypeScript tương ứng: `frontend/src/lib/api-types.ts`. Hình dạng chunk của stream đã kiểm chứng ở `docs/ai-sdk-protocol.md` và phát ra bởi `backend/app/stream.py`.

Quy ước chung: JSON UTF-8, ngày dạng `YYYY-MM-DD`. Lỗi luôn là `{"detail": "<thông báo tiếng Việt>"}`.

## Danh sách endpoint

| Method | Path | Mô tả | Thành công |
|---|---|---|---|
| POST | `/api/chat` | Hỏi đáp RAG, trả stream SSE | 200 `text/event-stream` |
| GET | `/api/health` | Trạng thái LLM, DB, phiên bản chỉ mục | 200 JSON |
| GET | `/api/docs` | Danh sách văn bản | 200 JSON (mảng) |
| GET | `/api/docs/{code}` | Chi tiết một văn bản và các điều | 200 JSON |
| POST | `/api/feedback` | Chấm điểm một câu trả lời | 204 |
| GET | `/api/cron/keepalive` | Giữ DB không bị pause (Vercel Cron) | 204 |

## POST /api/chat

Body:

| Trường | Kiểu | Quy tắc |
|---|---|---|
| `messages` | `UIMessage[]` (AI SDK) | 1 đến 10 phần tử; phần tử cuối phải là `role: "user"`, nội dung văn bản 1 đến 1000 ký tự |
| `as_of` | `"YYYY-MM-DD"` (tùy chọn) | Tra cứu theo hiệu lực tại ngày này; mặc định hôm nay |

Vi phạm quy tắc: 422 `{"detail":"Câu hỏi quá dài (tối đa 1000 ký tự)."}` (hoặc thông báo tương ứng cho rỗng, quá 10 tin nhắn, `as_of` sai định dạng).

Response headers: `x-vercel-ai-ui-message-stream: v1`, `content-type: text/event-stream`, `cache-control: no-cache`.

Mỗi chunk là một dòng `data: <json>` kết thúc bằng dòng trống; stream kết thúc bằng `data: [DONE]`.

### Thứ tự part

```
start → data-status → source-url* → text-start → text-delta* → text-end → (data-citation-warning)? → data-trace → finish → [DONE]
```

Khi lỗi sau `start`: `error` rồi `[DONE]` (không có `finish`). Lỗi trước khi stream mở dùng mã HTTP và `{detail}` ở mục Lỗi.

### Các part

| `type` | Payload | Ghi chú |
|---|---|---|
| `start` | `{messageId}` | Mở message |
| `data-status` | `data: {llm: "online"\|"offline", mode: "rag"\|"offline"\|"refused"}` | Luôn là data part đầu tiên |
| `source-url` | `{sourceId, url, title}` | Một part cho mỗi nguồn; `sourceId` = `S1`...`Sn`; `url` = `/van-ban/{doc_code}#D{n}` (phụ lục: `#PL{n}`); `title` đọc được, vd `145/2020/NĐ-CP, Điều 12. Hợp đồng lao động` |
| `text-start`, `text-delta`, `text-end` | `{id}`, `{id, delta}`, `{id}` | Nội dung trả lời; chú thích `[S1]` trong text trỏ tới `sourceId` |
| `data-citation-warning` | `data: {invalid: string[], mismatch: string[]}` | Chỉ phát khi có trích dẫn không hợp lệ hoặc lệch nội dung; hiển thị cảnh báo, không chặn câu trả lời |
| `data-trace` | `data: {trace_id: string}` | Phát một lần, gần cuối; dùng cho `/api/feedback` |
| `finish` | `{}` | Bắt buộc có khi thành công (client coi stream thiếu `finish` là lỗi) |
| `error` | `{errorText}` | Thay cho `finish` khi hỏng giữa chừng |

### Ba chế độ

| `mode` | `llm` | Hành vi |
|---|---|---|
| `rag` | `online` | Truy hồi, gọi LLM, stream câu trả lời có trích dẫn |
| `offline` | `offline` | Không gọi LLM. Sau các `source-url`, text cố định `Mô hình đang ngoại tuyến. Dưới đây là các điều luật liên quan nhất:` kèm danh sách điều luật truy hồi được |
| `refused` | `online` hoặc `offline` | Không đủ căn cứ hoặc ngoài phạm vi. Không gọi LLM; text là câu từ chối cố định `Tôi không tìm thấy căn cứ trong các văn bản hiện có.` |

### Ví dụ: online (câu hỏi lương tối thiểu theo ND293-2025)

Request:

```json
{"messages":[{"id":"u1","role":"user","parts":[{"type":"text","text":"Mức lương tối thiểu vùng I hiện nay là bao nhiêu?"}]}],"as_of":"2026-07-01"}
```

Stream:

```
data: {"type":"start","messageId":"m1"}

data: {"type":"data-status","data":{"llm":"online","mode":"rag"}}

data: {"type":"source-url","sourceId":"S1","url":"/van-ban/ND293-2025#D3","title":"293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu"}

data: {"type":"text-start","id":"t1"}

data: {"type":"text-delta","id":"t1","delta":"Mức lương tối thiểu vùng I là 5.310.000 đồng/tháng [S1]."}

data: {"type":"text-end","id":"t1"}

data: {"type":"data-trace","data":{"trace_id":"3f2c9a1e"}}

data: {"type":"finish"}

data: [DONE]
```

### Ví dụ: offline

```
data: {"type":"start","messageId":"m2"}

data: {"type":"data-status","data":{"llm":"offline","mode":"offline"}}

data: {"type":"source-url","sourceId":"S1","url":"/van-ban/ND293-2025#D3","title":"293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu"}

data: {"type":"text-start","id":"t1"}

data: {"type":"text-delta","id":"t1","delta":"Mô hình đang ngoại tuyến. Dưới đây là các điều luật liên quan nhất:\n\n- [S1] 293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu"}

data: {"type":"text-end","id":"t1"}

data: {"type":"data-trace","data":{"trace_id":"3f2c9a1f"}}

data: {"type":"finish"}

data: [DONE]
```

### Ví dụ: refused

```
data: {"type":"start","messageId":"m3"}

data: {"type":"data-status","data":{"llm":"online","mode":"refused"}}

data: {"type":"text-start","id":"t1"}

data: {"type":"text-delta","id":"t1","delta":"Tôi không tìm thấy căn cứ trong các văn bản hiện có."}

data: {"type":"text-end","id":"t1"}

data: {"type":"data-trace","data":{"trace_id":"3f2c9a20"}}

data: {"type":"finish"}

data: [DONE]
```

### Ví dụ: cảnh báo trích dẫn và lỗi giữa chừng

```
data: {"type":"data-citation-warning","data":{"invalid":["S9"],"mismatch":[]}}
```

```
data: {"type":"error","errorText":"Mô hình ngừng phản hồi, vui lòng thử lại."}

data: [DONE]
```

## GET /api/health

Header: `cache-control: no-store`.

```json
{"llm":"online","db":"ok","index_version":1}
```

| Trường | Giá trị |
|---|---|
| `llm` | `"online"` hoặc `"offline"` (gateway Kaggle tới được hay không) |
| `db` | `"ok"` hoặc `"down"` |
| `index_version` | số nguyên, bằng `app_config.active_index_version` |

## GET /api/docs

Header: `cache-control: public, s-maxage=3600`.

Mảng `DocSummary`, mỗi phần tử:

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `code` | string | Mã cố định, vd `ND293-2025` |
| `number` | string hoặc null | Số hiệu, vd `293/2025/NĐ-CP` |
| `title` | string hoặc null | |
| `doc_type` | `luat`, `bo_luat`, `vbhn`, `nghi_dinh`, `thong_tu` | |
| `effective_from` | `YYYY-MM-DD` | |
| `effective_to` | `YYYY-MM-DD` hoặc null | |
| `status` | `con_hieu_luc`, `chua_hieu_luc`, `het_hieu_luc` | |
| `articles` | number | Số điều của chỉ mục đang hoạt động, chỉ đếm `kind = 'dieu'` (không tính phụ lục) |

```json
[{"code":"ND293-2025","number":"293/2025/NĐ-CP","title":"Quy định mức lương tối thiểu theo vùng","doc_type":"nghi_dinh","effective_from":"2026-01-01","effective_to":null,"status":"con_hieu_luc","articles":8}]
```

## GET /api/docs/{code}

Header: `cache-control: public, s-maxage=3600`.

Trả `{doc, articles}`. `doc` là `DocDetail`: các trường của `DocSummary` (không có `articles`) cộng `issuer`, `issued_on`, `replaced_by` (mã văn bản thay thế hoặc null), `amends` (mảng mã), `source_url`. `articles` là mảng `ArticleItem` theo thứ tự `kind`, `number`, `suffix`:

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `id` | string | Vd `ND293-2025:D3` |
| `number` | number hoặc null | Số điều hoặc số phụ lục |
| `suffix` | string hoặc null | Vd `a` cho Điều 12a |
| `title` | string hoặc null | |
| `chapter` | string hoặc null | |
| `content` | string | |
| `kind` | `dieu`, `phu_luc` | Neo trang: `#D{n}` hoặc `#PL{n}` |

Nullability: cột `doc_type`, `status`, `content` có thể NULL trong DB nhưng API đảm bảo không null: bản ghi văn bản có `doc_type` hoặc `status` NULL hoặc ngoài tập giá trị bên trên bị loại khỏi kết quả, `content` NULL được đổi thành chuỗi rỗng. Các trường còn lại ghi "hoặc null" ở trên có thể null thật.

Mã không tồn tại: 404 `{"detail":"Không tìm thấy văn bản."}`.

## POST /api/feedback

Body: `{"trace_id":"3f2c9a1e","score":1,"comment":"Đúng, đủ ý"}`

| Trường | Quy tắc |
|---|---|
| `trace_id` | Giá trị nhận từ part `data-trace` của đúng câu trả lời đó |
| `score` | `1` (hữu ích) hoặc `-1` (chưa tốt) |
| `comment` | Tùy chọn |

Trả 204, không có body. Điểm được lưu vào bảng `feedback`, rồi (sau khi response đã gửi) chuyển thành score Langfuse `user-feedback` (giá trị `1` hoặc `-1`, kiểu NUMERIC) gắn vào trace có `trace_id` đó; `comment` được che PII trước khi gửi. Langfuse chưa cấu hình, lỗi hay chậm (tối đa 5 s) thì feedback vẫn trả 204. Chi tiết span và cách kiểm tra: [runbook-observability.md](runbook-observability.md).

## GET /api/cron/keepalive

Header bắt buộc: `Authorization: Bearer $CRON_SECRET`. Trả 204. Thiếu hoặc sai secret: 401 `{"detail":"Không được phép."}`.

## Lỗi

| Mã | Endpoint | Khi nào | `detail` |
|---|---|---|---|
| 422 | `/api/chat`, `/api/feedback` | Input sai | vd `Câu hỏi quá dài (tối đa 1000 ký tự).` |
| 429 | `/api/chat` (chỉ endpoint này) | Vượt giới hạn tần suất | `Bạn hỏi hơi nhanh, vui lòng thử lại sau ít phút.` |
| 413 | `/api/chat`, `/api/feedback` (mọi POST) | Body lớn hơn 64 KB | `Yêu cầu quá lớn.` |
| 503 | `/api/chat`, `/api/docs`, `/api/docs/{code}`, `/api/feedback`, `/api/cron/keepalive` | DB không khả dụng | `Cơ sở dữ liệu tạm thời không khả dụng, vui lòng thử lại sau.` |
| 404 | `/api/docs/{code}` | Mã không tồn tại | `Không tìm thấy văn bản.` |
| 401 | `/api/cron/keepalive` | Thiếu hoặc sai `CRON_SECRET` | `Không được phép.` |

`/api/health` không bao giờ trả 503: DB lỗi được báo bằng `db: "down"` với mã 200.

Mọi lỗi HTTP đều có body `{"detail": "..."}` và header `x-content-type-options: nosniff`, `cache-control: no-store`. Ngoài bảng trên: 404 đường dẫn không tồn tại `Không tìm thấy đường dẫn.`, 405 sai phương thức `Phương thức không được hỗ trợ.`, 500 lỗi hệ thống `Đã xảy ra lỗi hệ thống, vui lòng thử lại sau.`

### Lỗi trong stream (`error` part)

| `errorText` | Khi nào |
|---|---|
| `Kết nối tới mô hình bị gián đoạn, vui lòng thử lại.` | LLM đứt giữa chừng hoặc lỗi bất ngờ sau `start` |
| `Mô hình trả lời quá lâu, vui lòng thử lại.` | Quá ngân sách thời gian của một request (100 s) |

Nếu client ngắt kết nối, server dừng sinh và không phát thêm part nào.
