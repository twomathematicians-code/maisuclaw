"""
╔══════════════════════════════════════════════════════════════╗
║  MAISUCLAW — Agent Swarm System v2.1                      ║
║  7 Free AI Providers · Auto-Failover · Multi-Agent         ║
║  Zero Cost · Ollama + Cloud · Files & Vision              ║
╚══════════════════════════════════════════════════════════════╝

Providers (all free):
  Groq        → api.groq.com            (fastest inference ~500 tok/s)
  OpenRouter  → openrouter.ai           (50+ free models)
  Cerebras    → api.cerebras.ai         (fast free inference)
  Together AI → api.together.xyz        (free $5 credits)
  SambaNova   → api.sambanova.ai        (free tier, fast)
  Cohere      → api.cohere.ai           (free tier, Command R+)
  Ollama      → localhost:11434          (local, ALL free, no key needed)

Auto-failover: if one provider rate-limits or is unreachable,
automatically switches to the next available provider.
"""

import os, json, time, sqlite3, uuid, asyncio, re, base64, tempfile
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

PORT = int(os.environ.get("PORT", "8000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = f"file:{os.path.join(BASE_DIR, 'maisuclaw.db')}?mode=rwc&_journal_mode=WAL"
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "maisuclaw_uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024

ALLOWED_IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml", "image/bmp"}
ALLOWED_TEXT = {"text/plain", "text/csv", "text/markdown", "text/html", "text/css",
                "application/json", "application/xml", "text/x-python", "text/javascript",
                "application/pdf"}
ALLOWED_ALL = ALLOWED_IMAGE | ALLOWED_TEXT | {
    "application/zip", "application/x-tar", "application/gzip",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream"
}

# ═══════════════════════════════════════════════════════════════
# PROVIDERS (all OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════

PROVIDERS = {
    "groq": {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "color": "#f55036",
        "speed": "~500 tok/s",
        "free_tier": "30 req/min, 14400 req/day",
        "signup": "https://console.groq.com/keys",
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "color": "#8b5cf6",
        "speed": "varies",
        "free_tier": "50+ free models, 20 req/min",
        "signup": "https://openrouter.ai/keys",
        "extra_headers": lambda k: {
            "HTTP-Referer": "https://maisuclaw.app",
            "X-Title": "MaisuClaw",
        },
    },
    "cerebras": {
        "name": "Cerebras",
        "url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "color": "#06b6d4",
        "speed": "~1200 tok/s",
        "free_tier": "Unlimited free inference",
        "signup": "https://cloud.cerebras.ai/",
    },
    "together": {
        "name": "Together AI",
        "url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "color": "#22c55e",
        "speed": "~150 tok/s",
        "free_tier": "$5 free credits",
        "signup": "https://api.together.xyz/settings/api-keys",
    },
    "sambanova": {
        "name": "SambaNova",
        "url": "https://api.sambanova.ai/v1",
        "key_env": "SAMBANOVA_API_KEY",
        "color": "#f59e0b",
        "speed": "~200 tok/s",
        "free_tier": "Free tier available",
        "signup": "https://cloud.sambanova.ai/",
    },
    "cohere": {
        "name": "Cohere",
        "url": "https://api.cohere.ai/v1",
        "key_env": "COHERE_API_KEY",
        "color": "#f472b6",
        "speed": "~100 tok/s",
        "free_tier": "Free tier (rate limited)",
        "signup": "https://dashboard.cohere.com/api-keys",
    },
    "ollama": {
        "name": "Ollama",
        "url": "http://localhost:11434/v1",  # OpenAI-compatible endpoint
        "key_env": "OLLAMA_BASE_URL",
        "color": "#a3e635",
        "speed": "local GPU",
        "free_tier": "100% free, no key, no limits",
        "signup": "https://ollama.com",
        "no_key": True,  # Special: uses URL instead of API key
    },
}

# Runtime provider keys (can be updated via settings endpoint)
# For Ollama, provider_keys["ollama"] stores the base URL instead of an API key
provider_keys = {}
for pid, p in PROVIDERS.items():
    provider_keys[pid] = os.environ.get(p["key_env"], "")
# Ollama default URL if not set
if not provider_keys["ollama"]:
    provider_keys["ollama"] = "http://localhost:11434"

# Provider cooldown tracking (for auto-failover)
provider_cooldown = {}  # {provider_id: cooldown_until_timestamp}
COOLDOWN_SECONDS = 60  # Wait 60s before retrying a rate-limited provider

# ═══════════════════════════════════════════════════════════════
# MODELS (organized by provider)
# ═══════════════════════════════════════════════════════════════

MODELS = [
    # ── Groq (fastest) ──
    {"id": "llama-3.3-70b-versatile",       "name": "Llama 3.3 70B",        "provider": "groq",       "tier": 3},
    {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 70B",      "provider": "groq",       "tier": 3},
    {"id": "qwen-qwq-32b",                  "name": "Qwen QWQ 32B",         "provider": "groq",       "tier": 3},
    {"id": "llama3-70b-8192",               "name": "Llama 3 70B",          "provider": "groq",       "tier": 3},
    {"id": "mixtral-8x7b-32768",            "name": "Mixtral 8x7B",         "provider": "groq",       "tier": 2},
    {"id": "gemma2-9b-it",                  "name": "Gemma 2 9B",           "provider": "groq",       "tier": 2},
    {"id": "llama-3.1-8b-instant",          "name": "Llama 3.1 8B",         "provider": "groq",       "tier": 1},
    # ── Cerebras (ultra fast) ──
    {"id": "llama-3.3-70b",                 "name": "Llama 3.3 70B (Cerebras)", "provider": "cerebras", "tier": 3},
    {"id": "llama3.1-8b",                   "name": "Llama 3.1 8B (Cerebras)",  "provider": "cerebras", "tier": 2},
    {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 70B (Cerebras)", "provider": "cerebras", "tier": 3},
    # ── OpenRouter (many free models) ──
    {"id": "google/gemini-2.0-flash-exp:free",       "name": "Gemini 2.0 Flash",     "provider": "openrouter", "tier": 3, "vision": True},
    {"id": "deepseek/deepseek-r1-0528:free",         "name": "DeepSeek R1 0528",     "provider": "openrouter", "tier": 3},
    {"id": "deepseek/deepseek-chat-v3-0324:free",     "name": "DeepSeek V3",          "provider": "openrouter", "tier": 3},
    {"id": "qwen/qwen3-235b-a22b:free",              "name": "Qwen3 235B",           "provider": "openrouter", "tier": 3},
    {"id": "mistralai/mistral-small-3.1-24b-instruct:free", "name": "Mistral Small 3.1", "provider": "openrouter", "tier": 2},
    {"id": "meta-llama/llama-4-maverick:free",       "name": "Llama 4 Maverick",     "provider": "openrouter", "tier": 3},
    {"id": "google/gemma-3-27b-it:free",             "name": "Gemma 3 27B",          "provider": "openrouter", "tier": 2},
    {"id": "microsoft/phi-4:free",                   "name": "Phi-4",                "provider": "openrouter", "tier": 2},
    # ── Together AI ──
    {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B (Together)", "provider": "together", "tier": 3},
    {"id": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "name": "DeepSeek R1 (Together)", "provider": "together", "tier": 3},
    {"id": "meta-llama/Llama-3-70b-chat-hf",         "name": "Llama 3 70B (Together)",   "provider": "together", "tier": 3},
    {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1",  "name": "Mixtral 8x7B (Together)",  "provider": "together", "tier": 2},
    {"id": "Qwen/Qwen2.5-72B-Instruct-Turbo",       "name": "Qwen 2.5 72B (Together)", "provider": "together", "tier": 3},
    # ── SambaNova ──
    {"id": "Meta-Llama-3.3-70B-Instruct",            "name": "Llama 3.3 70B (SNova)",   "provider": "sambanova", "tier": 3},
    {"id": "DeepSeek-R1-Distill-Llama-70B",          "name": "DeepSeek R1 70B (SNova)", "provider": "sambanova", "tier": 3},
    {"id": "Llama-3.1-8B-Instruct",                  "name": "Llama 3.1 8B (SNova)",   "provider": "sambanova", "tier": 1},
    # ── Cohere ──
    {"id": "command-r-plus",                          "name": "Command R+",             "provider": "cohere",    "tier": 3},
    {"id": "command-r",                               "name": "Command R",              "provider": "cohere",    "tier": 2},
    # ── Ollama (100% free, local, no key) ──
    {"id": "llama3.3:70b",                              "name": "Llama 3.3 70B (Ollama)",   "provider": "ollama",     "tier": 3},
    {"id": "qwen2.5:72b",                              "name": "Qwen 2.5 72B (Ollama)",    "provider": "ollama",     "tier": 3},
    {"id": "deepseek-r1:70b",                          "name": "DeepSeek R1 70B (Ollama)",  "provider": "ollama",     "tier": 3},
    {"id": "mistral:7b",                               "name": "Mistral 7B (Ollama)",      "provider": "ollama",     "tier": 2},
    {"id": "gemma2:27b",                               "name": "Gemma 2 27B (Ollama)",     "provider": "ollama",     "tier": 2},
    {"id": "llama3.1:8b",                              "name": "Llama 3.1 8B (Ollama)",    "provider": "ollama",     "tier": 1},
    {"id": "phi4:14b",                                 "name": "Phi-4 14B (Ollama)",       "provider": "ollama",     "tier": 2},
    {"id": "codellama:13b",                            "name": "CodeLlama 13B (Ollama)",   "provider": "ollama",     "tier": 2},
    {"id": "dolphin-mixtral:8x7b",                     "name": "Dolphin Mixtral (Ollama)",  "provider": "ollama",     "tier": 2},
    {"id": "starling-lm:7b",                           "name": "Starling LM 7B (Ollama)",   "provider": "ollama",     "tier": 1},
    {"id": "tinyllama:1.1b",                           "name": "TinyLlama 1.1B (Ollama)",  "provider": "ollama",     "tier": 0},
]

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Equivalent model mapping for auto-failover
# If model X from provider Y fails, try these alternatives
FALLBACK_MAP = {
    "groq": ["cerebras", "sambanova", "together", "openrouter"],
    "cerebras": ["groq", "sambanova", "together", "openrouter"],
    "openrouter": ["groq", "cerebras", "together", "sambanova"],
    "together": ["groq", "cerebras", "sambanova", "openrouter"],
    "sambanova": ["groq", "cerebras", "together", "openrouter"],
    "cohere": ["groq", "cerebras", "openrouter", "together"],
    "ollama": ["groq", "cerebras", "openrouter", "together", "sambanova"],
}

# ═══════════════════════════════════════════════════════════════
# AGENTS
# ═══════════════════════════════════════════════════════════════

AGENTS = {
    "chat": {"name": "Chat",       "icon": "&#x222B;", "color": "#7c5cfc",
             "system_prompt": "You are MaisuClaw, a powerful AI assistant. Answer with markdown. Be precise, thorough, and use mathematical notation when appropriate."},
    "researcher": {"name": "Research", "icon": "&#x2207;", "color": "#06b6d4",
                   "system_prompt": "You are a deep research agent. Provide comprehensive analysis with facts, data, multiple perspectives, and structured ## headers. Distinguish facts from opinions."},
    "coder": {"name": "Code",       "icon": "&#x03BB;", "color": "#22c55e",
              "system_prompt": "You are an expert coder. Write clean production code in ```language blocks. Include error handling. Explain approach briefly first."},
    "writer": {"name": "Write",      "icon": "&#x2206;", "color": "#f472b6",
               "system_prompt": "You are a skilled writer. Write naturally and engagingly. Avoid robotic phrasing. Use vivid language and well-structured paragraphs."},
    "analyst": {"name": "Analyze",   "icon": "&#x2211;", "color": "#f59e0b",
                "system_prompt": "You are a data analyst. Use structured frameworks, markdown tables, comparisons, and metrics. Be data-driven and objective."},
    "tutor": {"name": "Tutor",      "icon": "&#x2202;", "color": "#8b5cf6",
              "system_prompt": "You are a patient tutor. Explain step-by-step with analogies. Use **bold** for key terms. Ask guiding questions."},
    "swarm": {"name": "Swarm",      "icon": "&#x2295;", "color": "#ef4444",
              "system_prompt": ""},
}

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, title TEXT DEFAULT 'New Chat',
            agent TEXT DEFAULT 'chat', model_id TEXT DEFAULT '""" + DEFAULT_MODEL + """',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, agent TEXT DEFAULT 'chat',
            model_id TEXT, timestamp TEXT NOT NULL, duration_ms INTEGER DEFAULT 0,
            attachment_type TEXT, attachment_name TEXT, attachment_data TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
    """)
    conn.commit()
    conn.close()

def create_conversation(agent="chat", model_id=DEFAULT_MODEL):
    cid = str(uuid.uuid4())[:8]; now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO conversations (id,title,agent,model_id,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                 (cid, "New Chat", agent, model_id, now, now))
    conn.commit(); conn.close()
    return cid

def list_conversations(limit=50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_conversation(cid):
    conn = get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    conn.close(); return dict(row) if row else None

def delete_conversation(cid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit(); conn.close()

def add_message(cid, role, content, agent="chat", model_id=None, duration_ms=0,
                att_type=None, att_name=None, att_data=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id,role,content,agent,model_id,timestamp,duration_ms,attachment_type,attachment_name,attachment_data) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cid, role, content, agent, model_id, datetime.utcnow().isoformat(), duration_ms,
         att_type, att_name, att_data))
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), cid))
    conn.commit(); conn.close()

def get_messages(cid, limit=200):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC LIMIT ?",
                        (cid, limit)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def clear_messages(cid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════════════════════════
# PROVIDER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# Track dynamic Ollama models (auto-detected from local Ollama)
ollama_detected_models = []

async def detect_ollama_models():
    """Query local Ollama for installed models and add them dynamically."""
    global ollama_detected_models
    url = provider_keys.get("ollama", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                ollama_detected_models = [m["name"] for m in models]
                return True
    except Exception:
        ollama_detected_models = []
    return False

def get_provider_status():
    """Return status of all providers."""
    result = {}
    for pid, p in PROVIDERS.items():
        key = provider_keys.get(pid, "")
        on_cooldown = provider_cooldown.get(pid, 0) > time.time()
        is_no_key = p.get("no_key", False)
        # Ollama: ready if URL is set (default localhost counts as set)
        is_ready = (bool(key) and not on_cooldown) if not is_no_key else (not on_cooldown)
        result[pid] = {
            "name": p["name"],
            "ready": is_ready,
            "has_key": bool(key),
            "on_cooldown": on_cooldown,
            "color": p["color"],
            "speed": p["speed"],
            "free_tier": p["free_tier"],
            "no_key": is_no_key,
        }
    return result

def get_available_providers():
    """Return list of provider IDs that are ready (have key + not on cooldown)."""
    now = time.time()
    result = []
    for pid, p in PROVIDERS.items():
        key = provider_keys.get(pid, "")
        on_cooldown = provider_cooldown.get(pid, 0) > now
        if key and not on_cooldown:
            result.append(pid)
    return result

def mark_rate_limited(provider_id):
    """Mark a provider as rate-limited (on cooldown)."""
    provider_cooldown[provider_id] = time.time() + COOLDOWN_SECONDS

def find_fallback_model(model_id, failed_provider):
    """Find an equivalent model from a different provider."""
    m = next((m for m in MODELS if m["id"] == model_id), None)
    if not m:
        return None

    target_tier = m.get("tier", 2)
    is_vision = m.get("vision", False)

    # Try providers in fallback order
    for fallback_pid in FALLBACK_MAP.get(failed_provider, []):
        if fallback_pid == failed_provider:
            continue
        if not provider_keys.get(fallback_pid):
            continue
        if provider_cooldown.get(fallback_pid, 0) > time.time():
            continue

        # Find equivalent model from this provider
        for cm in MODELS:
            if cm["provider"] == fallback_pid and cm.get("tier", 0) >= target_tier - 1:
                if is_vision and not cm.get("vision"):
                    continue
                return cm["id"]

    return None


# ═══════════════════════════════════════════════════════════════
# CLOUD LLM (with auto-failover)
# ═══════════════════════════════════════════════════════════════

async def stream_llm(messages, model_id=DEFAULT_MODEL, temperature=0.7, max_tokens=8192):
    """Stream LLM responses with automatic failover on rate limits."""

    m = next((m for m in MODELS if m["id"] == model_id), None)
    if not m:
        raise Exception(f"Unknown model: {model_id}")

    provider_id = m["provider"]
    provider = PROVIDERS[provider_id]
    key = provider_keys.get(provider_id, "")
    is_no_key = provider.get("no_key", False)

    # For Ollama: no key needed, URL is always available
    if not key and not is_no_key:
        # Try to find the model from a different provider
        fallback = find_fallback_model(model_id, provider_id)
        if fallback:
            model_id = fallback
            m = next((m for m in MODELS if m["id"] == model_id), None)
            provider_id = m["provider"]
            provider = PROVIDERS[provider_id]
            key = provider_keys.get(provider_id, "")

    if not key and not is_no_key:
        raise Exception(
            f"No API key for {provider['name']}. Set {provider['key_env']} in environment variables. "
            f"Or add more provider keys to enable auto-failover."
        )

    # Try with primary provider, then failover
    tried = [provider_id]
    current_model = model_id
    current_provider_id = provider_id

    while True:
        p = PROVIDERS[current_provider_id]
        k = provider_keys.get(current_provider_id, "")
        is_ollama = p.get("no_key", False)
        if not k and not is_ollama:
            break

        headers = {"Content-Type": "application/json"}
        if not is_ollama:
            headers["Authorization"] = f"Bearer {k}"
        if "extra_headers" in p:
            headers.update(p["extra_headers"](k))

        # Build URL and payload per provider type
        if is_ollama:
            # Ollama: URL stored in k is the base (e.g. http://localhost:11434)
            base_url = k.rstrip("/")
            chat_url = f"{base_url}/v1/chat/completions"
        elif current_provider_id == "cohere":
            chat_url = f"{p['url']}/chat"
            payload = {
                "model": current_model,
                "message": messages[-1]["content"] if messages else "",
                "stream": True,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            for msg in messages:
                if msg.get("role") == "system":
                    payload["preamble"] = msg["content"]
                    break
        else:
            chat_url = f"{p['url']}/chat/completions"
            payload = {
                "model": current_model,
                "messages": messages,
                "stream": True,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream("POST", chat_url,
                                         json=payload, headers=headers) as resp:
                    if resp.status_code == 429:
                        # Rate limited — mark cooldown and try fallback
                        mark_rate_limited(current_provider_id)
                        print(f"  [Rate Limit] {p['name']} rate-limited. Trying fallback...")

                        fallback = find_fallback_model(current_model, current_provider_id)
                        if fallback and current_provider_id not in tried:
                            fm = next((m for m in MODELS if m["id"] == fallback), None)
                            current_model = fallback
                            current_provider_id = fm["provider"]
                            tried.append(current_provider_id)
                            print(f"  [Failover] Switching to {fm['name']} on {PROVIDERS[current_provider_id]['name']}")
                            yield f"data: {json.dumps({'event':'info','content':f\"Switching to {PROVIDERS[current_provider_id]['name']} ({current_model}) due to rate limit...\"})}\n\n"
                            continue
                        else:
                            raise Exception(f"All providers rate-limited. Please wait {COOLDOWN_SECONDS}s or add more API keys.")

                    if resp.status_code != 200:
                        body = await resp.aread()
                        error_msg = body.decode()[:400]

                        # Check for rate limit in error body
                        if resp.status_code in (429, 503, 529):
                            mark_rate_limited(current_provider_id)
                            fallback = find_fallback_model(current_model, current_provider_id)
                            if fallback and current_provider_id not in tried:
                                fm = next((m for m in MODELS if m["id"] == fallback), None)
                                current_model = fallback
                                current_provider_id = fm["provider"]
                                tried.append(current_provider_id)
                                print(f"  [Failover] Error {resp.status_code} from {p['name']}. Switching to {PROVIDERS[current_provider_id]['name']}")
                                yield f"data: {json.dumps({'event':'info','content':f\"Switching to {PROVIDERS[current_provider_id]['name']}...\"})}\n\n"
                                continue

                        raise Exception(f"API error {resp.status_code}: {error_msg}")

                    # Stream the response
                    if is_ollama or (current_provider_id != "cohere"):
                        # OpenAI-compatible streaming (Groq, OpenRouter, Cerebras, Together, SambaNova, Ollama)
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "): continue
                            data = line[6:]
                            if data.strip() == "[DONE]": return
                            try:
                                chunk = json.loads(data)
                                text = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if text: yield text
                            except json.JSONDecodeError:
                                continue
                    elif current_provider_id == "cohere":
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "): continue
                            data = line[6:]
                            try:
                                chunk = json.loads(data)
                                if chunk.get("event_type") == "text-generation":
                                    text = chunk.get("text", "")
                                    if text: yield text
                            except json.JSONDecodeError:
                                continue
                    return  # Success, exit loop

        except httpx.ConnectError:
            mark_rate_limited(current_provider_id)
            fallback = find_fallback_model(current_model, current_provider_id)
            if fallback and current_provider_id not in tried:
                fm = next((m for m in MODELS if m["id"] == fallback), None)
                current_model = fallback
                current_provider_id = fm["provider"]
                tried.append(current_provider_id)
                print(f"  [Failover] Connection error from {p['name']}. Switching to {PROVIDERS[current_provider_id]['name']}")
                yield f"data: {json.dumps({'event':'info','content':f\"Connection error. Switching to {PROVIDERS[current_provider_id]['name']}...\"})}\n\n"
                continue
            raise Exception(f"Connection failed to {p['name']} and all fallback providers.")

        break  # If we get here without returning, something unexpected happened


# ═══════════════════════════════════════════════════════════════
# SWARM
# ═══════════════════════════════════════════════════════════════

async def run_swarm(query, model_id, temperature):
    swarm_prompt = (
        'You are the Swarm Coordinator. Reply ONLY in JSON: {"agents":["coder","researcher"],"plan":"brief plan"}\n'
        "Available: " + ", ".join(k for k in AGENTS if k != "swarm") + "\n"
        f"Query: {query}"
    )
    coord = ""
    async for c in stream_llm([{"role": "user", "content": swarm_prompt}], model_id, 0.3, 1024):
        if isinstance(c, str):
            coord += c

    try:
        jm = re.search(r'\{[^}]+\}', coord, re.DOTALL)
        if jm:
            p = json.loads(jm.group())
            agents = [a for a in p.get("agents", ["chat"]) if a in AGENTS and a != "swarm"]
            plan = p.get("plan", "Processing...")
        else:
            agents, plan = ["chat"], "Processing"
    except (json.JSONDecodeError, KeyError):
        agents, plan = ["chat"], "Processing"
    if not agents: agents = ["chat"]

    yield {"type": "swarm_plan", "agents": agents, "plan": plan}

    for aid in agents:
        yield {"type": "agent_start", "agent": aid}
        a = AGENTS[aid]
        ctx = f"[Swarm] You are the {a['name']} agent. Focus on your specialty.\nQuery: {query}" if len(agents) > 1 else query
        full = ""
        async for chunk in stream_llm(
            [{"role": "system", "content": a["system_prompt"]}, {"role": "user", "content": ctx}],
            model_id, temperature):
            if isinstance(chunk, str):
                full += chunk
                yield {"type": "agent_chunk", "agent": aid, "content": chunk}
        yield {"type": "agent_done", "agent": aid, "full_response": full}


# ═══════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    active = [pid for pid in PROVIDERS if provider_keys.get(pid)]
    print(f"\n  MaisuClaw v2.0 LIVE | Port: {PORT}")
    print(f"  Active providers: {', '.join(active) if active else 'NONE — add API keys!'}")
    print(f"  {len(MODELS)} models available across {len(PROVIDERS)} providers")
    print(f"  Auto-failover: ON (cooldown={COOLDOWN_SECONDS}s)\n")
    yield

app = FastAPI(title="MaisuClaw", version="2.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


class ChatReq(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    agent: Optional[str] = "chat"
    model_id: Optional[str] = DEFAULT_MODEL
    attachment_type: Optional[str] = None
    attachment_name: Optional[str] = None
    attachment_data: Optional[str] = None

active_streams = {}


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(BASE_DIR, "static", "index.html"), "r") as f:
        return HTMLResponse(f.read())


@app.get("/api/status")
async def status():
    prov_status = get_provider_status()
    avail = []
    for m in MODELS:
        ps = prov_status.get(m["provider"], {})
        avail.append({
            **m,
            "available": ps.get("ready", False),
            "provider_name": ps.get("name", m["provider"]),
            "provider_color": ps.get("color", "#666"),
        })
    return {
        "version": "2.1.0",
        "providers": prov_status,
        "active_count": sum(1 for p in prov_status.values() if p["ready"]),
        "total_providers": len(PROVIDERS),
        "models": avail,
        "agents": {k: {"name": v["name"], "icon": v["icon"], "color": v["color"]} for k, v in AGENTS.items()},
    }


@app.get("/api/conversations")
async def api_list():
    return {"conversations": list_conversations()}

@app.get("/api/conversations/{cid}")
async def api_get(cid: str):
    c = get_conversation(cid)
    if not c: raise HTTPException(404, "Not found")
    return {"conversation": c, "messages": get_messages(cid)}

@app.post("/api/conversations")
async def api_create(req: dict):
    return {"conversation_id": create_conversation(req.get("agent", "chat"), req.get("model_id", DEFAULT_MODEL))}

@app.delete("/api/conversations/{cid}")
async def api_delete(cid: str):
    delete_conversation(cid); return {"ok": True}

@app.post("/api/conversations/{cid}/clear")
async def api_clear(cid: str):
    clear_messages(cid); return {"ok": True}


# ── File Upload ─────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE//1024//1024}MB)")
    ct = file.content_type or "application/octet-stream"
    b64 = base64.b64encode(content).decode()
    thumbnail = b64 if ct in ALLOWED_IMAGE else None
    return {
        "filename": file.filename,
        "content_type": ct,
        "size": len(content),
        "base64": b64,
        "thumbnail": thumbnail,
        "is_image": ct in ALLOWED_IMAGE,
        "is_text": ct in ALLOWED_TEXT,
    }


# ── Chat (with file attachment + auto-failover) ─────────
@app.post("/api/chat")
async def chat(req: ChatReq):
    agent_id = req.agent if req.agent in AGENTS else "chat"
    cid = req.conversation_id or create_conversation(agent_id, req.model_id)

    user_content = req.message
    att_type = req.attachment_type
    att_name = req.attachment_name
    att_data = req.attachment_data

    if att_type and att_name:
        if att_type.startswith("image/"):
            user_content = f"[Image: {att_name}]\n{req.message}" if req.message else f"[Image: {att_name}]"
        else:
            user_content = f"[File: {att_name}]\n{req.message}" if req.message else f"[File: {att_name}]"

    add_message(cid, "user", user_content, agent=agent_id,
                att_type=att_type, att_name=att_name, att_data=att_data)

    history = get_messages(cid, limit=80)
    api_msgs = []
    for msg in history:
        if msg["role"] in ("user", "assistant"):
            content = msg["content"]
            if msg.get("attachment_name") and msg.get("attachment_data"):
                content += f"\n[Attached: {msg['attachment_name']}]"
            api_msgs.append({"role": msg["role"], "content": content})

    async def generate():
        start = time.time()
        skey = f"{cid}_{start}"
        active_streams[skey] = asyncio.current_task()
        try:
            if agent_id == "swarm":
                async for event in run_swarm(req.message, req.model_id, 0.7):
                    et = event.get("type", "")
                    if et == "swarm_plan":
                        yield f"data: {json.dumps({'event':'swarm_plan','agents':event['agents'],'plan':event['plan']})}\n\n"
                    elif et == "agent_start":
                        ai = AGENTS.get(event["agent"], {})
                        yield f"data: {json.dumps({'event':'agent_start','agent':event['agent'],'name':ai.get('name',''),'icon':ai.get('icon',''),'color':ai.get('color','')})}\n\n"
                    elif et == "agent_chunk":
                        yield f"data: {json.dumps({'event':'agent_chunk','agent':event['agent'],'content':event['content']})}\n\n"
                    elif et == "agent_done":
                        add_message(cid, "assistant", event["full_response"], agent=event["agent"])
                        yield f"data: {json.dumps({'event':'agent_done','agent':event['agent']})}\n\n"
                yield f"data: {json.dumps({'event':'done','duration_ms':int((time.time()-start)*1000)})}\n\n"
            else:
                full = ""
                agent = AGENTS[agent_id]
                sys_msg = {"role": "system", "content": agent["system_prompt"]}
                all_msgs = [sys_msg] + api_msgs
                async for chunk in stream_llm(all_msgs, req.model_id):
                    if isinstance(chunk, str):
                        full += chunk
                        yield f"data: {json.dumps({'event':'chunk','content':chunk})}\n\n"
                ms = int((time.time() - start) * 1000)
                add_message(cid, "assistant", full, agent=agent_id, model_id=req.model_id, duration_ms=ms)
                yield f"data: {json.dumps({'event':'done','duration_ms':ms})}\n\n"
        except Exception as e:
            add_message(cid, "assistant", f"[Error] {e}", agent=agent_id)
            yield f"data: {json.dumps({'event':'error','error':str(e)})}\n\n"
        finally:
            active_streams.pop(skey, None)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/stop")
async def stop(req: dict):
    cid = req.get("conversation_id", "")
    n = 0; td = []
    for k, t in active_streams.items():
        if k.startswith(cid):
            if not t.done(): t.cancel(); n += 1
            td.append(k)
    for k in td: active_streams.pop(k, None)
    return {"stopped": n}


@app.post("/api/settings")
async def save_settings(req: Request):
    body = await req.json()
    for pid, p in PROVIDERS.items():
        key_field = p["key_env"].lower()  # e.g., "groq_api_key" or "ollama_base_url"
        if body.get(key_field):
            provider_keys[pid] = body[key_field]
            provider_cooldown.pop(pid, None)
    return {"ok": True, "active": [pid for pid in PROVIDERS if provider_keys.get(pid)]}


@app.get("/api/providers")
async def api_providers():
    """Get all available providers with their info for settings UI."""
    result = []
    for pid, p in PROVIDERS.items():
        result.append({
            "id": pid,
            "name": p["name"],
            "key_env": p["key_env"],
            "has_key": bool(provider_keys.get(pid)),
            "color": p["color"],
            "speed": p["speed"],
            "free_tier": p["free_tier"],
            "signup": p["signup"],
            "on_cooldown": provider_cooldown.get(pid, 0) > time.time(),
            "model_count": sum(1 for m in MODELS if m["provider"] == pid),
            "no_key": p.get("no_key", False),
        })
    return {"providers": result}


@app.get("/api/ollama/models")
async def ollama_models():
    """Auto-detect models installed on local Ollama."""
    await detect_ollama_models()
    return {
        "ollama_url": provider_keys.get("ollama", "http://localhost:11434"),
        "detected": ollama_detected_models,
        "total": len(ollama_detected_models),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
