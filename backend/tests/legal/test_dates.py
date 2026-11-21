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
