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


@pytest.mark.parametrize(
    "kind,text",
    [
        ("company", "Imaginary LLC"),
        ("company", "Zamin Textile MChJ"),
        ("company", "FAKE_COMPANY_7E2F91"),
        ("broker", "Nonexistent Broker"),
        ("company", "123456789"),
    ],
)
def test_a_name_that_does_not_exist_has_no_candidates(sample_database, kind, text):
    assert sample_database.lookup(kind, text) == []


def test_misspelled_name_finds_the_real_company_first(sample_database):
    rows = sample_database.lookup("company", "Rukushu fermer")
    assert rows[0]["name"] == "RUKUSHO‘ FERMER MCHJ"


def test_generic_legal_words_alone_do_not_make_a_match(sample_database):
    rows = sample_database.lookup("company", "Rukushu MChJ")
    assert rows == [] or rows[0]["name"] == "RUKUSHO‘ FERMER MCHJ"


def test_a_generic_word_can_still_be_searched_directly(sample_database):
    assert len(sample_database.lookup("company", "MChJ")) > 1


def test_part_of_a_tax_number_is_not_matched_loosely(sample_database):
    inn = sample_database.catalog["company"][0]["inn"]
    assert all(row["match"] != "fuzzy" for row in sample_database.lookup("company", inn[:8]))


async def test_unknown_name_tells_the_model_to_stop_looking(sample_database):
    client = ScriptedClient(
        [
            ("lookup_entities", {"kind": "company", "text": "Imaginary LLC"}),
            finish("unavailable", None, "not_found"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Imaginary LLC nechta bitim qilgan?"
    )
    assert answer.outcome == "unavailable"
    assert answer.reason == "not_found"
    output = next(
        item["output"]
        for item in client.requests[-1]["input"]
        if isinstance(item, dict)
        and item.get("type") == "function_call_output"
        and "candidates" in item["output"]
    )
    assert "not_found" in output
