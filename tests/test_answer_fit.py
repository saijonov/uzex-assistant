import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import calculate_ratio
from uzex.engine import Engine


async def test_ranking_answer_must_name_who_was_ranked(sample_database):
    client = ScriptedClient(
        [
            review(task="rank", subject="broker", ranking_by="count"),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(),
            (
                "query_registry",
                {
                    "sql": "SELECT broker_code, COUNT(*) AS n FROM broker_deals GROUP BY broker_code "
                    "ORDER BY n DESC, broker_code LIMIT 1"
                },
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Какой брокер?")
    assert answer.outcome == "answer"
    assert "broker_code" in answer.evidence.rows[0]


async def test_percentage_answer_must_contain_a_percentage(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "query_registry",
                {"sql": "SELECT region, COUNT(*) AS n FROM registry GROUP BY region"},
            ),
            finish(),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "n",
                    "denominator": "n",
                    "scale": 2,
                    "operation": "share_percent",
                },
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какова доля каждого региона в процентах?"
    )
    assert answer.evidence.calculation.startswith("share_percent")


async def test_percentage_stored_in_a_field_counts_as_a_percentage(sample_database):
    client = ScriptedClient(
        [
            review(task="detail"),
            (
                "query_registry",
                {"sql": "SELECT deposit_percent FROM registry WHERE deal_id = '100001'"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "100001-bitim garovi necha foiz?"
    )
    assert answer.outcome == "answer"


@pytest.mark.parametrize("operation", ["ratio", "percentage", "change_percent"])
def test_a_measure_cannot_be_compared_with_itself_under_another_name(sample_database, operation):
    data = sample_database.query(
        "SELECT COUNT(*) AS cancelled_count, COUNT(*) AS total_count FROM registry", "q1"
    )
    with pytest.raises(ValueError, match="same measure"):
        calculate_ratio(data, "cancelled_count", "total_count", 2, operation)


def test_a_grouped_column_cannot_be_compared_with_itself(sample_database):
    data = sample_database.query("SELECT region, COUNT(*) AS n FROM registry GROUP BY region", "q1")
    with pytest.raises(ValueError, match="same measure"):
        calculate_ratio(data, "n", "n", 2, "change_percent")


def test_filtered_and_unfiltered_counts_are_different_measures(sample_database):
    data = sample_database.query(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_cancelled) AS cancelled FROM registry",
        "q1",
    )
    assert calculate_ratio(data, "cancelled", "total", 2, "percentage").rows[0]["ratio"] != "100.00"


async def test_model_recovers_from_comparing_a_measure_with_itself(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS cancelled, COUNT(*) AS total FROM registry"},
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "cancelled",
                    "denominator": "total",
                    "scale": 2,
                    "operation": "percentage",
                },
            ),
            (
                "query_registry",
                {
                    "sql": "SELECT COUNT(*) FILTER (WHERE is_cancelled) AS cancelled, "
                    "COUNT(*) AS total FROM registry"
                },
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q2",
                    "numerator": "cancelled",
                    "denominator": "total",
                    "scale": 2,
                    "operation": "percentage",
                },
            ),
            finish(query_id="q3"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какая доля отменённых в процентах?"
    )
    assert answer.outcome == "answer"
    assert answer.evidence.rows[0]["ratio"] == "18.52"
