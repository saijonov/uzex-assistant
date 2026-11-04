import pytest
from test_answer_fit import detail_review

from uzex.policy import unavailable_request


@pytest.mark.parametrize(
    "question",
    [
        "QQS to'lamaydigan sotuvchilar qancha?",
        "QQS to'laydigan sotuvchilar qancha?",
        "Плательщики НДС сколько?",
    ],
)
def test_vat_payer_status_is_answerable(question):
    assert unavailable_request(detail_review(), question) is None


@pytest.mark.parametrize(
    "question", ["QQS summasi qancha?", "Сколько уплачено НДС?", "Kompaniya foydasi qancha?"]
)
def test_actual_vat_and_profit_stay_unavailable(question):
    assert unavailable_request(detail_review(), question) == "missing_field"
