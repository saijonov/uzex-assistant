from decimal import Decimal

import pytest

from uzex.database import calculate_ratio, normalize, validate_query


def test_import_preserves_counts_and_source(sample_database):
    assert sample_database.manifest["counts"]["deals"] == 27
    result = sample_database.query("SELECT * FROM registry WHERE deal_id = '100001'", "q1")
    row = result.rows[0]
    assert row["source_file"] == "deals_2022.csv"
    assert row["source_row"] == 2
    assert Decimal(row["amount"]) == Decimal("304547938.4")
    assert Decimal(row["volume"]) == Decimal("79720")
    assert row["seller_name"]


def test_final_price_uses_physical_volume(sample_database):
    result = sample_database.query(
        "SELECT amount, volume FROM registry WHERE deal_id = '100001'", "q1"
    )
    computed = calculate_ratio(result, "amount", "volume", 2)
    assert computed.rows[0]["ratio"] == "3820.22"


def test_export_conversion_uses_date_rate(sample_database):
    row = sample_database.query(
        "SELECT amount, usd_uzs, amount_uzs FROM registry WHERE deal_id = '100024'", "q1"
    ).rows[0]
    assert Decimal(row["amount"]) == Decimal("43176.64")
    assert Decimal(row["amount_uzs"]) == Decimal(row["amount"]) * Decimal(row["usd_uzs"])


def test_missing_delivery_is_not_zero(sample_database):
    rows = sample_database.query(
        "SELECT delivered_lots FROM registry WHERE is_cancelled = true", "q1"
    ).rows
    assert rows
    assert all(row["delivered_lots"] is None for row in rows)


def test_region_mapping_is_grounded(sample_database):
    row = sample_database.query(
        "SELECT region, region_ru FROM registry WHERE deal_id = '100001'", "q1"
    ).rows[0]
    assert row == {"region": "Namangan viloyati", "region_ru": "Наманганская область"}


def test_mixed_currency_aggregation_rejected(sample_database):
    with pytest.raises(ValueError, match="Mixed currencies"):
        sample_database.query("SELECT SUM(amount) AS total FROM registry", "q1")


def test_mixed_unit_aggregation_rejected(sample_database):
    with pytest.raises(ValueError, match="Mixed units"):
        sample_database.query("SELECT SUM(volume) AS total FROM registry", "q1")


def test_compound_date_and_status_filters_work(sample_database):
    result = sample_database.query(
        "SELECT COUNT(*) AS n FROM registry WHERE "
        "deal_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' "
        "AND NOT is_cancelled",
        "q1",
    )
    assert result.rows[0]["n"] > 0
    assert result.period_start.startswith("2025-")
    assert result.period_end.startswith("2025-")


def test_percentage_is_computed_from_verified_columns(sample_database):
    evidence = sample_database.query(
        "SELECT COUNT(*) AS all_deals, "
        "COUNT(*) FILTER (WHERE is_cancelled) AS cancelled FROM registry",
        "q1",
    )
    answer = calculate_ratio(evidence, "cancelled", "all_deals", 2, "percentage")
    assert answer.rows[0]["ratio"] == "18.52"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM registry",
        "SELECT * FROM registry; DROP TABLE deals",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM metadata",
        "SELECT * FROM registry JOIN registry r USING(deal_id)",
        "SELECT * FROM (SELECT * FROM registry)",
        "SELECT amount / volume FROM registry",
        "SELECT AVG(amount) FROM registry",
        "SELECT 'Invented Company' AS seller_name FROM registry",
        "SELECT count(*) + 1000 AS total FROM registry",
        "SELECT CASE WHEN true THEN 42 ELSE 0 END FROM registry",
        "SELECT * FROM registry LIMIT 1000000",
        "SELECT * FROM main.registry",
        "COPY registry TO '/tmp/export.csv'",
        "INSTALL httpfs",
        "SELECT current_setting('secret') FROM registry",
        "SELECT SUM(99999) AS total FROM registry",
        "SELECT SUM(amount + amount) FROM registry",
        "SELECT * FROM registry USING SAMPLE 10 PERCENT",
        "SELECT * FROM registry QUALIFY ROW_NUMBER() OVER () = 1",
        "SELECT * FROM registry OFFSET 1",
    ],
)
def test_unsafe_queries_are_blocked(sql):
    with pytest.raises(ValueError):
        validate_query(sql)


def test_lookup_handles_uzbek_apostrophes_and_scripts(sample_database):
    assert normalize("Фарғона") == normalize("Farg‘ona")
    assert sample_database.lookup("region", "Наманган")[0]["name"] == "Namangan viloyati"
