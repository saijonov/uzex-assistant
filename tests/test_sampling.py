import csv
import io

import pytest
from test_engine import ScriptedClient, finish, review
from test_interface import make_service
from test_telegram import message_job

from uzex.config import Settings
from uzex.database import validate_query
from uzex.engine import Engine
from uzex.models import Answer
from uzex.policy import missing_requirements
from uzex.render import export_csv, render_answer


def test_sample_uses_real_unique_rows_and_frozen_provenance(sample_database):
    result = sample_database.sample("SELECT * FROM registry", 10, "q1")
    assert result.selection == "random"
    assert len(result.rows) == result.selected_record_count == 10
    ids = {row["deal_id"] for row in result.rows}
    assert len(ids) == 10
    assert {row["deal_id"] for row in result.samples} <= ids
    assert result.rows == sample_database.query(result.sql, "replay").rows
    dates = sorted(row["deal_date"] for row in result.rows)
    assert [result.period_start, result.period_end] == [dates[0], dates[-1]]
    assert "tasodifiy" in render_answer(Answer(outcome="answer", evidence=result))
    exported = list(csv.DictReader(io.StringIO(export_csv(result).decode("utf-8-sig"))))
    assert {row["deal_id"] for row in exported} == ids


def test_sample_preserves_requested_filter_and_selected_fields(sample_database):
    result = sample_database.sample(
        "SELECT deal_id, seller_name, deal_date FROM registry WHERE deal_date >= DATE '2025-01-01'",
        3,
        "q1",
    )
    assert len(result.rows) == 3
    assert all(row["deal_date"] >= "2025-01-01" for row in result.rows)
    assert set(result.rows[0]) == {"deal_id", "seller_name", "deal_date"}
    assert result.rows == sample_database.query(result.sql, "replay").rows


def test_sample_does_not_invent_rows_to_fill_requested_count(sample_database):
    result = sample_database.sample("SELECT * FROM registry WHERE deal_id='100001'", 100, "q1")
    assert len(result.rows) == 1
    assert result.rows[0]["deal_id"] == "100001"
    empty = sample_database.sample("SELECT * FROM registry WHERE deal_id='not-found'", 100, "q2")
    assert empty.rows == []
    assert empty.matched_count == 0


@pytest.mark.parametrize(
    "table,key",
    [
        ("contracts", "contract_id"),
        ("participants", "inn"),
        ("brokers", "broker_code"),
        ("usd_rates", "rate_date"),
    ],
)
def test_sample_works_with_each_directory(sample_database, table, key):
    result = sample_database.sample(f"SELECT * FROM {table}", 3, "q1")
    assert len(result.rows) == 3
    assert len({row[key] for row in result.rows}) == 3
    assert result.rows == sample_database.query(result.sql, "replay").rows


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM registry",
        "SELECT DISTINCT deal_id FROM registry",
        "SELECT * FROM registry LIMIT 2",
        "SELECT * FROM registry ORDER BY deal_id",
        "SELECT * FROM read_csv('/etc/passwd')",
        "DELETE FROM registry",
    ],
)
def test_sampling_preserves_query_restrictions(sample_database, sql):
    with pytest.raises(ValueError):
        sample_database.sample(sql, 3, "q1")


@pytest.mark.parametrize("count", [0, 101, 1000000])
def test_sample_size_is_bounded(sample_database, count):
    with pytest.raises(ValueError):
        sample_database.sample("SELECT * FROM registry", count, "q1")


def test_random_is_not_exposed_as_arbitrary_model_sql():
    with pytest.raises(ValueError, match="Function not allowed"):
        validate_query("SELECT * FROM registry ORDER BY RANDOM() LIMIT 10")


def test_list_does_not_require_optional_identifiers_or_dates():
    from uzex.models import RequestReview

    request = RequestReview.model_validate(
        review(
            task="list",
            subject="deal",
            reference="not_needed",
            period="all_available",
            missing_fields=["entity", "reference", "product", "period"],
        )[1]
    )
    assert missing_requirements(request, "100ta random", [], None) == []
    ambiguous = request.model_copy(
        update={"reference": "specified", "entity_text": "Toshkent", "missing_fields": ["region"]}
    )
    assert missing_requirements(ambiguous, "Toshkentdan 100 ta bitim", [], None) == ["region"]


async def test_complete_sample_request_answers_without_clarification(sample_database):
    client = ScriptedClient(
        [
            review(task="list", subject="deal", reference="not_needed", period="all_available"),
            ("sample_records", {"sql": "SELECT * FROM registry", "count": 10}),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "10ta random bitim haqida to‘liq ma’lumot ber"
    )
    assert answer.outcome == "answer"
    assert answer.evidence.selection == "random"
    assert len(answer.evidence.rows) == 10


async def test_any_records_followup_resolves_prior_identifier_question(tmp_path, sample_database):
    client = ScriptedClient(
        [
            review(
                task="list",
                subject="deal",
                reference="not_needed",
                period="all_available",
                continuation=True,
            ),
            ("sample_records", {"sql": "SELECT * FROM registry", "count": 100}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    service.state.set_pending(
        1,
        {
            "question": "100ta random birja haqida to'liq malumot ber",
            "missing_fields": ["entity"],
            "candidates": [],
            "delivery": "auto",
        },
    )
    result = await service.prepare(message_job("100ta random, farqi yoq"))
    assert result["answer"]["outcome"] == "answer"
    assert result["answer"]["evidence"]["selection"] == "random"
    assert len(result["answer"]["evidence"]["rows"]) == 27
    assert result["attach_csv"]
    assert service.state.pending(1) is None
    service.state.close()
