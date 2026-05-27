"""
services/github_backup.py — auto-backup chat history to a private GitHub repo
"""
import json
import time
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from config import (
    GITHUB_BACKUP_ENABLED,
    GITHUB_TOKEN,
    GITHUB_USERNAME,
    GITHUB_REPO,
    DB_PATH,
)


def _repo_url() -> str:
    return f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"


def _is_configured() -> bool:
    return all([
        GITHUB_BACKUP_ENABLED,
        GITHUB_TOKEN,
        GITHUB_USERNAME,
        GITHUB_REPO,
    ])


def _export_chats() -> str:
    """Export all conversations from SQLite to JSON text."""
    from services.memory import _conn
    with _conn() as conn:
        rows = conn.execute(
            "SELECT session_id, role, content, model, ts FROM conversations ORDER BY session_id, ts"
        ).fetchall()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1)


def _export_notes() -> str:
    """Export all notes to JSON text."""
    from services.memory import _conn
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY ts").fetchall()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1)


def run_backup() -> dict:
    """
    Export chats + notes and push to GitHub.
    Returns a status dict.
    """
    if not _is_configured():
        return {"ok": False, "error": "GitHub backup not configured. Edit config.py."}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # 1. Export data
        chats = _export_chats()
        notes = _export_notes()

        # 2. Write to temp files
        tmp = Path(tempfile.mkdtemp(prefix="maisuclaw_backup_"))
        (tmp / "chats.json").write_text(chats, encoding="utf-8")
        (tmp / "notes.json").write_text(notes, encoding="utf-8")
        (tmp / "last_backup.txt").write_text(
            f"Last backup: {timestamp}\n"
            f"Chats: {len(json.loads(chats))} messages\n"
            f"Notes: {len(json.loads(notes))} notes\n",
            encoding="utf-8",
        )

        # 3. Git push
        url = _repo_url()
        tmp_git = tmp / ".git"
        if tmp_git.exists():
            _run(["git", "init"], str(tmp))

        _run(["git", "add", "-A"], str(tmp))
        _run(["git", "commit", "-m", f"backup: {timestamp}"], str(tmp))
        result = _run(["git", "push", "-f", url, "HEAD:main"], str(tmp))

        return {
            "ok": True,
            "timestamp": timestamp,
            "message_count": len(json.loads(chats)),
            "note_count": len(json.loads(notes)),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def _run(args, cwd):
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=60)
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr}")
    return result.stdout
