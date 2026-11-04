import pytest
from test_interface import make_service
from test_telegram import message_job

from uzex.models import Answer
from uzex.policy import impossible_date
from uzex.render import render_answer


@pytest.mark.parametrize(
    "question,date",
    [
        ("2023-yil 29-fevralda nechta bitim bo'lgan?", "29.02.2023"),
        ("Сколько сделок было 29 февраля 2023 года?", "29.02.2023"),
        ("31.04.2025 kuni nechta bitim?", "31.04.2025"),
        ("2025-02-30 sanasidagi kurs", "30.02.2025"),
        ("31 июня 2024 сделки", "31.06.2024"),
        ("30 fevralda nechta bitim bo'lgan?", "30.02"),
    ],
)
def test_dates_that_do_not_exist_are_recognised(question, date):
    assert impossible_date(question) == date


@pytest.mark.parametrize(
    "question",
    [
        "2024-yil 29-fevralda nechta bitim bo'lgan?",
        "Сколько сделок 29 февраля 2024 года?",
        "31.12.2025 kuni nechta bitim?",
        "2025-10-30 sanasidagi kurs",
        "5 may kuni",
        "50 may",
        "100001-bitim sotuvchisi kim?",
        "2025-yilda 1000000 so'mdan katta bitimlar",
        "12.50 so'm",
    ],
)
def test_real_dates_and_other_numbers_are_left_alone(question):
    assert impossible_date(question) is None


def test_the_reply_says_the_date_does_not_exist():
    answer = Answer(
        outcome="unavailable", language="ru", reason="invalid_date", identifier="29.02.2023"
    )
    assert "29.02.2023" in render_answer(answer)
    assert "не существует" in render_answer(answer)


async def test_it_is_answered_without_the_model(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("2023-yil 29-fevralda nechta bitim bo'lgan?"))
    assert "29.02.2023" in result["texts"][0]
    assert result["answer"]["outcome"] == "unavailable"
    service.state.close()
