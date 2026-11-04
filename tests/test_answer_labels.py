import pytest
from conversation_helpers import stored

from uzex.database import calculate_ratio
from uzex.models import Answer
from uzex.render import applied_conditions, render_answer


def test_extracted_years_are_not_grouped_like_money(sample_database):
    text = render_answer(
        stored(
            sample_database,
            "SELECT EXTRACT(YEAR FROM deal_date) AS y, COUNT(*) AS n FROM registry GROUP BY 1 ORDER BY 1",
        )
    )
    assert "2022" in text
    assert "2 022" not in text


def test_each_filtered_value_says_which_condition_it_belongs_to(sample_database):
    text = render_answer(
        stored(
            sample_database,
            "SELECT COUNT(*) FILTER (WHERE deal_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31') AS a, "
            "COUNT(*) FILTER (WHERE deal_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31') AS b FROM registry",
        )
    )
    assert "2024-01-01" in text and "2025-12-31" in text


@pytest.mark.parametrize(
    "operation,expected",
    [("percentage", "Foiz"), ("change_percent", "O‘zgarish, %"), ("ratio", "nisbat")],
)
def test_calculated_value_is_named_after_its_operation(sample_database, operation, expected):
    data = sample_database.query(
        "SELECT COUNT(*) AS a, COUNT(*) FILTER (WHERE is_cancelled) AS b FROM registry", "q1"
    )
    computed = calculate_ratio(data, "b", "a", 2, operation)
    assert expected in render_answer(Answer(outcome="answer", language="uz", evidence=computed))


def test_answer_states_the_filters_it_applied(sample_database):
    text = render_answer(
        stored(
            sample_database,
            "SELECT COUNT(*) AS n FROM registry WHERE region = 'Namangan viloyati' "
            "AND LOWER(product_name) LIKE '%хлопок%'",
        )
    )
    assert "Shartlar" in text
    assert "Namangan viloyati" in text
    assert "хлопок" in text


def test_identity_filters_are_not_repeated_as_conditions(sample_database):
    text = render_answer(
        stored(sample_database, "SELECT seller_name FROM registry WHERE deal_id='100001'")
    )
    assert "Shartlar" not in text


def test_capped_list_tells_the_true_total(sample_database):
    data = sample_database.query("SELECT deal_id FROM registry ORDER BY deal_id LIMIT 5", "q1")
    capped = data.model_copy(update={"row_limit": 5})
    text = render_answer(Answer(outcome="answer", language="uz", evidence=capped))
    assert "27" in text
    assert "cheklangan" in text


@pytest.mark.parametrize(
    "where,expected,raw_sql",
    [
        ("paid_on IS NULL", "To‘lov sanasi: ko‘rsatilmagan", "IS NULL"),
        ("EXTRACT(YEAR FROM deal_date) = 2025", "yil: 2025", "EXTRACT"),
        ("delivered_on > delivery_due", "Yetkazish sanasi > Yetkazishning oxirgi sanasi", ">="),
    ],
)
def test_conditions_are_described_in_words_not_sql(sample_database, where, expected, raw_sql):
    data = sample_database.query(f"SELECT COUNT(*) AS n FROM registry WHERE {where}", "q1")
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    if "deal_date" in where:
        data_text = applied_conditions(data, "uz", include_dates=True)
        assert expected in data_text
        assert raw_sql not in data_text
    else:
        assert expected in text
        assert raw_sql not in text


def test_boolean_inside_a_filter_label_is_in_words(sample_database):
    data = sample_database.query(
        "SELECT COUNT(*) FILTER (WHERE is_cancelled = TRUE) AS c FROM registry", "q1"
    )
    assert "TRUE" not in render_answer(Answer(outcome="answer", language="uz", evidence=data))
