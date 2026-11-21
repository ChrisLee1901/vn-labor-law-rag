"""Chuẩn hóa Unicode dùng chung cho ingest và query."""
import unicodedata


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def strip_diacritics(s: str) -> str:
    d = unicodedata.normalize("NFD", s)
    d = "".join(c for c in d if not unicodedata.combining(c))
    return nfc(d.replace("đ", "d").replace("Đ", "D"))
