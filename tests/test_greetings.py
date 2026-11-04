import pytest
from test_engine import ScriptedClient, finish
from test_interface import make_service
from test_telegram import message_job

from uzex.interface import greeting


@pytest.mark.parametrize(
    "message,language",
    [
        ("Salom!", "uz"),
        ("  SALOM 🙂 ", "uz"),
        ("Assalomu alaykum!", "uz"),
        ("Ассалому алайкум", "uz"),
        ("салом", "uz"),
        ("Xayrli tong", "uz"),
        ("Привет!", "ru"),
        ("Здравствуйте", "ru"),
        ("Добрый день!", "ru"),
    ],
)
async def test_greeting_replies_without_model_and_preserves_history(
    tmp_path, sample_database, message, language
):
    service = make_service(tmp_path, sample_database)
    service.state.language(1, "ru" if language == "uz" else "uz")
    service.state.remember(1, "previous question", "previous answer")
    before = service.state.chat(1)
    result = await service.prepare(message_job(message))
    assert "answer" not in result
    assert (
        "savolingiz" in result["texts"][0] if language == "uz" else "вопрос" in result["texts"][0]
    )
    assert service.state.chat(1) == before
    assert result["ui_language"] == before["language"]
    assert result["menu_at"] == 0
    service.state.close()


@pytest.mark.parametrize(
    "message",
    [
        "Salom, 2025-yilda nechta bitim bor?",
        "Здравствуйте! Кто продавец по сделке 100001?",
        "Salom MChJ haqida ma’lumot ber",
        "Salom, brokers.csv faylini yubor",
        "100001",
    ],
)
def test_greeting_does_not_swallow_questions(message):
    assert greeting(message) is None


async def test_greeting_with_question_still_gets_database_answer(tmp_path, sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    result = await service.prepare(message_job("Здравствуйте! Кто продавец по сделке 100001?"))
    assert result["answer"]["outcome"] == "answer"
    assert "RUKUSHO‘ FERMER MCHJ" in result["texts"][0]
    service.state.close()
