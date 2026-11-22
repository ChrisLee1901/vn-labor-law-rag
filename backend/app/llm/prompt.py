"""Dựng messages cho LLM: system prompt tĩnh + nguồn/ngày áp dụng/câu hỏi trong tin nhắn user."""
from datetime import date
from pathlib import Path

from app.legal.ids import is_appendix_id
from app.llm.citations import REFUSAL_TEXT, strip_citations  # noqa: F401  (REFUSAL_TEXT tái xuất cho API)
from app.retrieval.expand import SourceDoc

PROMPT_VERSION = "answer_v1"
MAX_HISTORY = 6
MAX_HISTORY_CHARS = 1200
_DIR = Path(__file__).parent / "prompts"
_SYSTEM = (_DIR / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8").strip()
_CONDENSE = (_DIR / "condense_v1.md").read_text(encoding="utf-8").strip()
_MIN_S1 = 300  # ký tự tối thiểu giữ lại cho S1 khi phải cắt


def _d(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _safe(text: str) -> str:
    """Vô hiệu hóa `<`/`>` để nguồn/câu hỏi không đóng hoặc giả mạo khối `<nguon>`."""
    return text.replace("<", "‹").replace(">", "›")


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n].rstrip() + "…"


def format_source(s: SourceDoc, content: str | None = None) -> str:
    label = f"Phụ lục {s.article}" if is_appendix_id(s.id) else f"Điều {s.article}"
    window = f"hiệu lực {_d(s.effective_from)}" + (f" đến {_d(s.effective_to)}" if s.effective_to else "")
    body = s.content if content is None else content
    return f"[{s.sid}] {_safe(s.doc_number)}, {label}. {_safe(s.title)} — {window}\n{_safe(body)}"


def _history(history: list[dict]) -> list[dict]:
    out = []
    for m in history[-MAX_HISTORY:]:
        text = strip_citations(m["content"]) if m["role"] == "assistant" else m["content"]
        out.append({"role": m["role"], "content": _safe(_clip(text, MAX_HISTORY_CHARS))})
    return out


def build_messages(
    question: str, sources: list[SourceDoc], history: list[dict], as_of: date, max_context_chars: int = 15000
) -> list[dict]:
    """Ngân sách ký tự (~2.5-3 ký tự/token) cho system + lịch sử + nguồn + câu hỏi.

    S1 luôn được giữ (tối thiểu _MIN_S1 ký tự nội dung) nên tổng có thể vượt ngân sách một chút."""
    question = _safe(question)
    history = _history(history)
    used = len(_SYSTEM) + len(question) + sum(len(m["content"]) for m in history)
    blocks: list[str] = []
    for s in sources:
        block = format_source(s)
        if used + len(block) > max_context_chars:
            if blocks:
                break
            head = format_source(s, "")
            room = max(max_context_chars - used - len(head), _MIN_S1)
            block = format_source(s, _clip(s.content, room))
        blocks.append(block)
        used += len(block)
    user = (
        f"Ngày áp dụng: {_d(as_of)}\n\n<nguon>\n" + "\n\n".join(blocks) + "\n</nguon>\n\n"
        f"Câu hỏi: {question}"
    )
    return [{"role": "system", "content": _SYSTEM}, *history, {"role": "user", "content": user}]


def condense_messages(history: list[dict], question: str) -> list[dict]:
    """Viết lại câu hỏi nối tiếp thành câu độc lập; chỉ gọi từ lượt thứ 2."""
    turns = "\n".join(
        f"{'Người dùng' if m['role'] == 'user' else 'Trợ lý'}: {m['content']}" for m in _history(history)
    )
    user = f"Hội thoại trước:\n{turns}\n\nCâu hỏi nối tiếp: {_safe(question)}\n\nCâu hỏi độc lập:"
    return [{"role": "system", "content": _CONDENSE}, {"role": "user", "content": user}]
