import pytest
from test_interface import make_service
from test_telegram import message_job

from uzex.policy import CLARIFICATION_TEXT, OPTION_TEXT, asks_for_options
from uzex.render import render_options


@pytest.mark.parametrize(
    "text",
    [
        "qanday variantlar bor?",
        "variantlar?",
        "nima yozay?",
        "nimani yozish kerak?",
        "какие варианты?",
        "какие есть варианты",
        "что написать?",
        "что указать",
    ],
)
def test_asking_for_options_is_recognised(text):
    assert asks_for_options(text)


@pytest.mark.parametrize(
    "text",
    [
        "qanday tovarlar bor?",
        "qanday brokerlar bor?",
        "2025-yilda nechta bitim bo'lgan?",
        "какие товары есть?",
        "что продавал этот продавец в 2025 году и какие варианты упаковки у него были",
    ],
)
def test_data_questions_are_not_requests_for_options(text):
    assert not asks_for_options(text)


def test_every_question_the_bot_can_ask_has_options():
    assert set(OPTION_TEXT) == set(CLARIFICATION_TEXT)


def test_options_explain_how_to_identify_a_record():
    text = render_options({"missing_fields": ["entity"], "candidates": []}, "uz")
    assert "6" in text and "9" in text and "STIR" in text


def test_options_repeat_numbered_choices():
    pending = {
        "missing_fields": ["region"],
        "candidates": [
            {"name": "Toshkent shahri", "region_ru": "г. Ташкент"},
            {"name": "Toshkent viloyati", "region_ru": "Ташкентская область"},
        ],
    }
    text = render_options(pending, "uz")
    assert "1. Toshkent shahri" in text and "2. Toshkent viloyati" in text


async def test_options_reply_keeps_the_question_open_without_the_model(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    pending = {"question": "Shakar narxi?", "missing_fields": ["period"], "candidates": []}
    service.state.set_pending(1, pending)
    result = await service.prepare(message_job("qanday variantlar bor?"))
    assert "farqi yo‘q" in result["texts"][0]
    assert "answer" not in result
    assert service.state.pending(1) == pending
    service.state.close()


async def test_options_without_an_open_question_explain_the_bot(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("какие есть варианты?"))
    assert "сделк" in result["texts"][0]
    service.state.close()
