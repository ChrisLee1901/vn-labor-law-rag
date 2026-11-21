# Golden set v1 – hỏi đáp pháp luật lao động / BHXH

## Mục đích

Bộ 120 câu hỏi có đáp án và nhãn nguồn (gold) để đo hệ RAG pháp lý: độ chính xác truy hồi (gold ở cấp Điều), chất lượng câu trả lời, khả năng từ chối khi không có căn cứ, và khả năng chống prompt injection. File dữ liệu: `eval/golden/v1.jsonl`, nạp bằng `rag_pipelines.eval.golden_schema.load_golden`.

## Corpus

8 văn bản trong `docs/corpus/legal_docs.yaml`: `BLLD` (VBHN 18/VBHN-VPQH – Bộ luật Lao động 45/2019/QH14), `ND145-2020`, `ND293-2025`, `ND399-2026`, `LBHXH-2024` (41/2024/QH15), `ND158-2025`, `LVL-2025` (74/2025/QH15), `ND374-2025`, cộng Phụ lục 1 của ND293-2025 (34 mục địa bàn, id `ND293-2025:PL1:M<n>`). `ND399-2026` có `status: chua_hieu_luc` (hiệu lực từ 2027-01-01).

## Phương pháp

1. **Sinh**: Claude Sonnet 5.5 (effort medium) sinh 160 ứng viên từ bản dump corpus đã parse (`dump_corpus`: mỗi Điều/Khoản/Điểm kèm id, cộng danh sách cặp tham chiếu chéo văn bản `refs_pairs.md`), theo quota từng loại. Câu hỏi viết bằng ngôn ngữ đời thường; multi_hop lấy từ các cặp tham chiếu; temporal đối chiếu ND293 với ND399; `source_quote` trích nguyên văn.
2. **Kiểm chéo mù**: các agent Sonnet khác, độc lập với bước sinh, chỉ nhận câu hỏi và `as_of` (không thấy đáp án, gold hay quote), tự trả lời và tự gán gold.
3. **Luật giữ** (`select_golden`): với câu có đáp án, giữ khi verifier cho là trả lời được, tập gold của verifier giao tập gold ứng viên (>= 1 id) và mọi gold id tồn tại trong cấu trúc đã parse; với unanswerable / out_of_domain / injection, giữ khi verifier cho là không trả lời được (gold rỗng). Loại câu trùng nguyên văn câu hỏi (sau NFC) và câu chép quote: Jaccard theo âm tiết giữa câu hỏi và `source_quote` phải <= 0.6.
4. **Chọn**: theo quota, ưu tiên ứng viên đứng trước, id `q001…` xáo bằng seed 42; chia dev/test phân tầng theo loại (seed 42). Cuối cùng chạy `validate_set` (id hợp lệ, quota ±3 điểm %, tổng 120, dev 40 / test 80, phân tầng, anti-copy); bộ không hợp lệ thì không ghi.

## Số lượng

| Loại | Tổng | Dev | Test |
|---|---|---|---|
| single | 42 | 14 | 28 |
| numeric | 18 | 6 | 12 |
| multi_hop | 18 | 6 | 12 |
| temporal | 6 | 2 | 4 |
| compare | 12 | 4 | 8 |
| unanswerable | 12 | 4 | 8 |
| out_of_domain | 6 | 2 | 4 |
| injection | 6 | 2 | 4 |
| **Cộng** | **120** | **40** | **80** |

out_of_domain + injection = 12 câu (10%).

## Thống kê loại bỏ (từ `select_stats.json`)

| Loại | Ứng viên | Giữ | Loại: gold không giao | Loại: verifier trả lời được dù không có căn cứ | Chép quote / trùng / gold sai id / không trả lời được |
|---|---|---|---|---|---|
| single | 55 | 52 | 3 | – | 0 |
| numeric | 25 | 24 | 1 | – | 0 |
| multi_hop | 28 | 27 | 1 | – | 0 |
| temporal | 10 | 10 | 0 | – | 0 |
| compare | 14 | 13 | 1 | – | 0 |
| unanswerable | 14 | 13 | – | 1 | 0 |
| out_of_domain | 8 | 8 | – | 0 | 0 |
| injection | 6 | 6 | – | 0 | 0 |
| **Cộng** | **160** | **153** | **6** | **1** | **0** |

Từ 153 câu đạt luật giữ, chọn 120 theo quota (các câu thừa không dùng).

## Độ mịn nhãn

`gold` ghi id hẹp nhất chứa căn cứ (Điều `<mã>:D<n>`, Khoản `:K<k>`, Điểm `:<p>`, mục phụ lục `ND293-2025:PL1:M<n>`). Khi chấm, so khớp ở **cấp Điều** (rút id về `<mã>:D<n>`); phụ lục so theo `ND293-2025:PL1`. Câu unanswerable / out_of_domain / injection có `gold` rỗng: đáp án đúng là từ chối.

## Ngữ nghĩa `as_of`

`as_of` (YYYY-MM-DD) là ngày hiệu lực giả định của câu hỏi: văn bản nào có hiệu lực tại ngày đó thì được dùng làm căn cứ. 114/120 câu dùng `2026-11-22` (ngày tạo bộ). 6 câu temporal đặt ngày trước/sau 2027-01-01 để thử việc chọn ND293-2025 hay ND399-2026.

## Hạn chế đã biết

- Nhãn do một "người chú giải" LLM (Claude) sinh, verifier cũng là LLM cùng họ: có thể chung thiên lệch; chưa phải nhãn chuyên gia luật.
- Kiểm tra thủ công 20 câu (`review_sample.csv`, seed 42) **đang chờ**: kết quả đúng/sai sẽ điền vào đây. Kết quả: _chưa có_.
- Câu temporal phụ thuộc ND399-2026 (chưa có hiệu lực, hiệu lực 2027-01-01): nếu văn bản được sửa/hoãn trước ngày đó thì đáp án có thể lệch.
- Quy tắc giữ chỉ yêu cầu gold giao nhau >= 1 id, không so khớp văn bản đáp án của verifier với đáp án ứng viên.
- Id điểm của khoản không số (điểm đứng trước mọi khoản) không có dạng hợp lệ `D:K:p`; gold của các trường hợp đó ở cấp Điều.
- Corpus chỉ 8 văn bản; câu "ngoài phạm vi" chỉ đại diện, không phủ hết miền ngoài.

## Quy tắc sử dụng

Chỉ báo số liệu trên split **test**; chỉnh τ (ngưỡng) và prompt trên split **dev**.
