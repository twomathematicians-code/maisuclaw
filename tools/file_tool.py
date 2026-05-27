"""
maisuclaw v0.3.0 — Tool: File Operations
Read, write, list, and search files on the local system.
"""

import os
from typing import Optional


def execute(action: str, params: dict) -> str:
    """Execute a file tool action."""
    actions = {
        "read": _read_file,
        "write": _write_file,
        "list": _list_dir,
        "search": _search_files,
        "info": _file_info,
    }
    handler = actions.get(action)
    if not handler:
        return f"Unknown file action: {action}. Available: {list(actions.keys())}"
    return handler(params)


def _read_file(params: dict) -> str:
    path = params.get("path", "")
    if not path:
        return "Error: 'path' parameter required"
    if not os.path.exists(path):
        return f"Error: File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Truncate very large files
        if len(content) > 50000:
            content = content[:50000] + "\n\n... [truncated, file too large]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(params: dict) -> str:
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return "Error: 'path' parameter required"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def _list_dir(params: dict) -> str:
    path = params.get("path", ".")
    if not os.path.exists(path):
        return f"Error: Directory not found: {path}"
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries)[:100]:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                result.append(f"  [DIR]  {entry}/")
            else:
                size = os.path.getsize(full)
                result.append(f"  [FILE] {entry}  ({size:,} bytes)")
        return f"Contents of {path}:\n" + "\n".join(result)
    except Exception as e:
        return f"Error listing directory: {e}"


def _search_files(params: dict) -> str:
    path = params.get("path", ".")
    pattern = params.get("pattern", "")
    if not pattern:
        return "Error: 'pattern' parameter required"
    try:
        matches = []
        for root, dirs, files in os.walk(path):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if pattern.lower() in f.lower():
                    full = os.path.join(root, f)
                    size = os.path.getsize(full)
                    matches.append(f"  {full}  ({size:,} bytes)")
            if len(matches) >= 50:
                matches.append("  ... [truncated at 50 results]")
                break
        if not matches:
            return f"No files matching '{pattern}' found in {path}"
        return f"Found {len(matches)} file(s):\n" + "\n".join(matches)
    except Exception as e:
        return f"Error searching: {e}"


def _file_info(params: dict) -> str:
    path = params.get("path", "")
    if not path or not os.path.exists(path):
        return f"Error: File not found: {path}"
    try:
        stat = os.stat(path)
        info = [
            f"Path: {path}",
            f"Size: {stat.st_size:,} bytes",
            f"Type: {'Directory' if os.path.isdir(path) else 'File'}",
            f"Modified: {os.path.getmtime(path)}",
        ]
        return "\n".join(info)
    except Exception as e:
        return f"Error: {e}"
