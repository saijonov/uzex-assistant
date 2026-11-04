import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.database import calculate_ratio
from uzex.engine import Engine
from uzex.models import RequestReview
from uzex.policy import cancellation_gap, unit_gap


def detail_review(**overrides):
    values = {
        "language": "uz",
        "task": "count",
        "subject": "deal",
        "reference": "not_needed",
        "entity_text": None,
        "period": "not_needed",
        "ranking_by": "not_needed",
        "missing_fields": [],
        "continuation": False,
    }
    return RequestReview(**{**values, **overrides})


async def test_ranking_answer_must_name_who_was_ranked(sample_database):
    client = ScriptedClient(
        [
            review(task="rank", subject="broker", ranking_by="count"),
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish(),
            (
                "query_registry",
                {
                    "sql": "SELECT broker_code, COUNT(*) AS n FROM broker_deals GROUP BY broker_code "
                    "ORDER BY n DESC, broker_code LIMIT 1"
                },
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer("Какой брокер?")
    assert answer.outcome == "answer"
    assert "broker_code" in answer.evidence.rows[0]


async def test_percentage_answer_must_contain_a_percentage(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "query_registry",
                {"sql": "SELECT region, COUNT(*) AS n FROM registry GROUP BY region"},
            ),
            finish(),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "n",
                    "denominator": "n",
                    "scale": 2,
                    "operation": "share_percent",
                },
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какова доля каждого региона в процентах?"
    )
    assert answer.evidence.calculation.startswith("share_percent")


async def test_percentage_stored_in_a_field_counts_as_a_percentage(sample_database):
    client = ScriptedClient(
        [
            review(task="detail"),
            (
                "query_registry",
                {"sql": "SELECT deposit_percent FROM registry WHERE deal_id = '100001'"},
            ),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "100001-bitim garovi necha foiz?"
    )
    assert answer.outcome == "answer"


@pytest.mark.parametrize("operation", ["ratio", "percentage", "change_percent"])
def test_a_measure_cannot_be_compared_with_itself_under_another_name(sample_database, operation):
    data = sample_database.query(
        "SELECT COUNT(*) AS cancelled_count, COUNT(*) AS total_count FROM registry", "q1"
    )
    with pytest.raises(ValueError, match="same measure"):
        calculate_ratio(data, "cancelled_count", "total_count", 2, operation)


def test_a_grouped_column_cannot_be_compared_with_itself(sample_database):
    data = sample_database.query("SELECT region, COUNT(*) AS n FROM registry GROUP BY region", "q1")
    with pytest.raises(ValueError, match="same measure"):
        calculate_ratio(data, "n", "n", 2, "change_percent")


def test_filtered_and_unfiltered_counts_are_different_measures(sample_database):
    data = sample_database.query(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_cancelled) AS cancelled FROM registry",
        "q1",
    )
    assert calculate_ratio(data, "cancelled", "total", 2, "percentage").rows[0]["ratio"] != "100.00"


async def test_model_recovers_from_comparing_a_measure_with_itself(sample_database):
    client = ScriptedClient(
        [
            review(task="count"),
            (
                "query_registry",
                {"sql": "SELECT COUNT(*) AS cancelled, COUNT(*) AS total FROM registry"},
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "cancelled",
                    "denominator": "total",
                    "scale": 2,
                    "operation": "percentage",
                },
            ),
            (
                "query_registry",
                {
                    "sql": "SELECT COUNT(*) FILTER (WHERE is_cancelled) AS cancelled, "
                    "COUNT(*) AS total FROM registry"
                },
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q2",
                    "numerator": "cancelled",
                    "denominator": "total",
                    "scale": 2,
                    "operation": "percentage",
                },
            ),
            finish(query_id="q3"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Какая доля отменённых в процентах?"
    )
    assert answer.outcome == "answer"
    assert answer.evidence.rows[0]["ratio"] == "18.52"


def raw_count(sample_database, sql):
    with sample_database.connect() as db:
        return db.execute(sql).fetchone()[0]


@pytest.mark.parametrize(
    "where,expected",
    [
        ("", "SELECT count(*) FROM registry WHERE is_cancelled"),
        ("WHERE NOT is_cancelled", None),
        ("WHERE is_cancelled", "SELECT count(*) FROM registry WHERE is_cancelled"),
        (
            "WHERE status <> 'Аннулирован(Не оплачен)'",
            None,
        ),
    ],
)
def test_evidence_records_how_many_cancelled_deals_were_counted(sample_database, where, expected):
    data = sample_database.query(f"SELECT COUNT(*) AS n FROM registry {where}", "q1")
    assert data.cancelled_records == (raw_count(sample_database, expected) if expected else 0)


def test_cancelled_count_does_not_apply_outside_deals(sample_database):
    assert (
        sample_database.query("SELECT COUNT(*) AS n FROM brokers", "q1").cancelled_records is None
    )


@pytest.mark.parametrize(
    "question",
    [
        "2025-yilda bekor qilinganlarni chiqarib, barcha valyutalardagi bitimlar summasi",
        "bekor qilinganlarsiz summa qancha?",
        "bekor qilinganlarni hisobga olmang",
        "bekor qilinmagan bitimlar summasi",
        "Сумма без аннулированных сделок",
        "Сумма без учёта аннулированных",
        "исключая аннулированные",
        "кроме отменённых сделок",
        "не считая аннулированных",
    ],
)
def test_requests_to_exclude_cancelled_are_recognised(sample_database, question):
    data = sample_database.query(
        "SELECT SUM(amount_uzs) AS s FROM registry WHERE is_cancelled", "q1"
    )
    assert cancellation_gap(detail_review(), question, data)


@pytest.mark.parametrize(
    "question",
    [
        "bekor qilingan bitimlar nechta?",
        "Сколько аннулированных сделок?",
        "bekor qilinganlar summasi qancha?",
        "2025-yilda nechta bitim bo'lgan?",
    ],
)
def test_other_questions_about_cancelled_deals_are_not_flagged(sample_database, question):
    data = sample_database.query("SELECT COUNT(*) AS n FROM registry WHERE is_cancelled", "q1")
    assert cancellation_gap(detail_review(), question, data) is None


def test_excluding_cancelled_is_satisfied_by_any_correct_filter(sample_database):
    for where in (
        "NOT is_cancelled",
        "status <> 'Аннулирован(Не оплачен)'",
        "is_cancelled = FALSE",
    ):
        data = sample_database.query(f"SELECT COUNT(*) AS n FROM registry WHERE {where}", "q1")
        assert cancellation_gap(detail_review(), "bekor qilinganlarsiz", data) is None


def test_turnover_excludes_cancelled_by_default(sample_database):
    data = sample_database.query("SELECT SUM(amount_uzs) AS s FROM registry", "q1")
    turnover = detail_review(task="turnover", subject="market")
    assert cancellation_gap(turnover, "2025-yil aylanmasi qancha?", data)
    assert cancellation_gap(turnover, "Aylanma, bekor qilinganlar bilan birga", data) is None
    assert cancellation_gap(turnover, "Оборот по всем состояниям", data) is None
    assert cancellation_gap(detail_review(), "Nechta bitim?", data) is None


def test_price_of_one_deal_may_be_a_cancelled_deal(sample_database):
    data = sample_database.query("SELECT amount FROM registry WHERE is_cancelled LIMIT 1", "q1")
    deal = detail_review(task="price", subject="deal")
    assert cancellation_gap(deal, "bu bitim narxi qancha?", data) is None


async def test_inverted_cancelled_filter_is_corrected_before_answering(sample_database):
    client = ScriptedClient(
        [
            review(task="turnover", subject="market", language="uz"),
            (
                "query_registry",
                {"sql": "SELECT SUM(amount_uzs) AS s FROM registry WHERE is_cancelled"},
            ),
            finish(),
            (
                "query_registry",
                {"sql": "SELECT SUM(amount_uzs) AS s FROM registry WHERE NOT is_cancelled"},
            ),
            finish(query_id="q2"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "bekor qilinganlarni chiqarib, umumiy summa qancha?"
    )
    assert answer.outcome == "answer"
    assert answer.evidence.cancelled_records == 0


async def test_a_repeated_wrong_cancelled_filter_never_reaches_the_user(sample_database):
    bad = (
        "query_registry",
        {"sql": "SELECT SUM(amount_uzs) AS s FROM registry WHERE is_cancelled"},
    )
    client = ScriptedClient(
        [
            review(task="turnover", subject="market", language="uz"),
            bad,
            finish(),
            finish(),
            finish(),
        ]
        + [finish()] * 3
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "bekor qilinganlarsiz summa"
    )
    assert answer.outcome == "error"
    assert answer.evidence is None


def price_of(sample_database, unit, volume="SUM(volume)"):
    data = sample_database.query(
        f"SELECT SUM(amount) AS a, {volume} AS v FROM registry "
        f"WHERE unit = '{unit}' AND currency = 'Узбекский сум' AND NOT is_cancelled",
        "q1",
    )
    return calculate_ratio(data, "a", "v", 2)


def test_price_per_kilogram_cannot_be_a_price_per_tonne(sample_database):
    gap = unit_gap("2025-yilda 1 kg shakar necha pul?", price_of(sample_database, "тонна"))
    assert gap and "mass_kg" in gap


def test_price_per_tonne_cannot_be_a_price_per_kilogram(sample_database):
    gap = unit_gap("цена за тонну", price_of(sample_database, "килограмм"))
    assert gap and "mass_t" in gap


@pytest.mark.parametrize(
    "question,unit,volume",
    [
        ("1 kg shakar necha pul?", "тонна", "SUM(mass_kg)"),
        ("1 tonna narxi", "килограмм", "SUM(mass_t)"),
        ("1 kg narxi", "килограмм", "SUM(volume)"),
        ("1 tonna narxi", "тонна", "SUM(volume)"),
        ("Shakar narxi qancha?", "тонна", "SUM(volume)"),
    ],
)
def test_matching_units_are_accepted(sample_database, question, unit, volume):
    assert unit_gap(question, price_of(sample_database, unit, volume)) is None


async def test_wrong_unit_price_is_corrected_before_answering(sample_database):
    where = "WHERE unit = 'тонна' AND currency = 'Узбекский сум' AND NOT is_cancelled"
    client = ScriptedClient(
        [
            review(task="price", subject="product", period="specified", language="uz"),
            (
                "query_registry",
                {"sql": f"SELECT SUM(amount) AS a, SUM(volume) AS v FROM registry {where}"},
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q1",
                    "numerator": "a",
                    "denominator": "v",
                    "scale": 2,
                    "operation": "ratio",
                },
            ),
            finish(query_id="q2"),
            (
                "query_registry",
                {"sql": f"SELECT SUM(amount) AS a, SUM(mass_kg) AS v FROM registry {where}"},
            ),
            (
                "calculate_ratio",
                {
                    "query_id": "q3",
                    "numerator": "a",
                    "denominator": "v",
                    "scale": 2,
                    "operation": "ratio",
                },
            ),
            finish(query_id="q4"),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "2025-yilda 1 kg shakar necha pul?"
    )
    assert answer.outcome == "answer"
    assert "mass_kg" in answer.evidence.sql
