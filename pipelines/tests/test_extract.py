import unicodedata

import pytest

from rag_pipelines.extract import extract_text, strip_congbao_headers

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


def test_strip_congbao_headers():
    raw = (
        "CÔNG BÁO/Số 1203 + 1204/Ngày 26-12-2020\n12\nĐiều 1. Phạm vi\n"
        "CÔNG BÁO / Số 967 + 968 / Ngày 24-7-2025\n1. Nội dung\n"
        "Ký bởi: Cổng Thông tin\nEmail: a@b.vn\nCơ quan: Văn phòng\nThời gian ký: 28.12.2020 10:41:05 +07:00\n"
        "a) điểm a\n"
    )
    out = strip_congbao_headers(raw)
    assert out.split("\n") == ["Điều 1. Phạm vi", "1. Nội dung", "a) điểm a"]


def test_extract_is_nfc():
    nfd = unicodedata.normalize("NFD", "Điều 1. Phạm vi điều chỉnh")
    assert unicodedata.normalize("NFC", nfd) != nfd
    out = strip_congbao_headers(nfd)
    assert unicodedata.normalize("NFC", out) == unicodedata.normalize("NFC", nfd)
    text = extract_text("LVL-2025")
    assert text == unicodedata.normalize("NFC", text)


def test_extract_nd145_joins_two_parts():
    t = extract_text("ND145-2020")
    assert "Điều 1." in t and "Điều 115." in t
    assert t.index("Điều 1.") < t.index(
        "Điều 115."
    )  # ND145 có 115 Điều; Điều 115 chỉ nằm ở part2
    assert "CÔNG BÁO/" not in t


@pytest.mark.parametrize("code", CODES)
def test_extract_all_codes(code):
    t = extract_text(code)
    assert len(t) > 5000 and "Điều 1." in t
    assert "Thời gian ký" not in t and "CÔNG BÁO/Số" not in t


def test_nfd_header_is_stripped():
    nfd = unicodedata.normalize(
        "NFD", "CÔNG BÁO/Số 1203 + 1204/Ngày 26-12-2020\nĐiều 1. Phạm vi"
    )
    assert strip_congbao_headers(nfd) == "Điều 1. Phạm vi"


def test_strip_continuation_notes():
    raw = "(Tiếp theo Công báo số 1203 + 1204)\n(Xem tiếp theo Công báo số 1205 + 1206)\nĐiều 2. Đối tượng"
    assert strip_congbao_headers(raw) == "Điều 2. Đối tượng"


def test_body_lines_survive():
    raw = (
        "Cơ quan: Bộ Nội vụ chịu trách nhiệm hướng dẫn.\n"
        "Email: hotro@example.vn\n"
        "2025\n"
        "Văn bản được đăng Công báo theo quy định.\n"
    )
    assert strip_congbao_headers(raw, page_numbers=False) == raw.rstrip("\n")
    assert "2025" not in strip_congbao_headers(raw)  # mặc định vẫn bỏ dòng số trang
