import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DocsError } from "@/components/docs/docs-error";
import { HashHighlight } from "@/components/docs/hash-highlight";
import { MobileToc } from "@/components/docs/mobile-toc";
import { TocList } from "@/components/docs/toc";
import { EffectivenessBadge } from "@/components/effectiveness-badge";
import type { ArticleItem, DocDetailResponse } from "@/lib/api-types";
import { fetchDocDetail, fetchDocs } from "@/lib/api-server";
import { effectiveness, vnDate } from "@/lib/docs-cache";
import { articleAnchor, articleHeading, DOC_TYPE_LABEL, groupByChapter, isValidDocCode } from "@/lib/docs-view";
import { cn, focusRing } from "@/lib/utils";

// Render theo yêu cầu (không phải ISR), dữ liệu trúng Data Cache 1 giờ nhờ `next.revalidate` trong api-server.ts.
// Không thêm `cache: "no-store"`/`fetchCache`: sẽ tắt cache đó. Chi tiết ở van-ban/page.tsx.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ code: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { code } = await params;
  if (!isValidDocCode(code)) return { title: "Không tìm thấy văn bản" };
  try {
    const res = await fetchDocDetail(code);
    if (!res) return { title: "Không tìm thấy văn bản" };
    const { doc } = res;
    return {
      title: `${doc.number ?? code} — Văn bản`,
      description: `${doc.title ?? doc.number ?? code}. Hiệu lực từ ${vnDate(doc.effective_from)}.`,
    };
  } catch {
    return { title: "Văn bản" };
  }
}

const isHttpUrl = (u: string) => /^https?:\/\//i.test(u);

/** Số hiệu của văn bản thay thế (tra từ danh sách đã cache); không tra được thì dùng mã. */
async function replacementNumber(code: string): Promise<string> {
  try {
    return (await fetchDocs()).find((d) => d.code === code)?.number ?? code;
  } catch {
    return code;
  }
}

export default async function DocPage({ params }: Props) {
  const { code } = await params;
  if (!isValidDocCode(code)) notFound();

  let res: DocDetailResponse | null = null;
  try {
    res = await fetchDocDetail(code);
  } catch {
    return <DocsError message="Không tải được văn bản. Vui lòng thử lại sau." retryHref={`/van-ban/${code}`} />;
  }
  if (!res) notFound();

  const { doc, articles } = res;
  const groups = groupByChapter(articles);
  const appendices = articles.filter((a) => a.kind === "phu_luc");
  const replacedBy = doc.replaced_by && isValidDocCode(doc.replaced_by) ? doc.replaced_by : null;
  const replacedNumber = replacedBy ? await replacementNumber(replacedBy) : null;
  const toc = <TocList groups={groups} appendices={appendices} />;

  return (
    <div className="space-y-8">
      <HashHighlight />
      <header className="space-y-3">
        <Link href="/van-ban" className={cn("text-sm font-medium text-primary underline underline-offset-4", focusRing)}>
          Tất cả văn bản
        </Link>
        <div className="space-y-1">
          {doc.number && <p className="text-sm font-medium text-muted-foreground">{doc.number}</p>}
          <h1 className="text-2xl [overflow-wrap:anywhere] sm:text-3xl">{doc.title ?? doc.number ?? doc.code}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <EffectivenessBadge eff={effectiveness(doc)} />
          {replacedBy && (
            <span className="text-sm">
              Được thay thế bởi{" "}
              <Link href={`/van-ban/${replacedBy}`} className={cn("font-medium text-primary underline underline-offset-4", focusRing)}>
                {replacedNumber}
              </Link>
            </span>
          )}
        </div>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <Meta label="Loại" value={DOC_TYPE_LABEL[doc.doc_type]} />
          {doc.issuer && <Meta label="Cơ quan ban hành" value={doc.issuer} />}
          {doc.issued_on && <Meta label="Ngày ban hành" value={vnDate(doc.issued_on)} />}
          <Meta label="Hiệu lực từ" value={vnDate(doc.effective_from)} />
          {doc.effective_to && <Meta label="Hết hiệu lực từ" value={vnDate(doc.effective_to)} />}
        </dl>
        {doc.source_url && isHttpUrl(doc.source_url) && (
          <a
            href={doc.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("inline-block text-sm font-medium text-primary underline underline-offset-4", focusRing)}
          >
            Nguồn văn bản gốc (mở tab mới)
          </a>
        )}
      </header>

      <div className="lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-10">
        <MobileToc>{toc}</MobileToc>
        <nav
          aria-label="Mục lục"
          className="sticky top-4 hidden max-h-[calc(100dvh-2rem)] self-start overflow-y-auto pr-2 lg:block"
        >
          <p className="mb-3 font-semibold">Mục lục</p>
          {toc}
        </nav>

        <div className="min-w-0 space-y-10">
          {groups.map((g, i) => (
            <section key={i} className="space-y-6">
              {g.chapter && <h2 className="text-xl">{g.chapter}</h2>}
              {g.articles.map((a) => (
                <ArticleBlock key={a.id} a={a} />
              ))}
            </section>
          ))}
          {appendices.length > 0 && (
            <section className="space-y-6">
              <h2 className="text-xl">Phụ lục</h2>
              {appendices.map((a) => (
                <ArticleBlock key={a.id} a={a} />
              ))}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground">{label}:</dt>
      <dd>{value}</dd>
    </div>
  );
}

function ArticleBlock({ a }: { a: ArticleItem }) {
  return (
    <article
      id={articleAnchor(a)}
      className="group/art scroll-mt-4 border-l-2 border-transparent pl-4 transition-colors [contain-intrinsic-size:auto_10rem] [content-visibility:auto] target:border-cite-foreground data-[active=true]:bg-cite"
    >
      <h3 className="text-base [overflow-wrap:anywhere] group-target/art:underline group-target/art:decoration-cite-foreground group-target/art:decoration-2 group-target/art:underline-offset-4">
        {articleHeading(a)}
      </h3>
      <p className="mt-2 max-w-[var(--measure)] whitespace-pre-line [overflow-wrap:anywhere]">{a.content}</p>
    </article>
  );
}
