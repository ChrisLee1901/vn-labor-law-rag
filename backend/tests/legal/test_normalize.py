from app.legal.normalize import nfc, strip_diacritics


def test_strip_diacritics():
    assert strip_diacritics("Đường lương tối thiểu vùng I") == "Duong luong toi thieu vung I"
    assert strip_diacritics("đ") == "d"


def test_nfc_composes():
    assert nfc("e\u0302") == "\u00ea"
