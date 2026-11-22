import type { Metadata } from "next";
import Link from "next/link";
import { DocsError } from "@/components/docs/docs-error";
import { EffectivenessBadge } from "@/components/effectiveness-badge";
import type { DocSummary } from "@/lib/api-types";
import { fetchDocs } from "@/lib/api-server";
import { effectiveness, vnDate } from "@/lib/docs-cache";
import { DOC_TYPE_LABEL, sortDocs } from "@/lib/docs-view";
import { cn, focusRing } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Văn bản pháp luật",
  description: "Các văn bản pháp luật lao động và bảo hiểm xã hội dùng làm căn cứ cho câu trả lời.",
};

// Render theo yêu cầu: không gọi API lúc build (build offline vẫn qua) và không đóng băng thẻ lỗi vào trang tĩnh.
// Dữ liệu vẫn được cache 1 giờ ở tầng fetch (`next.revalidate`, xem api-server.ts).
export const dynamic = "force-dynamic";

function DocCard({ doc, now }: { doc: DocSummary; now: Date }) {
  return (
    <li className="space-y-3 rounded-md border bg-card p-4">
      <div className="space-y-1">
        {doc.number && <p className="text-sm font-medium text-muted-foreground">{doc.number}</p>}
        <h2 className="text-lg leading-snug">
          <Link href={`/van-ban/${doc.code}`} className={cn("underline-offset-4 hover:underline", focusRing)}>
            {doc.title ?? doc.number ?? doc.code}
          </Link>
        </h2>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
        <EffectivenessBadge eff={effectiveness(doc, now)} />
        <span>{DOC_TYPE_LABEL[doc.doc_type]}</span>
        <span>Hiệu lực từ {vnDate(doc.effective_from)}</span>
        <span>{doc.articles} Điều</span>
      </div>
    </li>
  );
}

export default async function DocsPage() {
  let docs: DocSummary[] | null = null;
  try {
    docs = await fetchDocs();
  } catch {
    // hiện thẻ lỗi bên dưới
  }
  const now = new Date();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl sm:text-3xl">Văn bản pháp luật</h1>
        <p className="max-w-[var(--measure)] text-muted-foreground">
          Các văn bản trợ lý dùng làm căn cứ. Đang hiệu lực xếp trước, trong mỗi nhóm văn bản mới nhất xếp trước.
        </p>
      </header>
      {docs && docs.length > 0 ? (
        <ul className="grid gap-4 sm:grid-cols-2">
          {sortDocs(docs, now).map((d) => (
            <DocCard key={d.code} doc={d} now={now} />
          ))}
        </ul>
      ) : (
        <DocsError message="Không tải được danh sách văn bản. Vui lòng thử lại sau." retryHref="/van-ban" />
      )}
    </div>
  );
}
