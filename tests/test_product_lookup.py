import pytest

from uzex.database import PRODUCT_MATCH_THRESHOLD, product_aliases, product_score


@pytest.mark.parametrize(
    "needle,name",
    [
        ("komir", "kombikorm marka ks 70"),
        ("oltin", "polietilen pe 3015"),
        ("arpa", "tsement portlandskiy"),
        ("gisht", "list stalnoy goryachekatanniy"),
        ("makkajoxori", "muka sort ii"),
    ],
)
def test_absent_goods_do_not_match_other_products(needle, name):
    assert product_score(needle, name) < PRODUCT_MATCH_THRESHOLD


@pytest.mark.parametrize(
    "needle,name",
    [
        ("sahar", "saxar pesok"),
        ("saxor", "saxar beliy"),
        ("psheniza", "pshenitsa prodovolstvennaya"),
        ("masla", "maslo xlopkovoe"),
    ],
)
def test_misspelled_goods_still_match(needle, name):
    assert product_score(needle, name) >= PRODUCT_MATCH_THRESHOLD


def test_brick_has_its_uzbek_name():
    assert product_aliases("gisht") == ["Кирпич"]


@pytest.mark.parametrize("word", ["oltin", "kumush", "komir", "arpa", "makkajoxori"])
def test_goods_outside_the_data_are_not_called_products(sample_database, word):
    assert not sample_database.names_product(word)
