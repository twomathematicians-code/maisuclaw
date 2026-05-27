"""
agent/router.py — intelligent model routing with multimodal detection
"""
from config import (
    MODEL_INSTANT, MODEL_FAST, MODEL_CODER, MODEL_GENERAL,
    MODEL_POWERFUL, MODEL_REASONING, MODEL_VISION, MODEL_VISION_LITE,
)

# Keyword sets for auto-detection
_CODE_KEYWORDS = {
    "code", "function", "class", "bug", "debug", "script", "program",
    "python", "javascript", "html", "css", "api", "git", "compile",
    "refactor", "algorithm", "sql", "database", "server", "deploy",
    "install", "package", "import", "module", "library", "framework",
    "test", "error", "syntax", "variable", "loop", "regex", "json",
    "typescript", "react", "node", "flask", "django", "fastapi",
}

_INSTANT_KEYWORDS = {
    "time", "date", "weather", "timer", "remind", "alarm",
    "calculate", "math", "convert", "hi", "hello", "thanks",
    "thank you", "bye", "yes", "no", "ok", "sure", "what is",
}

_REASONING_KEYWORDS = {
    "think", "reason", "step by step", "analyze", "explain why",
    "compare", "evaluate", "logic", "puzzle", "riddle", "proof",
    "derive", "complex", "difficult", "tricky", "research",
    "deep dive", "investigate", "thesis", "argument",
}

_RESEARCH_KEYWORDS = {
    "research", "deep dive", "find out", "look into", "investigate",
    "what are the latest", "recent developments", "literature review",
    "academic", "papers about", "studies on", "comprehensive analysis",
}

_WRITING_KEYWORDS = {
    "write", "essay", "article", "blog", "story", "poem", "book",
    "chapter", "novel", "creative", "letter", "email", "report",
    "summary", "paraphrase", "rewrite", "proofread", "edit",
}


def pick_model(message: str, mode: str = "",
               has_image: bool = False, has_pdf: bool = False) -> str:
    """Choose the best model. Supports multimodal detection."""
    mode_map = {
        "instant":   MODEL_INSTANT,
        "fast":      MODEL_FAST,
        "balanced":  MODEL_GENERAL,
        "coder":     MODEL_CODER,
        "powerful":  MODEL_POWERFUL,
        "reasoning": MODEL_REASONING,
        "vision":    MODEL_VISION,
    }
    if mode in mode_map:
        return mode_map[mode]

    # Vision model for image/PDF requests
    if has_image or has_pdf:
        return MODEL_VISION

    lower = message.lower()
    words = set(lower.split())

    if words & _INSTANT_KEYWORDS and len(message.split()) <= 5:
        return MODEL_INSTANT
    if words & _RESEARCH_KEYWORDS:
        return MODEL_POWERFUL
    if words & _REASONING_KEYWORDS:
        return MODEL_REASONING
    if words & _CODE_KEYWORDS:
        return MODEL_CODER
    if words & _WRITING_KEYWORDS:
        return MODEL_POWERFUL
    if words & _INSTANT_KEYWORDS:
        return MODEL_FAST
    return MODEL_GENERAL


def is_research_request(message: str) -> bool:
    """Check if the message requires deep research."""
    lower = message.lower()
    return any(kw in lower for kw in _RESEARCH_KEYWORDS)


def is_writing_request(message: str) -> bool:
    """Check if this is a creative/long-form writing request."""
    lower = message.lower()
    return any(kw in lower for kw in _WRITING_KEYWORDS)
