"""Parser cấu trúc văn bản pháp luật VN: Chương > Mục > Điều > Khoản > Điểm, từ text của `extract_text`.

Heuristic chính (PDF bị ngắt dòng cứng, DOCX thì sạch):
- Điều chỉ nhận khi là Điều kế tiếp: n+1, hoặc cùng n với hậu tố chữ kế tiếp (2 -> 2a -> 2b). Điều đầu phải là 1.
  `Điều N.` không phải kế tiếp và có N <= Điều cuối (mẫu biểu/phụ lục đánh số lại từ 1) => dừng parse;
  N lớn hơn kế tiếp (hụt số) => coi là dòng nối tiếp, không mất chữ. Dừng sớm hơn nếu gặp dòng khối ký/phụ lục.
- Khoản `N.` chỉ nhận khi N là khoản kế tiếp (1,2,3..); Điểm `x)` chỉ nhận khi x là chữ kế tiếp theo thứ tự
  a b c d đ e g h i k l m n o p q r s t u v x y (reset ở mỗi khoản). Còn lại là dòng nối tiếp, nối bằng 1 dấu cách.
  Điểm đứng trước mọi khoản được đặt vào Khoản không số (number=None, text rỗng).
- Dòng nằm trong trích dẫn “…” (văn bản sửa đổi) không bao giờ mở Khoản/Điểm mới; trạng thái trích dẫn reset ở mỗi Điều.
- Tiêu đề Điều có thể ngắt dòng (tối đa 3 dòng): dòng kế tiếp được nối vào tiêu đề nếu dòng tiêu đề trước không kết thúc
  bằng `. ; :`, dòng kế không giống khoản/điểm/Điều/Chương/Mục, không kết thúc bằng `. ; :`, và dòng kế bắt đầu bằng chữ
  thường (phần ngắt ở lề PDF) hoặc, với chữ hoa, dòng tiêu đề trước dài >= 60 ký tự (gồm "Điều N. "), kết thúc bằng từ
  viết hoa ("...Việt" / "Nam và...") và dòng kế < 60 ký tự. Còn lại là phần `intro` (thà giữ chữ ở intro còn hơn mất).
- Khối cuối bị bỏ khi gặp dòng ký (TM./KT./CHỦ TỊCH QUỐC HỘI/XÁC THỰC VĂN BẢN HỢP NHẤT/Nơi nhận), câu chốt "Luật này được
  Quốc hội nước Cộng hòa..." hoặc dòng đơn lẻ "Phụ lục [số La Mã]". Số ký tự bị bỏ trả về từ parse_document_with_stats.
- Chương/Mục: dòng `Chương IV` / `Mục 2` (hoặc kèm phần chữ HOA) + các dòng chữ HOA kế tiếp => "Chương IV. TÊN".
"""
import re
from dataclasses import dataclass, field

_POINTS = "abcdđeghiklmnopqrstuvxy"
_ARTICLE = re.compile(r"^Điều (\d+)([a-z]?)\.(?:\s+(.*))?$")
# Bản hợp nhất có chú thích cuối trang dính sau số khoản: "3.3 Người sử dụng..." (khoản 3, chú thích 3).
_CLAUSE = re.compile(r"^(\d+)\.(\d{1,2})?(?:\s+(.*))?$")
_POINT = re.compile(r"^([a-zđ])\)(?:\s+(.*))?$")
_CHAPTER = re.compile(r"^(Chương [IVXLC]+)\b\s*(.*)$")
_SECTION = re.compile(r"^(Mục \d+)\b\s*(.*)$")
# Khối ký / phụ lục / mẫu biểu sau Điều cuối (bảng DOCX có tiền tố "| ").
_END = re.compile(
    r"^(?:\|\s*)?(?:TM\.|KT\.|TUQ\.|CHỦ TỊCH QUỐC HỘI|VĂN PHÒNG QUỐC HỘI|XÁC THỰC VĂN BẢN HỢP NHẤT|Nơi nhận\b)"
    r"|^(?:Bộ luật|Luật) này (?:đã )?được Quốc hội nước Cộng hòa"
    r"|^(?:PHỤ LỤC|Phụ lục)(?:\s+[IVXLC\d]+)?$"
)
_TITLE_MIN_WRAP = 60
_TITLE_MAX_LINES = 3


@dataclass
class Point:
    letter: str
    text: str


@dataclass
class Clause:
    number: int | None
    text: str
    points: list[Point] = field(default_factory=list)


@dataclass
class Article:
    doc_code: str
    number: int
    suffix: str | None
    title: str
    chapter: str | None
    section: str | None
    intro: str
    clauses: list[Clause] = field(default_factory=list)


class _Open:
    """Điều đang dựng: các mảnh text theo vị trí, join bằng 1 dấu cách khi chốt."""

    def __init__(self, num: int, suffix: str, title: str, raw_len: int, chapter: str | None, section: str | None):
        self.num, self.suffix, self.chapter, self.section = num, suffix, chapter, section
        self.title = [title] if title else []
        self.title_raw_len = raw_len  # độ dài dòng tiêu đề cuối, gồm tiền tố "Điều N. "
        self.title_open = True
        self.intro: list[str] = []
        self.clauses: list[tuple[int | None, list[str], list[tuple[str, list[str]]]]] = []
        self.target = self.intro

    def numbered(self) -> int:
        return max((c[0] for c in self.clauses if c[0] is not None), default=0)

    def add_clause(self, n: int, text: str) -> None:
        self.target = [text] if text else []
        self.clauses.append((n, self.target, []))

    def add_point(self, letter: str, text: str) -> None:
        if not self.clauses:
            self.clauses.append((None, [], []))
        self.target = [text] if text else []
        self.clauses[-1][2].append((letter, self.target))

    def accepts_letter(self, letter: str) -> bool:
        pts = self.clauses[-1][2] if self.clauses else []
        i = _POINTS.index(pts[-1][0]) + 1 if pts else 0
        return letter == _POINTS[i:i + 1]

    def wants_title_line(self, line: str) -> bool:
        if not self.title or len(self.title) >= _TITLE_MAX_LINES:
            return False
        if self.title[-1][-1] in ".;:" or line[-1] in ".;:" or _looks_like_item(line):
            return False
        # Phần ngắt ở lề PDF gần như luôn bắt đầu bằng chữ thường; chữ hoa chỉ khi từ cuối dòng trước cũng viết hoa
        # (vd "...Mặt trận Tổ quốc Việt" / "Nam và các...") và dòng kế ngắn, tránh nuốt dòng đầu của intro.
        if line[0].islower():
            return True
        return self.title_raw_len >= _TITLE_MIN_WRAP and len(line) < _TITLE_MIN_WRAP and self.title[-1].split()[-1][:1].isupper()

    def build(self, code: str) -> Article:
        def j(parts: list[str]) -> str:
            return " ".join(parts).strip()

        clauses = [Clause(n, j(t), [Point(ltr, j(p)) for ltr, p in pts]) for n, t, pts in self.clauses]
        return Article(code, self.num, self.suffix or None, j(self.title), self.chapter, self.section, j(self.intro), clauses)


def _is_upper(line: str) -> bool:
    return any(c.isalpha() for c in line) and line == line.upper()


def _next_suffix(s: str) -> str:
    return "a" if not s else chr(ord(s) + 1)


def _looks_like_item(line: str) -> bool:
    return bool(_CLAUSE.match(line) or _POINT.match(line) or _ARTICLE.match(line) or _CHAPTER.match(line) or _SECTION.match(line))


def parse_document_with_stats(text: str, doc_code: str) -> tuple[list[Article], int]:
    """Trả (các Điều, số ký tự bị bỏ sau Điều cuối: khối ký, phụ lục, mẫu biểu)."""
    lines = [ln.strip() for ln in text.split("\n")]
    arts: list[Article] = []
    cur: _Open | None = None
    chapter = section = None
    last = (0, "")
    stop = len(lines)
    quote = 0  # độ sâu dấu ngoặc kép “…” còn mở
    i = 0

    def heading_name(i: int, rest: str) -> tuple[str, int]:
        parts = [rest] if rest else []
        while i < len(lines) and len(parts) < 4:
            ln = lines[i]
            if not ln and parts:
                break
            if ln and (not _is_upper(ln) or _looks_like_item(ln)):
                break
            if ln:
                parts.append(ln)
            i += 1
        return " ".join(parts), i

    while i < len(lines):
        line = lines[i]
        i += 1
        if not line:
            continue
        if cur and _END.match(line):
            stop = i - 1
            break
        m = _CHAPTER.match(line) or _SECTION.match(line)
        if m and (not m.group(2) or _is_upper(m.group(2))):
            name, i = heading_name(i, m.group(2))
            label = m.group(1) + (". " + name if name else "")
            if m.re is _CHAPTER:
                chapter, section = label, None
            else:
                section = label
            if cur:
                arts.append(cur.build(doc_code))
                cur = None
            continue
        m = _ARTICLE.match(line)
        if m:
            n, suf = int(m.group(1)), m.group(2)
            if (n == last[0] + 1 and not suf) or (last[0] > 0 and n == last[0] and suf == _next_suffix(last[1])):
                if cur:
                    arts.append(cur.build(doc_code))
                last = (n, suf)
                quote = 0
                cur = _Open(n, suf, m.group(3) or "", len(line), chapter, section)
                continue
            if 0 < last[0] and n <= last[0]:
                stop = i - 1
                break
        if cur is None:
            continue
        if cur.title_open:
            if cur.wants_title_line(line):
                cur.title.append(line)
                cur.title_raw_len = len(line)
                continue
            cur.title_open = False
        in_quote = quote > 0 or line.startswith("“")  # trích dẫn nguyên văn điều luật được sửa đổi
        quote = max(0, quote + line.count("“") - line.count("”"))
        m = None if in_quote else _CLAUSE.match(line)
        if m and int(m.group(1)) == cur.numbered() + 1 and (not m.group(2) or m.group(3)[:1].isupper()):
            cur.add_clause(int(m.group(1)), m.group(3) or "")
            continue
        m = None if in_quote else _POINT.match(line)
        if m and cur.accepts_letter(m.group(1)):
            cur.add_point(m.group(1), m.group(2) or "")
            continue
        cur.target.append(line)
    if cur:
        arts.append(cur.build(doc_code))
    return arts, len("\n".join(lines[stop:]))


def parse_document(text: str, doc_code: str) -> list[Article]:
    return parse_document_with_stats(text, doc_code)[0]
