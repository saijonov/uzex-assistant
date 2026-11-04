import re

from uzex.models import Answer
from uzex.render import render_answer


def test_uzbek_answer_localizes_currency_units_and_status(sample_database):
    data = sample_database.query(
        "SELECT deal_id, seller_name, currency, unit, status, contract_type, contract_form "
        "FROM registry WHERE deal_id='100001'",
        "q1",
    )
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "O‘zbekiston so‘mi" in text
    assert "kilogramm" in text
    assert "To‘liq bajarilgan" in text
    assert "RUKUSHO‘ FERMER MCHJ" in text
    assert not re.search("[А-Яа-яЁё]", text)


def test_russian_answer_localizes_uzbek_region(sample_database):
    data = sample_database.query(
        "SELECT region FROM registry WHERE deal_id='100001'",
        "q1",
    )
    text = render_answer(Answer(outcome="answer", language="ru", evidence=data))
    assert "Наманганская область" in text
    assert "Namangan viloyati" not in text
