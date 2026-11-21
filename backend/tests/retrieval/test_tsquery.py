from app.retrieval.tsquery import build_tsquery


def test_build_tsquery_or_and_stopwords():
    q = build_tsquery("Mức lương tối thiểu của vùng I là bao nhiêu")
    assert q is not None
    assert "của" not in q.split() and "bao" not in q.split()
    assert " | " in q


def test_build_tsquery_phrase():
    assert "thời <-> gian <-> thử <-> việc" in build_tsquery('"thời gian thử việc"')


def test_build_tsquery_none_when_empty():
    assert build_tsquery("của và là") is None
    assert build_tsquery("&|!():*<>'\\ ") is None
    assert build_tsquery("") is None


def test_build_tsquery_strips_specials():
    q = build_tsquery("a&b | !c (d):* <e> 'f' g\\h")
    assert q is not None
    assert not set(q.replace(" | ", " ").replace(" <-> ", " ")) & set("&!():*<>'\\|")
