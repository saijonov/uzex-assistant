from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
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
