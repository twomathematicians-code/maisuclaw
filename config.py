"""
maisuclaw configuration
-----------------------
Edit the values below to match your setup.
Nothing else in the codebase should need touching.
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

# Models — change to whatever you have pulled locally
MODEL_CODER = "qwen2.5-coder:7b"
MODEL_GENERAL = "gemma2:9b"
MODEL_FAST = "phi3.5:latest"
MODEL_EMBED = "nomic-embed-text"
MODEL_STT = "whisper:small"

# ── server ─────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── agent ──────────────────────────────────────────────────────────
# Maximum tool-call rounds before the agent gives up
MAX_TOOL_ROUNDS = 5
SYSTEM_PROMPT = (
    "You are maisuclaw, a personal AI assistant that lives entirely on the user's laptop.\n"
    "You have access to tools — use them whenever the user's request requires action beyond pure conversation.\n"
    "Always answer in the same language the user writes in.\n"
    "Be concise but thorough. When you use a tool, explain what you did and share the result."
)
