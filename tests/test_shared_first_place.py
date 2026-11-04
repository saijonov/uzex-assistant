from conversation_helpers import raw
from test_answer_fit import detail_review

from uzex.models import Answer
from uzex.policy import answer_gap
from uzex.render import render_answer


def test_a_hidden_tie_is_noticed_and_reported(sample_database):
    top = raw(sample_database, "SELECT min(deposit_percent) FROM contracts")
    holders = raw(sample_database, f"SELECT count(*) FROM contracts WHERE deposit_percent = {top}")
    assert holders > 1
    data = sample_database.query(
        "SELECT contract_id, deposit_percent FROM contracts ORDER BY deposit_percent LIMIT 1",
        "q1",
    )
    assert data.ties_beyond_limit
    assert "QUALIFY" in answer_gap(detail_review(task="rank"), "Qaysi shartnoma?", data)
    assert "и у других записей" in render_answer(
        Answer(outcome="answer", language="ru", evidence=data)
    )


def test_a_unique_key_is_not_a_tie(sample_database):
    data = sample_database.query("SELECT deal_id FROM registry ORDER BY deal_id LIMIT 1", "q1")
    assert not data.ties_beyond_limit


def test_the_latest_date_is_not_a_tie(sample_database):
    data = sample_database.query(
        "SELECT deal_id, deal_date FROM registry ORDER BY deal_date DESC, deal_id DESC LIMIT 1",
        "q1",
    )
    assert not data.ties_beyond_limit


def test_counting_cancelled_is_the_default_for_counts(sample_database):
    data = sample_database.query("SELECT COUNT(*) AS n FROM registry WHERE NOT is_cancelled", "q1")
    review = detail_review(task="count", subject="market")
    assert "include cancelled" in answer_gap(review, "nechta klient bor", data)
    assert answer_gap(review, "bekor qilinganlarsiz nechta", data) is None
