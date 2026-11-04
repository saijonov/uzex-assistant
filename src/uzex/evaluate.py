import asyncio
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from uzex.engine import Engine


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
            answer = await engine.answer(case["question"], case["language"])
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
