import shutil

import duckdb
import pytest

from uzex.database import Database
from uzex.ingest import product_families
from uzex.models import Answer
from uzex.render import render_answer


@pytest.mark.parametrize(
    "spellings",
    [
        ["ПОРТЛАНДЦЕМЕНТ", "Портландцемент ЦЕМ I 42,5 Н", "Цемент портландский ЦЕМ II/В-К 32,5Н"],
        ["БЕНЗИН АВТОМОБИЛЬНЫЙ", "Бензин", "Бензин автомобильный АИ-92"],
        ["Пшеница продовольственная", "Пшеница", "Пшеница 4-класс"],
        [
            "Хлопок сырец (спот)",
            "ХЛОПОК-СЫРЕЦ (СПОТ) 2 СОРТ 1-КЛАСС",
            "Хлопок-сырец (спот) I сорт 1-класс",
        ],
        ["Карбамид", "Мочевина (карбамид)"],
    ],
)
def test_every_way_of_writing_one_good_gets_one_name(spellings):
    counts = [(name, "000001", 10 - index) for index, name in enumerate(spellings)]
    assert set(product_families(counts).values()) == {spellings[0]}


@pytest.mark.parametrize(
    "first,second",
    [
        ("Хлопок сырец (спот)", "Хлопок сырец (форвард)"),
        ("Хлопок сырец (спот)", "ХЛОПОК-СЫРЕЦ (ФЬЮЧЕРС) ПЕРВЫЙ СОРТ II КЛАСС"),
        ("Топливо дизельное", "Мазут топочный"),
    ],
)
def test_different_goods_with_one_code_stay_apart(first, second):
    families = product_families([(first, "000001", 5), (second, "000001", 3)])
    assert families[first] != families[second]


def test_goods_with_different_codes_stay_apart():
    families = product_families([("Рис", "100630", 5), ("Соль", "250100", 3)])
    assert families["Рис"] != families["Соль"]


def test_the_good_is_named_after_its_most_traded_spelling():
    families = product_families([("Катод медный М0к", "740311", 3), ("КАТОД МЕДНЫЙ", "740311", 10)])
    assert families == {"Катод медный М0к": "КАТОД МЕДНЫЙ", "КАТОД МЕДНЫЙ": "КАТОД МЕДНЫЙ"}


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
