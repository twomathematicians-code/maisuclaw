"""
maisuclaw configuration  v0.3.0
===============================
Edit the values below to match your setup.
"""

from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "memory.db"

# ── ollama ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"

# ── model tiers ───────────────────────────────────────────────────
MODEL_INSTANT   = "qwen2.5:0.5b"
MODEL_FAST      = "phi3.5:latest"
MODEL_CODER     = "qwen2.5-coder:7b"
MODEL_GENERAL   = "gemma2:9b"
MODEL_POWERFUL  = "qwen2.5:14b"
MODEL_REASONING = "deepseek-r1:8b"
MODEL_VISION    = "llava:13b"            # image/screenshot analysis
MODEL_VISION_LITE = "minicpm-v:8b"      # lighter vision model
MODEL_EMBED     = "nomic-embed-text"
MODEL_STT       = "whisper:small"

MODEL_OPTIONS = {
    "auto":      "Auto (best pick)",
    "instant":   f"Instant — {MODEL_INSTANT}",
    "fast":      f"Fast — {MODEL_FAST}",
    "balanced":  f"Balanced — {MODEL_GENERAL}",
    "coder":     f"Coder — {MODEL_CODER}",
    "powerful":  f"Powerful — {MODEL_POWERFUL}",
    "reasoning": f"Reasoning — {MODEL_REASONING}",
    "vision":    f"Vision — {MODEL_VISION}",
}

# ── server ─────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── agent ──────────────────────────────────────────────────────────
MAX_TOOL_ROUNDS = 5
CHAT_HISTORY_LIMIT = 10

SYSTEM_PROMPT = (
    "You are maisuclaw, a powerful personal AI assistant running entirely on the user's laptop.\n"
    "You have access to tools — use them whenever needed.\n"
    "You can analyze images, read PDFs, browse the web, write code, do research, and more.\n"
    "Always answer in the same language the user writes in.\n"
    "Be thorough, accurate, and helpful. When you use a tool, explain what you did."
)

# ── remote access ─────────────────────────────────────────────────
# Cloudflare Tunnel / Tailscale — set to True when tunnel is active
REMOTE_ACCESS_ENABLED = False
PUBLIC_URL = ""  # e.g. "https://your-name.trycloudflare.com"

# ── GitHub cloud backup ───────────────────────────────────────────
GITHUB_BACKUP_ENABLED = False
GITHUB_TOKEN = ""
GITHUB_USERNAME = ""
GITHUB_REPO = "maisuclaw-chats"
GITHUB_BACKUP_INTERVAL = 3600

# ── research ───────────────────────────────────────────────────────
RESEARCH_MAX_SOURCES = 5
RESEARCH_DEPTH = 2  # how many levels of sub-questions

# ── allowed upload types ──────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
ALLOWED_DOC_TYPES   = {"pdf", "txt", "md", "csv", "json", "py", "js", "html", "css"}
MAX_UPLOAD_SIZE_MB = 50
