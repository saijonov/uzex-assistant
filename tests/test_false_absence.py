import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import named_regions
from uzex.engine import Engine


@pytest.mark.parametrize(
    "pattern",
    ["%tashkent%", "%toshkent%", "%namangan%", "%самарканд%"],
)
def test_a_region_is_not_searched_in_the_address_text(sample_database, pattern):
    with pytest.raises(ValueError, match="region"):
        sample_database.query(
            f"SELECT COUNT(*) AS n FROM registry WHERE LOWER(warehouse_address) LIKE '{pattern}'",
            "q1",
        )


def test_an_address_nothing_contains_is_rejected_not_reported_as_absent(sample_database):
    with pytest.raises(ValueError, match="not evidence of absence"):
        sample_database.query(
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(warehouse_address) LIKE '%zzzzq%'", "q1"
        )


def test_a_real_address_word_is_accepted(sample_database):
    address = sample_database.query(
        "SELECT warehouse_address FROM contracts WHERE warehouse_address IS NOT NULL LIMIT 1", "q1"
    ).rows[0]["warehouse_address"]
    word = next(
        item
        for item in address.lower().split()
        if item.isalpha() and len(item) > 3 and not named_regions(item)
    )
    data = sample_database.query(
        f"SELECT COUNT(*) AS n FROM registry WHERE LOWER(warehouse_address) LIKE '%{word}%'", "q2"
    )
    assert data.rows


async def test_goods_sold_in_another_unit_are_not_called_absent(sample_database):
    product = sample_database.query(
        "SELECT product_family, unit FROM registry WHERE unit = 'тонна' LIMIT 1", "q0"
    ).rows[0]["product_family"]
    condition = f"product_family = '{product}'"
    client = ScriptedClient(
        [
            review(task="price", subject="product", period="specified"),
            (
                "query_registry",
                {
                    "sql": f"SELECT SUM(amount) AS a FROM registry WHERE {condition} AND unit = 'литр'"
                },
            ),
            finish(outcome="no_match"),
            (
                "query_registry",
                {"sql": f"SELECT COUNT(*) AS n FROM registry WHERE {condition}"},
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("1 litr narxi?")
    assert answer.outcome == "answer"
    assert answer.evidence.query_id == "q2"


async def test_a_unit_word_is_not_reported_as_a_missing_product(sample_database, monkeypatch):
    monkeypatch.setattr(sample_database, "lookup", lambda *args: [])
    client = ScriptedClient(
        [
            review(task="count", subject="market"),
            ("lookup_entities", {"kind": "product", "text": "Dona"}),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(),
        ]
    )
    await Engine(Settings(_env_file=None), client, sample_database).answer("Dona bilan nechta?")
    note = [
        item["output"]
        for item in client.requests[2]["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ][-1]
    assert "unit" in note
    assert "not_found" not in note
