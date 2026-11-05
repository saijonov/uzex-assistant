import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.engine import Engine
from uzex.models import Answer
from uzex.policy import unnamed_code
from uzex.render import render_answer

WINTER = "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%дт-з-к5%'"
GRADE = "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%м0к%'"


@pytest.mark.parametrize(
    "question,sql,code",
    [
        ("Qishki dizel bo'yicha nechta bitim bo'lgan?", WINTER, "дт-з-к5"),
        ("Сколько сделок по зимнему дизелю?", WINTER, "дт-з-к5"),
        (
            "Евро-5 дизель qancha sotilgan?",
            "SELECT SUM(volume) AS v FROM registry WHERE LOWER(product_name) LIKE '%к5%'",
            "к5",
        ),
        (
            "Зимний дизель сколько сделок?",
            "SELECT COUNT(*) AS n FROM registry WHERE brand = 'ДТ-З-К5'",
            "ДТ-З-К5",
        ),
        (
            "Зимний дизель сколько сделок?",
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%дт-з%'",
            "дт-з",
        ),
        (
            "Сколько сделок по зимнему дизелю?",
            "SELECT COUNT(*) FILTER (WHERE brand IN ('ДТ-З-К5')) AS n FROM registry",
            "ДТ-З-К5",
        ),
    ],
)
def test_a_code_the_user_never_named_is_caught(question, sql, code):
    assert unnamed_code(question, sql) == code


@pytest.mark.parametrize(
    "question,sql",
    [
        ("ДТ-З-К5 bo'yicha nechta bitim?", WINTER),
        ("dt-z-k5 bo'yicha nechta bitim?", WINTER),
        (
            "АИ-92 benzin nechta bitim?",
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%аи-92%'",
        ),
        (
            "92 benzin nechta bitim?",
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%аи-92%'",
        ),
        (
            "1-navli un nechta bitim?",
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '% 1 сорт%' "
            "OR LOWER(product_name) LIKE '%1-сорт%' OR LOWER(product_name) LIKE '%4-класс%'",
        ),
        (
            "paxta nechta bitim?",
            "SELECT COUNT(*) AS n FROM registry WHERE LOWER(product_name) LIKE '%хлопок-сырец%'",
        ),
        (
            "2025-yilda BK111 nechta bitim qilgan?",
            "SELECT COUNT(*) AS n FROM registry WHERE deal_date >= DATE '2025-01-01' "
            "AND seller_broker_code = 'BK111' AND deal_id = '100001'",
        ),
        (
            "Shakar nechta?",
            "SELECT COUNT(*) AS n FROM registry WHERE product_family = 'Сахар белый'",
        ),
        ("Hammasi nechta?", "SELECT COUNT(*) AS n FROM registry"),
    ],
)
def test_named_codes_grades_and_other_filters_are_left_alone(question, sql):
    assert unnamed_code(question, sql) is None


async def test_engine_refuses_an_answer_built_on_an_unnamed_code(sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": GRADE}),
            finish(),
            finish("unavailable", None, "missing_field"),
        ]
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    answer = await engine.answer("Сколько сделок по самой чистой меди?")
    assert answer.outcome == "unavailable"
    assert answer.reason == "missing_field"
    assert "never named the code м0к" in str(client.requests[-1]["input"])


async def test_a_code_from_the_earlier_conversation_is_allowed(sample_database):
    client = ScriptedClient([("query_registry", {"sql": GRADE}), finish()])
    engine = Engine(Settings(_env_file=None), client, sample_database)
    history = [{"role": "assistant", "content": "Markalar: М00к, М0к"}]
    answer = await engine.answer("ikkinchisi nechta?", history=history)
    assert answer.outcome == "answer"


async def test_a_code_the_user_typed_is_allowed(sample_database):
    client = ScriptedClient([("query_registry", {"sql": GRADE}), finish()])
    engine = Engine(Settings(_env_file=None), client, sample_database)
    answer = await engine.answer("М0к bo'yicha nechta bitim?")
    assert answer.outcome == "answer"


def lookalike(monkeypatch, sample_database, match):
    rows = [
        {"inn": "938371632", "name": "Zo‘kot Trade", "role": "x", "match": match, "score": 90.0}
    ]
    monkeypatch.setattr(sample_database, "lookup", lambda kind, text: rows)


def company_review():
    return review(
        language="uz", subject="company", reference="specified", entity_text="Zoket Trade"
    )


async def test_only_lookalike_names_say_the_name_is_not_in_the_registry(
    monkeypatch, sample_database
):
    lookalike(monkeypatch, sample_database, "fuzzy")
    client = ScriptedClient(
        [
            company_review(),
            ("lookup_entities", {"kind": "company", "text": "Zoket Trade"}),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["entity"], "candidates_query_id": "lookup_1"},
            ),
        ],
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    answer = await engine.answer("Zoket Trade nechta bitim qilgan?")
    assert answer.reason == "name_not_found"
    assert answer.identifier == "Zoket Trade"
    text = render_answer(answer)
    assert "«Zoket Trade» nomi yo‘q" in text
    assert "O‘xshash nomlar" in text
    assert "1. Zo‘kot Trade" in text
    assert "Qaysi bitim" not in text


async def test_an_exact_or_partial_name_still_asks_which_one(monkeypatch, sample_database):
    lookalike(monkeypatch, sample_database, "partial")
    client = ScriptedClient(
        [
            company_review(),
            ("lookup_entities", {"kind": "company", "text": "Zoket"}),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["entity"], "candidates_query_id": "lookup_1"},
            ),
        ],
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    answer = await engine.answer("Zoket nechta bitim qilgan?")
    assert answer.reason == "missing_details"
    assert "Qaysi bitim" in render_answer(answer)


def test_russian_reply_for_a_name_not_in_the_registry():
    answer = Answer(
        outcome="clarify",
        language="ru",
        reason="name_not_found",
        identifier="Zoket Trade",
        missing_fields=["entity"],
        candidates=[{"name": "Zo‘kot Trade", "inn": "938371632"}],
    )
    text = render_answer(answer)
    assert "В реестре нет названия «Zoket Trade»" in text
    assert "Похожие названия" in text
