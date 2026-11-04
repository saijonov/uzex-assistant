import pytest

from uzex.policy import asks_for_options


@pytest.mark.parametrize(
    "question",
    [
        "Какие варианты упаковки есть?",
        "Qadoqlash variantlari qanday?",
        "Yetkazish variantlari qaysilar?",
        "Какие есть варианты базиса поставки?",
    ],
)
def test_asking_about_real_values_is_a_data_question(question):
    assert not asks_for_options(question)


@pytest.mark.parametrize(
    "question",
    [
        "qanday variantlar bor?",
        "variantlar?",
        "какие варианты?",
        "какие есть варианты",
        "nima yozay?",
        "что написать?",
    ],
)
def test_asking_what_to_type_is_still_recognised(question):
    assert asks_for_options(question)
