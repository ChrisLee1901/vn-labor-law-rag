/** Tách các mã trích dẫn `[S1]`, `[S1][S2]`, `[S1, S2]` khỏi văn bản câu trả lời. */
export type CitationSegment = { kind: "text"; text: string } | { kind: "cite"; id: string };

const TOKEN = /\[(S\d+(?:\s*,\s*S\d+)*)\]/g;

export function splitCitations(text: string): CitationSegment[] {
  const out: CitationSegment[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    if (m.index > last) out.push({ kind: "text", text: text.slice(last, m.index) });
    for (const id of m[1].split(",")) out.push({ kind: "cite", id: id.trim() });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

export const CITE_HREF_PREFIX = "#cite-";

/** Đổi mã trích dẫn thành liên kết markdown nội bộ `[S1](#cite-S1)`; component `a` sẽ dựng nút Citation. */
export function citationsToMarkdown(text: string): string {
  return splitCitations(text)
    .map((s) => (s.kind === "text" ? s.text : `[${s.id}](${CITE_HREF_PREFIX}${s.id})`))
    .join("");
}
