from app.legal.refs import DOC_ALIASES, Ref, extract_refs


def _x(text, self_doc="ND145-2020"):
    return extract_refs(text, self_doc, DOC_ALIASES)


def test_external_law_by_name():
    assert _x("theo quy định tại khoản 5 Điều 35 Luật Bảo hiểm y tế") == [
        Ref(None, "Luật Bảo hiểm y tế", 35, 5, None, "cites")
    ]


def test_corpus_law_by_name():
    (r,) = _x("Điều 47 Luật Việc làm")
    assert (r.dst_doc_code, r.dst_doc_number, r.article, r.clause, r.point) == ("LVL-2025", "74/2025/QH15", 47, None, None)


def test_point_clause_article_decree_by_number():
    (r,) = _x("điểm a khoản 2 Điều 5 Nghị định số 145/2020/NĐ-CP", "ND293-2025")
    assert (r.dst_doc_code, r.dst_doc_number, r.article, r.clause, r.point) == ("ND145-2020", "145/2020/NĐ-CP", 5, 2, "a")


def test_same_article_reference_skipped():
    assert _x("quy định tại khoản 1 Điều này", "BLLD") == []
    assert _x("các điểm a và b khoản 2 Điều này", "BLLD") == []


def test_self_doc_this_law():
    (r,) = _x("khoản 3 Điều 20 của Bộ luật này", "BLLD")
    assert (r.dst_doc_code, r.article, r.clause) == ("BLLD", 20, 3)


def test_rel_details():
    (r,) = _x("Nghị định này quy định chi tiết khoản 3 Điều 12 Bộ luật Lao động")
    assert (r.dst_doc_code, r.rel) == ("BLLD", "details")
    assert _x("hướng dẫn thi hành Điều 12 Bộ luật Lao động")[0].rel == "details"


def test_rel_amends_and_cites():
    assert _x("Sửa đổi, bổ sung khoản 2 Điều 5 Nghị định số 145/2020/NĐ-CP như sau")[0].rel == "amends"
    assert _x("theo Điều 5 Luật Việc làm")[0].rel == "cites"


def test_rel_is_per_ref_nearest_keyword():
    a, b = _x("Sửa đổi, bổ sung Điều 5 Nghị định 145/2020 quy định chi tiết Điều 12 Bộ luật Lao động")
    assert (a.dst_doc_code, a.rel) == ("ND145-2020", "amends")
    assert (b.dst_doc_code, b.rel) == ("BLLD", "details")


def test_old_law_number_not_mapped_by_name():
    (r,) = _x("Điều 5 Luật Bảo hiểm xã hội số 58/2014/QH13")
    assert (r.dst_doc_code, r.dst_doc_number) == (None, "58/2014/QH13")
    (r,) = _x("Điều 3 Luật Việc làm số 38/2013/QH13")
    assert (r.dst_doc_code, r.dst_doc_number) == (None, "38/2013/QH13")


def test_old_law_year_not_mapped_by_name():
    (r,) = _x("Điều 5 Luật Bảo hiểm xã hội năm 2014")
    assert r.dst_doc_code is None
    assert _x("Điều 5 Luật Bảo hiểm xã hội năm 2024")[0].dst_doc_code == "LBHXH-2024"


def test_name_without_number_is_corpus_doc():
    assert _x("Điều 5 Luật Bảo hiểm xã hội")[0].dst_doc_code == "LBHXH-2024"
    assert _x("Điều 5 Bộ luật Lao động năm 2019")[0].dst_doc_code == "BLLD"
    assert _x("Điều 5 Bộ luật Lao động số 45/2019/QH14")[0].dst_doc_code == "BLLD"


def test_consolidated_number_maps_to_blld():
    assert _x("Điều 5 Luật số 18/VBHN-VPQH")[0].dst_doc_code == "BLLD"


def test_short_decree_forms():
    for s in ("Nghị định 145/2020", "NĐ 145/2020", "Nghị định số 145/2020/NĐ-CP", "nghị định 145/2020/NĐ-CP"):
        (r,) = _x("Điều 12 " + s, None)
        assert (r.dst_doc_code, r.article) == ("ND145-2020", 12), s


def test_wrong_suffix_not_mapped():
    assert _x("Điều 12 Nghị định số 145/2020/QH14")[0].dst_doc_code is None


def test_bare_article_is_self_doc():
    (r,) = _x("theo Điều 12", "ND158-2025")
    assert (r.dst_doc_code, r.dst_doc_number, r.article) == ("ND158-2025", "158/2025/NĐ-CP", 12)


def test_bare_article_without_self_doc_kept_unresolved():
    (r,) = extract_refs("Điều 12 quy định gì")
    assert (r.dst_doc_code, r.dst_doc_number, r.article) == (None, "", 12)


def test_online_question():
    (r,) = extract_refs("Điều 12 Nghị định 145/2020 nói gì")
    assert (r.dst_doc_code, r.article) == ("ND145-2020", 12)


def test_enumerated_articles():
    rs = _x("Điều 23 và Điều 24 của Luật Bảo hiểm xã hội", "ND158-2025")
    assert [(r.dst_doc_code, r.article) for r in rs] == [("LBHXH-2024", 23), ("LBHXH-2024", 24)]
    rs = _x("Điều 5, 6 và 7 Luật Việc làm")
    assert [r.article for r in rs] == [5, 6, 7]


def test_enumerated_clauses_and_points():
    rs = _x("khoản 1, 2 và 3 Điều 5")
    assert [(r.article, r.clause) for r in rs] == [(5, 1), (5, 2), (5, 3)]
    rs = _x("các điểm a, b khoản 2 Điều 5")
    assert [(r.clause, r.point) for r in rs] == [(2, "a"), (2, "b")]
    rs = _x("điểm a và điểm b khoản 1 Điều 5")
    assert [(r.clause, r.point) for r in rs] == [(1, "a"), (1, "b")]
    rs = _x("khoản 1 và khoản 2 Điều 5 Luật Việc làm")
    assert [(r.dst_doc_code, r.clause) for r in rs] == [("LVL-2025", 1), ("LVL-2025", 2)]


def test_doc_only_reference():
    (r,) = _x("căn cứ Nghị định số 145/2020/NĐ-CP")
    assert (r.dst_doc_code, r.article) == ("ND145-2020", None)
    assert _x("Nghị định này có hiệu lực") == []


def test_no_duplicates_and_nfc():
    import unicodedata

    s = unicodedata.normalize("NFD", "Điều 47 Luật Việc làm")
    assert [r.dst_doc_code for r in _x(s)] == ["LVL-2025"]


def test_not_a_reference():
    assert _x("điều kiện lao động, khoản tiền 3 triệu") == []


def test_external_names_and_numbers():
    (r,) = _x("Điều 5 Luật Tổ chức Chính phủ số 63/2025/QH15")
    assert (r.dst_doc_code, r.dst_doc_number) == (None, "63/2025/QH15")
    assert _x("khoản 2 Điều 3 Luật An toàn, vệ sinh lao động.")[0].dst_doc_number == "Luật An toàn, vệ sinh lao động"
    assert _x("Điều 9 Luật Hôn nhân và gia đình")[0].dst_doc_number == "Luật Hôn nhân và gia đình"
    assert _x("Điều 9 Luật Doanh nghiệp, quy định")[0].dst_doc_number == "Luật Doanh nghiệp"
