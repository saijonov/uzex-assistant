import pytest
from test_answer_fit import detail_review

from uzex.models import Evidence
from uzex.policy import cancellation_gap


def cancelled_result():
    return Evidence(
        query_id="q1",
        sql="SELECT SUM(amount_uzs) AS total FROM registry",
        table="registry",
        rows=[{"total": "1"}],
        matched_count=10,
        samples=[],
        period_start=None,
        period_end=None,
        currencies=[],
        units=[],
        filters=None,
        cancelled_records=3,
    )


@pytest.mark.parametrize(
    "question",
    [
        "Bekor qilinganlarni chiqarib tashlamasdan jami summa",
        "Bekor qilinganlarni chiqarmasdan jami summa",
        "Сумма сделок, не исключая аннулированные",
    ],
)
def test_keeping_cancelled_deals_is_not_excluding_them(question):
    review = detail_review(task="turnover", subject="market")
    assert cancellation_gap(review, question, cancelled_result()) is None


@pytest.mark.parametrize(
    "question",
    [
        "Bekor qilinganlardan tashqari jami summa",
        "Сумма за вычетом аннулированных сделок",
        "Bekor qilinganlarni chiqarib jami summa",
        "Сумма без аннулированных сделок",
    ],
)
def test_every_way_of_excluding_cancelled_deals_is_recognised(question):
    review = detail_review(task="count", subject="market")
    assert "exclude cancelled" in cancellation_gap(review, question, cancelled_result())
