import shutil

import duckdb
import pytest

from uzex.database import Database
from uzex.ingest import product_families, product_key
from uzex.models import Answer
from uzex.render import render_answer


@pytest.mark.parametrize(
    "spellings",
    [
        [
            "Хлопок сырец (спот)",
            "Хлопок-сырец (спот)",
            "ХЛОПОК-СЫРЕЦ (СПОТ)",
            "ХЛОПОК СЫРЕЦ (СПОТ)",
        ],
        ["ПОРТЛАНДЦЕМЕНТ", "Портландцемент", "Цемент портландский"],
        ["Пряжа хлопковая", "ПРЯЖА ХЛОПЧАТОБУМАЖНАЯ"],
        ["КАТОД МЕДНЫЙ", "Медный катод"],
        ["Хлопок-сырец (спот) I сорт 1-класс", "ХЛОПОК СЫРЕЦ (СПОТ) ПЕРВЫЙ СОРТ I КЛАСС"],
    ],
)
def test_seller_spellings_of_one_product_share_a_key(spellings):
    assert len({product_key(spelling) for spelling in spellings}) == 1


@pytest.mark.parametrize(
    "first,second",
    [
        ("Хлопок сырец (спот)", "Хлопок сырец (форвард)"),
        ("Катод медный М00к", "Катод медный М0к"),
        ("Сахар белый", "САХАР-ПЕСОК"),
        ("Хлопок-сырец (спот) I сорт 1-класс", "Хлопок-сырец (спот) I сорт II класс"),
        ("Пшеница", "Пшеница продовольственная"),
    ],
)
def test_different_products_and_grades_stay_apart(first, second):
    assert product_key(first) != product_key(second)


def test_family_is_named_after_the_most_used_spelling():
    families = product_families(
        [("ХЛОПОК-СЫРЕЦ (СПОТ)", 3), ("Хлопок сырец (спот)", 10), ("Сахар белый", 1)]
    )
    assert families == {
        "ХЛОПОК-СЫРЕЦ (СПОТ)": "Хлопок сырец (спот)",
        "Хлопок сырец (спот)": "Хлопок сырец (спот)",
        "Сахар белый": "Сахар белый",
    }


def test_registry_can_group_by_merged_product(sample_database):
    data = sample_database.query(
        "SELECT product_family, COUNT(*) AS n FROM registry GROUP BY product_family "
        "ORDER BY n DESC, product_family LIMIT 3",
        "q1",
    )
    assert data.rows[0]["product_family"]
    answer = Answer(outcome="answer", language="uz", evidence=data)
    assert "Tovar (umumiy nom)" in render_answer(answer)


def test_product_lookup_tells_the_model_the_merged_name(sample_database):
    assert all("product_family" in row for row in sample_database.lookup("product", "цемент"))


def test_merged_columns_do_not_clutter_a_full_deal_card(sample_database):
    data = sample_database.query("SELECT * FROM registry WHERE deal_id = '100001'", "q1")
    text = render_answer(Answer(outcome="answer", language="uz", evidence=data))
    assert "Tovar (umumiy nom)" not in text
    assert "Massa, t" not in text
    assert "Birlik narxi: 3 820.22" in text
    assert "Sotuvchi faoliyati" in text


def test_older_dataset_without_new_relations_still_loads(tmp_path, sample_database):
    copy = tmp_path / "old.duckdb"
    shutil.copy(sample_database.path, copy)
    with duckdb.connect(str(copy)) as db:
        db.execute("DROP VIEW broker_deals")
        db.execute(
            "CREATE OR REPLACE VIEW registry AS SELECT * EXCLUDE (product_family) FROM ("
            + db.execute("SELECT sql FROM duckdb_views() WHERE view_name = 'registry'")
            .fetchone()[0]
            .split(" AS ", 1)[1]
            .rstrip(";")
            + ")"
        )
    old = Database(copy)
    assert "broker_deals" not in old.schema
    assert old.query("SELECT COUNT(*) AS n FROM registry", "q1").rows[0]["n"] == 27
