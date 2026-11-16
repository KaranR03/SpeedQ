"""SQLite persistence (stdlib). Cases are stored as JSON documents, mock account state as key/value.

NRY_DB overrides the file path (":memory:" for tests).
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

PATH = os.environ.get("NRY_DB", str(Path(__file__).parent / "nry.db"))
_lock = threading.Lock()
_db = sqlite3.connect(PATH, check_same_thread=False)
_db.execute("CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
_db.execute("CREATE TABLE IF NOT EXISTS mock_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
# Prorio's learning loop: protocol suggestions, approved protocol versions and decision counts
_db.execute("CREATE TABLE IF NOT EXISTS docs (kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, "
            "PRIMARY KEY (kind, id))")
_db.commit()


def _enc(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"not serialisable: {type(o)}")


def _run(sql, args=()):
    with _lock:
        _db.execute(sql, args)
        _db.commit()


def save_case(case):
    _run("INSERT OR REPLACE INTO cases VALUES (?, ?)", (case["case_id"], json.dumps(case, default=_enc)))


def save_state(key, value):
    _run("INSERT OR REPLACE INTO mock_state VALUES (?, ?)", (key, str(value)))


def load_cases():
    with _lock:
        return [json.loads(r[0]) for r in _db.execute("SELECT body FROM cases")]


def load_state():
    with _lock:
        return dict(_db.execute("SELECT key, value FROM mock_state").fetchall())


def save_doc(kind, doc_id, body):
    _run("INSERT OR REPLACE INTO docs VALUES (?, ?, ?)", (kind, doc_id, json.dumps(body, default=_enc)))


def delete_doc(kind, doc_id):
    _run("DELETE FROM docs WHERE kind = ? AND id = ?", (kind, doc_id))


def load_docs(kind):
    with _lock:
        rows = _db.execute("SELECT id, body FROM docs WHERE kind = ? ORDER BY id", (kind,)).fetchall()
    return {r[0]: json.loads(r[1]) for r in rows}


def clear():
    _run("DELETE FROM cases")
    _run("DELETE FROM mock_state")
    _run("DELETE FROM docs")
