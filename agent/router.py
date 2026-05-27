"""
agent/router.py — decide which LLM to use based on the request
"""
from config import MODEL_CODER, MODEL_GENERAL, MODEL_FAST

# Keywords that hint at coding tasks
_CODE_KEYWORDS = {
    "code", "function", "class", "bug", "debug", "script", "program",
    "python", "javascript", "html", "css", "api", "git", "compile",
    "refactor", "algorithm", "sql", "database", "server", "deploy",
    "install", "package", "import", "module", "library", "framework",
    "test", "error", "syntax", "variable", "loop", "regex", "json",
}

# Keywords for fast / trivial tasks
_FAST_KEYWORDS = {
    "time", "date", "weather", "timer", "remind", "alarm",
    "calculate", "math", "convert", "translate word",
}


def pick_model(message: str, mode: str = "") -> str:
    """Choose the best model for a given user message + explicit mode."""
    if mode == "code":
        return MODEL_CODER
    if mode == "fast":
        return MODEL_FAST

    lower = message.lower()
    words = set(lower.split())

    if words & _FAST_KEYWORDS:
        return MODEL_FAST
    if words & _CODE_KEYWORDS:
        return MODEL_CODER
    return MODEL_GENERAL
