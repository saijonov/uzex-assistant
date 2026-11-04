import pytest
from aiogram.exceptions import TelegramBadRequest
from conversation_helpers import enqueue
from test_engine import ScriptedClient, finish
from test_interface import make_service

from uzex.models import Answer
from uzex.render import label, render_answer


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT COUNT(DISTINCT seller_inn) AS n FROM registry", "Sotuvchilar soni"),
        ("SELECT SUM(DISTINCT amount_uzs) AS n FROM registry", "Summa, so‘m"),
    ],
)
def test_distinct_aggregates_render(sample_database, sql, expected):
    answer = Answer(outcome="answer", language="uz", evidence=sample_database.query(sql, "q1"))
    assert expected in render_answer(answer)


def test_distinct_label_exists_in_russian():
    assert "Количество покупателей" in label("COUNT(DISTINCT buyer_inn)", "ru")


def test_label_never_raises_on_expressions_it_cannot_parse():
    assert label("DISTINCT )(", "uz") == "DISTINCT )("


async def test_internal_failure_replies_once_without_rerunning_the_model(
    tmp_path, sample_database, monkeypatch
):
    client = ScriptedClient(
        [("query_registry", {"sql": "SELECT seller_name FROM registry LIMIT 1"}), finish()]
    )
    service = make_service(tmp_path, sample_database, client)

    def broken(*args, **kwargs):
        raise RuntimeError("renderer bug")

    monkeypatch.setattr("uzex.telegram.render_answer", broken)
    job = enqueue(service, "Кто продавец?")
    await service.process(job)
    assert len(client.requests) == 3
    assert len(service.bot.messages) == 1
    assert "Не удалось" in service.bot.messages[0]["text"]
    assert service.state.claim() is None
    service.state.close()


async def test_rejected_telegram_message_still_tells_the_user(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    original = service.bot.send_message
    calls = []

    async def rejecting(chat_id, text, **kwargs):
        calls.append(text)
        if len(calls) == 1:
            raise TelegramBadRequest(method=None, message="can't parse entities")
        await original(chat_id, text, **kwargs)

    service.bot.send_message = rejecting
    job = enqueue(service, "/help")
    await service.process(job)
    assert len(calls) == 2
    assert service.state.claim() is None
    service.state.close()
