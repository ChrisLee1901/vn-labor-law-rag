from datetime import date

from app.legal.dates import extract_as_of

T = date(2026, 11, 22)


def test_extract_as_of():
    assert extract_as_of("từ 1/1/2027 lương tối thiểu vùng I", T) == date(2027, 1, 1)
    assert extract_as_of("từ ngày 01/01/2027 lương", T) == date(2027, 1, 1)
    assert extract_as_of("lương tối thiểu vùng I", T) == T


def test_year_only():
    assert extract_as_of("lương năm 2027", T) == date(2027, 1, 1)
    assert extract_as_of("lương năm 2025", T) == date(2025, 12, 31)
    assert extract_as_of("lương năm 2026", T) == date(2026, 12, 31)


def test_year_in_law_name_ignored_and_bad_dates():
    assert extract_as_of("Luật Bảo hiểm xã hội năm 2014 quy định gì", T) == T
    assert extract_as_of("từ 31/2/2027", T) == T


def test_year_not_cancelled_by_unrelated_words():
    for q in (
        "hệ số lương năm 2027 là bao nhiêu",
        "theo nghị định mới, lương tối thiểu năm 2027",
        "pháp luật về lương năm 2027",
        "theo luật, lương tối thiểu năm 2027",
    ):
        assert extract_as_of(q, T) == date(2027, 1, 1), q
    assert extract_as_of("Bộ luật Lao động năm 2019 quy định gì", T) == T


def test_unaccented_and_nfd():
    import unicodedata

    assert extract_as_of("luong toi thieu nam 2027", T) == date(2027, 1, 1)
    assert extract_as_of("tu ngay 01/01/2027 luong", T) == date(2027, 1, 1)
    assert extract_as_of(unicodedata.normalize("NFD", "lương năm 2027"), T) == date(
        2027, 1, 1
    )
    assert extract_as_of("Luat bao hiem xa hoi nam 2014", T) == T


def test_other_date_formats():
    assert extract_as_of("ngày 1 tháng 7 năm 2027 lương", T) == date(2027, 7, 1)
    assert extract_as_of("từ tháng 7/2027", T) == date(2027, 7, 1)
    assert extract_as_of("từ tháng 7 năm 2027", T) == date(2027, 7, 1)
    assert extract_as_of("từ 1-1-2027", T) == date(2027, 1, 1)
    assert extract_as_of("từ 01.01.2027", T) == date(2027, 1, 1)
    assert extract_as_of("Nghị định 145/2020/NĐ-CP quy định gì", T) == T
