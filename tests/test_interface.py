import csv
import io
import json

import pytest
from test_engine import ScriptedClient, finish
from test_telegram import FakeBot, message_job

from uzex.config import Settings
from uzex.engine import Engine
from uzex.interface import COPY, MENU, main_keyboard, telegram_html
from uzex.models import Answer
from uzex.render import LABELS, TEXT, export_csv, render_answer, split_text
from uzex.state import State
from uzex.telegram import Service


def make_service(tmp_path, sample_database, client=None):
    state = State(tmp_path / "state.db")
    return Service(FakeBot(), state, Engine(Settings(_env_file=None), client, sample_database))


async def test_first_start_has_picker_and_persistent_menu(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.enqueue(1, 1, {"type": "message", "text": "/start", "language_code": "ru"})
    job = service.state.claim()
    result = await service.prepare(job)
    service.state.save_result(job["id"], result)
    await service.deliver(job, result)
    first, second = service.bot.messages
    assert "<b>UZEX21</b>" in first["text"]
    assert "Задавайте" in first["text"]
    assert first["reply_markup"].is_persistent
    assert first["reply_markup"].keyboard[0][0].text == "Примеры"
    assert second["reply_markup"].inline_keyboard[0][0].callback_data == "lang:uz"
    assert len(second["reply_markup"].inline_keyboard[0]) == 2
    assert service.state.chat(1)["language"] is None
    service.state.close()


async def test_changing_menu_language_preserves_conversation(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.remember(1, "Кто продавец?", "Ответ")
    before = service.state.chat(1)["history"]
    result = await service.prepare(
        {
            "chat_id": 1,
            "payload": json.dumps({"type": "callback", "data": "lang:uz", "callback_id": "c"}),
        }
    )
    assert service.state.chat(1)["language"] == "uz"
    assert service.state.chat(1)["history"] == before
    assert result["ui_language"] == "uz"
    assert service.bot.commands[0][1]["scope"].chat_id == 1
    service.state.close()


@pytest.mark.parametrize(
    "menu_language,question,answer_language",
    [
        ("uz", "Кто продавец по сделке 100001?", "ru"),
        ("ru", "100001-bitimning sotuvchisi kim?", "uz"),
        ("uz", "Ответь на узбекском: кто продавец по сделке 100001?", "uz"),
    ],
)
async def test_menu_language_does_not_force_answer_language(
    tmp_path, sample_database, menu_language, question, answer_language
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
    service.state.language(1, menu_language)
    result = await service.prepare(message_job(question))
    assert result["answer"]["language"] == answer_language
    assert service.state.chat(1)["language"] == menu_language
    assert "override from the caller is: none" in client.requests[0]["instructions"]
    service.state.close()


async def test_direct_question_works_without_language_selection(tmp_path, sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    result = await service.prepare(message_job("Кто продавец по сделке 100001?"))
    assert result["answer"]["outcome"] == "answer"
    assert service.state.chat(1)["language"] is None
    service.state.close()


@pytest.mark.parametrize("button", ["Misollar", "Примеры", "Yordam", "Помощь", "Menyu"])
async def test_menu_does_not_call_model(tmp_path, sample_database, button):
    service = make_service(tmp_path, sample_database)
    value = "/menu" if button == "Menyu" else button
    result = await service.prepare(message_job(value))
    assert "answer" not in result
    assert result["menu_at"] == 0
    service.state.close()


async def test_reset_clears_history_but_keeps_menu_language(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    service.state.language(1, "ru")
    service.state.remember(1, "q", "a")
    await service.prepare(message_job("Новый диалог"))
    assert service.state.chat(1) == {"language": "ru", "history": []}
    service.state.close()


async def test_whitespace_is_handled_without_retry_loop(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("   \n "))
    assert result["texts"] == [COPY["text_only"][0]]
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
    for language in ("uz", "ru"):
        keyboard = main_keyboard(language)
        assert keyboard.is_persistent and keyboard.resize_keyboard
