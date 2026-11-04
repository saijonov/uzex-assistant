from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.engine import Engine


def test_a_city_is_not_guessed_to_be_a_region(sample_database):
    assert sample_database.lookup("region", "Qarshi") == []
    assert sample_database.lookup("region", "Карши") == []


def test_a_real_region_is_still_found(sample_database):
    assert sample_database.lookup("region", "Namangan")[0]["name"] == "Namangan viloyati"
    assert sample_database.lookup("region", "Samarqan")


async def test_an_unknown_region_points_to_the_warehouse_address(sample_database):
    client = ScriptedClient(
        [
            review(task="count", subject="market"),
            ("lookup_entities", {"kind": "region", "text": "Qarshi"}),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(),
        ]
    )
    await Engine(Settings(_env_file=None), client, sample_database).answer("Qarshi shahrida?")
    notes = [
        item["output"]
        for item in client.requests[2]["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert "warehouse_address" in notes[-1]
