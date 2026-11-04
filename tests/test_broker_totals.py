import pytest

from uzex.database import validate_query


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SUM(amount_uzs) AS total FROM broker_deals",
        "SELECT COUNT(*) AS n FROM broker_deals",
        "SELECT product_family, COUNT(*) AS n FROM broker_deals GROUP BY product_family",
        "SELECT region, SUM(amount_uzs) AS total FROM broker_deals WHERE status = 'Исполнен' GROUP BY region",
    ],
)
def test_totals_that_count_a_deal_twice_are_rejected(sql):
    with pytest.raises(ValueError, match="twice"):
        validate_query(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT broker_code, COUNT(*) AS n FROM broker_deals GROUP BY broker_code",
        "SELECT broker_name, SUM(amount_uzs) AS total FROM broker_deals GROUP BY broker_name",
        "SELECT COUNT(*) AS n FROM broker_deals WHERE broker_code = 'BK111'",
        "SELECT SUM(amount_uzs) AS t FROM broker_deals WHERE broker_side = 'Продавец'",
        "SELECT broker_region, COUNT(*) AS n FROM broker_deals GROUP BY broker_region",
        "SELECT COUNT(DISTINCT deal_id) AS n FROM broker_deals",
        "SELECT deal_id, broker_code FROM broker_deals LIMIT 5",
    ],
)
def test_totals_per_broker_are_allowed(sql):
    validate_query(sql)
