from decimal import Decimal

import pytest
from conversation_helpers import price_review, raw
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import calculate_ratio, validate_query
from uzex.engine import Engine
from uzex.models import Answer
from uzex.policy import (
    missing_requirements,
    unavailable_request,
)
from uzex.prompt import instructions
from uzex.render import render_answer


def test_groups_can_be_filtered_by_their_aggregate(sample_database):
    data = sample_database.query(
        "SELECT seller_inn, COUNT(*) AS n FROM registry GROUP BY seller_inn HAVING COUNT(*) >= 1",
        "q1",
    )
    assert data.rows


def test_having_cannot_hide_a_scope_filter():
    with pytest.raises(ValueError):
        validate_query(
            "SELECT seller_inn, COUNT(*) FROM registry GROUP BY 1 HAVING seller_inn = 'x'"
        )


def test_counting_filtered_groups_is_supported(sample_database):
    data = sample_database.query(
        "SELECT COUNT(*) AS n FROM (SELECT seller_inn FROM registry "
        "GROUP BY seller_inn HAVING COUNT(*) >= 2)",
        "q1",
    )
    expected = raw(
        sample_database,
        "SELECT count(*) FROM (SELECT seller_inn FROM deals GROUP BY 1 HAVING count(*) >= 2)",
    )
    assert data.rows == [{"n": expected}]
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "Guruhlar soni" in text


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM (SELECT * FROM registry)",
        "SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM registry GROUP BY seller_inn)",
        "SELECT COUNT(*) FROM (SELECT * FROM metadata)",
        "SELECT COUNT(*) FROM (SELECT seller_inn FROM registry) WHERE seller_inn = 'x'",
        "SELECT COUNT(*) FROM (SELECT seller_inn FROM (SELECT * FROM registry))",
        "SELECT (SELECT COUNT(*) FROM registry) AS n FROM brokers",
        "SELECT * FROM brokers WHERE inn IN (SELECT manifest FROM metadata)",
        "SELECT * FROM brokers WHERE inn IN (SELECT inn, name FROM participants)",
        "SELECT * FROM brokers WHERE inn IN (SELECT inn FROM participants, brokers)",
        "SELECT * FROM brokers WHERE EXISTS (SELECT 1 FROM participants)",
        "SELECT * FROM brokers WHERE inn IN (SELECT read_text('/etc/passwd') FROM participants)",
    ],
)
def test_nested_queries_stay_restricted(sql):
    with pytest.raises(ValueError):
        validate_query(sql)


def test_anti_join_finds_companies_without_deals(sample_database):
    data = sample_database.query(
        "SELECT COUNT(*) AS n FROM participants WHERE role = 'Покупатель' "
        "AND inn NOT IN (SELECT buyer_inn FROM registry)",
        "q1",
    )
    expected = raw(
        sample_database,
        "SELECT count(*) FROM participants WHERE role = 'Покупатель' "
        "AND inn NOT IN (SELECT buyer_inn FROM deals)",
    )
    assert data.rows == [{"n": expected}]
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "STIR bitimlarda yo‘q" in text


def test_activity_filter_works_without_a_join(sample_database):
    assert sample_database.query(
        "SELECT COUNT(*) AS n FROM registry WHERE buyer_activity = 'Торговая компания'", "q1"
    ).rows


def test_median_is_available_and_guarded(sample_database):
    data = sample_database.query("SELECT MEDIAN(amount_uzs) AS m FROM registry", "q1")
    assert "Mediana" in render_answer(Answer(outcome="answer", language="uz", evidence=data))
    with pytest.raises(ValueError, match="Mixed currencies"):
        sample_database.query("SELECT MEDIAN(amount) AS m FROM registry", "q1")


def test_second_place_can_be_selected(sample_database):
    data = sample_database.query(
        "SELECT deal_id FROM registry ORDER BY amount_uzs DESC LIMIT 1 OFFSET 1", "q1"
    )
    first_two = sample_database.query(
        "SELECT deal_id FROM registry ORDER BY amount_uzs DESC LIMIT 2", "q1"
    )
    assert data.rows == first_two.rows[1:]


def test_offset_still_needs_an_order_and_a_limit():
    with pytest.raises(ValueError):
        validate_query("SELECT deal_id FROM registry LIMIT 1 OFFSET 1")


@pytest.mark.parametrize(
    "expression",
    ["DATE_TRUNC('month', deal_date)", "STRFTIME(deal_date, '%Y-%m')"],
)
def test_date_grouping_the_prompt_recommends_really_works(sample_database, expression):
    data = sample_database.query(
        f"SELECT {expression} AS period, COUNT(*) AS n FROM registry GROUP BY 1 ORDER BY 1", "q1"
    )
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "TRUNC" not in text and "TIME_TO_STR" not in text


@pytest.mark.parametrize(
    "sql,message",
    [
        ("SELECT deal_id FROM registry ORDER BY amount DESC LIMIT 3", "Mixed currencies"),
        ("SELECT deal_id FROM registry ORDER BY unit_price DESC LIMIT 3", "Mixed"),
        ("SELECT deal_id FROM registry ORDER BY volume DESC LIMIT 3", "Mixed units"),
    ],
)
def test_ranking_cannot_compare_different_currencies_or_units(sample_database, sql, message):
    with pytest.raises(ValueError, match=message):
        sample_database.query(sql, "q1")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT deal_id FROM registry ORDER BY amount_uzs DESC LIMIT 3",
        "SELECT deal_id FROM registry WHERE currency = 'Доллар США' ORDER BY amount DESC LIMIT 3",
        "SELECT deal_id FROM registry WHERE currency = 'Узбекский сум' AND unit = 'тонна' "
        "ORDER BY unit_price DESC LIMIT 3",
    ],
)
def test_comparable_rankings_are_allowed(sample_database, sql):
    assert sample_database.query(sql, "q1").rows


def test_broker_ranking_counts_each_deal_once_for_either_side(sample_database):
    data = sample_database.query(
        "SELECT broker_code, broker_name, COUNT(*) AS n FROM broker_deals "
        "GROUP BY broker_code, broker_name ORDER BY n DESC, broker_code LIMIT 1",
        "q1",
    )
    expected = raw(
        sample_database,
        "SELECT count(*) FROM (SELECT deal_id, seller_broker_code b FROM deals UNION "
        "SELECT deal_id, buyer_broker_code FROM deals) WHERE b = '"
        + data.rows[0]["broker_code"]
        + "'",
    )
    assert data.rows[0]["n"] == expected
    assert data.selected_record_count is None
    assert data.matched_count == 27


def test_broker_deals_shows_its_source_and_cannot_be_sampled(sample_database):
    data = sample_database.query(
        "SELECT broker_code, COUNT(*) AS n FROM broker_deals GROUP BY broker_code", "q1"
    )
    text = render_answer(Answer(outcome="answer", language="ru", evidence=data))
    assert "реестр биржевых сделок" in text
    with pytest.raises(ValueError):
        sample_database.sample("SELECT * FROM broker_deals", 3, "q1")


def test_share_of_total_is_calculated_across_rows(sample_database):
    data = sample_database.query(
        "SELECT region, COUNT(*) AS n FROM registry GROUP BY region ORDER BY n DESC", "q1"
    )
    share = calculate_ratio(data, "n", "n", 2, "share_percent")
    assert sum(Decimal(row["ratio"]) for row in share.rows) == pytest.approx(100, abs=0.2)
    text = render_answer(Answer(outcome="answer", language="uz", evidence=share))
    assert "Ulush, %" in text


def test_share_of_a_truncated_result_is_refused(sample_database):
    data = sample_database.query("SELECT region, COUNT(*) AS n FROM registry GROUP BY region", "q1")
    with pytest.raises(ValueError, match="complete"):
        calculate_ratio(data.model_copy(update={"truncated": True}), "n", "n", 2, "share_percent")


async def test_more_than_the_cap_returns_the_cap_and_says_so(sample_database):
    client = ScriptedClient(
        [("sample_records", {"sql": "SELECT * FROM brokers", "count": 150}), finish()]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("150 брокеров")
    assert answer.outcome == "answer"
    assert len(answer.evidence.rows) == 100
    text = render_answer(answer)
    assert "150" in text and "100" in text


def test_largest_deal_defaults_to_amount_instead_of_asking():
    review_ = price_review(
        task="rank",
        subject="deal",
        reference="not_needed",
        entity_text=None,
        ranking_by="missing",
        missing_fields=["ranking"],
    )
    assert missing_requirements(review_, "Eng katta 3 ta bitim qaysilar?", [], None) == []


def test_company_ranking_still_asks_for_the_metric():
    review_ = price_review(
        task="rank",
        subject="broker",
        reference="not_needed",
        entity_text=None,
        ranking_by="missing",
    )
    assert missing_requirements(review_, "Eng yaxshi broker?", [], None) == ["ranking"]


@pytest.mark.parametrize(
    "question,subject",
    [
        ("Hozir 100001-bitim narxi qancha?", "deal"),
        ("Сейчас скажи цену сделки 100001", "deal"),
        ("Hozir 100001 shartnoma narxi qancha?", "contract"),
        ("Bugun 100001 narxi qancha?", "product"),
    ],
)
def test_time_words_do_not_block_a_specific_record(question, subject):
    assert unavailable_request(price_review(subject=subject), question) is None


@pytest.mark.parametrize(
    "question",
    [
        "Bugungi shakar narxi qancha?",
        "hozirgi shakar narxi kg",
        "Текущая цена сахара за тонну?",
        "сегодняшняя цена сахара",
        "завтрашняя цена сахара",
    ],
)
def test_live_price_words_are_recognised_in_any_form(question):
    assert unavailable_request(price_review(), question) == "outside_dates"


def test_historical_price_with_a_year_is_not_blocked():
    assert unavailable_request(price_review(), "Bugungi kunda 2025 yil shakar narxi") is None


def test_record_kinds_reports_which_records_use_a_number(sample_database):
    deal = raw(sample_database, "SELECT deal_id FROM deals LIMIT 1")
    contract = raw(sample_database, "SELECT contract_id FROM contracts LIMIT 1")
    assert "deal" in sample_database.record_kinds(deal)
    assert "contract" in sample_database.record_kinds(contract)
    assert sample_database.record_kinds("999999") == []


async def test_number_that_is_both_deal_and_contract_asks_which(sample_database, monkeypatch):
    monkeypatch.setattr(sample_database, "record_kinds", lambda number: ["deal", "contract"])
    client = ScriptedClient(
        [
            review(
                language="uz",
                subject="unknown",
                reference="specified",
                entity_text="100024",
                missing_fields=["reference"],
            )
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "100024 haqida ma'lumot ber"
    )
    assert answer.outcome == "clarify"
    assert answer.missing_fields == ["record_kind"]
    text = render_answer(answer)
    assert "bitim" in text and "shartnoma" in text


async def test_number_that_is_only_a_deal_needs_no_question(sample_database):
    number = raw(
        sample_database,
        "SELECT deal_id FROM deals WHERE deal_id NOT IN (SELECT contract_id FROM contracts) LIMIT 1",
    )
    client = ScriptedClient(
        [
            review(
                language="uz",
                subject="unknown",
                reference="specified",
                entity_text=number,
                missing_fields=["reference"],
            ),
            (
                "query_registry",
                {"sql": f"SELECT seller_name FROM registry WHERE deal_id = '{number}'"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        f"{number} haqida ma'lumot ber"
    )
    assert answer.outcome == "answer"


async def test_named_record_kind_is_not_questioned(sample_database):
    client = ScriptedClient(
        [
            review(language="uz", subject="deal", reference="specified", entity_text="100024"),
            (
                "query_registry",
                {"sql": "SELECT seller_name FROM registry WHERE deal_id = '100024'"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "100024-bitim sotuvchisi kim?"
    )
    assert answer.outcome == "answer"


def test_prompt_does_not_repeat_the_registry_fields_for_broker_deals(sample_database):
    text = instructions(
        sample_database.schema, sample_database.manifest, None, sample_database.values
    )
    assert "broker_deals" in sample_database.schema
    assert text.count('["amount_uzs"') == 1
    assert "broker_side" in text


def test_grouped_result_is_not_described_with_a_deal_total(sample_database):
    data = sample_database.query(
        "SELECT seller_inn, COUNT(*) AS n FROM registry GROUP BY seller_inn LIMIT 2", "q1"
    )
    assert data.grouped
    at_cap = data.model_copy(update={"row_limit": 2})
    assert not at_cap.capped
    truncated = data.model_copy(update={"row_limit": 2, "truncated": True})
    text = render_answer(Answer(outcome="answer", language="uz", evidence=truncated))
    assert "cheklangan" in text
    assert "Shartlarga mos jami" not in text


def test_plain_list_is_not_marked_as_grouped(sample_database):
    assert not sample_database.query("SELECT deal_id FROM registry LIMIT 2", "q1").grouped


@pytest.mark.parametrize(
    "question",
    [
        "Eng ko'p foyda qilgan kompaniya qaysi?",
        "Eng ko'p daromad qiladigan 10 ta broker kim?",
        "Какая прибыль у компании?",
        "Самый большой доход брокера",
        "Какова фактически уплаченная сумма НДС по сделке 100001?",
        "100001-bitim bo'yicha to'langan QQS miqdori qancha?",
        "Kompaniyaning telefon raqami qanday?",
    ],
)
def test_information_the_registry_lacks_is_refused_at_once(question):
    assert unavailable_request(price_review(task="count"), question) == "missing_field"


@pytest.mark.parametrize(
    "question",
    [
        "QQS to'lovchilari soni qancha?",
        "QQS to'lovchi sotuvchilar nechta?",
        "Сколько плательщиков НДС среди продавцов?",
        "921912462 kompaniyasi QQS to'lovchisimi?",
        "Foydalanish muddati qancha?",
        "Eng ko'p bitim qilgan kompaniya qaysi?",
    ],
)
def test_answerable_questions_near_those_words_are_not_refused(question):
    assert unavailable_request(price_review(task="count"), question) is None


def test_hs_codes_of_a_company_can_be_listed(sample_database):
    seller = raw(sample_database, "SELECT seller_inn FROM deals LIMIT 1")
    data = sample_database.query(
        "SELECT DISTINCT hs_code, product_family FROM registry "
        f"WHERE seller_inn = '{seller}' ORDER BY hs_code",
        "q1",
    )
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert data.rows and "TIF TN kodi" in text


def test_prompt_guides_the_mistakes_seen_in_live_runs(sample_database):
    text = instructions(
        sample_database.schema, sample_database.manifest, None, sample_database.values
    )
    assert "hs_code" in text and "seller_inn" in text
    assert "bekor qilinganlarsiz" in text and "NOT is_cancelled" in text
    assert "ORDER BY the metric" in text
    assert "warehouse column region" in text
    assert "one FILTER column per year" in text
    assert "is not a missing reference" in text


@pytest.mark.parametrize(
    "question",
    [
        "100001-raqamli bitim uchun to‘langan QQSning haqiqiy summasi qancha?",
        "QQSni qancha to'lagan?",
        "Сумма НДС по сделке 100001",
    ],
)
def test_paid_vat_is_recognised_with_grammatical_endings(question):
    assert unavailable_request(price_review(task="count"), question) == "missing_field"


def test_prompt_keeps_calculated_numbers_short(sample_database):
    text = instructions(
        sample_database.schema, sample_database.manifest, None, sample_database.values
    )
    assert "scale 2" in text
    assert "Never ask for a unit or a currency" in text
