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
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    args = parser.parse_args()
    settings = Settings()
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


if __name__ == "__main__":
    main()
