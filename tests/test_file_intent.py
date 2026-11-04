import pytest
from conversation_helpers import enqueue
from test_engine import ScriptedClient, finish
from test_interface import make_service

from uzex.policy import (
    export_followup,
    file_preference,
)
from uzex.render import export_csv


@pytest.mark.parametrize(
    "question,preference",
    [
        ("brokerlar nomini csv qilib ber", "csv"),
        ("kompaniya nomi bilan csv fayl yubor", "csv"),
        ("nomlari csv formatida kerak", "csv"),
        ("excel qilib ber", "csv"),
        ("faylda ber", "csv"),
        ("файлом пришли", "csv"),
        ("в экселе пришли", "csv"),
        ("csv bermang", "text"),
        ("csv qilmang", "text"),
        ("faylda bermang", "text"),
        ("faylsiz ko'rsat", "text"),
        ("excel kerak emas", "text"),
        ("не присылай файл", "text"),
        ("csv nima?", "auto"),
        ("fayl nechta qatordan iborat?", "auto"),
    ],
)
def test_file_intent_is_not_fooled_by_word_fragments(question, preference):
    assert file_preference(question) == preference


async def test_file_request_for_a_long_list_sends_the_file_without_pages_of_text(
    tmp_path, sample_database
):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT broker_code FROM brokers ORDER BY broker_code"}),
            finish(),
        ]
    )
    service = make_service(tmp_path, sample_database, client)
    await service.process(enqueue(service, "brokerlar kodini csv qilib ber"))
    assert len(service.bot.documents) == 1
    assert len(service.bot.messages) == 1
    assert "BK001" not in service.bot.messages[0]["text"]
    assert "120" in service.bot.messages[0]["text"]
    service.state.close()


@pytest.mark.parametrize("question", ["faylsiz", "fayl kerak emas", "csv bermang"])
def test_declining_a_file_is_never_an_export_request(question):
    assert not export_followup(question)


def test_negative_numbers_stay_numbers_in_csv_while_formulas_are_neutralised(sample_database):
    data = sample_database.query("SELECT broker_code FROM brokers LIMIT 1", "q1").model_copy(
        update={"rows": [{"change": "-14.22", "name": "-cmd", "other": "=1+1"}]}
    )
    content = export_csv(data).decode("utf-8-sig")
    assert "-14.22" in content
    assert "'-14.22" not in content
    assert "'-cmd" in content
    assert "'=1+1" in content
