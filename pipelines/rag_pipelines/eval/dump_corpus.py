"""Dump corpus đã parse ra markdown cho bước sinh golden set.
Chạy: python -m rag_pipelines.eval.dump_corpus [--out eval/golden/_work]"""
import argparse
import sys
from pathlib import Path

from app.legal.ids import make_appendix_id, make_id
from app.legal.refs import extract_refs

from rag_pipelines.eval.golden_schema import ROOT, load_corpus, valid_ids


def _texts(code: str, a):
    """(id nguồn, text) cho intro, khoản, điểm của một Điều."""
    aid = make_id(code, a.number, suffix=a.suffix)
    yield aid, a.intro
    for c in a.clauses:
        cid = make_id(code, a.number, c.number, suffix=a.suffix) if c.number is not None else aid
        yield cid, c.text
        for p in c.points:
            yield (make_id(code, a.number, c.number, p.letter, a.suffix) if c.number is not None else cid), p.text


def dump(out: Path, codes: list[str] | None = None) -> dict[str, int]:
    """Ghi <code>.md (chỉ `codes` nếu có) và refs_pairs.md; trả về kích thước file."""
    out.mkdir(parents=True, exist_ok=True)
    ids = valid_ids()
    sizes: dict[str, int] = {}
    pairs: dict[str, None] = {}
    for code, (arts, apps) in load_corpus().items():
        lines: list[str] = []
        for a in arts:
            aid = make_id(code, a.number, suffix=a.suffix)
            lines += [f"## {aid} — Điều {a.number}{a.suffix or ''}. {a.title}", ""]
            if a.intro:
                lines.append(a.intro)
            for c in a.clauses:
                if c.number is None:
                    if c.text:
                        lines.append(c.text)
                else:
                    lines.append(f"[{make_id(code, a.number, c.number, suffix=a.suffix)}] {c.text}")
                for p in c.points:
                    pid = make_id(code, a.number, c.number, p.letter, a.suffix) if c.number is not None else aid
                    lines.append(f"[{pid}] {p.letter}) {p.text}")
            lines.append("")
            for src, text in _texts(code, a):
                for r in extract_refs(text, self_doc=code):
                    if r.explicit_doc and r.dst_doc_code and r.dst_doc_code != code and r.article is not None:
                        dst = make_id(r.dst_doc_code, r.article)
                        if dst in ids:
                            pairs.setdefault(f"{src} -> {dst} ({r.rel})")
        for ap in apps:
            lines += [f"## {make_appendix_id(code, ap.number)} — Phụ lục {ap.number}. {ap.title}", ""]
            lines += [f"[{make_appendix_id(code, ap.number, n)}] {head}: {body}" for n, head, body in ap.items]
        if codes is None or code in codes:
            (out / f"{code}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            sizes[f"{code}.md"] = (out / f"{code}.md").stat().st_size
    (out / "refs_pairs.md").write_text("\n".join(pairs) + "\n", encoding="utf-8")
    sizes["refs_pairs.md"] = (out / "refs_pairs.md").stat().st_size
    return sizes


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "eval/golden/_work")
    for name, size in dump(ap.parse_args(argv).out).items():
        print(f"{name}\t{size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
