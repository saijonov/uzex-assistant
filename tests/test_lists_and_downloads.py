import csv
import io
import json
from pathlib import Path

import pytest
from test_engine import ScriptedClient, finish
from test_interface import make_service

from uzex.downloads import requested_source_file, source_csv
from uzex.models import Answer
from uzex.render import render_answer


def test_source_download_has_all_original_broker_rows_and_headers(sample_database):
    content, count, columns = source_csv(sample_database, "brokers.csv")
    records = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    with Path("tests/fixtures/brokers.csv").open() as file:
        expected = list(csv.DictReader(file))
    assert records == expected
    assert count == len(expected)
    assert columns == 4
    assert list(records[0]) == ["Код брокера", "Наименование", "ИНН", "Регион"]


@pytest.mark.parametrize(
    "question,filename",
    [
        ("menga brokers csv fileni jo'nat", "brokers.csv"),
        ("Отправь brokers.csv", "brokers.csv"),
        ("менга brokers.csv файлини жўнат", "brokers.csv"),
        ("Send participants.csv", "participants.csv"),
        ("brokers.csv faylda nechta broker bor?", None),
        ("Пришли .env", None),
        ("send ../../brokers.csv", None),
    ],
)
def test_source_intent_is_explicit_and_allowlisted(question, filename):
    assert requested_source_file(question) == filename


def test_unknown_files_cannot_be_read(sample_database):
    with pytest.raises(ValueError):
        source_csv(sample_database, "../.env")


def test_all_brokers_are_not_silently_capped_at_one_hundred(sample_database):
    complete = sample_database.query("SELECT broker_code FROM brokers ORDER BY broker_code", "q1")
    limited = sample_database.query(
        "SELECT broker_code FROM brokers ORDER BY broker_code LIMIT 100", "q2"
    )
    assert len(complete.rows) == 120
    assert not complete.truncated
    assert len(limited.rows) == 100
    assert complete.matched_count == limited.matched_count == 120


def test_pages_have_different_rows_and_global_indices(sample_database):
    evidence = sample_database.query(
        "SELECT broker_code, name FROM brokers ORDER BY broker_code", "q1"
    )
    assert len(evidence.rows) > 10
    answer = Answer(outcome="answer", language="uz", evidence=evidence)
    first, second = render_answer(answer), render_answer(answer, 1)
    assert second.startswith("11.\n")
    assert evidence.rows[10]["broker_code"] in second
    assert evidence.rows[0]["broker_code"] not in second
    assert first != second
    with pytest.raises(ValueError):
        render_answer(answer, 1000)


async def test_page_callbacks_use_owners_full_result_without_model(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    evidence = sample_database.query(
        "SELECT broker_code, name FROM brokers ORDER BY broker_code", "q1"
    )
    service.state.enqueue(1, 10, {})
    owner = service.state.claim()
    service.state.save_result(
        owner["id"],
        {
            "texts": [],
            "answer": Answer(outcome="answer", language="uz", evidence=evidence).model_dump(
                mode="json"
            ),
        },
    )
    service.state.complete(owner["id"])
    payload = {"type": "callback", "data": "page:" + owner["id"] + ":1", "callback_id": "c"}
    service.state.enqueue(2, 10, payload)
    job = service.state.claim()
    result = await service.prepare(job)
    assert result["page"] == 1
    assert result["source_job_id"] == owner["id"]
    await service.deliver(job, result)
    buttons = service.bot.messages[-1]["reply_markup"].inline_keyboard
    assert buttons[1][0].callback_data == "page:" + owner["id"] + ":0"
    forbidden = await service.prepare({"chat_id": 11, "payload": json.dumps(payload)})
    assert "answer" not in forbidden
    service.state.close()


async def test_explicit_source_request_sends_a_document_not_a_preview(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.enqueue(1, 10, {"type": "message", "text": "menga brokers csv fileni jo'nat"})
    job = service.state.claim()
    result = await service.prepare(job)
    assert result["texts"] == []
    assert result["source_csv"] == "brokers.csv"
    await service.deliver(job, result)
    assert service.bot.messages == []
    assert len(service.bot.documents) == 1
    assert service.bot.documents[0]["document"].filename == "brokers.csv"
    service.state.close()


async def test_large_list_automatically_attaches_all_result_rows(tmp_path, sample_database):
    client = ScriptedClient(
        [
            (
                "query_registry",
                {"sql": "SELECT broker_code, name FROM brokers ORDER BY broker_code"},
            ),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    service.state.enqueue(1, 10, {"type": "message", "text": "Все брокеры"})
    job = service.state.claim()
    result = await service.prepare(job)
    assert result["attach_csv"]
    await service.deliver(job, result)
    content = service.bot.documents[0]["document"].data.decode("utf-8-sig")
    exported = list(csv.DictReader(io.StringIO(content)))
    assert len(exported) == len(result["answer"]["evidence"]["rows"])
    assert len(exported) > 10
    assert (
        service.bot.messages[-1]["reply_markup"]
        .inline_keyboard[1][0]
        .callback_data.startswith("page:")
    )
    service.state.close()
