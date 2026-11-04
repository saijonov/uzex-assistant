import json

import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import arrange_result, calculate_ratio
from uzex.engine import TOOLS, Engine
from uzex.models import Answer, Evidence
from uzex.render import render_answer


def result(rows):
    return Evidence(
        query_id="q1",
        sql="SELECT 1",
        table="registry",
        rows=rows,
        matched_count=len(rows),
        samples=[],
        period_start=None,
        period_end=None,
        currencies=[],
        units=[],
        filters=None,
        grouped=True,
    )


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("difference", "7.00"),
        ("add", "13.00"),
        ("multiply", "30.00"),
        ("percent_of", "0.30"),
        ("range_size", "8.00"),
    ],
)
def test_arithmetic_operations(operation, expected):
    data = calculate_ratio(result([{"a": "10", "b": "3"}]), "a", "b", 2, operation)
    assert data.rows[0]["ratio"] == expected


def test_a_zero_only_blocks_division():
    rows = [{"a": "5", "b": "0"}]
    assert calculate_ratio(result(rows), "a", "b", 2, "difference").rows[0]["ratio"] == "5.00"
    assert calculate_ratio(result(rows), "a", "b", 2, "ratio").rows[0]["ratio"] is None


def test_chained_calculations_keep_every_result():
    data = result([{"a": "100", "b": "10", "c": "200", "d": "10"}])
    data = calculate_ratio(data, "a", "b", 2, "ratio")
    data = calculate_ratio(data, "c", "d", 2, "ratio")
    data = calculate_ratio(data, "ratio_2", "ratio", 2, "change_percent")
    assert data.rows[0]["ratio"] == "10.00"
    assert data.rows[0]["ratio_2"] == "20.00"
    assert data.rows[0]["ratio_3"] == "100.00"
    assert list(data.computed_columns) == ["ratio", "ratio_2", "ratio_3"]


def test_each_calculated_column_has_its_own_label():
    data = result([{"a": "100", "b": "10"}])
    data = calculate_ratio(data, "a", "b", 2, "difference")
    data = calculate_ratio(data, "ratio", "b", 2, "percentage")
    text = render_answer(Answer(outcome="answer", language="ru", evidence=data))
    assert "Разница: 90" in text
    assert "Процент, %: 900" in text


def test_a_result_can_be_sorted_by_a_calculated_value():
    rows = [{"r": "A", "v": "1.5"}, {"r": "B", "v": "20"}, {"r": "C", "v": "3"}]
    data = arrange_result(result(rows), "v", "descending", None)
    assert [row["r"] for row in data.rows] == ["B", "C", "A"]
    data = arrange_result(result(rows), "v", "ascending", 1)
    assert [row["r"] for row in data.rows] == ["A"]


def test_keeping_the_top_keeps_ties_and_drops_blanks():
    rows = [
        {"r": "A", "v": "5"},
        {"r": "B", "v": "5.0"},
        {"r": "C", "v": "1"},
        {"r": "D", "v": None},
    ]
    assert [row["r"] for row in arrange_result(result(rows), "v", "descending", 1).rows] == [
        "A",
        "B",
    ]
    assert [row["r"] for row in arrange_result(result(rows), "v", "ascending", 9).rows] == [
        "C",
        "A",
        "B",
    ]


def test_a_capped_or_unknown_sort_is_rejected():
    rows = [{"r": "A", "v": "5"}]
    with pytest.raises(ValueError):
        arrange_result(result(rows).model_copy(update={"truncated": True}), "v", "descending", 1)
    with pytest.raises(ValueError):
        arrange_result(result(rows), "missing", "descending", 1)
    with pytest.raises(ValueError):
        arrange_result(result(rows), "v", "descending", 0)


async def test_the_model_can_sort_a_calculated_result(sample_database):
    client = ScriptedClient(
        [
            review(task="rank", subject="market", ranking_by="amount"),
            (
                "query_registry",
                {
                    "sql": "SELECT region, SUM(amount_uzs) AS total, COUNT(*) AS n FROM registry "
                    "WHERE NOT is_cancelled GROUP BY region"
                },
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "total",
                    "denominator": "n",
                    "scale": 2,
                    "operation": "ratio",
                },
            ),
            (
                "arrange_result",
                {"query_id": "q2", "column": "ratio", "direction": "descending", "keep_first": 1},
            ),
            finish(query_id="q3"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Qaysi hudud?")
    assert answer.outcome == "answer"
    assert len(answer.evidence.rows) == 1


def test_every_tool_field_is_required_for_strict_mode():
    for item in TOOLS:
        schema = item["parameters"]
        assert sorted(schema.get("required", [])) == sorted(schema["properties"]), item["name"]
        assert "default" not in json.dumps(schema), item["name"]
