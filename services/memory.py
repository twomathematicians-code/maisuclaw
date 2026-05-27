"""
services/memory.py — SQLite-backed conversation memory & notes
"""
import sqlite3, json, time
from pathlib import Path
from config import DB_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,   -- 'user' | 'assistant'
            content    TEXT NOT NULL,
            model      TEXT,
            ts         REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT NOT NULL,
            content  TEXT NOT NULL,
            tags     TEXT,              -- JSON list
            ts       REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath  TEXT NOT NULL,
            text      TEXT,
            embedding TEXT,             -- JSON list of floats
            ts        REAL NOT NULL
        );
        """)
    conn.close()


# ── conversations ─────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str, model: str = ""):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, model, ts) VALUES (?,?,?,?,?)",
            (session_id, role, content, model, time.time()),
        )


def get_history(session_id: str, limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE session_id=? ORDER BY ts DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def list_sessions() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT session_id, MIN(ts) as started, MAX(ts) as last_msg, COUNT(*) as msgs "
            "FROM conversations GROUP BY session_id ORDER BY last_msg DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── notes ─────────────────────────────────────────────────────────

def save_note(title: str, content: str, tags: list[str] | None = None):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO notes (title, content, tags, ts) VALUES (?,?,?,?)",
            (title, content, json.dumps(tags or []), time.time()),
        )


def search_notes(query: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY ts DESC",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def list_notes() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]


def delete_note(note_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))


# ── documents (for RAG) ──────────────────────────────────────────

def save_document(filepath: str, text: str, embedding: list[float] | None = None):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO documents (filepath, text, embedding, ts) VALUES (?,?,?,?)",
            (filepath, text, json.dumps(embedding) if embedding else None, time.time()),
        )


def list_documents() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, filepath, ts FROM documents ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]
