import pytest
from conversation_helpers import price_review
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import named_regions
from uzex.engine import Engine
from uzex.policy import (
    missing_requirements,
)
from uzex.render import render_answer


def test_price_does_not_demand_a_unit_the_data_already_has():
    assert missing_requirements(price_review(), "2025-yilda Shakar narxi", [], None) == []


@pytest.mark.parametrize(
    "words",
    ["tonnada", "tonnasi", "kilogrammda", "kilosi", "в килограммах", "в тоннах", "литрах", "за кг"],
)
def test_any_natural_unit_wording_settles_a_unit_question(words):
    review = price_review(missing_fields=["unit"])
    assert missing_requirements(review, f"2025 Shakar narxi {words}", [], None) == []


@pytest.mark.parametrize("reply", ["farqi yo'q", "bilmadim", "istalgan", "неважно", "не знаю"])
def test_no_preference_accepts_defaults_instead_of_asking_again(reply):
    pending = {"question": "Shakar narxi qancha?", "missing_fields": ["period", "unit"]}
    review = price_review(period="missing", missing_fields=["period", "unit"], continuation=True)
    assert missing_requirements(review, reply, [], pending) == []


def test_all_available_period_is_accepted_once_the_user_was_asked():
    pending = {"question": "Shakar narxi qancha?", "missing_fields": ["period"]}
    review = price_review(period="all_available", continuation=True)
    assert missing_requirements(review, "hammasi", [], pending) == []


def test_optional_question_is_not_repeated_after_a_reply():
    pending = {"question": "Shakar narxi qancha?", "missing_fields": ["period"]}
    review = price_review(period="missing", missing_fields=["period"], continuation=True)
    assert missing_requirements(review, "hmm", [], pending) == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("в Намангане", ["Namangan viloyati"]),
        ("а в Бухаре?", ["Buxoro viloyati"]),
        ("в Фергане", ["Farg‘ona viloyati"]),
        ("Samarqandda", ["Samarqand viloyati"]),
        ("Farg'onada", ["Farg‘ona viloyati"]),
        ("в Каракалпакстане", ["Qoraqalpog‘iston Respublikasi"]),
        ("Сырдарьинская область", ["Sirdaryo viloyati"]),
        ("Toshkentda", ["Toshkent shahri", "Toshkent viloyati"]),
        ("Toshkentda 2025 g.", ["Toshkent shahri", "Toshkent viloyati"]),
        ("Toshkent shahrida", ["Toshkent shahri"]),
        ("город Ташкент", ["Toshkent shahri"]),
        ("г. Ташкент", ["Toshkent shahri"]),
        ("Toshkent viloyati", ["Toshkent viloyati"]),
        ("Ташкентская область", ["Toshkent viloyati"]),
        ("2025 yil savdosi", []),
    ],
)
def test_regions_are_recognised_in_every_form(text, expected):
    assert named_regions(text) == expected


def test_inflected_region_lookup_is_an_exact_match(sample_database):
    rows = sample_database.lookup("region", "в Намангане")
    assert [(row["name"], row["match"]) for row in rows] == [("Namangan viloyati", "exact")]


def test_region_question_is_dropped_when_the_text_already_names_one():
    count = {"task": "count", "reference": "not_needed", "entity_text": None}
    review = price_review(**count, missing_fields=["region"], continuation=True)
    assert missing_requirements(review, "а в Бухаре?", [], {"question": "В Намангане?"}) == []
    first = price_review(**count, missing_fields=["region"])
    assert missing_requirements(first, "Toshkentda nechta bitim?", [], None) == ["region"]


TOSHKENT_SQL = "SELECT COUNT(*) AS n FROM registry WHERE region = 'Toshkent shahri'"


@pytest.mark.parametrize("reply", ["shahar", "город", "shahri", "Toshkent shahri"])
async def test_city_reply_resolves_toshkent(sample_database, reply):
    client = ScriptedClient(
        [
            review(task="count", language="uz", continuation=True),
            ("lookup_entities", {"kind": "region", "text": "Toshkent"}),
            ("query_registry", {"sql": TOSHKENT_SQL}),
            finish(),
        ]
    )
    pending = {"question": "Toshkentda nechta bitim bo'lgan?", "missing_fields": ["region"]}
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        reply, None, [], pending
    )
    assert answer.outcome == "answer"
    assert answer.evidence.sql == TOSHKENT_SQL


async def test_numbered_choice_resolves_toshkent(sample_database):
    client = ScriptedClient(
        [
            review(task="count", language="uz", continuation=True),
            ("lookup_entities", {"kind": "region", "text": "Toshkent"}),
            ("query_registry", {"sql": TOSHKENT_SQL}),
            finish(),
        ]
    )
    pending = {
        "question": "Toshkentda nechta bitim bo'lgan?",
        "missing_fields": ["region"],
        "selected_candidate": {"name": "Toshkent shahri", "region_ru": "г. Ташкент"},
    }
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "2", None, [], pending
    )
    assert answer.outcome == "answer"


async def test_no_preference_on_toshkent_allows_both_regions(sample_database):
    sql = "SELECT COUNT(*) AS n FROM registry WHERE region IN ('Toshkent shahri', 'Toshkent viloyati')"
    client = ScriptedClient(
        [
            review(task="count", language="uz", continuation=True),
            ("lookup_entities", {"kind": "region", "text": "Toshkent"}),
            ("query_registry", {"sql": sql}),
            finish(),
        ]
    )
    pending = {"question": "Toshkentda nechta bitim?", "missing_fields": ["region"]}
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "farqi yo'q", None, [], pending
    )
    assert answer.outcome == "answer"


async def test_unresolved_toshkent_is_still_blocked(sample_database):
    client = ScriptedClient(
        [
            review(task="count", language="uz"),
            ("lookup_entities", {"kind": "region", "text": "Toshkent"}),
            ("query_registry", {"sql": TOSHKENT_SQL}),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["region"], "candidates_query_id": "lookup_1"},
            ),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Toshkentda nechta bitim?"
    )
    assert answer.outcome == "clarify"
    assert len(answer.candidates) == 2


async def test_required_detail_gives_up_instead_of_repeating_itself(sample_database):
    client = ScriptedClient(
        [
            review(
                language="uz",
                task="price",
                subject="product",
                reference="missing",
                period="specified",
                continuation=True,
            )
        ]
    )
    pending = {"question": "Narx qancha?", "missing_fields": ["product"]}
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "bilmadim", None, [], pending
    )
    assert answer.outcome == "unavailable"
    assert answer.reason == "needs_detail"
    assert "Qaysi tovar" not in render_answer(answer)


async def test_clarification_tool_cannot_repeat_the_same_question(sample_database):
    client = ScriptedClient(
        [
            review(language="uz", task="count", continuation=True),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["metric"], "candidates_query_id": None},
            ),
        ]
    )
    pending = {"question": "Savdo qanday?", "missing_fields": ["metric"]}
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "hmm", None, [], pending
    )
    assert answer.outcome == "unavailable"
    assert answer.reason == "needs_detail"
