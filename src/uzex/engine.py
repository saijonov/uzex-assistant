import asyncio
import json
import logging
import re
import time
import uuid

from openai import AsyncOpenAI

from uzex.config import Settings
from uzex.database import Database, calculate_ratio
from uzex.models import Answer, Calculation, Finish, Lookup, Query
from uzex.prompt import instructions

logger = logging.getLogger(__name__)


def guess_language(text: str) -> str:
    if re.search("[ўқғҳЎҚҒҲ]", text):
        return "uz"
    return "ru" if re.search("[а-яА-ЯёЁ]", text) else "uz"


def tool(name, model, description):
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": model.model_json_schema(),
        "strict": True,
    }


TOOLS = [
    tool(
        "lookup_entities",
        Lookup,
        "Find real product, company, broker, region, category or status names.",
    ),
    tool(
        "query_registry",
        Query,
        "Execute one restricted read-only SELECT and return evidence with source rows.",
    ),
    tool(
        "calculate_ratio",
        Calculation,
        "Divide two numeric result columns with exact Decimal arithmetic, row by row.",
    ),
    tool(
        "finish",
        Finish,
        "End the turn using a real evidence ID or a fixed unavailable/clarification reason.",
    ),
]


class Engine:
    def __init__(self, settings: Settings, client=None, database=None):
        self.settings = settings
        self.database = database or Database(settings.database_path)
        self.client = client
        if self.client is None and settings.openai_api_key.get_secret_value():
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=40,
                max_retries=0,
            )
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_questions)

    async def close(self):
        if self.client:
            await self.client.close()

    async def answer(
        self, question: str, language: str | None = None, history: list | None = None
    ) -> Answer:
        start = time.monotonic()
        request_id = uuid.uuid4().hex[:12]
        fallback_language = language or guess_language(question)
        try:
            async with asyncio.timeout(self.settings.answer_timeout_seconds):
                async with self.semaphore:
                    if not self.client:
                        raise RuntimeError("Model credentials are missing")
                    result = await self._run(question, language, history or [])
        except Exception as error:
            logger.warning("answer_failed request=%s type=%s", request_id, type(error).__name__)
            result = Answer(outcome="error", language=fallback_language, reason="service_failure")
        result.elapsed_seconds = round(time.monotonic() - start, 3)
        result.request_id = request_id
        logger.info(
            "answer_complete request=%s outcome=%s seconds=%.3f",
            request_id,
            result.outcome,
            result.elapsed_seconds,
        )
        return result

    async def _run(self, question: str, language: str | None, history: list) -> Answer:
        evidence = {}
        lookups = {}
        messages = [*history[-8:], {"role": "user", "content": question[:6000]}]
        for _ in range(8):
            response = await self.client.responses.create(
                model=self.settings.openai_model,
                reasoning={"effort": self.settings.openai_reasoning_effort},
                instructions=instructions(self.database.schema, self.database.manifest, language),
                tools=TOOLS,
                input=messages,
                parallel_tool_calls=False,
                max_output_tokens=2500,
                store=False,
            )
            messages.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                messages.append(
                    {
                        "role": "user",
                        "content": "Call a tool or finish. Free-text factual answers are not accepted.",
                    }
                )
                continue
            for call in calls:
                try:
                    arguments = json.loads(call.arguments)
                    if call.name == "lookup_entities":
                        lookup = Lookup.model_validate(arguments)
                        rows = self.database.lookup(lookup.kind, lookup.text)
                        query_id = f"lookup_{len(lookups) + 1}"
                        lookups[query_id] = rows
                        output = {
                            "query_id": query_id,
                            "candidates": rows,
                            "may_be_truncated": len(rows) == 30,
                        }
                    elif call.name == "query_registry":
                        query = Query.model_validate(arguments)
                        query_id = f"q{len(evidence) + 1}"
                        data = await asyncio.to_thread(self.database.query, query.sql, query_id)
                        evidence[query_id] = data
                        output = data.model_dump(mode="json")
                        output["result_row_count"] = len(data.rows)
                        output["rows"] = output["rows"][:20]
                    elif call.name == "calculate_ratio":
                        calculation = Calculation.model_validate(arguments)
                        if calculation.query_id not in evidence:
                            raise ValueError("Unknown evidence ID")
                        data = calculate_ratio(
                            evidence[calculation.query_id],
                            calculation.numerator,
                            calculation.denominator,
                            calculation.scale,
                            calculation.operation,
                        )
                        query_id = f"q{len(evidence) + 1}"
                        data.query_id = query_id
                        evidence[query_id] = data
                        output = data.model_dump(mode="json")
                        output["result_row_count"] = len(data.rows)
                        output["rows"] = output["rows"][:20]
                    elif call.name == "finish":
                        finish = Finish.model_validate(arguments)
                        data = evidence.get(finish.query_id)
                        if finish.outcome in {"answer", "no_match"}:
                            if data is None:
                                raise ValueError("Answer needs an executed evidence ID")
                            empty = data.matched_count == 0 or not data.rows
                            if finish.outcome == "no_match" and not empty:
                                raise ValueError("No-match claim contradicts returned data")
                            if finish.outcome == "answer" and empty:
                                finish.outcome = "no_match"
                        if finish.outcome in {"clarify", "unavailable"} and finish.reason == "none":
                            raise ValueError("A fixed clarification or absence reason is required")
                        return Answer(
                            outcome=finish.outcome,
                            language=language or finish.language,
                            reason=finish.reason,
                            evidence=data,
                            candidates=lookups.get(finish.candidates_query_id, [])[:5],
                        )
                    else:
                        raise ValueError("Unknown tool")
                except Exception as error:
                    logger.info("tool_rejected tool=%s error=%s", call.name, str(error)[:1000])
                    output = {
                        "error": str(error)[:1000],
                        "instruction": "Correct the tool arguments. This is not evidence of missing data.",
                    }
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(output, ensure_ascii=False),
                    }
                )
        raise RuntimeError("Tool budget exhausted")
