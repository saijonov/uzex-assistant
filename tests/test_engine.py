import asyncio
import json
from types import SimpleNamespace

from uzex.config import Settings
from uzex.engine import TOOLS, Engine
from uzex.render import render_answer, split_text


class ScriptedClient:
    def __init__(self, steps):
        self.responses = self
        self.steps = iter(steps)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        name, arguments = next(self.steps)
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name=name,
                    arguments=json.dumps(arguments),
                    call_id="call",
                )
            ]
        )

    async def close(self):
        pass


def finish(outcome="answer", query_id="q1", reason="none"):
    return (
        "finish",
        {
            "outcome": outcome,
            "query_id": query_id,
            "reason": reason,
            "language": "ru",
            "candidates_query_id": None,
        },
    )


async def test_grounded_answer_uses_executed_evidence(sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT seller_name FROM registry WHERE deal_id='100001'"}),
            finish(),
        ]
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    answer = await engine.answer("Кто продавец по сделке 100001?")
    assert answer.outcome == "answer"
    assert "RUKUSHO‘ FERMER MCHJ" in render_answer(answer)
    assert client.requests[0]["store"] is False
    assert client.requests[0]["parallel_tool_calls"] is False


async def test_model_cannot_invent_evidence_id(sample_database):
    client = ScriptedClient([finish(query_id="imaginary")])
    engine = Engine(Settings(_env_file=None), client, sample_database)
    assert (await engine.answer("test")).outcome == "error"


async def test_false_no_match_is_rejected_and_corrected(sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}),
            finish("no_match"),
            finish(),
        ]
    )
    answer = await Engine(Settings(_env_file=None), client, sample_database).answer(
        "Сколько сделок?"
    )
    assert answer.outcome == "answer"
    assert answer.evidence.rows[0]["n"] == 27


async def test_empty_lookup_does_not_support_no_match(sample_database):
    client = ScriptedClient(
        [
            ("lookup_entities", {"kind": "company", "text": "imaginary"}),
            finish("no_match", "lookup_1"),
        ]
    )
    result = await Engine(Settings(_env_file=None), client, sample_database).answer("test")
    assert result.outcome == "error"


async def test_service_failure_is_not_reported_as_absence(sample_database):
    result = await Engine(Settings(_env_file=None), None, sample_database).answer("Savol")
    assert result.outcome == "error"
    assert "ma’lumot yo‘q degani emas" in render_answer(result)


async def test_deadline_returns_service_error_without_unchecked_content(sample_database):
    class SlowClient(ScriptedClient):
        async def create(self, **kwargs):
            await asyncio.sleep(1)

    settings = Settings(_env_file=None).model_copy(update={"answer_timeout_seconds": 0.01})
    answer = await Engine(settings, SlowClient([]), sample_database).answer("Savol")
    assert answer.outcome == "error"
    assert answer.evidence is None
    assert answer.elapsed_seconds < 0.5


async def test_concurrent_answers_are_isolated(sample_database):
    async def ask(deal_id):
        client = ScriptedClient(
            [
                (
                    "query_registry",
                    {"sql": f"SELECT deal_id FROM registry WHERE deal_id='{deal_id}'"},
                ),
                finish(),
            ]
        )
        return await Engine(Settings(_env_file=None), client, sample_database).answer("Вопрос")

    first, second = await asyncio.gather(ask("100001"), ask("100002"))
    assert first.evidence.rows == [{"deal_id": "100001"}]
    assert second.evidence.rows == [{"deal_id": "100002"}]


def test_strict_tools_have_required_fields_and_no_extra_properties():
    for tool in TOOLS:
        schema = tool["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_long_telegram_text_splits_without_losing_content():
    text = "a" * 9000
    chunks = split_text(text)
    assert all(len(part) <= 3500 for part in chunks)
    assert "".join(chunks) == text
