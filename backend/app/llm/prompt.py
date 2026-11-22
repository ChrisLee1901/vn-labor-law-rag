"""Dựng messages cho LLM: system prompt tĩnh + nguồn/ngày áp dụng/câu hỏi trong tin nhắn user."""
from datetime import date
from pathlib import Path

from app.legal.ids import is_appendix_id
from app.llm.citations import REFUSAL_TEXT  # noqa: F401  (tái xuất cho API)
from app.retrieval.expand import SourceDoc

PROMPT_VERSION = "answer_v1"
MAX_HISTORY = 6
_DIR = Path(__file__).parent / "prompts"
_SYSTEM = (_DIR / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8").strip()
_CONDENSE = (_DIR / "condense_v1.md").read_text(encoding="utf-8").strip()
_MIN_S1 = 300  # ký tự tối thiểu giữ lại cho S1 khi phải cắt


def _d(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def format_source(s: SourceDoc, content: str | None = None) -> str:
    label = f"Phụ lục {s.article}" if is_appendix_id(s.id) else f"Điều {s.article}"
    window = f"hiệu lực {_d(s.effective_from)}" + (f" đến {_d(s.effective_to)}" if s.effective_to else "")
    return f"[{s.sid}] {s.doc_number}, {label}. {s.title} — {window}\n{s.content if content is None else content}"


def build_messages(
    question: str, sources: list[SourceDoc], history: list[dict], as_of: date, max_context_chars: int = 18000
) -> list[dict]:
    """Ngân sách ký tự (~3 ký tự/token) tính cho nguồn + lịch sử + câu hỏi, không tính system prompt."""
    history = history[-MAX_HISTORY:]
    used = len(question) + sum(len(m["content"]) for m in history)
    blocks: list[str] = []
    for s in sources:
        block = format_source(s)
        if used + len(block) > max_context_chars:
            if not blocks:  # luôn giữ S1, cắt nội dung
                head = format_source(s, "")
                room = max(max_context_chars - used - len(head), _MIN_S1)
                block = format_source(s, s.content[:room].rstrip() + "…")
            else:
                break
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
        f"{'Người dùng' if m['role'] == 'user' else 'Trợ lý'}: {m['content']}" for m in history[-MAX_HISTORY:]
    )
    user = f"Hội thoại trước:\n{turns}\n\nCâu hỏi nối tiếp: {question}\n\nCâu hỏi độc lập:"
    return [{"role": "system", "content": _CONDENSE}, {"role": "user", "content": user}]
