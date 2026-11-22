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
_LAW_BEFORE = re.compile(r"(?<!phap )\bluat\b[^,;.]{0,25}$")


def _date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def extract_as_of(q: str, today: date) -> date:
    """"từ 1/1/2027" -> 2027-01-01; "năm 2027" -> 2027-01-01 nếu năm > năm nay, ngược lại 31/12; mặc định `today`."""
    n = strip_diacritics(nfc(q)).lower()
    for m in _DMY.finditer(n):
        if d := _date(int(m[3]), int(m[2]), int(m[1])):
            return d
    for m in _LONG.finditer(n):
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
