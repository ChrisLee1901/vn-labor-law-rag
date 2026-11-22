// Sơ đồ kiến trúc vẽ tay, màu lấy từ token (fill-card, stroke-input, ...) nên tự đổi theo sáng/tối. Nguồn Mermaid: docs/architecture.md.
const box = "fill-card stroke-input";
const dash = "[stroke-dasharray:5_4]";
const title = "fill-foreground text-[13px] font-semibold";
const sub = "fill-muted-foreground text-[11px]";
const line = "stroke-muted-foreground fill-none";

function Node({ x, y, w, h, name, detail = [], dashed }: { x: number; y: number; w: number; h: number; name: string; detail?: string[]; dashed?: boolean }) {
  const oneLine = detail.length === 0;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6} className={dashed ? `${box} ${dash}` : box} strokeWidth={1.5} />
      <text x={x + w / 2} y={oneLine ? y + h / 2 + 4.5 : y + 20} textAnchor="middle" className={title}>
        {name}
      </text>
      {detail.map((t, i) => (
        <text key={t} x={x + w / 2} y={y + 37 + i * 14} textAnchor="middle" className={sub}>
          {t}
        </text>
      ))}
    </g>
  );
}

export function ArchitectureDiagram() {
  return (
    <div
      role="region"
      aria-label="Sơ đồ kiến trúc (cuộn ngang trên màn hình nhỏ)"
      tabIndex={0}
      className="overflow-x-auto rounded-md border bg-background p-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <svg viewBox="0 0 760 466" role="img" aria-labelledby="arch-title" aria-describedby="arch-desc" className="mx-auto h-auto w-full min-w-[700px] max-w-[760px]">
        <title id="arch-title">Sơ đồ kiến trúc hệ thống</title>
        <desc id="arch-desc">
          Trình duyệt gọi Next.js trên Vercel, Next.js chuyển /api tới FastAPI. FastAPI truy vấn Supabase Postgres (pgvector, tìm kiếm lai) và gọi qua ngrok tới gateway trên
          Kaggle, nơi chạy embedder, reranker và llama-server Qwen3-8B. Đường ngoại tuyến nạp văn bản vào Supabase qua cùng gateway. CI/CD chạy bằng GitHub Actions.
        </desc>
        <defs>
          <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" className="fill-muted-foreground" />
          </marker>
        </defs>

        <rect x={210} y={20} width={260} height={190} rx={8} className={`fill-none stroke-input ${dash}`} strokeWidth={1.5} />
        <text x={224} y={42} className={sub}>
          Vercel (sin1)
        </text>
        <rect x={16} y={310} width={504} height={140} rx={8} className={`fill-none stroke-input ${dash}`} strokeWidth={1.5} />
        <text x={28} y={330} className={sub}>
          Kaggle notebook (T4 x2, chỉ bật khi demo)
        </text>

        <Node x={16} y={60} w={140} h={60} name="Trình duyệt" detail={["Hỏi đáp, Văn bản"]} />
        <Node x={226} y={52} w={228} h={48} name="Next.js 16 (web)" detail={["giao diện, rewrite /api/*"]} />
        <Node x={226} y={140} w={228} h={56} name="FastAPI (api)" detail={["truy xuất, prompt, kiểm tra trích dẫn"]} />
        <Node x={540} y={128} w={204} h={80} name="Supabase Postgres" detail={["pgvector halfvec 1024 + tsvector", "hybrid_search (RRF)"]} />
        <Node x={220} y={250} w={240} h={32} name="ngrok (HTTPS, domain tĩnh)" />
        <Node x={32} y={340} w={472} h={30} name="Gateway FastAPI (Bearer)" />
        <Node x={32} y={386} w={148} h={58} name="Embedder" detail={["Vietnamese_Embedding", "GPU 1, fp16"]} />
        <Node x={192} y={386} w={148} h={58} name="Reranker" detail={["Vietnamese_Reranker", "GPU 1, fp16"]} />
        <Node x={352} y={386} w={152} h={58} name="llama-server" detail={["Qwen3-8B Q5_K_M", "GPU 0"]} />
        <Node x={540} y={310} w={204} h={80} name="Ingest (ngoại tuyến)" detail={["parse, chunk Điều/Khoản,", "embed, ghi index_version mới"]} dashed />
        <Node x={540} y={410} w={204} h={40} name="CI/CD: GitHub Actions" dashed />

        <g className={line} strokeWidth={1.5} markerEnd="url(#arch-arrow)">
          <path d="M156 90 H226" />
          <path d="M340 100 V140" />
          <path d="M454 168 H540" />
          <path d="M340 196 V250" />
          <path d="M340 282 V340" />
          <path d="M106 370 V386" />
          <path d="M266 370 V386" />
          <path d="M428 370 V386" />
          <path d="M642 310 V208" />
          <path d="M540 355 H504" />
        </g>
      </svg>
    </div>
  );
}
