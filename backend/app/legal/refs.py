"""Trích tham chiếu chéo giữa các điều khoản (regex, chỉ stdlib).

Dùng hai nơi: ingest (điền `legal_refs` từ text khoản/điểm/intro) và query (lấy ID pháp lý user nhắc trong câu hỏi).

Quy ước:
- `dst_doc_number`: số hiệu chuẩn nếu văn bản thuộc corpus; số hiệu như viết nếu có số mà ngoài corpus; nếu chỉ có tên
  ngoài corpus thì là tên ("Luật Bảo hiểm y tế"). Văn bản ngoài corpus => `dst_doc_code=None`.
- Tên corpus chỉ map theo tên khi KHÔNG kèm số/năm khác: "Luật Bảo hiểm xã hội số 58/2014/QH13" và "... năm 2014" là luật cũ.
- `self_doc`: "Nghị định này"/"Luật này"/"Điều N" trần (không nêu văn bản) => self_doc. Với `self_doc=None` (dùng khi query)
  các tham chiếu đó được GIỮ với `dst_doc_code=None, dst_doc_number=""` để caller tự suy ra từ ngữ cảnh.
- "Điều này"/"khoản N Điều này" và "khoản N"/"điểm a" không kèm Điều: bỏ (cùng Điều, không lưu).
- Liệt kê tách thành nhiều Ref; Điều/văn bản nêu ở cuối chuỗi áp cho cả các mục đứng trước nó nếu chúng chưa có.
- Tham chiếu chỉ nêu văn bản (không Điều): giữ khi văn bản thuộc corpus hoặc có số hiệu, trừ "X này".
- rel: từ khóa gần nhất đứng trước tham chiếu trong cùng câu ("quy định chi tiết"/"hướng dẫn" => details,
  "sửa đổi, bổ sung" => amends); không có thì từ khóa đứng sau; không có nữa => cites.
- Giới hạn đã biết (shortcut): bỏ Điều có hậu tố (4a) vì Ref không có chỗ lưu; "từ Điều 5 đến Điều 8" chỉ ra hai đầu mút;
  tên luật ngoài corpus cắt theo danh sách từ dừng nên có thể thiếu/thừa chữ.
"""
import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Literal

from app.legal.normalize import nfc

Rel = Literal["cites", "details", "amends"]


@dataclass(frozen=True)
class Ref:
    dst_doc_code: str | None
    dst_doc_number: str
    article: int | None
    clause: int | None
    point: str | None
    rel: Rel
    explicit_doc: bool = True  # False: văn bản đích được suy ra (Điều N trần => self_doc), không được nêu trong text


# code -> (số hiệu chuẩn, số hiệu khác, tên)
_DOCS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "BLLD": ("45/2019/QH14", ("18/VBHN-VPQH",), ("bộ luật lao động", "luật lao động")),
    "ND145-2020": ("145/2020/NĐ-CP", (), ()),
    "ND293-2025": ("293/2025/NĐ-CP", (), ()),
    "ND399-2026": ("399/2026/NĐ-CP", (), ()),
    "LBHXH-2024": ("41/2024/QH15", (), ("luật bảo hiểm xã hội",)),
    "ND158-2025": ("158/2025/NĐ-CP", (), ()),
    "LVL-2025": ("74/2025/QH15", (), ("luật việc làm",)),
    "ND374-2025": ("374/2025/NĐ-CP", (), ()),
}
DOC_NUMBERS = {c: v[0] for c, v in _DOCS.items()}
# Khóa chữ thường: tên, số hiệu đầy đủ, dạng ngắn "n/năm".
DOC_ALIASES: dict[str, str] = {
    k.lower(): code
    for code, (num, more, names) in _DOCS.items()
    for k in (num, num.rsplit("/", 1)[0], *more, *names)
}

_NUM = r"\d+/(?:\d{4}(?:/\s?[^\W\d_][\w-]*)?|[^\W\d_][\w-]+)"  # chấp nhận "128/2025/ NĐ-CP"
_KIND = re.compile(
    r"(?i:thông tư liên tịch|thông tư|bộ luật|luật|nghị định|nđ|nghị quyết|pháp lệnh|quyết định|hiến pháp|điều lệ|công ước|lệnh)\b"
)
_THIS = re.compile(r"\s+(?i:này)\b")
_NUMREF = re.compile(rf"\s+(?:(?i:số)\s+)?({_NUM})")
_YEAR = re.compile(r"\s+(?i:năm)\s+(\d{4})\b")
_WORD = re.compile(r"\s+([^\W\d_]+)")
# Cầu nối trước tên văn bản: "của", "Phụ lục I kèm theo của", "kèm theo".
_TO_DOC = re.compile(
    r"\s+(?:(?:(?i:và)\s+)?(?i:phụ lục)(?:\s+[IVXLC\d]+)?\s+)?(?:(?i:kèm theo)\s+)?(?:(?i:của|trong)\s+)?"
)
_NAMED_KINDS = {"luật", "bộ luật", "pháp lệnh", "điều lệ"}  # có tên không số; các loại khác (kể cả ngoài corpus) bắt buộc có số hiệu
_WINDOW = 80  # từ khóa rel phải nằm trong ngần này ký tự trước tham chiếu
# Tên ngoài corpus có dấu phẩy/"và" (danh sách từ dừng không cắt đúng được).
_EXT_NAMES = ("luật an toàn, vệ sinh lao động", "luật hôn nhân và gia đình", "luật thi đua, khen thưởng")
_STOP = frozenset(
    "năm số này và hoặc hay thì của được để quy có là mà sau trước theo thuộc do khi nếu cho với trong tại đã đang sẽ không "
    "các những về ngày sửa bổ hướng đối mới hiện hết từ đến nhưng cũng phải trừ bao như tính nên thực ban".split()
)

_SEP = r"(?:\s*,\s*(?:(?:và|hoặc)\s+)?|\s+(?:và|hoặc)\s+)"
_PT, _CL, _AR = r"[a-zđ]\b", r"\d+\b", r"\d+[a-z]?\b"
_UNIT = re.compile(
    r"(?<!\w)(?=(?i:điểm|khoản|điều)\s)"
    rf"(?:(?i:điểm)\s+(?P<pts>{_PT}(?:{_SEP}{_PT})*)(?:\s+(?:(?i:của)\s+)?(?=(?i:khoản|điều)\b))?)?"
    rf"(?:(?i:khoản)\s+(?P<cls>{_CL}(?:{_SEP}{_CL})*)(?:\s+(?:(?i:của)\s+)?(?=(?i:điều)\b))?)?"
    rf"(?:(?i:điều)\s+(?:(?P<arts>{_AR}(?:{_SEP}{_AR})*)|(?P<this>(?i:này)\b)))?"
)
_GAP = re.compile(r"\s*[,;]?\s*(?:(?i:và|hoặc|hay)\s+)?")
_ITEM_SPLIT = re.compile(r"\s*(?:,|\bvà\b|\bhoặc\b)\s*")
_SENT_END = re.compile(r"[.;]\s|\n")
_DETAILS = re.compile(r"quy định chi tiết|hướng dẫn", re.I)
_AMENDS = re.compile(r"sửa đổi,? bổ sung", re.I)


def _by_number(num: str, aliases: dict[str, str]) -> tuple[str | None, str]:
    num = re.sub(r"\s+", "", num)
    code = aliases.get(num.lower())
    return (code, DOC_NUMBERS.get(code, num)) if code else (None, num)


def _doc_at(text: str, low: str, pos: int, aliases: dict[str, str], self_doc: str | None):
    """Văn bản bắt đầu tại pos => (end, code, number, is_self, has_number), hoặc None."""
    k = _KIND.match(text, pos)
    if not k:
        return None
    if t := _THIS.match(text, k.end()):
        return t.end(), self_doc, DOC_NUMBERS.get(self_doc, ""), True, False
    if n := _NUMREF.match(text, k.end()):
        return (n.end(), *_by_number(n.group(1), aliases), False, True)
    for key in sorted((a for a in aliases if not a[0].isdigit()), key=len, reverse=True):
        end = pos + len(key)
        if not low.startswith(key, pos) or (end < len(low) and low[end].isalnum()):
            continue
        code = aliases[key]
        if n := _NUMREF.match(text, end):  # số hiệu đi kèm quyết định hơn tên
            return (n.end(), *_by_number(n.group(1), aliases), False, True)
        if y := _YEAR.match(text, end):
            end = y.end()
            cy = re.search(r"/(\d{4})/", f"/{DOC_NUMBERS.get(code, '')}/")
            if cy and cy.group(1) != y.group(1):
                return end, None, text[pos:end], False, False
        return end, code, DOC_NUMBERS.get(code, text[pos:end]), False, False
    for name in _EXT_NAMES:
        if low.startswith(name, pos):
            return pos + len(name), None, text[pos : pos + len(name)], False, False
    kind = k.group().lower()
    if kind == "hiến pháp":
        return k.end(), None, text[pos : k.end()], False, False
    if kind in _NAMED_KINDS and (k.group()[0].isupper() or kind == "điều lệ"):  # tên ngoài corpus: "Luật Bảo hiểm y tế"
        end, words = k.end(), 0
        while (w := _WORD.match(text, end)) and words < 8:
            word = w.group(1)
            if word.lower() in _STOP or (words == 0 and not word[0].isupper() and kind != "điều lệ"):
                break
            end, words = w.end(), words + 1
        if words:
            if n := _NUMREF.match(text, end):
                return (n.end(), *_by_number(n.group(1), aliases), False, True)
            return end, None, text[pos:end], False, False
    return None


def _expand(u: dict) -> list[tuple[int, int | None, str | None]]:
    split = lambda s: [x for x in _ITEM_SPLIT.split(s) if x]  # noqa: E731
    cls = [int(c) for c in split(u["cls"])] if u["cls"] else [None]
    pts = split(u["pts"]) if u["pts"] else [None]
    return [(int(a), c, p) for a in split(u["arts"]) if a.isdigit() for c in cls for p in pts]


class _RelIndex:
    """Ranh giới câu và từ khóa tính một lần cho cả text => mỗi tra cứu O(log n)."""

    def __init__(self, text: str):
        self.ends = [m.end() for m in _SENT_END.finditer(text)]
        self.kw = sorted(
            [(m.start(), m.end(), "details") for m in _DETAILS.finditer(text)]
            + [(m.start(), m.end(), "amends") for m in _AMENDS.finditer(text)]
        )
        self.kw_ends = [k[1] for k in self.kw]

    def rel(self, start: int) -> Rel:
        """Từ khóa gần nhất đứng trước `start`, cùng câu, trong _WINDOW ký tự; không có => cites."""
        i = bisect_right(self.ends, start)
        lo = self.ends[i - 1] if i else 0
        i = bisect_right(self.kw_ends, start) - 1
        if i >= 0 and self.kw[i][0] >= lo and start - self.kw_ends[i] <= _WINDOW:
            return self.kw[i][2]
        return "cites"


def extract_refs(text: str, self_doc: str | None = None, aliases: dict[str, str] = DOC_ALIASES) -> list[Ref]:
    text = nfc(text)
    low = text.lower()
    rels = _RelIndex(text)
    units: list[dict] = []
    doc_spans: list[tuple[int, int]] = []
    pos = 0
    while m := _UNIT.search(text, pos):
        pos = max(m.end(), m.start() + 1)
        if not (m["pts"] or m["cls"] or m["arts"] or m["this"]):
            continue
        u = {"start": m.start(), "end": m.end(), "pts": m["pts"], "cls": m["cls"], "arts": m["arts"], "this": bool(m["this"]), "doc": None}
        if u["arts"] and (to := _TO_DOC.match(text, m.end())) and (d := _doc_at(text, low, to.end(), aliases, self_doc)):
            u["doc"], u["end"] = d, d[0]
            doc_spans.append((to.end(), d[0]))
            pos = d[0]
        units.append(u)

    # Chuỗi liệt kê ("khoản 1 và khoản 2 Điều 5 Luật X") thừa kế phần thiếu từ mục đứng sau.
    for u, v in reversed(list(zip(units, units[1:]))):
        if not _GAP.fullmatch(text, u["end"], v["start"]):
            continue
        if not (u["arts"] or u["this"]):
            if u["pts"] and not u["cls"]:
                u["cls"] = v["cls"]
            u["arts"], u["this"] = v["arts"], v["this"]
        u["doc"] = u["doc"] or v["doc"]

    out: list[tuple[int, Ref]] = []
    for u in units:
        if u["this"] or not u["arts"]:
            continue
        _, code, number, is_self, _ = u["doc"] or (0, self_doc, DOC_NUMBERS.get(self_doc, ""), True, False)
        explicit = bool(u["doc"]) and not (is_self and self_doc is None)
        rel = rels.rel(u["start"])
        out += [(u["start"], Ref(code, number, a, c, p, rel, explicit)) for a, c, p in _expand(u)]

    for k in _KIND.finditer(text):  # tham chiếu chỉ nêu văn bản
        if any(s <= k.start() < e for s, e in doc_spans) or (k.start() and text[k.start() - 1].isalnum()):
            continue
        d = _doc_at(text, low, k.start(), aliases, self_doc)
        if d and not d[3] and (d[1] or d[4]) and (d[1] is None or d[1] != self_doc):
            out.append((k.start(), Ref(d[1], d[2], None, None, None, "cites")))

    refs: dict[Ref, None] = {}
    for _, r in sorted(out, key=lambda x: x[0]):
        refs.setdefault(r)
    return list(refs)
