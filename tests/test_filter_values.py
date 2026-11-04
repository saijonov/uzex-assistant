import pytest
from test_engine import ScriptedClient, finish

from uzex.config import Settings
from uzex.engine import Engine
from uzex.prompt import instructions


@pytest.mark.parametrize(
    "where",
    [
        "currency = 'USD'",
        "LOWER(currency) = 'usd'",
        "currency IN ('USD', 'Доллар США')",
        "unit = 'кг'",
        "status = 'Cancelled'",
        "contract_form = 'forward'",
        "auction_type LIKE '%english%'",
        "LOWER(product_name) LIKE '%несуществующий товар%'",
        "seller_name = 'Imaginary LLC'",
    ],
)
def test_invented_filter_values_are_rejected(sample_database, where):
    with pytest.raises(ValueError, match="not evidence"):
        sample_database.query(f"SELECT COUNT(*) AS n FROM registry WHERE {where}", "q1")


@pytest.mark.parametrize(
    "where",
    [
        "currency = 'Доллар США'",
        "LOWER(currency) = 'доллар сша'",
        "unit IN ('тонна', 'килограмм')",
        "status <> 'Исполнен'",
        "LOWER(product_name) LIKE '%цемент%'",
        "contract_type LIKE 'Экспорт%'",
    ],
)
def test_real_filter_values_are_accepted(sample_database, where):
    assert sample_database.query(f"SELECT COUNT(*) AS n FROM registry WHERE {where}", "q1").rows


def test_sampling_rejects_invented_filter_values(sample_database):
    with pytest.raises(ValueError, match="Доллар США"):
        sample_database.sample("SELECT * FROM registry WHERE currency = 'USD'", 3, "q1")


def test_absent_record_is_still_a_valid_empty_result(sample_database):
    data = sample_database.query("SELECT deal_id FROM registry WHERE deal_id = '999999'", "q1")
    assert data.rows == []


def test_real_filter_values_reach_the_model(sample_database):
    text = instructions(
        sample_database.schema, sample_database.manifest, None, sample_database.values
    )
    assert "Доллар США" in text
    for values in sample_database.values.values():
        assert all(value in text for value in values)


async def test_invented_value_makes_the_model_correct_itself_instead_of_no_match(sample_database):
    real = "SELECT COUNT(*) AS n FROM registry WHERE currency = 'Доллар США'"
    client = ScriptedClient(
        [
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS n FROM registry WHERE currency = 'USD'"},
            ),
            ("query_registry", {"sql": real}),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("В долларах?")
    assert answer.outcome == "answer"
    assert answer.evidence.sql == real
    assert answer.evidence.rows[0]["n"] > 0
