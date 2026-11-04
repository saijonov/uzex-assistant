import json
import sqlite3
import time

import duckdb

from uzex.config import Settings


def health(settings: Settings) -> dict:
    result = {"database": False, "bot": False}
    try:
        with duckdb.connect(str(settings.database_path), read_only=True) as db:
            result["dataset"] = json.loads(
                db.execute("SELECT manifest FROM metadata").fetchone()[0]
            )
            result["database"] = True
    except (duckdb.Error, OSError):
        pass
    try:
        with sqlite3.connect(f"file:{settings.state_path.resolve()}?mode=ro", uri=True) as db:
            row = db.execute("SELECT value FROM meta WHERE key='heartbeat'").fetchone()
            age = time.time() - float(row[0]) if row else None
            result["heartbeat_age_seconds"] = round(age, 2) if age is not None else None
            result["bot"] = age is not None and age < 90
            result["jobs"] = dict(db.execute("SELECT status,count(*) FROM jobs GROUP BY status"))
    except (sqlite3.Error, OSError):
        pass
    result["healthy"] = result["database"] and result["bot"]
    return result
