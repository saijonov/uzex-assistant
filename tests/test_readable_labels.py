import pytest
import sqlglot

from uzex.models import Answer
from uzex.render import describe_condition, label, render_answer


@pytest.mark.parametrize(
    "expression,language,expected",
    [
        ("EXTRACT(DAYOFWEEK FROM deal_date)", "uz", "Bitim sanasi: hafta kuni"),
        ("COUNT(DISTINCT product)", "uz", "Yozilish turlari soni"),
        ("COUNT(DISTINCT product)", "ru", "Количество вариантов написания"),
        ("EXTRACT(ISODOW FROM deal_date)", "ru", "Дата сделки: день недели"),
        ("EXTRACT(HOUR FROM deal_time)", "ru", "Время: час"),
        ("ABS(amount)", "ru", "Сумма в валюте контракта"),
        ("LOWER(seller_name)", "uz", "Sotuvchi"),
        ("COALESCE(delivered_on, paid_on)", "ru", "Дата поставки"),
        ("CAST(deal_date AS VARCHAR)", "uz", "Bitim sanasi"),
        ("LENGTH(seller_name)", "ru", "Продавец: длина"),
    ],
)
def test_functions_are_named_in_plain_words(expression, language, expected):
    assert label(expression, language) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("COUNT(DISTINCT seller_inn)", "Количество продавцов"),
        ("COUNT(DISTINCT buyer_inn)", "Количество покупателей"),
        ("COUNT(DISTINCT deal_id)", "Количество сделок"),
        ("COUNT(DISTINCT hs_code)", "Количество разных значений: Код ТН ВЭД"),
    ],
)
def test_distinct_counts_name_what_is_counted(expression, expected):
    assert label(expression, "ru") == expected


def test_a_broker_side_condition_reads_naturally():
    text = label("COUNT(DISTINCT seller_inn) FILTER (WHERE seller_broker_code = broker_code)", "ru")
    assert text == "Количество продавцов (на стороне продавца)"
    text = label("COUNT(DISTINCT buyer_inn) FILTER (WHERE buyer_broker_code = broker_code)", "uz")
    assert text == "Xaridorlar soni (xaridor tomonida)"


def test_days_of_the_week_are_shown_by_name(sample_database):
    data = sample_database.query(
        "SELECT EXTRACT(DAYOFWEEK FROM deal_date) AS weekday, COUNT(*) AS n FROM registry "
        "GROUP BY weekday ORDER BY n DESC, weekday LIMIT 1",
        "q1",
    )
    data.rows[0]["weekday"] = 3
    text = render_answer(Answer(outcome="answer", language="ru", evidence=data))
    assert "День недели: Среда" in text or "Дата сделки: день недели: Среда" in text
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "Chorshanba" in text


@pytest.mark.parametrize(
    "condition,expected",
    [
        ("LOWER(product_name) LIKE '%хлопок%сырец%'", "хлопок сырец"),
        ("paid_on IS NOT NULL", "Дата оплаты: указано"),
        ("region IN ('a', 'b', 'c', 'd', 'e', 'f')", "a, b, c и ещё 3"),
    ],
)
def test_conditions_read_naturally(condition, expected):
    node = sqlglot.parse_one(f"SELECT 1 FROM t WHERE {condition}", read="duckdb").args["where"].this
    assert expected in describe_condition(node, "ru")


@pytest.mark.parametrize("language,name", [("uz", "Oktabr"), ("ru", "Октябрь")])
def test_a_month_is_shown_by_its_name(sample_database, language, name):
    data = sample_database.query(
        "SELECT EXTRACT(MONTH FROM deal_date) AS month, COUNT(*) AS n FROM registry "
        "GROUP BY EXTRACT(MONTH FROM deal_date)",
        "q1",
    )
    data.rows[0]["month"] = 10
    text = render_answer(Answer(outcome="answer", language=language, evidence=data))
    assert name in text
