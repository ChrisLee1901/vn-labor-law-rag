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

interface MdNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
}

// Chỉ đổi mã trong nút `text`: mã trong `inlineCode`/`code` là nút khác, còn chữ trong liên kết thì không đi vào.
const SKIP = new Set(["link", "linkReference", "inlineCode", "code", "definition", "html"]);

function rewrite(node: MdNode) {
  if (!node.children || SKIP.has(node.type)) return;
  node.children = node.children.flatMap((child): MdNode[] => {
    if (child.type !== "text" || child.value === undefined) {
      rewrite(child);
      return [child];
    }
    const segs = splitCitations(child.value);
    if (!segs.some((s) => s.kind === "cite")) return [child];
    return segs.map((s) =>
      s.kind === "text"
        ? { type: "text", value: s.text }
        : { type: "link", url: `${CITE_HREF_PREFIX}${s.id}`, children: [{ type: "text", value: s.id }] },
    );
  });
}

/** Remark plugin: `[S1]` trong văn bản thường -> liên kết nội bộ `#cite-S1`; component `a` dựng nút Citation. */
export function remarkCitations() {
  return (tree: MdNode) => rewrite(tree);
}
