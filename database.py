"""
maisuclaw v0.3.0 — Database & Memory
SQLite-based chat history, conversation management, and long-term memory.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

from config import DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT 'New Chat',
            model_id TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'ollama',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
            content TEXT NOT NULL,
            tool_name TEXT,
            tool_result TEXT,
            model_id TEXT,
            timestamp TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    # Memory / notes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # File uploads tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filetype TEXT,
            size_bytes INTEGER,
            conversation_id TEXT,
            uploaded_at TEXT NOT NULL
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_active ON conversations(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)")

    conn.commit()
    conn.close()


# ── Conversation Operations ─────────────────────────────

def create_conversation(model_id: str = "llama3", provider: str = "ollama", title: str = "New Chat") -> str:
    """Create a new conversation and return its ID."""
    import uuid
    conv_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (id, title, model_id, provider, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, title, model_id, provider, now, now)
    )
    conn.commit()
    conn.close()
    return conv_id


def get_conversation(conv_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_conversations(limit: int = 50) -> list[dict]:
    """List all conversations, most recent first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_conversation_title(conv_id: str, title: str):
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.utcnow().isoformat(), conv_id)
    )
    conn.commit()
    conn.close()


def delete_conversation(conv_id: str):
    """Delete a conversation and all its messages."""
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()


def touch_conversation(conv_id: str):
    """Update the conversation's updated_at timestamp."""
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), conv_id)
    )
    conn.commit()
    conn.close()


# ── Message Operations ─────────────────────────────────

def add_message(
    conversation_id: str,
    role: str,
    content: str,
    model_id: str = None,
    tool_name: str = None,
    tool_result: str = None,
    tokens_used: int = 0,
    duration_ms: int = 0
) -> int:
    """Add a message and return its ID."""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO messages
           (conversation_id, role, content, model_id, tool_name, tool_result, timestamp, tokens_used, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (conversation_id, role, content, model_id, tool_name, tool_result,
         datetime.utcnow().isoformat(), tokens_used, duration_ms)
    )
    msg_id = cursor.lastrowid
    touch_conversation(conversation_id)
    conn.commit()
    conn.close()
    return msg_id


def get_messages(conversation_id: str, limit: int = 200) -> list[dict]:
    """Get all messages for a conversation."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC LIMIT ?",
        (conversation_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_message_count(conversation_id: str) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
        (conversation_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def clear_conversation_messages(conv_id: str):
    """Remove all messages from a conversation (keep the conversation)."""
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    conn.commit()
    conn.close()


# ── Memory Operations ──────────────────────────────────

def save_memory(key: str, value: str):
    conn = get_db()
    conn.execute(
        """INSERT INTO memory (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_memory(key: str) -> Optional[str]:
    conn = get_db()
    row = conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def get_all_memory() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM memory").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ── Stats ──────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_db()
    conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    mem_count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    conn.close()
    return {
        "conversations": conv_count,
        "messages": msg_count,
        "memory_entries": mem_count,
    }


# Initialize DB on module load
init_db()
