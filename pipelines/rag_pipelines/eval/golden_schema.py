"""Schema + validator cho golden set (eval/golden/v1.jsonl)."""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from app.legal.ids import make_appendix_id, make_id

from rag_pipelines.extract import extract_text
from rag_pipelines.structure import Article, parse_appendices, parse_document

ROOT = Path(__file__).resolve().parents[3]
QUOTA = {
    "single": 42,
    "numeric": 18,
    "multi_hop": 18,
    "temporal": 6,
    "compare": 12,
    "unanswerable": 12,
    "out_of_domain": 6,
    "injection": 6,
}
TYPES = tuple(QUOTA)
NO_GOLD = {"unanswerable", "out_of_domain", "injection"}
TOTAL, DEV, TEST = 120, 40, 80
MAX_JACCARD = 0.6
TOL_PP = 3.0  # độ lệch tỷ lệ cho phép (điểm %)


@dataclass
class GoldItem:
    id: str
    question: str
    answer: str
    gold: list[str]
    type: str
    as_of: str
    split: str
    source_quote: str


def load_golden(path) -> list[GoldItem]:
    items = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        d = json.loads(line)
        try:
            if set(d) != set(GoldItem.__dataclass_fields__):
                raise ValueError(f"fields {sorted(d)}")
            for k in (
                "id",
                "question",
                "answer",
                "type",
                "as_of",
                "split",
                "source_quote",
            ):
                if not isinstance(d[k], str):
                    raise ValueError(f"{k} must be str")
            if not (
                isinstance(d["gold"], list)
                and all(isinstance(g, str) for g in d["gold"])
            ):
                raise ValueError("gold must be list[str]")
            if d["type"] not in TYPES or d["split"] not in ("dev", "test"):
                raise ValueError("bad type/split")
            if not re.fullmatch(r"\d{4}-\d\d-\d\d", d["as_of"]):
                raise ValueError("as_of must be YYYY-MM-DD")
            date.fromisoformat(d["as_of"])
            if bool(d["gold"]) == (d["type"] in NO_GOLD):
                raise ValueError(
                    "gold must be empty iff unanswerable/out_of_domain/injection"
                )
        except (ValueError, KeyError) as e:
            raise ValueError(f"{path}:{n}: {e}") from e
        items.append(GoldItem(**d))
    return items


@lru_cache(maxsize=1)
def load_corpus() -> dict[str, tuple[list[Article], list]]:
    """code -> (articles, appendices) theo thứ tự legal_docs.yaml."""
    docs = yaml.safe_load(
        (ROOT / "docs/corpus/legal_docs.yaml").read_text(encoding="utf-8")
    )["docs"]
    out = {}
    for d in docs:
        text = extract_text(d["code"])
        out[d["code"]] = (
            parse_document(text, d["code"]),
            parse_appendices(text, d["code"]) if d.get("keep_appendix") else [],
        )
    return out


@lru_cache(maxsize=1)
def valid_ids() -> frozenset[str]:
    ids: set[str] = set()
    for code, (arts, apps) in load_corpus().items():
        for a in arts:
            ids.add(make_id(code, a.number, suffix=a.suffix))
            for c in a.clauses:
                if c.number is None:
                    continue
                ids.add(make_id(code, a.number, c.number, suffix=a.suffix))
                ids |= {
                    make_id(code, a.number, c.number, p.letter, a.suffix)
                    for p in c.points
                }
        ids |= {
            make_appendix_id(code, ap.number, n) for ap in apps for n, _, _ in ap.items
        }
    return frozenset(ids)


def syllable_jaccard(a: str, b: str) -> float:
    tok = lambda s: set(re.findall(r"\w+", unicodedata.normalize("NFC", s).lower()))  # noqa: E731
    x, y = tok(a), tok(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def validate_set(items: list[GoldItem], ids=None) -> list[str]:
    ids = valid_ids() if ids is None else ids
    errs: list[str] = []
    for it in items:
        errs += [f"{it.id}: unknown gold id {g}" for g in it.gold if g not in ids]
        if (j := syllable_jaccard(it.question, it.source_quote)) > MAX_JACCARD:
            errs.append(
                f"{it.id}: jaccard {j:.2f} > {MAX_JACCARD} (question copies source_quote)"
            )
    n = len(items)
    if n != TOTAL:
        errs.append(f"total {n} != {TOTAL}")
    count = lambda *ts: sum(i.type in ts for i in items)  # noqa: E731
    groups = [(t,) for t in QUOTA if t not in ("out_of_domain", "injection")] + [
        ("out_of_domain", "injection")
    ]
    for g in groups:
        want = sum(QUOTA[t] for t in g) / TOTAL * 100
        got = count(*g) / n * 100 if n else 0.0
        if abs(got - want) > TOL_PP:
            errs.append(f"quota {'+'.join(g)}: {got:.1f}% vs {want:.1f}% (±{TOL_PP}pp)")
    dev = sum(i.split == "dev" for i in items)
    if (dev, n - dev) != (DEV, TEST):
        errs.append(f"split dev/test {dev}/{n - dev} != {DEV}/{TEST}")
    for t in TYPES:
        k = count(t)
        d = sum(i.type == t and i.split == "dev" for i in items)
        if abs(d - k / 3) > 1:
            errs.append(f"stratification {t}: dev {d} of {k} (want ~{k / 3:.1f} ±1)")
    return errs
