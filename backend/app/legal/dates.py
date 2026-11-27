"""Suy ra ngày hiệu lực (`as_of`) mà người dùng hỏi từ câu hỏi."""

import re
from datetime import date

from app.legal.normalize import nfc, strip_diacritics

# Chạy trên văn bản đã NFC + bỏ dấu + chữ thường, nên hỗ trợ cả câu hỏi không dấu.
_DMY = re.compile(r"(?<![\d/.-])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?![\d/.-])")
_LONG = re.compile(r"\b(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})\b")
_MONTH = re.compile(r"\bthang\s+(\d{1,2})\s*(?:/|\s+nam\s+)(\d{4})\b")
_YEAR = re.compile(r"\bnam\s+(\d{4})\b")
# "Luật BHXH năm 2014" là tên văn bản: "luật" (không phải "pháp luật") cách "năm" tối đa 25 ký tự, không ngắt mệnh đề.
_LAW_BEFORE = re.compile(
    r"(?<!phap )(?:\bluat\b|\b(?:nghi dinh|thong tu)\s+(?:so\s+)?\d)[^,;.]{0,25}$"
)
# Ngày ban hành ngay sau số hiệu ("145/2020/NĐ-CP ngày 14/12/2020") không phải ngày tra cứu.
_CITED = re.compile(
    r"\d+/\d{4}/[a-zđ0-9-]+[\s,]*(?:ngay\s*)?"
    r"(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+\d{4})"
)


def _date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def extract_as_of(q: str, today: date) -> date:
    """ "từ 1/1/2027" -> 2027-01-01; "năm 2027" -> 2027-01-01 nếu năm > năm nay, ngược lại 31/12; mặc định `today`."""
    n = strip_diacritics(nfc(q)).lower()
    n = _CITED.sub(" ", n)
    for rx in (_DMY, _LONG):
        for m in rx.finditer(n):
            if d := _date(int(m[3]), int(m[2]), int(m[1])):
                return d
    for m in _MONTH.finditer(n):
        if d := _date(int(m[2]), int(m[1]), 1):
            return d
    for m in _YEAR.finditer(n):
        y = int(m[1])
        if 1990 <= y <= 2100 and not _LAW_BEFORE.search(n[: m.start()]):
            return date(y, 1, 1) if y > today.year else date(y, 12, 31)
    return today
