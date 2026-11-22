from app.legal.normalize import nfc, strip_diacritics


def test_strip_diacritics():
    assert (
        strip_diacritics("Đường lương tối thiểu vùng I")
        == "Duong luong toi thieu vung I"
    )
    assert strip_diacritics("đ") == "d"


def test_nfc_composes():
    assert nfc("e\u0302") == "\u00ea"


def test_question_key():
    from app.legal.normalize import question_key

    assert (
        question_key("  Mức   LƯƠNG tối thiểu vùng I?? ")
        == "mức lương tối thiểu vùng i"
    )
    import unicodedata

    assert question_key(unicodedata.normalize("NFD", "Mức lương")) == question_key(
        "Mức lương"
    )
