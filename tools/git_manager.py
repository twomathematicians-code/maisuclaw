"""
tools/git_manager.py — basic git operations
"""
import subprocess
from pathlib import Path


def _git(args: list[str], cwd: str = ".") -> str:
    """Run a git command and return the output."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )
    parts = []
    if result.stdout.strip():
        parts.append(result.stdout.strip())
    if result.stderr.strip():
        parts.append(result.stderr.strip())
    return "\n".join(parts) if parts else "(no output)"


def git_status(repo_path: str = ".") -> str:
    return _git(["status", "--short"], repo_path)


def git_log(repo_path: str = ".", n: int = 10) -> str:
    return _git(["log", f"--oneline", f"-{n}"], repo_path)


def git_commit(repo_path: str = ".", message: str = "update") -> str:
    return _git(["add", "-A"] + [repo_path]) + "\n" + _git(["commit", "-m", message], repo_path)


def git_diff(repo_path: str = ".") -> str:
    return _git(["diff"], repo_path)
