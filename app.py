"""
MaisuClaw — AI Chat Assistant (Cloud-Hosted)
=============================================
Deploys to Render.com free tier — auto-deploys from GitHub.
Uses Groq (free) for blazing-fast AI inference.
"""

import os
import json
import time
import sqlite3
import uuid
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx

# ── Config ───────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
PORT = int(os.environ.get("PORT", "8000"))

# SQLite — Render.com free tier has read-only filesystem except /tmp
DB_PATH = os.environ.get("DATABASE_URL", f"file:{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maisuclaw.db')}?mode=rwc&_journal_mode=WAL")

# ── Models ───────────────────────────────────────────────
MODELS = [
    {"id": "llama-3.3-70b-versatile",  "name": "Llama 3.3 70B",   "provider": "groq",       "tier": 3, "desc": "Most powerful, fast"},
    {"id": "llama-3.1-8b-instant",     "name": "Llama 3.1 8B",    "provider": "groq",       "tier": 1, "desc": "Fastest responses"},
    {"id": "llama3-70b-8192",          "name": "Llama 3 70B",     "provider": "groq",       "tier": 3, "desc": "Powerful general model"},
    {"id": "mixtral-8x7b-32768",       "name": "Mixtral 8x7B",    "provider": "groq",       "tier": 2, "desc": "MoE architecture"},
    {"id": "gemma2-9b-it",             "name": "Gemma 2 9B",      "provider": "groq",       "tier": 2, "desc": "Google model"},
    {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 70B", "provider": "groq", "tier": 3, "desc": "Reasoning model"},
    {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B (OR Free)", "provider": "openrouter", "tier": 1, "desc": "Free via OpenRouter"},
    {"id": "google/gemma-2-9b-it:free",          "name": "Gemma 2 9B (OR Free)",  "provider": "openrouter", "tier": 2, "desc": "Free via OpenRouter"},
]

SYSTEM_PROMPT = (
    "You are MaisuClaw, a helpful AI assistant. "
    "Be thorough, accurate, and friendly. "
    "Use markdown formatting for code blocks and structured responses."
)


# ── Database ─────────────────────────────────────────────
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
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT 'New Chat',
            model_id TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model_id TEXT,
            timestamp TEXT NOT NULL,
            duration_ms INTEGER DEFAULT 0,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
    """)
    conn.commit()
    conn.close()


# ── DB Helpers ───────────────────────────────────────────
def create_conversation(model_id: str = "llama-3.3-70b-versatile") -> str:
    cid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO conversations (id,title,model_id,created_at,updated_at) VALUES (?,?,?,?,?)",
                 (cid, "New Chat", model_id, now, now))
    conn.commit()
    conn.close()
    return cid


def list_conversations(limit=50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conversation(cid):
    conn = get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_conversation(cid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def update_title(cid, title):
    conn = get_db()
    conn.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                 (title, datetime.utcnow().isoformat(), cid))
    conn.commit()
    conn.close()


def add_message(cid, role, content, model_id=None, duration_ms=0):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id,role,content,model_id,timestamp,duration_ms) VALUES (?,?,?,?,?,?)",
        (cid, role, content, model_id, datetime.utcnow().isoformat(), duration_ms))
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), cid))
    conn.commit()
    conn.close()


def get_messages(cid, limit=200):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC LIMIT ?",
                        (cid, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_messages(cid):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    conn.commit()
    conn.close()


# ── Cloud AI Client ─────────────────────────────────────
async def stream_groq(messages, model="llama-3.3-70b-versatile", temperature=0.7, max_tokens=8192):
    """Stream from Groq API."""
    if not GROQ_API_KEY:
        raise Exception("Groq API key not set. Add GROQ_API_KEY environment variable in Render.com dashboard.")

    payload = {
        "model": model, "messages": messages,
        "stream": True, "temperature": temperature, "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{GROQ_URL}/chat/completions",
                                 json=payload,
                                 headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                                          "Content-Type": "application/json"}) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"Groq error {resp.status_code}: {body.decode()[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def stream_openrouter(messages, model, temperature=0.7, max_tokens=8192):
    """Stream from OpenRouter API."""
    if not OPENROUTER_API_KEY:
        raise Exception("OpenRouter API key not set. Add OPENROUTER_API_KEY in Render dashboard.")

    payload = {
        "model": model, "messages": messages,
        "stream": True, "temperature": temperature, "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{OPENROUTER_URL}/chat/completions",
                                 json=payload,
                                 headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                                          "Content-Type": "application/json",
                                          "HTTP-Referer": "https://maisuclaw.app",
                                          "X-Title": "MaisuClaw"}) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"OpenRouter error {resp.status_code}: {body.decode()[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def stream_chat(messages, model_id="llama-3.3-70b-versatile", temperature=0.7):
    """Route to correct provider and stream."""
    model_cfg = next((m for m in MODELS if m["id"] == model_id), None)
    if not model_cfg:
        raise Exception(f"Unknown model: {model_id}")

    if model_cfg["provider"] == "groq":
        async for chunk in stream_groq(messages, model_id, temperature):
            yield chunk
    elif model_cfg["provider"] == "openrouter":
        async for chunk in stream_openrouter(messages, model_id, temperature):
            yield chunk
    else:
        raise Exception(f"Unknown provider: {model_cfg['provider']}")


# ── App ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("=" * 50)
    print("  MaisuClaw is LIVE")
    print(f"  Groq key: {'SET' if GROQ_API_KEY else 'NOT SET'}")
    print(f"  OpenRouter key: {'SET' if OPENROUTER_API_KEY else 'NOT SET'}")
    print("=" * 50)
    yield

app = FastAPI(title="MaisuClaw", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ── Request Models ───────────────────────────────────────
class ChatReq(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = "llama-3.3-70b-versatile"

class StopReq(BaseModel):
    conversation_id: str

class TitleReq(BaseModel):
    conversation_id: str
    title: str


# ── Active Streams (for stop) ───────────────────────────
active_streams = {}


# ── Routes ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r") as f:
        return HTMLResponse(f.read())


@app.get("/api/status")
async def status():
    available_models = []
    for m in MODELS:
        avail = False
        if m["provider"] == "groq" and GROQ_API_KEY:
            avail = True
        elif m["provider"] == "openrouter" and OPENROUTER_API_KEY:
            avail = True
        available_models.append({**m, "available": avail})
    return {
        "version": "0.3.0",
        "groq_ready": bool(GROQ_API_KEY),
        "openrouter_ready": bool(OPENROUTER_API_KEY),
        "models": available_models,
    }


@app.get("/api/conversations")
async def api_list_convos():
    return {"conversations": list_conversations()}


@app.get("/api/conversations/{cid}")
async def api_get_convo(cid: str):
    conv = get_conversation(cid)
    if not conv:
        raise HTTPException(404, "Not found")
    return {"conversation": conv, "messages": get_messages(cid)}


@app.post("/api/conversations")
async def api_create_convo():
    cid = create_conversation()
    return {"conversation_id": cid}


@app.put("/api/conversations/title")
async def api_update_title(req: TitleReq):
    update_title(req.conversation_id, req.title)
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
async def api_delete_convo(cid: str):
    delete_conversation(cid)
    return {"ok": True}


@app.post("/api/conversations/{cid}/clear")
async def api_clear_convo(cid: str):
    clear_messages(cid)
    return {"ok": True}


@app.post("/api/chat")
async def chat(req: ChatReq):
    cid = req.conversation_id or create_conversation(req.model_id)
    add_message(cid, "user", req.message)

    # Build message history
    history = get_messages(cid, limit=80)
    api_msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        api_msgs.append({"role": msg["role"], "content": msg["content"]})

    async def generate():
        start = time.time()
        full = ""
        stream_key = f"{cid}_{start}"
        task = asyncio.current_task()
        active_streams[stream_key] = task

        try:
            async for chunk in stream_chat(api_msgs, req.model_id):
                full += chunk
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

            ms = int((time.time() - start) * 1000)
            add_message(cid, "assistant", full, model_id=req.model_id, duration_ms=ms)
            yield f"data: {json.dumps({'done': True, 'duration_ms': ms})}\n\n"

        except Exception as e:
            err = str(e)
            add_message(cid, "assistant", f"[Error] {err}", model_id=req.model_id)
            yield f"data: {json.dumps({'error': err, 'done': True})}\n\n"

        finally:
            active_streams.pop(stream_key, None)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/stop")
async def stop(req: StopReq):
    stopped = 0
    to_del = []
    for key, task in active_streams.items():
        if key.startswith(req.conversation_id):
            if not task.done():
                task.cancel()
                stopped += 1
            to_del.append(key)
    for k in to_del:
        active_streams.pop(k, None)
    return {"stopped": stopped}


@app.post("/api/settings")
async def save_settings(req: Request):
    """Save API keys. On Render.com, this updates environment variables via their API.
    For local use, this is informational — set keys in .env or Render dashboard instead."""
    body = await req.json()
    # On Render.com, env vars are set in the dashboard, not via API from the app itself.
    # This endpoint just confirms the keys were received and tells the user to set them in Render.
    groq = body.get("groq_api_key", "")
    orkey = body.get("openrouter_api_key", "")

    # For local development, we can update a .env file
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path) as f:
                lines = f.readlines()

        env_map = {}
        for line in lines:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_map[k.strip()] = v.strip()

        if groq:
            env_map["GROQ_API_KEY"] = groq
        if orkey:
            env_map["OPENROUTER_API_KEY"] = orkey

        with open(env_path, "w") as f:
            for k, v in env_map.items():
                f.write(f"{k}={v}\n")
    except Exception:
        pass

    # Update runtime globals
    global GROQ_API_KEY, OPENROUTER_API_KEY
    if groq:
        GROQ_API_KEY = groq
    if orkey:
        OPENROUTER_API_KEY = orkey

    return {"ok": True, "message": "Settings saved. If on Render.com, also add keys in Environment Variables."}


# ── Run ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
