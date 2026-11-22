"""Che thông tin cá nhân trước khi ghi trace."""

import re

MASK = "[đã ẩn]"
_EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
_PHONE = r"(?<!\d)(?:\+84|0)\d{9,10}(?!\d)"
_ID = r"(?<!\d)(?:\d{12}|\d{9})(?!\d)"  # CCCD 12 số, CMND 9 số
_PII = re.compile(f"{_EMAIL}|{_PHONE}|{_ID}")


def redact_pii(s: str) -> str:
    return _PII.sub(MASK, s)
