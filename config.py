"""
maisuclaw v0.3.0 — Configuration
Supports: Local Ollama + Cloud (Groq, OpenRouter)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

# ── Paths ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "maisuclaw.db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Server ─────────────────────────────────────────────
HOST = os.getenv("MAISUCLAW_HOST", "0.0.0.0")
PORT = int(os.getenv("MAISUCLAW_PORT", "8000"))

# ── Ollama (Local) ────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ── Groq Cloud (Free Tier) ────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── OpenRouter Cloud (Free Models Available) ──────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER", "https://maisuclaw.onrender.com")

# ── GitHub Backup ─────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BACKUP_BRANCH = "chat-backup"

# ── Whisper (Voice) ──────────────────────────────────
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


@dataclass
class ModelConfig:
    """Single model entry."""
    id: str
    name: str
    provider: str            # "ollama" | "groq" | "openrouter"
    tier: int = 1            # 1=lightweight, 2=standard, 3=powerful
    supports_vision: bool = False
    supports_tools: bool = True
    max_tokens: int = 4096
    description: str = ""
    is_free: bool = True


@dataclass
class AppConfig:
    """Full application configuration."""
    models: list[ModelConfig] = field(default_factory=list)
    default_model: str = "llama3"
    system_prompt: str = (
        "You are MaisuClaw, a powerful local AI assistant. "
        "You help with coding, research, writing, analysis, and general questions. "
        "Be thorough, accurate, and helpful. Use tools when available."
    )

    def __post_init__(self):
        self.models = self._build_models()

    def _build_models(self) -> list[ModelConfig]:
        models = [
            # ── Ollama Local Models ──
            ModelConfig(
                id="llama3", name="Llama 3 (8B)", provider="ollama", tier=1,
                max_tokens=8192,
                description="Fast & capable general-purpose model"
            ),
            ModelConfig(
                id="llama3:70b", name="Llama 3 (70B)", provider="ollama", tier=3,
                max_tokens=8192,
                description="Most powerful Llama 3 variant"
            ),
            ModelConfig(
                id="mistral", name="Mistral (7B)", provider="ollama", tier=1,
                max_tokens=4096,
                description="Efficient & fast reasoning"
            ),
            ModelConfig(
                id="codellama", name="Code Llama (7B)", provider="ollama", tier=1,
                max_tokens=16384,
                description="Code generation & understanding"
            ),
            ModelConfig(
                id="deepseek-coder:6.7b", name="DeepSeek Coder (6.7B)", provider="ollama", tier=1,
                max_tokens=16384,
                description="Excellent coding model"
            ),
            ModelConfig(
                id="gemma2:2b", name="Gemma 2 (2B)", provider="ollama", tier=1,
                max_tokens=8192,
                description="Google's lightweight model"
            ),
            ModelConfig(
                id="phi3:mini", name="Phi-3 Mini (3.8B)", provider="ollama", tier=1,
                max_tokens=8192,
                description="Microsoft's compact but capable model"
            ),
            ModelConfig(
                id="qwen2.5:7b", name="Qwen 2.5 (7B)", provider="ollama", tier=1,
                max_tokens=8192,
                description="Alibaba's multilingual model"
            ),
            ModelConfig(
                id="nomic-embed-text", name="Nomic Embed", provider="ollama", tier=1,
                supports_tools=False, max_tokens=8192,
                description="Embedding model for RAG"
            ),
            ModelConfig(
                id="llava", name="LLaVA (Vision)", provider="ollama", tier=2,
                supports_vision=True, max_tokens=4096,
                description="Vision model for image analysis"
            ),
            ModelConfig(
                id="llava:13b", name="LLaVA 13B (Vision)", provider="ollama", tier=3,
                supports_vision=True, max_tokens=4096,
                description="More powerful vision model"
            ),

            # ── Groq Cloud Models (Free Tier) ──
            ModelConfig(
                id="llama-3.3-70b-versatile", name="Llama 3.3 70B (Groq)", provider="groq", tier=3,
                supports_tools=True, supports_vision=False, max_tokens=32768,
                description="Lightning-fast cloud inference via Groq"
            ),
            ModelConfig(
                id="llama-3.1-8b-instant", name="Llama 3.1 8B (Groq)", provider="groq", tier=1,
                supports_tools=True, max_tokens=32768,
                description="Instant cloud inference via Groq"
            ),
            ModelConfig(
                id="mixtral-8x7b-32768", name="Mixtral 8x7B (Groq)", provider="groq", tier=2,
                supports_tools=True, max_tokens=32768,
                description="MoE architecture, fast cloud inference"
            ),
            ModelConfig(
                id="gemma2-9b-it", name="Gemma 2 9B (Groq)", provider="groq", tier=2,
                supports_tools=True, max_tokens=32768,
                description="Google Gemma 2 via Groq"
            ),
            ModelConfig(
                id="meta-llama/llama-4-scout-17b-16e-instruct", name="Llama 4 Scout (Groq)", provider="groq", tier=3,
                supports_tools=True, max_tokens=32768,
                description="Latest Llama 4 via Groq"
            ),

            # ── OpenRouter Cloud Models (Free) ──
            ModelConfig(
                id="meta-llama/llama-3.1-8b-instruct:free", name="Llama 3.1 8B (OpenRouter Free)", provider="openrouter", tier=1,
                supports_tools=True, max_tokens=8192,
                description="Free Llama 3.1 via OpenRouter"
            ),
            ModelConfig(
                id="google/gemma-2-9b-it:free", name="Gemma 2 9B (OpenRouter Free)", provider="openrouter", tier=2,
                supports_tools=True, max_tokens=8192,
                description="Free Gemma 2 via OpenRouter"
            ),
            ModelConfig(
                id="qwen/qwen-2.5-7b-instruct:free", name="Qwen 2.5 7B (OpenRouter Free)", provider="openrouter", tier=1,
                supports_tools=True, max_tokens=8192,
                description="Free Qwen 2.5 via OpenRouter"
            ),
        ]

        # If no cloud API keys, still include them (UI shows them but they need key setup)
        return models

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def get_models_by_provider(self, provider: str) -> list[ModelConfig]:
        return [m for m in self.models if m.provider == provider]


# Global config instance
config = AppConfig()
