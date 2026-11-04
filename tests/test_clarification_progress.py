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


@pytest.mark.parametrize(
    "text",
    [
        "Shakar narxi qancha?",
        "2025-yilda shakarning tonnasi necha pul?",
        "sementning narxi",
        "цена сахара",
        "Цемент за тонну",
        "paxta bo'yicha",
        "nomida «сахар» bo‘lgan tovarlar",
        "un narxi",
        "мука",
    ],
)
def test_named_products_are_recognised(sample_database, text):
    assert sample_database.names_product(text)


@pytest.mark.parametrize(
    "text",
    [
        "Narx qancha?",
        "Narxi qancha?",
        "Qaysi tovar?",
        "2025-yilda nechta bitim bo'lgan?",
        "Какая цена?",
        "Сколько сделок?",
        "kompaniya haqida",
        "qancha pul",
        "uning narxi",
    ],
)
def test_ordinary_words_are_not_products(sample_database, text):
    assert not sample_database.names_product(text)


def test_a_named_product_is_not_asked_for_again():
    review_ = price_review(reference="missing", entity_text=None)
    assert missing_requirements(review_, "2025 Shakar narxi", [], None) == ["product"]
    assert missing_requirements(review_, "2025 Shakar narxi", [], None, knows_product=True) == []


def test_a_named_product_settles_a_vague_record_question():
    review_ = price_review(task="count", subject="product", reference="missing", entity_text=None)
    assert (
        missing_requirements(review_, "2025 shakar bitimlari", [], None, knows_product=True) == []
    )
    company = price_review(task="count", subject="company", reference="missing", entity_text=None)
    assert missing_requirements(company, "shakar sotuvchi", [], None, knows_product=True) == [
        "entity"
    ]


def test_a_year_settles_the_period():
    review_ = price_review(period="missing", missing_fields=["period"])
    assert missing_requirements(review_, "2025-yilda Shakar narxi", [], None) == []
    assert missing_requirements(review_, "Shakar narxi 01.03.2024", [], None) == []
    assert missing_requirements(review_, "Shakar narxi", [], None) == ["period"]
    whole = price_review(period="all_available")
    assert missing_requirements(whole, "2025-yilda Shakar narxi", [], None) == []


@pytest.mark.parametrize("task", ["rank", "list"])
def test_rankings_and_lists_never_need_one_specific_record(task):
    review_ = price_review(
        task=task,
        subject="deal",
        reference="missing",
        entity_text=None,
        ranking_by="count",
        missing_fields=["entity"],
    )
    assert missing_requirements(review_, "Eng qimmat bitim qaysi?", [], None) == []


async def test_named_product_answers_instead_of_asking_which_product(sample_database):
    client = ScriptedClient(
        [
            review(
                language="uz",
                task="price",
                subject="product",
                reference="missing",
                period="specified",
            ),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS n FROM registry WHERE NOT is_cancelled"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "2025-yilda shakarning tonnasi necha pul?"
    )
    assert answer.outcome == "answer"


async def test_no_preference_on_a_named_product_answers(sample_database):
    client = ScriptedClient(
        [
            review(
                language="uz",
                task="price",
                subject="product",
                reference="missing",
                period="missing",
                missing_fields=["period"],
                continuation=True,
            ),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS n FROM registry WHERE NOT is_cancelled"},
            ),
            finish(),
        ]
    )
    pending = {"question": "Shakar narxi qancha?", "missing_fields": ["product"]}
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "farqi yo'q", None, [], pending
    )
    assert answer.outcome == "answer"


async def test_model_cannot_ask_about_a_region_the_user_named(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "ask_clarification",
                {"language": "ru", "fields": ["region"], "candidates_query_id": None},
            ),
            ("query_registry", {"sql": TOSHKENT_SQL}),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Сколько сделок в городе Ташкент?"
    )
    assert answer.outcome == "answer"


async def test_broad_product_is_answered_instead_of_asking_which_variant(sample_database):
    client = ScriptedClient(
        [
            review(task="price", subject="product", period="specified", language="uz"),
            ("lookup_entities", {"kind": "product", "text": "sement"}),
            (
                "ask_clarification",
                {"language": "uz", "fields": ["product"], "candidates_query_id": "lookup_1"},
            ),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS n FROM registry WHERE NOT is_cancelled"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "2025-yilda sement narxi qancha?"
    )
    assert answer.outcome == "answer"


@pytest.mark.parametrize("task", ["price", "turnover", "count", "volume"])
def test_currency_is_not_asked_when_the_data_already_gives_it(task):
    review_ = price_review(task=task, missing_fields=["currency"])
    assert missing_requirements(review_, "2025 Shakar qancha?", [], None) == []


def test_ranking_across_currencies_may_still_ask_which_one():
    review_ = price_review(
        task="rank",
        subject="deal",
        reference="not_needed",
        entity_text=None,
        missing_fields=["currency"],
    )
    assert missing_requirements(review_, "Birlik narxi eng qimmat bitim", [], None) == ["currency"]
