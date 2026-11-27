import pytest

from rag_pipelines.extract import extract_text
from rag_pipelines.structure import Article, parse_document, parse_document_with_stats

CODES = [
    "BLLD",
    "ND145-2020",
    "ND293-2025",
    "ND399-2026",
    "LBHXH-2024",
    "ND158-2025",
    "LVL-2025",
    "ND374-2025",
]
COUNTS = {"BLLD": 220, "LBHXH-2024": 141, "LVL-2025": 55, "ND145-2020": 115}


def _numbers(arts: list[Article]) -> list[int]:
    return [a.number for a in arts if a.suffix is None]


@pytest.fixture(scope="module")
def parsed():
    return {c: parse_document_with_stats(extract_text(c), c) for c in CODES}


@pytest.mark.parametrize("code,n", COUNTS.items())
def test_article_counts(parsed, code, n):
    arts = parsed[code][0]
    nums = _numbers(arts)
    assert len(arts) == n, (code, sorted(set(range(1, n + 1)) - set(nums)), len(arts))
    assert nums == list(range(1, n + 1))


@pytest.mark.parametrize("code", CODES)
def test_numbering_consecutive_from_one(parsed, code):
    arts, dropped = parsed[code]
    assert _numbers(arts) == list(range(1, len(_numbers(arts)) + 1)) and arts
    assert all(a.doc_code == code and a.title for a in arts)
    assert dropped >= 0


def test_clause_and_point_parsing():
    arts = parse_document(extract_text("BLLD"), "BLLD")
    assert any(
        a.clauses and a.clauses[0].points and a.clauses[0].points[0].letter == "a"
        for a in arts
    )


def test_parse_document_matches_stats_version():
    t = extract_text("LVL-2025")
    assert parse_document(t, "LVL-2025") == parse_document_with_stats(t, "LVL-2025")[0]


def test_appendix_forms_dropped(parsed):
    arts, dropped = parsed["ND145-2020"]
    assert dropped > 10000
    body = arts[-1].intro + " ".join(c.text for c in arts[-1].clauses)
    assert (
        "TM. CHÍNH PHỦ" not in body and "Phụ lục" not in body.split("Điều")[-1][-200:]
    )


def test_chapter_section_and_wrapped_title():
    arts = {a.number: a for a in parse_document(extract_text("BLLD"), "BLLD")}
    assert (
        arts[1].chapter == "Chương I. NHỮNG QUY ĐỊNH CHUNG" and arts[1].section is None
    )
    assert arts[13].chapter == "Chương III. HỢP ĐỒNG LAO ĐỘNG"
    assert arts[13].section == "Mục 1. GIAO KẾT HỢP ĐỒNG LAO ĐỘNG"
    lb = {a.number: a for a in parse_document(extract_text("LBHXH-2024"), "LBHXH-2024")}
    assert (
        lb[10].title
        == "Quyền của người tham gia và người thụ hưởng chế độ bảo hiểm xã hội"
    )
    assert lb[2].chapter == "Chương I. NHỮNG QUY ĐỊNH CHUNG"


SYN = """Điều 1. Phạm vi
Văn bản này quy định như sau:
1. Khoản một nói về luật năm
2019. Dòng này là phần nối tiếp.
a) điểm a của khoản một;
b) điểm b dài lắm
nối sang dòng sau;
2. Khoản hai.
Điều 2. Hai
Nội dung.
Điều 1. Biểu mẫu sau cùng
"""


def test_synthetic_rules():
    arts, dropped = parse_document_with_stats(SYN, "X")
    assert [a.number for a in arts] == [1, 2] and dropped > 0
    c1, c2 = arts[0].clauses
    assert c1.number == 1 and "2019. Dòng này" in c1.text and "năm 2019." in c1.text
    assert [p.letter for p in c1.points] == ["a", "b"]
    assert c1.points[1].text == "điểm b dài lắm nối sang dòng sau;"
    assert c2.number == 2 and arts[0].intro == "Văn bản này quy định như sau:"
    assert arts[1].intro == "Nội dung."


def test_chapter_intro_kept_in_next_article_intro():
    arts = {
        a.number: a for a in parse_document(extract_text("ND158-2025"), "ND158-2025")
    }
    assert arts[6].intro.startswith(
        "Đăng ký tham gia và quản lý thu, đóng bảo hiểm xã hội bắt buộc được thực hiện theo quy định tại Chương IV"
    )
    assert arts[6].intro.split("\n")[1].startswith("Việc đăng ký tham gia")


def test_four_line_title_not_truncated():
    a5 = parse_document(extract_text("ND145-2020"), "ND145-2020")[4]
    assert a5.title.endswith("quyền biểu quyết") and a5.intro.startswith(
        "Hợp đồng lao động"
    )


def test_point_with_footnote_digit():
    a59 = {a.number: a for a in parse_document(extract_text("BLLD"), "BLLD")}[59]
    assert [p.letter for p in a59.clauses[1].points] == ["a", "b"]
    assert a59.clauses[1].points[0].text.startswith("Thành lập cơ sở")
