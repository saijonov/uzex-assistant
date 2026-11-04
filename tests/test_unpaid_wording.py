import pytest
from test_answer_fit import detail_review
from test_cancelled_wording import cancelled_result

from uzex.policy import cancellation_gap


@pytest.mark.parametrize(
    "question",
    [
        "To'lanmagan bitimlar summasi",
        "Сумма неоплаченных сделок",
        "Sotilmay qolgan tovarlar summasi",
    ],
)
def test_unpaid_questions_may_include_cancelled_deals(question):
    review = detail_review(task="turnover", subject="market")
    assert cancellation_gap(review, question, cancelled_result()) is None


def test_ordinary_turnover_still_excludes_cancelled_deals():
    review = detail_review(task="turnover", subject="market")
    assert "by default" in cancellation_gap(review, "2025 jami summa", cancelled_result())
