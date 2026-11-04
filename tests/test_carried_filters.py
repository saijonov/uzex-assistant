import pytest
from test_answer_fit import detail_review

from uzex.policy import answer_gap


@pytest.fixture
def year_count(sample_database):
    return sample_database.query(
        "SELECT COUNT(*) AS n FROM registry WHERE deal_date BETWEEN DATE '2025-01-01' "
        "AND DATE '2025-12-31' AND is_cancelled",
        "q1",
    )


@pytest.mark.parametrize(
    "question", ["Nechta bitim bekor qilingan?", "Сколько сделок аннулировано?"]
)
def test_a_new_question_does_not_keep_an_old_period(question, year_count):
    assert "no period" in answer_gap(
        detail_review(task="count", subject="market"), question, year_count
    )


@pytest.mark.parametrize(
    "question",
    [
        "2025-yilda nechta bitim bekor qilingan?",
        "Shu yilda nechta bekor qilingan?",
        "Ulardan nechtasi bekor qilingan?",
        "Из них сколько аннулировано?",
        "А за этот период сколько аннулировано?",
        "Nechtasi bekor qilingan?",
        "Oxirgi oyda nechta bekor qilingan?",
        "В октябре сколько аннулировано?",
        "Bekor qilinganlari-chi?",
    ],
)
def test_a_stated_period_or_a_reference_keeps_it(question, year_count):
    assert answer_gap(detail_review(task="count", subject="market"), question, year_count) is None


def test_unpaid_totals_keep_cancelled_deals_unless_excluded(sample_database):
    data = sample_database.query(
        "SELECT SUM(amount_uzs) AS t FROM registry WHERE paid_on IS NULL AND NOT is_cancelled", "q1"
    )
    review = detail_review(task="turnover", subject="market")
    assert "cancelled" in answer_gap(review, "To'lanmagan bitimlar summasi qancha?", data)
    assert answer_gap(review, "Hali to'lanmagan, lekin bekor qilinmagan summa", data) is None
