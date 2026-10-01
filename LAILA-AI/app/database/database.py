import sqlite3, json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from app.core.config import DATA, Settings


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid4().hex


@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / "laila.db", timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
        INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT NOT NULL, pinned INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE, role TEXT, content TEXT, meta TEXT DEFAULT '{}', created_at TEXT);
        CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation_id);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, content TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY, title TEXT, content TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, title TEXT, due_date TEXT, priority TEXT, completed INTEGER DEFAULT 0, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, filename TEXT, path TEXT, status TEXT, error TEXT, embedding_model TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS document_chunks(id TEXT PRIMARY KEY, document_id TEXT REFERENCES documents(id) ON DELETE CASCADE, page INTEGER, location TEXT, content TEXT, embedding TEXT);
        CREATE TABLE IF NOT EXISTS tool_logs(id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE, name TEXT, arguments TEXT, status TEXT, result TEXT, created_at TEXT);
        """)
        version = con.execute("SELECT version FROM schema_version").fetchone()[0]
        if version != 1:
            raise RuntimeError(
                "Unsupported database schema. Back up data before upgrading."
            )


def rows(sql, args=()):
    with connect() as con:
        return [dict(x) for x in con.execute(sql, args).fetchall()]


def run(sql, args=()):
    with connect() as con:
        return con.execute(sql, args).rowcount


def settings():
    values = rows("SELECT value FROM settings WHERE key='app'")
    return Settings.model_validate_json(values[0]["value"]) if values else Settings()


def save_settings(value):
    run(
        "INSERT INTO settings VALUES('app',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (value.model_dump_json(),),
    )


def message(cid, role, content, meta=None):
    ident = uid()
    with connect() as con:
        con.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?,?)",
            (ident, cid, role, content, json.dumps(meta or {}), now()),
        )
        con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), cid))
    return ident
