from datetime import date
from decimal import Decimal

from conversation_helpers import raw

from uzex.models import Answer
from uzex.render import render_answer


def test_days_between_events_are_available(sample_database):
    row = sample_database.query(
        "SELECT deal_date, paid_on, delivered_on, days_to_payment, days_to_delivery, "
        "days_payment_to_delivery FROM registry WHERE delivered_on IS NOT NULL "
        "ORDER BY deal_id LIMIT 1",
        "q1",
    ).rows[0]
    deal, paid, delivered = (
        date.fromisoformat(row[name]) for name in ("deal_date", "paid_on", "delivered_on")
    )
    assert row["days_to_payment"] == (paid - deal).days
    assert row["days_to_delivery"] == (delivered - deal).days
    assert row["days_payment_to_delivery"] == (delivered - paid).days


def test_an_unpaid_deal_has_no_days_to_payment(sample_database):
    blank = raw(
        sample_database,
        "SELECT count(*) FROM registry WHERE paid_on IS NULL AND days_to_payment IS NOT NULL",
    )
    assert blank == 0


def test_every_deal_has_a_dollar_amount_at_its_own_rate(sample_database):
    rows = sample_database.query(
        "SELECT amount, currency, usd_uzs, amount_usd FROM registry ORDER BY deal_id", "q1"
    ).rows
    for row in rows:
        amount, rate = Decimal(row["amount"]), Decimal(row["usd_uzs"])
        expected = amount if row["currency"] == "Доллар США" else amount / rate
        assert abs(Decimal(row["amount_usd"]) - expected) < Decimal("0.000001")


def test_a_dollar_total_is_shown_in_cents(sample_database):
    data = sample_database.query(
        "SELECT SUM(amount_usd) AS total FROM registry WHERE NOT is_cancelled", "q1"
    )
    text = render_answer(Answer(outcome="answer", language="ru", evidence=data))
    assert "Итого: Сумма, доллар США" in text
    value = text.split("Итого: Сумма, доллар США: ")[1].splitlines()[0]
    assert len(value.rpartition(".")[2]) <= 2
