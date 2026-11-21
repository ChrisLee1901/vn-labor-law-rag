"""Suy ra ngày hiệu lực (`as_of`) mà người dùng hỏi từ câu hỏi."""
import re
from datetime import date

_FULL = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
_YEAR = re.compile(r"\bnăm\s+(\d{4})\b", re.IGNORECASE)
_LAW_BEFORE = re.compile(r"luật|nghị định|thông tư|số", re.IGNORECASE)


def extract_as_of(q: str, today: date) -> date:
    """"từ 1/1/2027" -> 2027-01-01; "năm 2027" -> 2027-01-01 nếu năm > năm nay, ngược lại 31/12; mặc định `today`."""
    for m in _FULL.finditer(q):
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            continue
    for m in _YEAR.finditer(q):
        y = int(m.group(1))
        # "Luật BHXH năm 2014" là tên văn bản, không phải thời điểm hỏi.
        if not 1990 <= y <= 2100 or _LAW_BEFORE.search(q[max(0, m.start() - 40) : m.start()]):
            continue
        return date(y, 1, 1) if y > today.year else date(y, 12, 31)
    return today
