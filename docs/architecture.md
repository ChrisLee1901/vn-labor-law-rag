# Kiến trúc hệ thống

Nguồn Mermaid của sơ đồ trên trang Giới thiệu. Bản vẽ tay, theo giao diện sáng/tối, nằm ở `frontend/src/components/about/architecture-diagram.tsx`: sửa sơ đồ thì sửa cả hai chỗ. Thiết kế đầy đủ: `docs/superpowers/specs/2026-11-22-vietnamese-legal-rag-design.md`, cách bật Kaggle: `docs/runbook-kaggle.md`.

## Thành phần

```mermaid
flowchart LR
    B[Trình duyệt]

    subgraph V["Vercel (syd1)"]
        W["Next.js 16 (web)<br/>giao diện, /api/* chuyển sang api (Vercel Services)"]
        A["FastAPI (api)<br/>truy xuất, prompt, kiểm tra trích dẫn"]
    end

    S[("Supabase Postgres<br/>pgvector halfvec 1024 + tsvector<br/>hybrid_search RRF")]
    N["ngrok<br/>HTTPS, domain tĩnh"]

    subgraph K["Kaggle notebook (T4 x2, chỉ bật khi demo)"]
        G["Gateway FastAPI<br/>Bearer, /health /v1/*"]
        E["Embedder<br/>Vietnamese_Embedding, GPU 1"]
        R["Reranker<br/>Vietnamese_Reranker, GPU 1"]
        L["llama-server<br/>Qwen3-8B Q5_K_M, GPU 0"]
        G --> E
        G --> R
        G --> L
    end

    B --> W --> A
    A --> S
    A --> N --> G

    I["Ingest (ngoại tuyến)<br/>parse, chunk Điều/Khoản, embed"] -. "ghi index_version mới" .-> S
    I -. "embed qua cùng gateway" .-> G

    CI["GitHub Actions<br/>CI, rồi vercel deploy --prebuilt"] -. deploy .-> V
```

- Mọi route của gateway trừ `/health` đòi `Authorization: Bearer`. `LLM_BASE_URL` phải khớp mẫu ngrok, sai mẫu thì coi như ngoại tuyến.
- Kết nối DB từ Vercel qua pooler transaction mode (cổng 6543). Gọi gateway có timeout connect 3 s, read 60 s.
- Re-ingest ghi vào `index_version` mới, chuyển bằng `app_config.active_index_version`.

## Một câu hỏi, chế độ trực tuyến

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant W as Next.js
    participant A as FastAPI
    participant D as Supabase
    participant G as Gateway Kaggle
    participant L as llama-server

    U->>W: câu hỏi
    W->>A: POST /api/chat
    A->>A: chuẩn hóa NFC, trích số hiệu / Điều / Khoản, dựng tsquery
    A->>G: embed câu hỏi
    G-->>A: vector 1024 chiều
    A->>D: hybrid_search (RRF k=50, 40 ứng viên, lọc hiệu lực theo ngày hỏi)
    D-->>A: đoạn ứng viên
    A->>G: rerank
    G-->>A: điểm, giữ 6 Điều cha
    A->>D: mở rộng 1 bước theo legal_refs (tối đa 4 đoạn)
    alt điểm rerank cao nhất dưới ngưỡng
        A-->>W: từ chối, không gọi LLM
    else đủ căn cứ
        A->>G: chat completions kèm nguồn [S1..Sn]
        G->>L: proxy SSE
        L-->>A: token (stream)
        A->>A: kiểm tra [S#] hợp lệ và số Điều khớp tiêu đề nguồn
        A-->>W: stream (source-url, text-delta, data-status)
    end
    W-->>U: câu trả lời kèm trích dẫn
```

Chế độ ngoại tuyến bỏ các bước gọi gateway: chỉ FTS cộng tra cứu ID bằng regex, trả danh sách Điều để đọc, hoặc câu trả lời đã lưu nếu khớp câu mẫu.
