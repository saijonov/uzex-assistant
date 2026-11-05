import csv
import io

import pytest
from test_engine import ScriptedClient, finish
from test_telegram import FakeBot, message_job

from uzex.config import Settings
from uzex.engine import Engine
from uzex.interface import COPY, MENU, both, main_keyboard, telegram_html
from uzex.models import Answer
from uzex.render import LABELS, TEXT, export_csv, render_answer, split_text
from uzex.state import State
from uzex.telegram import Service


def make_service(tmp_path, sample_database, client=None):
    state = State(tmp_path / "state.db")
    return Service(FakeBot(), state, Engine(Settings(_env_file=None), client, sample_database))


async def test_start_greets_in_both_languages_without_asking_for_one(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.enqueue(1, 1, {"type": "message", "text": "/start"})
    job = service.state.claim()
    result = await service.prepare(job)
    service.state.save_result(job["id"], result)
    await service.deliver(job, result)
    assert len(service.bot.messages) == 1
    message = service.bot.messages[0]
    assert "<b>UZEX21</b>" in message["text"]
    assert "so‘rang" in message["text"] and "Задавайте" in message["text"]
    assert message["reply_markup"].is_persistent
    service.state.close()


def test_keyboard_offers_every_action_in_both_languages_and_no_language_button():
    keyboard = main_keyboard()
    labels = [button.text for row in keyboard.keyboard for button in row]
    assert labels == ["Misollar / Примеры", "Yordam / Помощь", "Yangi suhbat / Новый диалог"]


async def test_start_removes_the_language_command_saved_for_the_chat(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    await service.prepare(message_job("/start"))
    assert service.bot.deleted_commands[0]["scope"].chat_id == 1
    service.state.close()


async def test_commands_are_published_once_without_a_language_command(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    await service.publish_commands()
    assert [item["language_code"] for item in service.bot.deleted_commands] == ["uz", "ru"]
    assert len(service.bot.commands) == 1
    published, options = service.bot.commands[0]
    assert options == {}
    assert [command.command for command in published] == [
        "start",
        "menu",
        "examples",
        "help",
        "reset",
    ]
    service.state.close()


async def test_the_old_language_command_only_shows_the_menu(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("/language"))
    assert "answer" not in result
    assert result["menu_at"] == 0
    assert "language_keyboard" not in result
    service.state.close()


@pytest.mark.parametrize(
    "question,answer_language",
    [
        ("Кто продавец по сделке 100001?", "ru"),
        ("100001-bitimning sotuvchisi kim?", "uz"),
        ("Ответь на узбекском: кто продавец по сделке 100001?", "uz"),
    ],
)
async def test_the_question_alone_decides_the_answer_language(
    tmp_path, sample_database, question, answer_language
):
    end = finish()
    end[1]["language"] = answer_language
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            end,
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    result = await service.prepare(message_job(question))
    assert result["answer"]["language"] == answer_language
    assert "override from the caller is: none" in client.requests[0]["instructions"]
    service.state.close()


@pytest.mark.parametrize(
    "button",
    [
        "Misollar / Примеры",
        "Yordam / Помощь",
        "Misollar",
        "Примеры",
        "Yordam",
        "Помощь",
        "Til",
        "Язык",
        "/menu",
    ],
)
async def test_menu_does_not_call_model(tmp_path, sample_database, button):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job(button))
    assert "answer" not in result
    assert result["menu_at"] == 0
    service.state.close()


async def test_menu_replies_come_in_both_languages(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    examples = await service.prepare(message_job("Misollar / Примеры"))
    assert "100001-bitimning" in examples["texts"][0]
    assert "по сделке 100001" in examples["texts"][0]
    support = await service.prepare(message_job("Yordam / Помощь"))
    assert "Yordam" in support["texts"][0] and "Помощь" in support["texts"][0]
    assert "tilini" not in support["texts"][0] and "Язык меню" not in support["texts"][0]
    service.state.close()


async def test_reset_clears_history(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.remember(1, "q", "a")
    result = await service.prepare(message_job("Yangi suhbat / Новый диалог"))
    assert service.state.chat(1) == {"history": []}
    assert "Yangi suhbat" in result["texts"][0] and "Новый диалог" in result["texts"][0]
    service.state.close()


async def test_whitespace_is_handled_without_retry_loop(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("   \n "))
    assert result["texts"] == [both("text_only")]
    service.state.close()


async def test_csv_contains_exact_answer_columns_and_explains_scope(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    data = sample_database.query(
        "SELECT deal_id, seller_name, seller_inn FROM registry WHERE deal_id='100001'",
        "q1",
    )
    service.state.enqueue(1, 1, {})
    owner = service.state.claim()
    service.state.save_result(
        owner["id"],
        {
            "texts": [],
            "answer": Answer(outcome="answer", language="uz", evidence=data).model_dump(
                mode="json"
            ),
        },
    )
    service.state.complete(owner["id"])
    service.state.enqueue(
        2, 1, {"type": "callback", "data": "csv:" + owner["id"], "callback_id": "c"}
    )
    job = service.state.claim()
    result = await service.prepare(job)
    await service.deliver(job, result)
    document = service.bot.documents[0]
    assert "Qatorlar: 1. Ustunlar: 3." in document["caption"]
    rows = list(csv.reader(io.StringIO(document["document"].data.decode("utf-8-sig"))))
    assert rows[0] == ["deal_id", "seller_name", "seller_inn"]
    assert len(rows) == 2
    service.state.close()


def test_html_escapes_data_without_losing_bold_labels():
    result = telegram_html('Sotuvchi: <a href="https://evil.example">Fake</a> & Co')
    assert result.startswith("<b>Sotuvchi:</b>")
    assert "<a " not in result
    assert "&lt;a href=" in result
    assert "&amp; Co" in result


def test_plain_text_is_split_before_html_formatting():
    text = ("Sotuvchi: " + "<&" * 100 + "\n") * 30
    for chunk in split_text(text):
        html = telegram_html(chunk)
        assert html.count("<b>") == html.count("</b>")
        assert len(chunk) <= 3500


def test_short_lookup_does_not_add_unrelated_metadata(sample_database):
    data = sample_database.query("SELECT seller_name FROM registry WHERE deal_id='100001'", "q1")
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert text.startswith("Sotuvchi:")
    assert "Valyuta" not in text
    assert "Birlik" not in text
    assert len(text.splitlines()) <= 4


def test_export_neutralizes_formulas(sample_database):
    data = sample_database.query("SELECT seller_name FROM registry WHERE deal_id='100001'", "q1")
    data.rows = [{"seller_name": "=IMPORTDATA(1)"}]
    assert "'=IMPORTDATA(1)" in export_csv(data).decode("utf-8-sig")


async def test_empty_result_has_no_buttons_or_empty_csv(tmp_path, sample_database):
    client = ScriptedClient(
        [
            (
                "query_registry",
                {"sql": "SELECT seller_name FROM registry WHERE deal_id='999999999'"},
            ),
            finish("no_match"),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    service.state.enqueue(1, 1, {"type": "message", "text": "Кто продавец по сделке 999999999?"})
    job = service.state.claim()
    result = await service.prepare(job)
    await service.deliver(job, result)
    assert service.bot.messages[-1]["reply_markup"] is None
    assert service.bot.documents == []
    service.state.close()


def test_authored_messages_have_no_long_dashes():
    for mapping in (COPY, MENU, TEXT, LABELS):
        for pair in mapping.values():
            assert all("—" not in value and "–" not in value for value in pair)
    keyboard = main_keyboard()
    assert keyboard.is_persistent and keyboard.resize_keyboard
