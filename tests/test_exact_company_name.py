from uzex.database import Database


def company_database(sample_database, *names):
    database = Database.__new__(Database)
    database.catalog = {
        **sample_database.catalog,
        "company": [
            {"inn": f"90000000{index}", "name": name, "role": "Продавец"}
            for index, name in enumerate(names)
        ],
    }
    return database


def test_an_exact_name_settles_a_near_match(sample_database):
    database = company_database(sample_database, "RUKUSHO‘ FERMER MCHJ", '"Husho‘ Fermer" MChJ')
    rows = database.lookup("company", "RUKUSHO FERMER")
    assert [row["name"] for row in rows] == ["RUKUSHO‘ FERMER MCHJ"]
    assert rows[0]["match"] == "exact"


def test_two_companies_with_the_same_name_stay_ambiguous(sample_database):
    database = company_database(sample_database, '"Xofo‘ Savdo" OK', "XO‘FO‘ SAVDO MCHJ")
    rows = database.lookup("company", "Xofo Savdo")
    assert len(rows) == 2
    assert {row["match"] for row in rows} == {"exact"}


def test_a_partial_name_still_lists_every_candidate(sample_database):
    database = company_database(sample_database, "ALFA SAVDO MCHJ", "ALFA QURILISH MCHJ")
    assert len(database.lookup("company", "ALFA")) == 2
