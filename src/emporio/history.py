"""Conversation persistence, so a customer can come back to the same chat.

Kept in its own SQLite file because the store database is opened read-only.
"""

import json
import sqlite3

from emporio.config import PROCESSED_DIR

HISTORY_PATH = PROCESSED_DIR / "conversations.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HISTORY_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, position)
        )
        """
    )
    return conn


def load(session_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT message FROM messages WHERE session_id = ? ORDER BY position", (session_id,)
        ).fetchall()
    return [json.loads(r[0]) for r in rows]


def save(session_id: str, messages: list[dict]) -> None:
    with _connect() as conn:
        start = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        conn.executemany(
            "INSERT INTO messages (session_id, position, message) VALUES (?, ?, ?)",
            [(session_id, start + i, json.dumps(m, ensure_ascii=False)) for i, m in enumerate(messages[start:])],
        )
