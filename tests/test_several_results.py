import json

from test_answer_fit import detail_review
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.engine import Engine
from uzex.evaluate import grade
from uzex.models import Answer
from uzex.policy import cancellation_gap
from uzex.render import memory_text, render_answer


def several_parts(extra_ids, *queries):
    calls = [review(task="count")]
    for sql in queries:
        calls.append(("query_registry", {"sql": sql}))
    calls.append(finish(also=extra_ids))
    return ScriptedClient(calls)


async def test_an_answer_can_show_several_results(sample_database):
    client = several_parts(
        ["q2", "q3"],
        "SELECT COUNT(*) AS n FROM registry",
        "SELECT SUM(amount_uzs) AS total FROM registry WHERE NOT is_cancelled",
        "SELECT deal_id FROM registry WHERE NOT is_cancelled ORDER BY amount_uzs DESC LIMIT 1",
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Uchta savol")
    assert answer.outcome == "answer"
    assert [part.query_id for part in answer.extra_evidence] == ["q2", "q3"]
    text = render_answer(answer)
    assert "Количество записей" in text
    assert "Итого: Сумма, сум" in text
    assert "Номер сделки" in text


async def test_a_made_up_result_id_is_rejected(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(also=["q9"]),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Savol")
    assert answer.outcome == "answer"
    assert answer.extra_evidence == []
    assert len(client.requests) >= 4


async def test_an_empty_first_part_does_not_hide_the_second(sample_database):
    client = several_parts(
        ["q2"],
        "SELECT COUNT(*) AS n FROM registry WHERE deal_date = DATE '2000-01-01'",
        "SELECT COUNT(*) AS n FROM registry",
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Savol")
    assert answer.outcome == "answer"
    text = render_answer(answer)
    assert "Записей по этим условиям нет" in text
    assert "———" in text


async def test_every_part_is_checked_for_cancelled_deals(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS n FROM registry WHERE NOT is_cancelled"},
            ),
            ("query_registry", {"sql": "SELECT SUM(amount_uzs) AS total FROM registry"}),
            finish(also=["q2"]),
            (
                "query_registry",
                {"sql": "SELECT SUM(amount_uzs) AS total FROM registry WHERE NOT is_cancelled"},
            ),
            finish(also=["q3"]),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Bekor qilinganlarsiz soni va summasi"
    )
    assert answer.outcome == "answer"
    assert answer.extra_evidence[0].query_id == "q3"


def test_later_turns_can_see_every_part(sample_database):
    answer = Answer(
        outcome="answer",
        evidence=sample_database.query("SELECT COUNT(*) AS n FROM registry", "q1"),
        extra_evidence=[sample_database.query("SELECT MAX(amount_uzs) AS m FROM registry", "q2")],
    )
    summary = json.loads(memory_text(answer, "").partition(": ")[2])
    assert summary["other_results"][0]["columns"] == ["m"]


def test_a_count_next_to_a_turnover_may_include_cancelled(sample_database):
    review_model = detail_review(task="turnover", subject="market")
    count = sample_database.query("SELECT COUNT(*) AS n FROM registry", "q1")
    assert cancellation_gap(review_model, "soni va summasi", count) is None


def test_a_filter_inside_the_measure_counts_as_excluding(sample_database):
    review_model = detail_review(task="turnover", subject="market")
    data = sample_database.query(
        "SELECT COUNT(*) AS n, SUM(amount_uzs) FILTER (WHERE NOT is_cancelled) AS total FROM registry",
        "q1",
    )
    assert cancellation_gap(review_model, "2025 summa", data) is None


def test_a_plain_sum_still_breaks_the_turnover_default(sample_database):
    review_model = detail_review(task="turnover", subject="market")
    data = sample_database.query("SELECT SUM(amount_uzs) AS total FROM registry", "q1")
    assert "by default" in cancellation_gap(review_model, "2025 summa", data)


def test_grading_looks_at_every_part(sample_database):
    answer = Answer(
        outcome="answer",
        language="uz",
        evidence=sample_database.query("SELECT COUNT(*) AS n FROM registry", "q1"),
        extra_evidence=[sample_database.query("SELECT COUNT(*) AS m FROM participants", "q2")],
    )
    assert answer.extra_evidence[0].rows[0]["m"] != answer.evidence.rows[0]["n"]
    case = {
        "outcomes": ["answer"],
        "language": "uz",
        "expected_values": [str(answer.extra_evidence[0].rows[0]["m"])],
    }
    assert grade(case, answer)
