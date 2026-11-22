"""Kiểm tra trích dẫn xác định (không dùng LLM) và ngưỡng từ chối."""
import re
import unicodedata
from dataclasses import dataclass

from app.legal.ids import is_appendix_id
from app.retrieval.expand import SourceDoc
from app.retrieval.search import Candidate

REFUSAL_TEXT = "Tôi không tìm thấy căn cứ trong các văn bản hiện có."

_CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
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
    cited = list(dict.fromkeys(t for m in _CITE.findall(answer) for t in re.findall(r"S\d+", m)))
    valid = [c for c in cited if c in known]
    invalid = [c for c in cited if c not in known]
    # shortcut: chỉ so số Điều, không đối chiếu văn bản đi kèm; nâng cấp khi cần phân biệt Điều của nhiều văn bản.
    # Phụ lục không có số Điều thật nên không được tính.
    articles = {s.article for s in sources if not is_appendix_id(s.id)}
    mismatch = [f"Điều {n}" for n in dict.fromkeys(_ARTICLE.findall(answer)) if int(n) not in articles]
    return CitationReport(valid, invalid, not valid and REFUSAL_TEXT not in answer, mismatch)


def should_refuse(candidates: list[Candidate], tau: float) -> bool:
    """Từ chối khi có điểm rerank và điểm cao nhất < tau. Không rerank (offline) thì không từ chối."""
    scores = [c.rerank for c in candidates if c.rerank is not None]
    return bool(scores) and max(scores) < tau
