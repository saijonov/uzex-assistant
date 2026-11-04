from uzex.database import ROW_LIMITS, validate_query


def test_a_grouped_list_may_be_longer_than_a_list_of_deals():
    validate_query(
        "SELECT buyer_inn, COUNT(*) AS n FROM registry GROUP BY buyer_inn ORDER BY n DESC LIMIT 150"
    )
    validate_query("SELECT DISTINCT seller_inn FROM registry LIMIT 5000")


def test_a_grouped_result_is_not_held_to_the_deal_limit(sample_database):
    data = sample_database.query(
        "SELECT seller_inn, COUNT(*) AS n FROM registry GROUP BY seller_inn", "q1"
    )
    assert data.row_limit > ROW_LIMITS["registry"]
    assert not data.capped


def test_asking_for_more_deals_than_one_answer_holds_is_reported(sample_database, monkeypatch):
    monkeypatch.setitem(ROW_LIMITS, "registry", 3)
    data = sample_database.query("SELECT deal_id FROM registry ORDER BY deal_id LIMIT 5", "q1")
    assert data.requested_count == 5
    assert len(data.rows) == 3
    assert data.capped


def test_a_large_limit_on_a_short_list_reports_no_cap(sample_database):
    data = sample_database.query("SELECT deal_id FROM registry ORDER BY deal_id LIMIT 500", "q1")
    assert data.requested_count is None
    assert not data.truncated
