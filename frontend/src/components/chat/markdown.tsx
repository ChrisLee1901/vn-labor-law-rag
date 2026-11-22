"use client";

import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CITE_HREF_PREFIX, citationsToMarkdown } from "@/lib/citations";
import { focusRing } from "@/lib/utils";
import { Citation } from "./citation";

const linkCls = `text-primary underline underline-offset-4 ${focusRing}`;

/** Chỉ cho phép: liên kết nội bộ /van-ban/, http(s) ngoài (mở tab mới), mã trích dẫn. Không ảnh, không HTML thô. */
const components: Components = {
  a({ href = "", children }) {
    if (href.startsWith(CITE_HREF_PREFIX)) return <Citation id={href.slice(CITE_HREF_PREFIX.length)} />;
    if (href.startsWith("/van-ban/"))
      return (
        <Link href={href} className={linkCls}>
          {children}
        </Link>
      );
    if (/^https?:\/\//i.test(href))
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className={linkCls}>
          {children}
        </a>
      );
    return <span>{children}</span>;
  },
  img: () => null,
  p: ({ children }) => <p className="my-3 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1.5 pl-5">{children}</ol>,
  h1: ({ children }) => <h3 className="mt-5 mb-2 text-base font-semibold">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-5 mb-2 text-base font-semibold">{children}</h3>,
  h3: ({ children }) => <h3 className="mt-5 mb-2 text-base font-semibold">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-4 mb-1.5 text-base font-semibold">{children}</h4>,
  blockquote: ({ children }) => <blockquote className="my-3 border-l-2 border-cite-border pl-3 text-muted-foreground">{children}</blockquote>,
  code: ({ children }) => <code className="rounded-sm bg-muted px-1 py-0.5 text-[0.9em]">{children}</code>,
  pre: ({ children }) => <pre className="my-3 overflow-x-auto rounded-md bg-muted p-3 text-sm">{children}</pre>,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-border px-2 py-1 align-top">{children}</td>,
};

export function AnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="max-w-(--measure) text-base leading-relaxed wrap-anywhere">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {citationsToMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}
