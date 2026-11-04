import pytest

from uzex.database import validate_query

TOP_PER_YEAR = (
    "SELECT EXTRACT(YEAR FROM deal_date) AS y, buyer_inn, COUNT(*) AS n FROM registry "
    "GROUP BY y, buyer_inn "
    "QUALIFY RANK() OVER (PARTITION BY EXTRACT(YEAR FROM deal_date) ORDER BY COUNT(*) DESC) = 1"
)


def test_the_leader_of_each_group_can_be_selected(sample_database):
    data = sample_database.query(TOP_PER_YEAR, "q1")
    years = {row["y"] for row in data.rows}
    assert years == {2022, 2023, 2024, 2025, 2026}
    counts = sample_database.query(
        "SELECT EXTRACT(YEAR FROM deal_date) AS y, buyer_inn, COUNT(*) AS n FROM registry "
        "GROUP BY y, buyer_inn",
        "q2",
    ).rows
    for row in data.rows:
        best = max(item["n"] for item in counts if item["y"] == row["y"])
        assert row["n"] == best


def test_a_shared_first_place_shows_everyone(sample_database):
    data = sample_database.query(
        "SELECT contract_id, deposit_percent FROM contracts "
        "QUALIFY RANK() OVER (ORDER BY deposit_percent DESC) = 1",
        "q1",
    )
    top = max(
        row["deposit_percent"]
        for row in sample_database.query("SELECT deposit_percent FROM contracts", "q2").rows
    )
    assert {str(row["deposit_percent"]) for row in data.rows} == {str(top)}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM registry QUALIFY ROW_NUMBER() OVER () = 1",
        "SELECT * FROM registry QUALIFY ROW_NUMBER() OVER (ORDER BY deal_id) = 1",
        "SELECT * FROM registry QUALIFY RANK() OVER () = 1",
        "SELECT RANK() OVER (ORDER BY amount_uzs) AS r FROM registry",
        "SELECT LAG(amount_uzs) OVER (ORDER BY deal_id) AS r FROM registry",
    ],
)
def test_other_window_uses_stay_blocked(sql):
    with pytest.raises(ValueError):
        validate_query(sql)


def test_mixed_currencies_cannot_be_ranked_through_a_window(sample_database):
    with pytest.raises(ValueError, match="Mixed currencies"):
        sample_database.query(
            "SELECT deal_id, amount FROM registry QUALIFY RANK() OVER (ORDER BY amount DESC) = 1",
            "q1",
        )


def test_random_samples_cannot_use_a_window(sample_database):
    with pytest.raises(ValueError):
        sample_database.sample(
            "SELECT deal_id FROM registry QUALIFY RANK() OVER (ORDER BY deal_id) = 1", 2, "q1"
        )


def test_a_tied_list_reports_how_many_records_it_holds(sample_database):
    data = sample_database.query(
        "SELECT contract_id, deposit_percent FROM contracts "
        "QUALIFY RANK() OVER (ORDER BY deposit_percent DESC) = 1",
        "q1",
    )
    assert data.matched_count == len(data.rows)
