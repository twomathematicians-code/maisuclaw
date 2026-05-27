"""
tools/file_manager.py — file system operations
"""
import os
from pathlib import Path


def list_files(path: str) -> str:
    """List files and directories at a given path."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: path does not exist: {p}"
    if not p.is_dir():
        return f"Error: not a directory: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = []
    for e in entries:
        prefix = "[DIR] " if e.is_dir() else "[FILE]"
        size = ""
        if e.is_file():
            try:
                size = f" ({e.stat().st_size} bytes)"
            except OSError:
                pass
        lines.append(f"  {prefix} {e.name}{size}")
    return "\n".join(lines) if lines else "(empty directory)"


def read_file(path: str) -> str:
    """Read a text file and return its contents."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: file does not exist: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Error: file is not UTF-8 text (binary?)."


def write_file(path: str, content: str) -> str:
    """Write content to a file (creates parent dirs automatically)."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} characters to {p}"
    except Exception as e:
        return f"Error writing file: {e}"
