"use client";

import { useEffect, useState } from "react";
import { EffectivenessBadge } from "@/components/effectiveness-badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  articleFor,
  effectiveness,
  excerpt,
  getDocDetail,
  getDocs,
  parseSourceUrl,
  type Effectiveness,
} from "@/lib/docs-cache";

/** Badge hiệu lực của văn bản chứa nguồn; không hiện gì nếu chưa tra được. */
export function SourceEffectiveness({ url, className }: { url: string; className?: string }) {
  const code = parseSourceUrl(url)?.code;
  const [eff, setEff] = useState<Effectiveness | null>(null);

  useEffect(() => {
    if (!code) return;
    let alive = true;
    getDocs()
      .then((docs) => {
        const doc = docs.find((d) => d.code === code);
        if (alive && doc) setEff(effectiveness(doc));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [code]);

  return eff ? <EffectivenessBadge eff={eff} className={className} /> : null;
}

/** Trích ~300 ký tự đầu của điều luật, tải khi cần. Đang tải: skeleton; lỗi hoặc không thấy: không hiện gì. */
export function SourceExcerpt({ url }: { url: string }) {
  const ref = parseSourceUrl(url);
  const code = ref?.code;
  const [state, setState] = useState<{ url: string; text: string | null } | null>(null);

  useEffect(() => {
    if (!ref) return;
    let alive = true;
    getDocDetail(ref.code)
      .then(({ articles }) => {
        const a = articleFor(articles, ref);
        if (alive) setState({ url, text: a ? excerpt(a.content) : null });
      })
      .catch(() => alive && setState({ url, text: null }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ref được suy ra từ url
  }, [url]);

  if (!code) return null;
  if (state?.url !== url)
    return (
      <div className="space-y-1.5" aria-hidden>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-11/12" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    );
  return state.text ? <p className="text-sm leading-relaxed text-muted-foreground">{state.text}</p> : null;
}
