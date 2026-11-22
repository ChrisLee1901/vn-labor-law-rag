import pytest

from app.legal.ids import make_id, parse_id


def test_make_parse_id_roundtrip():
    assert parse_id(make_id("ND145-2020", 12, 2, "a")) == ("ND145-2020", 12, 2, "a")


@pytest.mark.parametrize(
    "args,expected",
    [
        (("LBHXH-2024", 33, 1), "LBHXH-2024:D33:K1"),
        (("ND145-2020", 12, 2, "a"), "ND145-2020:D12:K2:a"),
        (("BLLD", 5), "BLLD:D5"),
        (("BLLD", 2, None, None, "a"), "BLLD:D2a"),
    ],
)
def test_make_id_format(args, expected):
    assert make_id(*args) == expected


def test_parse_id_article_only_and_suffix():
    assert parse_id("BLLD:D5") == ("BLLD", 5, None, None)
    assert parse_id("BLLD:D2a:K1") == ("BLLD", 2, 1, None)


@pytest.mark.parametrize(
    "bad", ["", "BLLD", "BLLD:D", "BLLD:K1", "BLLD:D1:a", "BLLD:D1:K1:A"]
)
def test_parse_id_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_id(bad)


def test_appendix_id_roundtrip():
    from app.legal.ids import is_appendix_id, make_appendix_id

    assert make_appendix_id("ND293-2025", 1) == "ND293-2025:PL1"
    assert make_appendix_id("ND293-2025", 1, 3) == "ND293-2025:PL1:M3"
    assert is_appendix_id("ND293-2025:PL1:M3") and is_appendix_id("ND293-2025:PL1")
    assert not is_appendix_id("ND293-2025:D3") and not is_appendix_id(
        "ND293-2025:PL1:K3"
    )
