import pytest

from uzex.render import format_value, value_field


@pytest.mark.parametrize(
    "expression,field",
    [
        ("SUM(amount_uzs)", "amount_uzs"),
        ("SUM(amount_uzs) FILTER(WHERE is_cancelled)", "amount_uzs"),
        ("MEDIAN(amount_uzs)", "amount_uzs"),
        ("SUM(amount)", "amount"),
        ("SUM(amount_usd)", "amount_usd"),
        ("MAX(amount_uzs)", "amount_uzs"),
    ],
)
def test_money_totals_are_recognised(expression, field):
    assert value_field(expression) == field


@pytest.mark.parametrize(
    "value,expected",
    [
        ("55976577480267.0551", "55 976 577 480 267.06"),
        ("205738738879694.1818", "205 738 738 879 694.18"),
        ("100", "100.00"),
    ],
)
def test_money_is_shown_to_the_tiyin(value, expected):
    assert format_value(value, "uz", "amount_uzs") == expected
