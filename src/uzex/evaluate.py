import asyncio
import csv
import html
import io
import json
import re
import tempfile
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from uzex.engine import Engine
from uzex.render import RECORD_KEYS
from uzex.state import State
from uzex.telegram import Service


def equivalent(expected, actual) -> bool:
    if str(expected) == str(actual):
        return True
    try:
        return Decimal(str(expected)) == Decimal(str(actual))
    except (InvalidOperation, ValueError):
        return False


def grade(case: dict, answer) -> bool:
    if answer.outcome not in case["outcomes"]:
        return False
    if answer.language != case["language"]:
        return False
    actual = [
        value for row in (answer.evidence.rows if answer.evidence else []) for value in row.values()
    ]
    return all(
        any(equivalent(expected, value) for value in actual) for expected in case["expected_values"]
    )


async def evaluate(
    engine: Engine,
    cases_path: Path,
    output: Path,
    limit: int | None = None,
    concurrency: int = 2,
    category: str | None = None,
):
    cases = json.loads(await asyncio.to_thread(cases_path.read_text))
    if category:
        cases = [case for case in cases if case["category"] == category]
    cases = cases[:limit] if limit else cases
    results = []
    semaphore = asyncio.Semaphore(concurrency)
    output.parent.mkdir(parents=True, exist_ok=True)
    trace = output.with_suffix(".jsonl")

    async def run(case):
        async with semaphore:
            answer = await engine.answer(case["question"])
            row = {
                "id": case["id"],
                "category": case["category"],
                "passed": grade(case, answer),
                "expected_values": case["expected_values"],
                "answer": answer.model_dump(mode="json"),
            }
            results.append(row)
            with trace.open("a") as file:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"{case['id']}: {'PASS' if row['passed'] else 'FAIL'} ({answer.elapsed_seconds:.1f}s)",
                flush=True,
            )

    trace.write_text("")
    await asyncio.gather(*(run(case) for case in cases))
    durations = sorted(row["answer"]["elapsed_seconds"] for row in results)
    answerable = [row for row in results if row["category"] != "safety"]
    safety = [row for row in results if row["category"] == "safety"]
    summary = {
        "run_at_unix": time.time(),
        "model": engine.settings.openai_model,
        "total": len(results),
        "passed": sum(row["passed"] for row in results),
        "answerable": len(answerable),
        "answerable_passed": sum(row["passed"] for row in answerable),
        "safety": len(safety),
        "safety_passed": sum(row["passed"] for row in safety),
        "p95_seconds": durations[min(int(len(durations) * 0.95), len(durations) - 1)]
        if durations
        else None,
        "max_seconds": max(durations, default=0),
        "failures": [row["id"] for row in results if not row["passed"]],
    }
    await asyncio.to_thread(output.write_text, json.dumps(summary, indent=2) + "\n")
    return summary


class RecordingBot:
    def __init__(self):
        self.messages = []
        self.files = []

    async def send_chat_action(self, *args, **kwargs):
        pass

    async def set_my_commands(self, *args, **kwargs):
        pass

    async def answer_callback_query(self, *args, **kwargs):
        pass

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(html.unescape(re.sub(r"</?b>", "", text)))

    async def send_document(self, chat_id, document, caption=None, **kwargs):
        rows = list(csv.reader(io.StringIO(document.data.decode("utf-8-sig"))))
        self.files.append(len(rows) - 1)
        if caption:
            self.messages.append(caption)


def without_spaces(value) -> str:
    return re.sub(r"\s+", "", str(value))


def grade_turn(turn: dict, seen: dict, previous: dict | None = None) -> list[str]:
    problems = []
    if seen["outcome"] not in turn["outcomes"]:
        problems.append(f"outcome {seen['outcome']} not in {turn['outcomes']}")
    if turn.get("language") and seen["language"] != turn["language"]:
        problems.append(f"language {seen['language']} instead of {turn['language']}")
    compact = without_spaces(seen["text"])
    for expected in turn.get("in_text", []):
        if without_spaces(expected) not in compact:
            problems.append(f"missing from the reply: {expected}")
    acceptable = turn.get("any_in_text", [])
    if acceptable and not any(without_spaces(value) in compact for value in acceptable):
        problems.append(f"none of these in the reply: {acceptable}")
    stored = without_spaces(json.dumps(seen["rows"], ensure_ascii=False))
    for expected in turn.get("in_rows", []):
        if without_spaces(expected) not in stored:
            problems.append(f"missing from the stored rows: {expected}")
    for forbidden in turn.get("not_in_text", []):
        if forbidden in seen["text"]:
            problems.append(f"must not appear in the reply: {forbidden}")
    if "file_rows" in turn and seen["files"] != [turn["file_rows"]]:
        problems.append(f"file rows {seen['files']} instead of {turn['file_rows']}")
    if turn.get("no_file") and seen["files"]:
        problems.append(f"unwanted file with rows {seen['files']}")
    if turn.get("uses_previous_ids"):
        rows = (previous or {}).get("rows") or []
        key = next((name for name in RECORD_KEYS if rows and name in rows[0]), None)
        unused = (
            [row[key] for row in rows if str(row[key]) not in (seen["sql"] or "")] if key else []
        )
        if not key or unused:
            problems.append(f"previous records not used: {unused or 'none available'}")
    if turn.get("differs_from_previous") and previous and seen["text"] == previous["text"]:
        problems.append("repeated the previous reply")
    return problems


async def evaluate_conversations(
    engine: Engine,
    cases_path: Path,
    output: Path,
    limit: int | None = None,
    concurrency: int = 2,
    category: str | None = None,
):
    cases = json.loads(await asyncio.to_thread(cases_path.read_text))
    if category:
        cases = [case for case in cases if case["category"] == category]
    cases = cases[:limit] if limit else cases
    results = []
    durations = []
    semaphore = asyncio.Semaphore(concurrency)
    output.parent.mkdir(parents=True, exist_ok=True)
    trace = output.with_suffix(".jsonl")
    trace.write_text("")

    async def run(case, folder):
        async with semaphore:
            state = State(Path(folder) / f"{case['id']}.sqlite3")
            bot = RecordingBot()
            service = Service(bot, state, engine)
            previous = None
            turns = []
            for index, turn in enumerate(case["turns"], 1):
                bot.messages, bot.files = [], []
                started = time.monotonic()
                state.enqueue(index, 1, {"type": "message", "text": turn["q"], "message_id": index})
                job = state.claim()
                await service.process(job)
                durations.append(time.monotonic() - started)
                row = state.db.execute(
                    "SELECT result FROM jobs WHERE id=?", (job["id"],)
                ).fetchone()
                stored = json.loads(row["result"]) if row and row["result"] else {}
                answer = stored.get("answer") or {}
                evidence = answer.get("evidence") or {}
                seen = {
                    "text": "\n".join(bot.messages),
                    "outcome": answer.get("outcome"),
                    "language": answer.get("language"),
                    "files": bot.files,
                    "sql": evidence.get("sql"),
                    "rows": evidence.get("rows") or [],
                }
                problems = grade_turn(turn, seen, previous)
                turns.append(
                    {
                        "q": turn["q"],
                        "passed": not problems,
                        "problems": problems,
                        "outcome": seen["outcome"],
                        "sql": seen["sql"],
                        "text": seen["text"][:1500],
                        "files": seen["files"],
                    }
                )
                previous = seen
            state.close()
            passed = all(item["passed"] for item in turns)
            result = {
                "id": case["id"],
                "category": case["category"],
                "passed": passed,
                "turns": turns,
            }
            results.append(result)
            with trace.open("a") as file:
                file.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"{case['id']}: {'PASS' if passed else 'FAIL'}", flush=True)

    with tempfile.TemporaryDirectory() as folder:
        await asyncio.gather(*(run(case, folder) for case in cases))
    durations.sort()
    summary = {
        "run_at_unix": time.time(),
        "model": engine.settings.openai_model,
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "turns": sum(len(result["turns"]) for result in results),
        "turns_passed": sum(item["passed"] for result in results for item in result["turns"]),
        "p95_seconds": round(durations[min(int(len(durations) * 0.95), len(durations) - 1)], 3)
        if durations
        else None,
        "max_seconds": round(max(durations, default=0), 3),
        "failures": [
            {"id": result["id"], "q": item["q"], "problems": item["problems"]}
            for result in results
            for item in result["turns"]
            if not item["passed"]
        ],
    }
    await asyncio.to_thread(
        output.write_text, json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return summary
