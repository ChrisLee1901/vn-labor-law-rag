"""Câu hỏi -> chuỗi hợp lệ cho `to_tsquery('simple', …)` (OR giữa các từ, cụm trong "…" nối bằng `<->`)."""
import re

from app.legal.normalize import nfc, strip_diacritics

_STOP_ACCENTED = frozenset(
    ["của", "và", "là", "các", "những", "được", "có", "cho", "với", "thì", "mà", "này", "đó", "khi", "nào", "gì", "bao", "nhiêu", "không", "tôi", "em", "ạ", "ơi", "nhé", "hay", "hoặc"]
)
# Truy vấn không dấu cũng bỏ từ dừng tương ứng, trừ những từ trùng với từ nội dung: "tôi"~"tối", "có"~"co", "mà"~"ma", "đó"~"do", "ạ"~"a".
_AMBIGUOUS = {"toi", "co", "ma", "do", "a"}
STOPWORDS = _STOP_ACCENTED | ({strip_diacritics(w) for w in _STOP_ACCENTED} - _AMBIGUOUS)

_PHRASE = re.compile(r'"([^"]*)"')
_TOKEN = re.compile(r"\w+")  # chữ/số/_ ; mọi ký tự đặc biệt của tsquery (& | ! ( ) : * < > ' \) đều bị loại
MAX_TERMS = 64


def build_tsquery(q: str) -> str | None:
    q = nfc(q).lower()
    parts: list[str] = []
    for m in _PHRASE.finditer(q):
        toks = _TOKEN.findall(m.group(1))
        if toks:
            parts.append(" <-> ".join(toks))
    for tok in _TOKEN.findall(_PHRASE.sub(" ", q)):
        if tok not in STOPWORDS:
            parts.append(tok)
    return " | ".join(parts[:MAX_TERMS]) or None
