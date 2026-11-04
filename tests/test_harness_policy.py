import json

import pytest
from test_engine import ScriptedClient, finish, review
from test_interface import make_service
from test_telegram import message_job

from uzex.config import Settings
from uzex.engine import Engine
from uzex.models import Answer
from uzex.policy import attach_csv, file_preference, resolve_pending_reply
from uzex.render import cancellation_note, render_answer
from uzex.state import State


async def test_missing_detail_is_asked_before_any_query(sample_database):
    client = ScriptedClient(
        [
            review(
                language="uz",
                task="price",
                subject="product",
                reference="missing",
                period="missing",
                missing_fields=["product", "period"],
            )
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Narx qancha?")
    assert answer.outcome == "clarify"
    assert answer.missing_fields == ["product"]
    assert len(client.requests) == 1
    assert client.requests[0]["tool_choice"] == {"type": "function", "name": "review_request"}
    assert "Qaysi tovar" in render_answer(answer)


async def test_query_cannot_bypass_required_review(sample_database):
    client = ScriptedClient(
        [("query_registry", {"sql": "SELECT COUNT(*) FROM registry"})], review_first=False
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Сколько сделок?"
    )
    assert answer.outcome == "error"
    assert answer.evidence is None


async def test_review_cannot_invent_an_entity_reference(sample_database):
    client = ScriptedClient([review(reference="specified", entity_text="Imaginary Company")])
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Сколько сделок?"
    )
    assert answer.outcome == "clarify"
    assert answer.missing_fields == ["entity"]


async def test_ranking_requires_a_ranking_metric(sample_database):
    client = ScriptedClient([review(task="rank", subject="broker", ranking_by="missing")])
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Лучший брокер?"
    )
    assert answer.outcome == "clarify"
    assert answer.missing_fields == ["ranking"]


async def test_live_price_is_unavailable_not_a_unit_question(sample_database):
    client = ScriptedClient(
        [
            review(
                task="price",
                subject="product",
                reference="specified",
                entity_text="сахара",
                period="specified",
                missing_fields=["unit"],
            )
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какова живая цена сахара прямо сейчас?"
    )
    assert answer.outcome == "unavailable"
    assert not answer.missing_fields


async def test_unsupported_information_does_not_trigger_useless_questions(sample_database):
    client = ScriptedClient(
        [
            review(task="unsupported", missing_fields=["entity"]),
            finish("unavailable", None, "missing_field"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какая чистая прибыль?"
    )
    assert answer.outcome == "unavailable"


async def test_pending_period_is_resolved_and_cleared(tmp_path, sample_database):
    client = ScriptedClient(
        [
            review(
                language="uz",
                task="count",
                subject="market",
                period="missing",
                missing_fields=["period"],
            ),
            review(
                language="uz", task="count", subject="market", period="specified", continuation=True
            ),
            (
                "query_registry",
                {
                    "sql": "SELECT COUNT(*) AS n FROM registry WHERE deal_date BETWEEN DATE '2022-01-01' AND DATE '2022-12-31'"
                },
            ),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    first = await service.prepare(message_job("Shu davrdagi bitimlar soni?"))
    assert first["answer"]["outcome"] == "clarify"
    assert service.state.pending(1)["question"] == "Shu davrdagi bitimlar soni?"
    second = await service.prepare(message_job("2022"))
    assert second["answer"]["outcome"] == "answer"
    assert "2022-01-01" in second["answer"]["evidence"]["sql"]
    assert service.state.pending(1) is None
    assert any(
        isinstance(item, dict) and "Unresolved request context" in item.get("content", "")
        for item in client.requests[1]["input"]
    )
    service.state.close()


def test_pending_questions_survive_restart_and_are_isolated(tmp_path):
    path = tmp_path / "state.db"
    state = State(path)
    pending = {"question": "Shakar narxi?", "missing_fields": ["period"]}
    state.set_pending(1, pending)
    state.close()
    state = State(path)
    assert state.pending(1) == pending
    assert state.pending(2) is None
    state.reset(1)
    assert state.pending(1) is None
    state.close()


def test_numbered_choice_is_bound_to_verified_candidate():
    pending = {"question": "Kompaniya?", "candidates": [{"inn": "111111111"}, {"inn": "222222222"}]}
    assert resolve_pending_reply(pending, "2")["selected_candidate"] == {"inn": "222222222"}
    assert resolve_pending_reply(pending, "ikkinchisi")["selected_candidate"] == {
        "inn": "222222222"
    }
    assert "selected_candidate" not in resolve_pending_reply(pending, "999999")


async def test_ambiguous_identity_cannot_be_queried_until_user_chooses(sample_database):
    client = ScriptedClient(
        [
            review(task="detail", subject="company", reference="specified", entity_text="MChJ"),
            ("lookup_entities", {"kind": "company", "text": "MChJ"}),
            ("query_registry", {"sql": "SELECT name FROM participants LIMIT 1"}),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["entity"], "candidates_query_id": "lookup_1"},
            ),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "MChJ kompaniyasi haqida"
    )
    assert answer.outcome == "clarify"
    assert answer.evidence is None
    assert answer.candidates
    real_inns = {row["inn"] for row in sample_database.catalog["company"]}
    assert all(row["inn"] in real_inns for row in answer.candidates)
    outputs = [
        json.loads(item["output"])
        for item in client.requests[-1]["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert any("Ambiguous entity" in item.get("error", "") for item in outputs)


@pytest.mark.parametrize(
    "question,preference",
    [
        ("100001 sotuvchisi kim?", "auto"),
        ("100001 sotuvchisini CSV formatida ber", "csv"),
        ("CSV qilib ber", "csv"),
        ("Все брокеры без CSV", "text"),
        ("Все брокеры, CSV не нужен", "text"),
        ("Barcha brokerlar, CSV kerak emas", "text"),
        ("Faol brokerlar, faqat matn", "text"),
        ("brokers.csv faylda nechta broker bor?", "auto"),
        ("2025-yilda nechta bitim? CSV formatida ber", "csv"),
        ("Все брокеры, не нужен CSV", "text"),
    ],
)
def test_delivery_preference_is_explicit(question, preference):
    assert file_preference(question) == preference


@pytest.mark.parametrize(
    "question,many,expected",
    [
        ("Kim sotuvchi?", False, False),
        ("CSV formatida ber", False, True),
        ("Все брокеры", True, True),
        ("Все брокеры без CSV", True, False),
    ],
)
def test_small_answers_and_large_lists_have_different_file_policy(
    sample_database, question, many, expected
):
    sql = (
        "SELECT broker_code FROM brokers ORDER BY broker_code"
        if many
        else "SELECT seller_name FROM registry WHERE deal_id='100001'"
    )
    answer = Answer(outcome="answer", evidence=sample_database.query(sql, "q1"))
    assert attach_csv(question, answer) is expected
    assert not attach_csv(question, Answer(outcome="clarify"))


async def test_small_explicit_csv_is_attached_without_buttons(tmp_path, sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    service.state.enqueue(
        1, 1, {"type": "message", "text": "100001 sotuvchisini CSV formatida ber"}
    )
    job = service.state.claim()
    result = await service.prepare(job)
    await service.deliver(job, result)
    assert len(service.bot.documents) == 1
    assert service.bot.messages[-1]["reply_markup"] is None
    service.state.close()


async def test_large_text_only_answer_has_no_file_or_export_buttons(tmp_path, sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT broker_code FROM brokers ORDER BY broker_code"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    service.state.enqueue(1, 1, {"type": "message", "text": "Все брокеры без CSV"})
    job = service.state.claim()
    result = await service.prepare(job)
    await service.deliver(job, result)
    assert not service.bot.documents
    buttons = service.bot.messages[-1]["reply_markup"].inline_keyboard
    assert all(button.callback_data.startswith("page:") for row in buttons for button in row)
    service.state.close()


async def test_export_without_previous_result_asks_for_reference(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("CSV qilib ber"))
    assert result["answer"]["outcome"] == "clarify"
    assert result["answer"]["missing_fields"] == ["reference"]
    assert service.state.pending(1)["delivery"] == "csv"
    assert "csv_answer" not in result
    service.state.close()


def test_export_does_not_skip_latest_unavailable_answer(tmp_path, sample_database):
    state = State(tmp_path / "state.db")
    evidence = sample_database.query(
        "SELECT seller_name FROM registry WHERE deal_id='100001'", "q1"
    )
    for update, answer in [
        (1, Answer(outcome="answer", evidence=evidence)),
        (2, Answer(outcome="unavailable")),
    ]:
        state.enqueue(update, 1, {})
        job = state.claim()
        state.save_result(job["id"], {"texts": [], "answer": answer.model_dump(mode="json")})
        state.complete(job["id"])
    assert state.latest_answer(1) is None
    state.close()


@pytest.mark.parametrize(
    "predicate,expected",
    [
        ("NOT is_cancelled", "исключены"),
        ("is_cancelled = FALSE", "исключены"),
        ("is_cancelled = TRUE", "Только"),
        ("NOT is_cancelled OR deal_id='100001'", None),
    ],
)
def test_inline_evidence_describes_cancellation_filter(sample_database, predicate, expected):
    data = sample_database.query(f"SELECT COUNT(*) FROM registry WHERE {predicate}", "q1")
    note = cancellation_note(data, "ru")
    assert (expected in note) if expected else note is None
