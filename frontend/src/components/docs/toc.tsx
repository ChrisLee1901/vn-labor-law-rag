import type { ArticleItem } from "@/lib/api-types";
import { articleAnchor, articleHeading, type ChapterGroup } from "@/lib/docs-view";
import { cn, focusRing } from "@/lib/utils";

const link = cn("block py-0.5 leading-snug text-foreground hover:underline", focusRing);

function Item({ a }: { a: ArticleItem }) {
  return (
    <li>
      <a href={`#${articleAnchor(a)}`} className={link}>
        {articleHeading(a)}
      </a>
    </li>
  );
}

/** Mục lục Chương/Điều (+ Phụ lục). Liên kết neo thuần, không cần JS. */
export function TocList({ groups, appendices }: { groups: ChapterGroup[]; appendices: ArticleItem[] }) {
  return (
    <div className="space-y-4 text-sm">
      {groups.map((g, i) => (
        <section key={i}>
          {g.chapter && <h2 className="mb-1 text-sm font-semibold text-muted-foreground">{g.chapter}</h2>}
          <ol>
            {g.articles.map((a) => (
              <Item key={a.id} a={a} />
            ))}
          </ol>
        </section>
      ))}
      {appendices.length > 0 && (
        <section>
          <h2 className="mb-1 text-sm font-semibold text-muted-foreground">Phụ lục</h2>
          <ol>
            {appendices.map((a) => (
              <Item key={a.id} a={a} />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
