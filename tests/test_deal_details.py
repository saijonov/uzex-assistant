import csv
import io

import pytest

from uzex.models import Answer
from uzex.render import export_csv, format_value, render_answer, render_sources
from uzex.terminology import display_value


def test_earliest_record_has_selected_date_and_matching_source(sample_database):
    evidence = sample_database.query(
        "SELECT * FROM registry ORDER BY deal_date, deal_time, deal_id LIMIT 1",
        "q1",
    )
    assert evidence.matched_count == 27
    assert evidence.selected_record_count == 1
    assert evidence.period_start == evidence.period_end == "2022-01-03"
    assert evidence.samples[0]["deal_id"] == evidence.rows[0]["deal_id"] == "100001"
    assert evidence.currencies == ["Узбекский сум"]
    text = render_answer(Answer(outcome="answer", language="uz", evidence=evidence))
    assert "Hisobga olingan yozuvlar: 27" not in text
    assert "Paxta chigiti shroti" in text
    assert "1-nav" in text and "tostlangan" in text
    assert "первый сорт" not in text and "тостированный" not in text
    assert "Narx va hajm\n" in text
    assert "79 720" in text and "79720.000" not in text
    assert "Sotuvchi STIR: 921912462" in text
    sources = render_sources(evidence, "uz")
    assert "Qidiruvdagi yozuvlar: 27" in sources
    assert "Tanlangan bitimlar: 1" in sources
    assert "Шрот хлопковых семян" in sources


def test_latest_source_samples_follow_result_order(sample_database):
    evidence = sample_database.query(
        "SELECT deal_id, deal_date FROM registry "
        "ORDER BY deal_date DESC, deal_time DESC, deal_id DESC LIMIT 1",
        "q1",
    )
    assert evidence.selected_record_count == 1
    assert evidence.samples[0]["deal_id"] == evidence.rows[0]["deal_id"]
    assert evidence.period_start == evidence.rows[0]["deal_date"]
    assert evidence.period_end == evidence.rows[0]["deal_date"]


def test_aggregation_keeps_full_population_context(sample_database):
    evidence = sample_database.query("SELECT count(*) AS n FROM registry", "q1")
    assert evidence.selected_record_count is None
    assert evidence.matched_count == 27
    assert evidence.rows == [{"n": 27}]


def test_product_translations_do_not_change_export_or_identifiers(sample_database):
    evidence = sample_database.query("SELECT * FROM registry WHERE deal_id='100001'", "q1")
    text = render_answer(Answer(outcome="answer", language="uz", evidence=evidence))
    assert '"КЕКУХО БРОКЕР" МЧЖ' in text
    assert "BK060" in text and "230610" in text
    original = list(csv.DictReader(io.StringIO(export_csv(evidence).decode("utf-8-sig"))))[0]
    assert original["grade"] == "первый сорт"
    assert original["product_type"] == "тостированный"
    assert original["product"] == "Шрот хлопковых семян"


@pytest.mark.parametrize(
    "source,field,expected",
    [
        ("первый сорт", "grade", "1-nav"),
        ("II СОРТ", "grade", "2-nav"),
        ("3-СОРТА", "grade", "3-nav"),
        ("В/С", "grade", "oliy nav"),
        ("IV КЛАСС", "product_class", "4-sinf"),
        ("тостированный", "product_type", "tostlangan"),
        ("АИ-80", "brand", "АИ-80"),
        ("А500С", "product_class", "А500С"),
        ("21Х30ММ", "size", "21×30 mm"),
        (
            "Масло хлопковое 1-сорта рафинированное дезодорированное",
            "product",
            "Paxta yog‘i 1-nav rafinatsiyalangan va hidsizlantirilgan",
        ),
        ("Рис", "seller_name", "Рис"),
    ],
)
def test_contextual_translation_preserves_codes_and_names(source, field, expected):
    assert display_value(source, "uz", field) == expected


@pytest.mark.parametrize(
    "value,field,expected",
    [
        ("79720.000000", "volume", "79 720"),
        ("304547938.4000", "amount_uzs", "304 547 938.40"),
        ("-0.45", "ratio", "-0.45"),
        ("001234567", "seller_inn", "001234567"),
    ],
)
def test_numeric_display_does_not_change_precision_or_identifiers(value, field, expected):
    assert format_value(value, "uz", field) == expected
