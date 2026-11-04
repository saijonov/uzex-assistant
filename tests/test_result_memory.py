import json

import pytest
from conversation_helpers import enqueue, stored
from test_engine import ScriptedClient, finish, review
from test_interface import make_service
from test_telegram import message_job

from uzex.config import Settings
from uzex.engine import Engine
from uzex.models import Answer
from uzex.policy import (
    export_followup,
)
from uzex.render import memory_text, render_answer


def about(topic, language="uz"):
    return ("about_previous_result", {"language": language, "topic": topic})


async def ask_about(sample_database, previous, topic, language="uz", question="?"):
    client = ScriptedClient(
        [review(language=language, reference="context", period="context"), about(topic, language)]
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    answer = await engine.answer(question, None, history, None, previous)
    assert len(client.requests) == 2
    return answer


def test_memory_keeps_every_id_of_a_long_result(sample_database):
    previous = stored(sample_database, "SELECT * FROM registry ORDER BY deal_id")
    text = memory_text(previous, render_answer(previous))
    assert len(text) < 10000
    assert all(row["deal_id"] in text for row in previous.evidence.rows)
    assert "rows_in_result" in text


def test_memory_keeps_the_rows_a_follow_up_refers_to(sample_database):
    previous = stored(
        sample_database,
        "SELECT buyer_inn, buyer_name, COUNT(*) AS n FROM registry "
        "GROUP BY buyer_inn, buyer_name ORDER BY n DESC, buyer_inn LIMIT 3",
    )
    text = memory_text(previous, render_answer(previous))
    assert json.dumps(previous.evidence.rows[0]["buyer_name"], ensure_ascii=False) in text
    assert "COUNT(*)" in text


def test_memory_of_a_clarification_is_the_question_itself():
    answer = Answer(outcome="clarify", language="uz", missing_fields=["period"])
    assert memory_text(answer, "Qaysi davr uchun?") == "Qaysi davr uchun?"


async def test_follow_up_sees_all_ids_even_when_the_display_is_long(tmp_path, sample_database):
    sql = "SELECT * FROM registry ORDER BY deal_id"
    client = ScriptedClient(
        [
            ("query_registry", {"sql": sql}),
            finish(),
            review(reference="context"),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    first = await service.prepare(message_job("Покажи все сделки"))
    await service.prepare(message_job("сумма по ним?"))
    context = json.dumps(client.requests[3]["input"], ensure_ascii=False, default=str)
    assert all(row["deal_id"] in context for row in first["answer"]["evidence"]["rows"])
    service.state.close()


async def test_completeness_of_full_fields_is_answered_in_words(sample_database):
    previous = Answer(
        outcome="answer",
        language="uz",
        evidence=sample_database.sample("SELECT * FROM brokers", 100, "q1"),
    )
    answer = await ask_about(sample_database, previous, "completeness")
    assert answer.outcome == "about"
    text = render_answer(answer)
    assert text.startswith("Ha")
    assert "4 ta maydon" in text
    assert "Broker kodi" in text and "STIR" in text
    assert "120 ta" in text and "100" in text
    assert "tasodifiy" in text
    assert "CSV" in text
    assert "BK0" not in text


async def test_completeness_of_partial_fields_says_no(sample_database):
    previous = stored(sample_database, "SELECT name FROM brokers ORDER BY name")
    text = render_answer(await ask_about(sample_database, previous, "completeness"))
    assert text.startswith("Yo‘q")
    assert "1 ta maydon" in text and "4 ta" in text


async def test_completeness_says_when_only_part_of_the_records_was_returned(sample_database):
    previous = stored(sample_database, "SELECT * FROM brokers ORDER BY broker_code LIMIT 5")
    text = render_answer(
        await ask_about(sample_database, previous, "completeness", "ru", "это всё?")
    )
    assert "120" in text and "5" in text


async def test_method_explains_filters_and_treatment_of_cancelled(sample_database):
    previous = stored(
        sample_database,
        "SELECT SUM(amount_uzs) AS total FROM registry "
        "WHERE deal_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' AND NOT is_cancelled",
    )
    text = render_answer(await ask_about(sample_database, previous, "method"))
    assert "Summa, so‘m" in text
    assert "2025-01-01" in text
    assert "kiritilmagan" in text
    assert "SELECT" not in text


async def test_cancellation_question_reports_inclusion_too(sample_database):
    previous = stored(sample_database, "SELECT COUNT(*) AS n FROM registry")
    text = render_answer(await ask_about(sample_database, previous, "cancellation"))
    assert "kiritilgan" in text


async def test_source_and_confidence_are_answered_from_the_result(sample_database):
    previous = stored(sample_database, "SELECT seller_name FROM registry WHERE deal_id='100001'")
    source = render_answer(await ask_about(sample_database, previous, "source"))
    assert "deals_2022.csv" in source
    assert "o‘ylab topilgan" in source
    confident = render_answer(await ask_about(sample_database, previous, "confidence"))
    assert "deals_2022.csv" in confident


async def test_question_about_nothing_asks_which_result(sample_database):
    client = ScriptedClient([review(language="uz"), about("completeness")])
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("to‘liqmi?")
    assert answer.outcome == "clarify"
    assert answer.missing_fields == ["reference"]


async def answered_list(tmp_path, sample_database, extra_steps):
    client = ScriptedClient(
        [
            (
                "query_registry",
                {"sql": "SELECT broker_code, name FROM brokers ORDER BY broker_code"},
            ),
            finish(),
            *extra_steps,
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    job = enqueue(service, "Все брокеры")
    await service.process(job)
    return service, job


async def test_typed_next_page_continues_the_stored_list(tmp_path, sample_database):
    steps = [review(reference="context"), about("next_page", "ru")] * 2
    service, owner = await answered_list(tmp_path, sample_database, steps)
    second = enqueue(service, "дальше", update=2)
    await service.process(second)
    assert "\n11.\n" in "\n" + service.bot.messages[-1]["text"]
    third = enqueue(service, "ещё", update=3)
    await service.process(third)
    assert "\n21.\n" in "\n" + service.bot.messages[-1]["text"]
    button = service.bot.messages[-1]["reply_markup"].inline_keyboard[0][0]
    assert button.callback_data == f"page:{owner['id']}:1"
    service.state.close()


async def test_next_page_after_the_last_page_says_so(tmp_path, sample_database):
    client = ScriptedClient(
        [
            (
                "query_registry",
                {"sql": "SELECT broker_code FROM brokers ORDER BY broker_code LIMIT 3"},
            ),
            finish(),
            review(reference="context"),
            about("next_page", "ru"),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    await service.process(enqueue(service, "Три брокера"))
    await service.process(enqueue(service, "дальше", update=2))
    assert "3" in service.bot.messages[-1]["text"]
    assert "показан" in service.bot.messages[-1]["text"].casefold()
    service.state.close()


async def test_about_result_has_no_page_buttons_and_keeps_the_list_exportable(
    tmp_path, sample_database
):
    steps = [review(reference="context"), about("completeness", "ru")]
    service, _ = await answered_list(tmp_path, sample_database, steps)
    await service.process(enqueue(service, "это всё?", update=2))
    assert service.bot.messages[-1]["reply_markup"] is None
    assert service.state.latest_answer(1).evidence.rows
    documents = len(service.bot.documents)
    await service.process(enqueue(service, "csv ber", update=3))
    assert len(service.bot.documents) == documents + 1
    service.state.close()


async def test_export_topic_sends_the_stored_rows_without_querying(tmp_path, sample_database):
    steps = [review(reference="context"), about("export", "ru")]
    service, _ = await answered_list(tmp_path, sample_database, steps)
    documents = len(service.bot.documents)
    messages = len(service.bot.messages)
    await service.process(enqueue(service, "сохрани это себе в таблицу", update=2))
    assert len(service.bot.documents) == documents + 1
    assert len(service.bot.messages) == messages
    service.state.close()


@pytest.mark.parametrize(
    "question",
    [
        "csv ber",
        "CSV qilib yubor",
        "shularni csv qilib yubor",
        "shu natijani csv formatida jo'nat",
        "excel qilib ber",
        "faylda yubor",
        "шу csv қилиб бер",
        "файлом пришли",
        "пришли это в csv",
        "в экселе пришли",
    ],
)
def test_short_file_follow_ups_reuse_the_stored_result(question):
    assert export_followup(question)


@pytest.mark.parametrize(
    "question",
    ["2025-yilda nechta bitim csv", "brokers.csv faylda nechta broker bor?", "csv nima?", "salom"],
)
def test_questions_with_their_own_content_are_not_export_follow_ups(question):
    assert not export_followup(question)
