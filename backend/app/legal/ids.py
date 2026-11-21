"""ID pháp lý: `<doc_code>:D<điều>[<hậu tố>][:K<khoản>[:<điểm>]]`, vd `ND145-2020:D12:K2:a`."""
import re

_ID = re.compile(r"^([^:\s]+):D(\d+)([a-z]?)(?::K(\d+)(?::([a-zđ]))?)?$")


def make_id(doc_code: str, article: int, clause: int | None = None, point: str | None = None, suffix: str | None = None) -> str:
    s = f"{doc_code}:D{article}{suffix or ''}"
    if clause is not None:
        s += f":K{clause}"
        if point is not None:
            s += f":{point}"
    return s


def parse_id(s: str) -> tuple[str, int, int | None, str | None]:
    """Ngược của make_id; hậu tố Điều (vd `2a`) được chấp nhận nhưng không trả về (chữ ký cố định)."""
    m = _ID.match(s)
    if not m:
        raise ValueError(f"invalid legal id: {s!r}")
    code, art, _suffix, clause, point = m.groups()
    return code, int(art), int(clause) if clause else None, point
