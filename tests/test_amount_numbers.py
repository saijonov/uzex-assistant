import pytest
from test_answer_fit import detail_review

from uzex.policy import bare_record_number


@pytest.mark.parametrize(
    "question",
    [
        "105000 so'mdan qimmat bitimlar nechta?",
        "дороже 105000 сумов сделки",
        "100500 so'mlik bitimlar",
        "300000 so'mdan yuqori",
        "narxi 105000 bo'lgan tovarlar",
        "Сделки дороже 250000",
        "250000 dan kam",
    ],
)
def test_amounts_are_not_taken_for_record_numbers(question):
    assert bare_record_number(detail_review(subject="unknown"), question, None) is None


@pytest.mark.parametrize("question", ["100001 haqida ayting", "100001 kim?", "Что за 100001?"])
def test_a_bare_record_number_is_still_found(question):
    assert bare_record_number(detail_review(subject="unknown"), question, None) == "100001"
