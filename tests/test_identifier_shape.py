import pytest
from conversation_helpers import enqueue
from test_engine import ScriptedClient, review
from test_interface import make_service
from test_telegram import message_job

from uzex.models import Answer
from uzex.policy import malformed_identifier, resolve_pending_reply
from uzex.render import render_answer


@pytest.mark.parametrize(
    "question,number",
    [
        ("menga 1000001 firmani hs kodini ber", "1000001"),
        ("1000001-bitim sotuvchisi kim?", "1000001"),
        ("Кто продавец сделки 1000001?", "1000001"),
        ("сделка номер 12345678", "12345678"),
        ("shartnoma 1234567 narxi", "1234567"),
        ("12345 STIRli kompaniya kim?", "12345"),
        ("ИНН 921912 чей?", "921912"),
        ("firma 12345678 haqida", "12345678"),
        ("1234567890 raqamli kompaniya", "1234567890"),
    ],
)
def test_impossible_record_numbers_are_recognised(question, number):
    assert malformed_identifier(question) == number


@pytest.mark.parametrize(
    "question",
    [
        "100001-bitim sotuvchisi kim?",
        "100001 firma hs kodi",
        "921912462 STIRli kompaniya QQS to'lovchisimi?",
        "1000000 so'mdan katta bitimlar nechta?",
        "bitimlar 1000000 so'mdan yuqori",
        "сделки 5000000 сум",
        "5000000 dan yuqori bitimlar",
        "2025-yilda nechta bitim bo'lgan?",
        "100 ta bitim ko'rsat",
        "10 ta random bitim ko'rsat",
        "5-bitim haqida",
        "innovatsiya 1234567",
    ],
)
def test_amounts_counts_and_valid_numbers_are_left_alone(question):
    assert malformed_identifier(question) is None


def test_suggestions_come_from_real_records(sample_database):
    assert sample_database.identifier_suggestions("1000001") == ["100001"]
    assert sample_database.identifier_suggestions("7777777") == []
    inn = sample_database.catalog["company"][0]["inn"]
    assert inn in sample_database.identifier_suggestions(inn + "7")


def test_reply_explains_the_lengths_and_lists_the_suggestion():
    answer = Answer(
        outcome="clarify",
        language="uz",
        reason="wrong_length",
        identifier="1000001",
        candidates=[{"name": "100001", "replaces": "1000001"}],
    )
    text = render_answer(answer)
    assert "1000001" in text and "7 ta" in text
    assert "6 ta" in text and "9 ta" in text
    assert "1. 100001" in text


def test_reply_in_russian_without_a_suggestion():
    answer = Answer(outcome="clarify", language="ru", reason="wrong_length", identifier="7777777")
    text = render_answer(answer)
    assert "7777777" in text and "ИНН" in text
    assert "1." not in text


def test_choosing_a_suggestion_corrects_the_original_question():
    pending = {
        "question": "menga 1000001 firmani hs kodini ber",
        "missing_fields": ["entity"],
        "candidates": [{"name": "100001", "replaces": "1000001"}],
    }
    resolved = resolve_pending_reply(pending, "1")
    assert resolved["question"] == "menga 100001 firmani hs kodini ber"
    assert resolved["missing_fields"] == []


async def test_wrong_length_is_answered_without_the_model(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("menga 1000001 firmani hs kodini ber"))
    assert "100001" in result["texts"][0]
    assert result["answer"]["outcome"] == "clarify"
    pending = service.state.pending(1)
    assert pending["question"] == "menga 1000001 firmani hs kodini ber"
    assert pending["candidates"][0]["name"] == "100001"
    service.state.close()


async def test_choice_continues_with_the_corrected_number(tmp_path, sample_database, monkeypatch):
    monkeypatch.setattr(sample_database, "record_kinds", lambda number: ["deal", "contract"])
    client = ScriptedClient(
        [
            review(
                language="uz",
                subject="company",
                reference="specified",
                entity_text="100001",
                continuation=True,
            )
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    await service.process(enqueue(service, "menga 1000001 firmani hs kodini ber"))
    await service.process(enqueue(service, "1", update=2))
    assert "ham bitim, ham shartnoma" in service.bot.messages[-1]["text"]
    assert any(
        "100001 firmani" in str(item.get("content", ""))
        for item in client.requests[0]["input"]
        if isinstance(item, dict)
    )
    service.state.close()
