import json
import time

from uzex.config import Settings
from uzex.engine import Engine
from uzex.state import State
from uzex.telegram import Service


class FakeBot:
    def __init__(self):
        self.messages = []
        self.commands = []
        self.documents = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})

    async def answer_callback_query(self, callback_id):
        pass

    async def send_chat_action(self, *args):
        pass

    async def set_my_commands(self, commands, **kwargs):
        self.commands.append((commands, kwargs))

    async def send_document(self, chat_id, document, **kwargs):
        self.documents.append({"chat_id": chat_id, "document": document, **kwargs})


def message_job(text, chat_id=1):
    return {
        "id": "job",
        "chat_id": chat_id,
        "received": time.time(),
        "next_part": 0,
        "payload": json.dumps({"type": "message", "text": text}),
    }


async def test_welcome_and_language_work_without_model(tmp_path, sample_database):
    bot = FakeBot()
    state = State(tmp_path / "state.db")
    service = Service(bot, state, Engine(Settings(_env_file=None), database=sample_database))
    result = await service.prepare(message_job("/start"))
    assert "UZEX21" in result["texts"][0]
    result = await service.prepare(message_job("/language"))
    assert result["language_keyboard"]
    assert state.chat(1)["history"] == []
    state.close()


async def test_telegram_replies_from_verified_answer(tmp_path, sample_database):
    from test_engine import ScriptedClient, finish

    bot = FakeBot()
    state = State(tmp_path / "state.db")
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            finish(),
        ]
    )
    service = Service(bot, state, Engine(Settings(_env_file=None), client, sample_database))
    state.enqueue(1, 50, {"type": "message", "text": "Кто продавец по сделке 100001?"})
    job = state.claim()
    result = await service.prepare(job)
    state.save_result(job["id"], result)
    await service.deliver(job, result)
    assert bot.messages[0]["chat_id"] == 50
    assert "RUKUSHO‘ FERMER MCHJ" in bot.messages[0]["text"]
    assert (
        bot.messages[0]["reply_markup"].inline_keyboard[0][0].callback_data.startswith("sources:")
    )
    assert state.claim() is None
    assert state.answer_for(job["id"], 51) is None
    assert state.answer_for(job["id"], 50).outcome == "answer"
    state.close()


async def test_source_callback_cannot_access_another_chat(tmp_path, sample_database):
    state = State(tmp_path / "state.db")
    service = Service(FakeBot(), state, Engine(Settings(_env_file=None), database=sample_database))
    state.enqueue(1, 1, {})
    job = state.claim()
    state.save_result(
        job["id"], {"texts": ["private"], "answer": {"outcome": "answer", "language": "ru"}}
    )
    other = {
        "chat_id": 2,
        "payload": json.dumps(
            {
                "type": "callback",
                "data": "sources:" + job["id"],
                "callback_id": "c",
                "language_code": "ru",
            }
        ),
    }
    result = await service.prepare(other)
    assert "private" not in result["texts"][0]
    assert "не найден" in result["texts"][0]
    state.close()
