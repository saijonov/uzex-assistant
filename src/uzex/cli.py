import argparse
import asyncio
import json
from pathlib import Path

from uzex.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="uzex")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import")
    ingest.add_argument("archive", type=Path)
    commands.add_parser("check")
    commands.add_parser("bot")
    commands.add_parser("health")
    commands.add_parser("install-service")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--cases", type=Path, default=Path("evaluation/cases.json"))
    evaluate_parser.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    evaluate_parser.add_argument("--limit", type=int)
    evaluate_parser.add_argument("--category")
    evaluate_parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "health":
        from uzex.health import health

        result = health(settings)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["healthy"] else 1)
    if args.command == "install-service":
        from uzex.service import install_service

        print(install_service(Path.cwd()))
        return
    if args.command == "import":
        from uzex.ingest import import_archive

        print(json.dumps(import_archive(args.archive, settings.database_path), indent=2))
    elif args.command == "check":
        import duckdb

        with duckdb.connect(str(settings.database_path), read_only=True) as db:
            print(db.execute("SELECT manifest FROM metadata").fetchone()[0])
    elif args.command == "bot":
        from uzex.telegram import run_bot

        asyncio.run(run_bot(settings))
    elif args.command == "ask":
        from uzex.engine import Engine
        from uzex.render import render_answer

        async def run():
            engine = Engine(settings)
            try:
                print(render_answer(await engine.answer(args.question)))
            finally:
                await engine.close()

        asyncio.run(run())
    elif args.command == "evaluate":
        from uzex.engine import Engine
        from uzex.evaluate import evaluate, evaluate_conversations

        cases = json.loads(args.cases.read_text())
        runner = evaluate_conversations if cases and "turns" in cases[0] else evaluate

        async def run_evaluation():
            engine = Engine(settings)
            try:
                result = await runner(
                    engine, args.cases, args.output, args.limit, args.concurrency, args.category
                )
                print(json.dumps(result, indent=2))
            finally:
                await engine.close()

        asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()
