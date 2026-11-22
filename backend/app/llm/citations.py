"""Kiểm tra trích dẫn xác định (không dùng LLM) và ngưỡng từ chối."""
import logging
import re
import unicodedata
from dataclasses import dataclass

from app.legal.ids import is_appendix_id
from app.retrieval.expand import SourceDoc
from app.retrieval.search import Candidate

REFUSAL_TEXT = "Tôi không tìm thấy căn cứ trong các văn bản hiện có."

log = logging.getLogger(__name__)

_BRACKET = re.compile(r"\[\s*(S\d[^\]]*)\]", re.IGNORECASE)
_VALID = re.compile(r"S\d+(?:\s*,\s*S\d+)*", re.IGNORECASE)
_CITE_TOKENS = re.compile(r"\s*\[\s*S\d+(?:\s*,\s*S\d+)*\s*\]", re.IGNORECASE)
_ARTICLE = re.compile(r"điều\s+(\d+)", re.IGNORECASE)


@dataclass
class CitationReport:
    valid: list[str]
    invalid: list[str]
    uncited: bool
    article_mismatch: list[str]


def check_citations(answer: str, sources: list[SourceDoc]) -> CitationReport:
    answer = unicodedata.normalize("NFC", answer)
    known = {s.sid for s in sources}
    cited: list[str] = []
    for inner in _BRACKET.findall(answer):
        # Token không parse được (vd `S1-S3`) bị coi là không hợp lệ.
        cited += re.findall(r"S\d+", inner.upper()) if _VALID.fullmatch(inner.strip()) else [inner.strip()]
    cited = list(dict.fromkeys(cited))
    valid = [c for c in cited if c in known]
    invalid = [c for c in cited if c not in known]
    # shortcut: chỉ so số Điều, không đối chiếu văn bản đi kèm; nâng cấp khi cần phân biệt Điều của nhiều văn bản.
    # Phụ lục không có số Điều thật nên không được tính.
    articles = {s.article for s in sources if not is_appendix_id(s.id)}
    mismatch = [f"Điều {n}" for n in dict.fromkeys(_ARTICLE.findall(answer)) if int(n) not in articles]
    return CitationReport(valid, invalid, not valid and REFUSAL_TEXT not in answer, mismatch)


def strip_citations(text: str) -> str:
    """Bỏ token `[S#]` (mã nguồn chỉ có nghĩa trong một lượt)."""
    return _CITE_TOKENS.sub("", text)


def should_refuse(candidates: list[Candidate], tau: float) -> bool:
    """Từ chối khi có điểm rerank và điểm cao nhất < tau. Không rerank (offline) thì không từ chối."""
    scores = [c.rerank for c in candidates if c.rerank is not None]
    if candidates and not scores:
        log.warning("should_refuse: %d candidates but none has a rerank score; refusal check skipped", len(candidates))
    return bool(scores) and max(scores) < tau
