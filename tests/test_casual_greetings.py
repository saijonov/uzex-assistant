import pytest

from uzex.interface import greeting


@pytest.mark.parametrize(
    "phrase,reply",
    [
        ("nma gap", ("greeting", "uz")),
        ("nima gap", ("greeting", "uz")),
        ("Нима гап?", ("greeting", "uz")),
        ("ishlar qalay", ("greeting", "uz")),
        ("qalaysiz", ("greeting", "uz")),
        ("salom nma gap", ("greeting", "uz")),
        ("как дела", ("greeting", "ru")),
    ],
)
def test_casual_greetings_get_a_greeting(phrase, reply):
    assert greeting(phrase) == reply


def test_a_data_question_is_not_small_talk():
    assert greeting("nima gap 2025 yilda") is None
