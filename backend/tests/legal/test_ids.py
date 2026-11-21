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


@pytest.mark.parametrize("bad", ["", "BLLD", "BLLD:D", "BLLD:K1", "BLLD:D1:a", "BLLD:D1:K1:A"])
def test_parse_id_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_id(bad)
