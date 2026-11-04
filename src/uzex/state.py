import json
import sqlite3
import time
import uuid
from pathlib import Path

from uzex.models import Answer


class State:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY, language TEXT, history TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS pending_questions (
                chat_id INTEGER PRIMARY KEY, body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, update_id INTEGER UNIQUE NOT NULL, chat_id INTEGER NOT NULL,
                payload TEXT NOT NULL, received REAL NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
                result TEXT, next_part INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, received);
            UPDATE jobs SET status='queued' WHERE status='working';
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def offset(self) -> int:
        row = self.db.execute("SELECT value FROM meta WHERE key='offset'").fetchone()
        return int(row[0]) if row else 0

    def enqueue(self, update_id: int, chat_id: int, payload: dict) -> bool:
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO jobs(id,update_id,chat_id,payload,received) VALUES(?,?,?,?,?)",
                (
                    uuid.uuid4().hex[:16],
                    update_id,
                    chat_id,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )
            self.db.execute(
                "INSERT INTO meta(key,value) VALUES('offset',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(update_id + 1),),
            )
        return cursor.rowcount == 1

    def advance(self, update_id: int):
        with self.db:
            self.db.execute(
                "INSERT INTO meta(key,value) VALUES('offset',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(update_id + 1),),
            )

    def claim(self):
        with self.db:
            row = self.db.execute(
                """
                SELECT j.* FROM jobs j WHERE j.status IN ('queued','ready')
                AND j.next_attempt <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM jobs older WHERE older.chat_id=j.chat_id
                    AND older.status NOT IN ('sent','failed')
                    AND (older.received < j.received OR
                        (older.received=j.received AND older.update_id<j.update_id))
                ) ORDER BY j.received, j.update_id LIMIT 1
            """,
                (time.time(),),
            ).fetchone()
            if not row:
                return None
            job = dict(row)
            self.db.execute("UPDATE jobs SET status='working' WHERE id=?", (job["id"],))
            return job

    def save_result(self, job_id: str, result: dict):
        with self.db:
            self.db.execute(
                "UPDATE jobs SET result=?,status='working' WHERE id=?",
                (json.dumps(result, ensure_ascii=False), job_id),
            )

    def sent_part(self, job_id: str, part: int):
        with self.db:
            self.db.execute("UPDATE jobs SET next_part=? WHERE id=?", (part, job_id))

    def complete(self, job_id: str):
        with self.db:
            self.db.execute("UPDATE jobs SET status='sent' WHERE id=?", (job_id,))

    def retry(self, job_id: str, delay: float, failed: bool = False):
        with self.db:
            self.db.execute(
                "UPDATE jobs SET status=?,attempts=attempts+1,next_attempt=? WHERE id=?",
                ("failed" if failed else "ready", time.time() + delay, job_id),
            )

    def chat(self, chat_id: int) -> dict:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO chats(chat_id) VALUES(?)", (chat_id,))
        row = self.db.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
        return {"language": row["language"], "history": json.loads(row["history"])}

    def language(self, chat_id: int, language: str):
        self.chat(chat_id)
        with self.db:
            self.db.execute("UPDATE chats SET language=? WHERE chat_id=?", (language, chat_id))

    def remember(self, chat_id: int, question: str, answer: str):
        chat = self.chat(chat_id)
        history = [
            *chat["history"],
            {"role": "user", "content": question[:6000]},
            {"role": "assistant", "content": answer[:10000]},
        ][-8:]
        with self.db:
            self.db.execute(
                "UPDATE chats SET history=? WHERE chat_id=?",
                (json.dumps(history, ensure_ascii=False), chat_id),
            )

    def reset(self, chat_id: int):
        self.chat(chat_id)
        with self.db:
            self.db.execute("UPDATE chats SET history='[]' WHERE chat_id=?", (chat_id,))
            self.db.execute("DELETE FROM pending_questions WHERE chat_id=?", (chat_id,))

    def pending(self, chat_id: int) -> dict | None:
        row = self.db.execute(
            "SELECT body FROM pending_questions WHERE chat_id=?", (chat_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def set_pending(self, chat_id: int, value: dict | None):
        with self.db:
            if value is None:
                self.db.execute("DELETE FROM pending_questions WHERE chat_id=?", (chat_id,))
            else:
                self.db.execute(
                    "INSERT INTO pending_questions(chat_id,body) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET body=excluded.body",
                    (chat_id, json.dumps(value, ensure_ascii=False)),
                )

    def latest_answer(self, chat_id: int) -> Answer | None:
        rows = self.db.execute(
            "SELECT result FROM jobs WHERE chat_id=? AND result IS NOT NULL AND status='sent' ORDER BY received DESC, update_id DESC LIMIT 20",
            (chat_id,),
        ).fetchall()
        for row in rows:
            payload = json.loads(row[0])
            if payload.get("source_csv"):
                return None
            if payload.get("answer"):
                return (
                    Answer.model_validate(payload["answer"])
                    if payload["answer"].get("outcome") == "answer"
                    else None
                )
        return None

    def answer_for(self, job_id: str, chat_id: int) -> Answer | None:
        row = self.db.execute(
            "SELECT result FROM jobs WHERE id=? AND chat_id=?", (job_id, chat_id)
        ).fetchone()
        if not row or not row["result"]:
            return None
        payload = json.loads(row["result"])
        return Answer.model_validate(payload["answer"]) if payload.get("answer") else None

    def health(self) -> dict:
        counts = {
            row[0]: row[1]
            for row in self.db.execute("SELECT status,count(*) FROM jobs GROUP BY status")
        }
        row = self.db.execute("SELECT value FROM meta WHERE key='heartbeat'").fetchone()
        return {"jobs": counts, "heartbeat": float(row[0]) if row else None}

    def heartbeat(self):
        with self.db:
            self.db.execute(
                "INSERT INTO meta(key,value) VALUES('heartbeat',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(time.time()),),
            )
