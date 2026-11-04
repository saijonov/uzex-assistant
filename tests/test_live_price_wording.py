import pytest
from test_answer_fit import detail_review

from uzex.policy import unavailable_request


@pytest.mark.parametrize(
    "question",
    [
        "Hozirgacha shakarning o'rtacha narxi qancha?",
        "Какая средняя цена сахара на сегодняшний день за весь период?",
        "Butun davr uchun hozirgi shakar narxi",
    ],
)
def test_an_all_time_price_is_not_a_live_price(question):
    review = detail_review(task="price", subject="product")
    assert unavailable_request(review, question) is None


@pytest.mark.parametrize(
    "question", ["Shakar narxi hozir qancha?", "Какая цена сахара сегодня?", "ertaga narx qancha"]
)
def test_a_live_price_stays_unavailable(question):
    review = detail_review(task="price", subject="product")
    assert unavailable_request(review, question) == "outside_dates"
