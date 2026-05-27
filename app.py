"""
╔══════════════════════════════════════════════════════════════╗
║  MAISUCLAW — Open Source Agent Swarm System                ║
║  One-click deploy · Free cloud AI · Multi-agent reasoning   ║
╚══════════════════════════════════════════════════════════════╝

Deploy: Push to GitHub → Connect to Render.com → Add GROQ_API_KEY → Live

Architecture:
  User → App (FastAPI) → Swarm Coordinator → Agent Pool → Cloud LLM
                                                    ├─ Research Agent
                                                    ├─ Code Agent
                                                    ├─ Writer Agent
                                                    ├─ Analyst Agent
                                                    ├─ Search Agent
                                                    └─ Chat Agent (default)
"""

import os, json, time, sqlite3, uuid, asyncio, re
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import httpx
from config import OPENROUTER_REFERER

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
PORT = int(os.environ.get("PORT", "8000"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = f"file:{os.path.join(BASE_DIR, 'maisuclaw.db')}?mode=rwc&_journal_mode=WAL"

# ═══════════════════════════════════════════════════════════════
# MODELS (all free-tier)
# ═══════════════════════════════════════════════════════════════

MODELS = [
    {"id": "llama-3.3-70b-versatile",       "name": "Llama 3.3 70B",     "provider": "groq",       "tier": 3},
    {"id": "llama-3.1-8b-instant",          "name": "Llama 3.1 8B",      "provider": "groq",       "tier": 1},
    {"id": "llama3-70b-8192",               "name": "Llama 3 70B",       "provider": "groq",       "tier": 3},
    {"id": "mixtral-8x7b-32768",            "name": "Mixtral 8x7B",      "provider": "groq",       "tier": 2},
    {"id": "gemma2-9b-it",                  "name": "Gemma 2 9B",        "provider": "groq",       "tier": 2},
    {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 70B",   "provider": "groq",       "tier": 3},
    {"id": "qwen-qwq-32b",                  "name": "Qwen QWQ 32B",       "provider": "groq",       "tier": 3},
    {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B (OR)", "provider": "openrouter", "tier": 1},
    {"id": "google/gemma-2-9b-it:free",              "name": "Gemma 2 9B (OR)",  "provider": "openrouter", "tier": 2},
]

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# ═══════════════════════════════════════════════════════════════
# AGENT SWARM DEFINITIONS
# ═══════════════════════════════════════════════════════════════

AGENTS = {
    "chat": {
        "name": "Chat",
        "icon": "💬",
        "color": "#7c5cfc",
        "system_prompt": (
            "You are MaisuClaw, a friendly and powerful AI assistant. "
            "Answer questions helpfully using markdown formatting. "
            "Be concise but thorough. Use code blocks for code."
        ),
    },
    "researcher": {
        "name": "Researcher",
        "icon": "🔍",
        "color": "#06b6d4",
        "system_prompt": (
            "You are a deep research agent. Your job is to:\n"
            "1. Break down complex topics systematically\n"
            "2. Provide comprehensive, well-structured analysis\n"
            "3. Include facts, data points, and multiple perspectives\n"
            "4. Cite sources and distinguish facts from opinions\n"
            "5. Use clear sections with headers\n\n"
            "Format: Use ## headers, bullet points, and numbered lists. "
            "Be thorough but organized."
        ),
    },
    "coder": {
        "name": "Coder",
        "icon": "⚡",
        "color": "#22c55e",
        "system_prompt": (
            "You are an expert coding agent. Your job is to:\n"
            "1. Write clean, production-ready code\n"
            "2. Always specify the language in code blocks\n"
            "3. Explain your approach briefly before writing code\n"
            "4. Include error handling and best practices\n"
            "5. Suggest optimizations when relevant\n\n"
            "Always wrap code in ```language ... ``` blocks. "
            "Add brief comments for complex logic."
        ),
    },
    "writer": {
        "name": "Writer",
        "icon": "✍️",
        "color": "#f472b6",
        "system_prompt": (
            "You are a skilled writing agent. Your job is to:\n"
            "1. Write in a natural, engaging, human-like style\n"
            "2. Match the requested tone (formal, casual, creative, etc.)\n"
            "3. Use vivid language and varied sentence structures\n"
            "4. Organize content with clear paragraphs and sections\n"
            "5. Avoid robotic phrasing, cliches, and filler words\n\n"
            "Write compelling content that feels authentic and well-crafted."
        ),
    },
    "analyst": {
        "name": "Analyst",
        "icon": "📊",
        "color": "#f59e0b",
        "system_prompt": (
            "You are a data and business analyst agent. Your job is to:\n"
            "1. Analyze data, trends, and patterns\n"
            "2. Provide actionable insights and recommendations\n"
            "3. Use structured frameworks (SWOT, pros/cons, etc.)\n"
            "4. Include metrics, comparisons, and visual descriptions\n"
            "5. Present findings in clear, executive-ready format\n\n"
            "Use tables (markdown), bullet points, and numbered rankings. "
            "Be data-driven and objective."
        ),
    },
    "tutor": {
        "name": "Tutor",
        "icon": "🎓",
        "color": "#8b5cf6",
        "system_prompt": (
            "You are a patient, expert tutor. Your job is to:\n"
            "1. Explain concepts step-by-step from basics\n"
            "2. Use analogies and real-world examples\n"
            "3. Ask guiding questions to check understanding\n"
            "4. Break complex topics into digestible parts\n"
            "5. Encourage and motivate the learner\n\n"
            "Use simple language first, then add complexity. "
            "Use formatting like **bold** for key terms."
        ),
    },
    "swarm": {
        "name": "Swarm (All Agents)",
        "icon": "🐝",
        "color": "#ef4444",
        "system_prompt": "",  # Dynamically built
    },
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
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT 'New Chat',
            agent TEXT DEFAULT 'chat',
            model_id TEXT DEFAULT '""" + DEFAULT_MODEL + """',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            agent TEXT DEFAULT 'chat',
            model_id TEXT,
            timestamp TEXT NOT NULL,
            duration_ms INTEGER DEFAULT 0,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
    """)
    conn.commit()
    conn.close()

def create_conversation(agent="chat", model_id=DEFAULT_MODEL):
    cid = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO conversations (id,title,agent,model_id,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                 (cid, f"New Chat", agent, model_id, now, now))
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

def add_message(cid, role, content, agent="chat", model_id=None, duration_ms=0):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id,role,content,agent,model_id,timestamp,duration_ms) VALUES (?,?,?,?,?,?,?)",
        (cid, role, content, agent, model_id, datetime.utcnow().isoformat(), duration_ms))
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


# ═══════════════════════════════════════════════════════════════
# CLOUD LLM STREAMING
# ═══════════════════════════════════════════════════════════════

async def stream_llm(messages, model_id=DEFAULT_MODEL, temperature=0.7, max_tokens=8192):
    """Stream from Groq or OpenRouter."""
    m = next((m for m in MODELS if m["id"] == model_id), None)
    if not m:
        raise Exception(f"Unknown model: {model_id}")

    provider = m["provider"]
    if provider == "groq" and not GROQ_API_KEY:
        raise Exception("Groq API key not set. Add GROQ_API_KEY in Render dashboard.")
    if provider == "openrouter" and not OPENROUTER_API_KEY:
        raise Exception("OpenRouter key not set. Add OPENROUTER_API_KEY in Render dashboard.")

    url = GROQ_URL if provider == "groq" else OPENROUTER_URL
    key = GROQ_API_KEY if provider == "groq" else OPENROUTER_API_KEY

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = OPENROUTER_REFERER
        headers["X-Title"] = "MaisuClaw"

    payload = {"model": model_id, "messages": messages, "stream": True,
               "temperature": temperature, "max_tokens": max_tokens}

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", f"{url}/chat/completions",
                                 json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"API error {resp.status_code}: {body.decode()[:400]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                    text = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue


# ═══════════════════════════════════════════════════════════════
# SWARM COORDINATOR
# ═══════════════════════════════════════════════════════════════

async def run_single_agent(agent_id, messages, model_id, temperature):
    """Run a single agent and stream output."""
    agent = AGENTS[agent_id]
    sys_msg = {"role": "system", "content": agent["system_prompt"]}
    all_msgs = [sys_msg] + messages
    async for chunk in stream_llm(all_msgs, model_id, temperature):
        yield {"agent": agent_id, "content": chunk}


async def run_swarm(query, model_id, temperature):
    """
    Swarm mode: Coordinator decides which agents to use,
    then runs them sequentially, combining results.
    """
    swarm_prompt = (
        "You are the Swarm Coordinator. Given the user query, decide which agents "
        "should handle it. Reply in this EXACT JSON format only, nothing else:\n"
        '{"agents": ["coder", "researcher"], "plan": "brief plan"}\n\n'
        "Available agents: " + ", ".join(k for k in AGENTS if k != "swarm") + "\n\n"
        f"User query: {query}"
    )

    # Ask coordinator which agents to use
    coord_msgs = [{"role": "user", "content": swarm_prompt}]
    coord_response = ""
    async for chunk in stream_llm(coord_msgs, model_id, 0.3, 1024):
        coord_response += chunk

    # Parse agent selection
    try:
        json_match = re.search(r'\{[^}]+\}', coord_response, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())
            selected_agents = plan.get("agents", ["chat"])
            plan_text = plan.get("plan", "Processing...")
        else:
            selected_agents = ["chat"]
            plan_text = "Processing with default agent"
    except (json.JSONDecodeError, KeyError):
        selected_agents = ["chat"]
        plan_text = "Processing with default agent"

    # Filter to valid agents
    valid = [a for a in selected_agents if a in AGENTS and a != "swarm"]
    if not valid:
        valid = ["chat"]

    yield {"type": "swarm_plan", "agents": valid, "plan": plan_text}

    # Run each selected agent
    for agent_id in valid:
        yield {"type": "agent_start", "agent": agent_id}
        agent = AGENTS[agent_id]
        user_msgs = [{"role": "user", "content": query}]

        # For swarm, give agents context about other agents running
        if len(valid) > 1:
            ctx = f"[Swarm Mode] Multiple agents are collaborating. You are the {agent['name']} agent. Focus on your specialty. User query: {query}"
            user_msgs = [{"role": "user", "content": ctx}]

        sys_msg = {"role": "system", "content": agent["system_prompt"]}
        all_msgs = [sys_msg] + user_msgs

        response = ""
        async for chunk in stream_llm(all_msgs, model_id, temperature):
            response += chunk
            yield {"type": "agent_chunk", "agent": agent_id, "content": chunk}

        yield {"type": "agent_done", "agent": agent_id, "full_response": response}


# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("╔══════════════════════════════════════════════╗")
    print("║  MAISUCLAW AGENT SWARM — LIVE               ║")
    print(f"║  Groq:       {'✓ READY' if GROQ_API_KEY else '✗ NO KEY'}                        ║")
    print(f"║  OpenRouter: {'✓ READY' if OPENROUTER_API_KEY else '✗ NO KEY'}                        ║")
    print("║  Agents:     7 (Chat, Research, Code, ...)    ║")
    print(f"║  URL:        http://localhost:{PORT}               ║")
    print("╚══════════════════════════════════════════════╝")
    yield

app = FastAPI(title="MaisuClaw Agent Swarm", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ── Request Models ────────────────────────────────────────
class ChatReq(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    agent: Optional[str] = "chat"
    model_id: Optional[str] = DEFAULT_MODEL


# ── Active Streams ───────────────────────────────────────
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
    avail = []
    for m in MODELS:
        a = (m["provider"] == "groq" and GROQ_API_KEY) or (m["provider"] == "openrouter" and OPENROUTER_API_KEY)
        avail.append({**m, "available": bool(a)})
    return {
        "version": "1.0.0",
        "groq_ready": bool(GROQ_API_KEY),
        "openrouter_ready": bool(OPENROUTER_API_KEY),
        "models": avail,
        "agents": {k: {"name": v["name"], "icon": v["icon"], "color": v["color"]} for k, v in AGENTS.items()},
    }


@app.get("/api/conversations")
async def api_list():
    return {"conversations": list_conversations()}


@app.get("/api/conversations/{cid}")
async def api_get(cid: str):
    c = get_conversation(cid)
    if not c:
        raise HTTPException(404, "Not found")
    return {"conversation": c, "messages": get_messages(cid)}


@app.post("/api/conversations")
async def api_create(req: dict):
    agent = req.get("agent", "chat")
    mid = req.get("model_id", DEFAULT_MODEL)
    cid = create_conversation(agent, mid)
    return {"conversation_id": cid}


@app.delete("/api/conversations/{cid}")
async def api_delete(cid: str):
    delete_conversation(cid)
    return {"ok": True}


@app.post("/api/conversations/{cid}/clear")
async def api_clear(cid: str):
    clear_messages(cid)
    return {"ok": True}


@app.post("/api/chat")
async def chat(req: ChatReq):
    agent_id = req.agent if req.agent in AGENTS else "chat"
    cid = req.conversation_id or create_conversation(agent_id, req.model_id)
    add_message(cid, "user", req.message, agent=agent_id)

    history = get_messages(cid, limit=80)
    api_msgs = []
    for msg in history:
        if msg["role"] in ("user", "assistant"):
            api_msgs.append({"role": msg["role"], "content": msg["content"]})

    async def generate():
        start = time.time()
        skey = f"{cid}_{start}"
        active_streams[skey] = asyncio.current_task()

        try:
            if agent_id == "swarm":
                # Swarm mode — multi-agent
                full_parts = {}  # agent_id -> content
                async for event in run_swarm(req.message, req.model_id, 0.7):
                    etype = event.get("type", "")

                    if etype == "swarm_plan":
                        add_message(cid, "assistant", f"🐝 **Swarm Plan:** {event['plan']}\nAgents: {', '.join(a['name'] for a in AGENTS.values() if a != 'swarm' and a in event.get('agents', []))}", agent="swarm")
                        yield f"data: {json.dumps({'event': 'swarm_plan', 'agents': event['agents'], 'plan': event['plan']})}\n\n"

                    elif etype == "agent_start":
                        agent_info = AGENTS.get(event["agent"], {})
                        yield f"data: {json.dumps({'event': 'agent_start', 'agent': event['agent'], 'name': agent_info.get('name',''), 'icon': agent_info.get('icon',''), 'color': agent_info.get('color','')})}\n\n"

                    elif etype == "agent_chunk":
                        full_parts.setdefault(event["agent"], "")
                        full_parts[event["agent"]] += event["content"]
                        yield f"data: {json.dumps({'event': 'agent_chunk', 'agent': event['agent'], 'content': event['content']})}\n\n"

                    elif etype == "agent_done":
                        add_message(cid, "assistant", event["full_response"], agent=event["agent"])
                        yield f"data: {json.dumps({'event': 'agent_done', 'agent': event['agent']})}\n\n"

                ms = int((time.time() - start) * 1000)
                yield f"data: {json.dumps({'event': 'done', 'duration_ms': ms})}\n\n"

            else:
                # Single agent mode
                full = ""
                agent = AGENTS[agent_id]
                sys_msg = {"role": "system", "content": agent["system_prompt"]}
                all_msgs = [sys_msg] + api_msgs

                async for chunk in stream_llm(all_msgs, req.model_id):
                    full += chunk
                    yield f"data: {json.dumps({'event': 'chunk', 'content': chunk})}\n\n"

                ms = int((time.time() - start) * 1000)
                add_message(cid, "assistant", full, agent=agent_id, model_id=req.model_id, duration_ms=ms)
                yield f"data: {json.dumps({'event': 'done', 'duration_ms': ms})}\n\n"

        except Exception as e:
            err = str(e)
            add_message(cid, "assistant", f"[Error] {err}", agent=agent_id)
            yield f"data: {json.dumps({'event': 'error', 'error': err})}\n\n"

        finally:
            active_streams.pop(skey, None)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/stop")
async def stop(req: dict):
    cid = req.get("conversation_id", "")
    stopped = 0
    to_del = []
    for key, task in active_streams.items():
        if key.startswith(cid):
            if not task.done():
                task.cancel()
                stopped += 1
            to_del.append(key)
    for k in to_del:
        active_streams.pop(k, None)
    return {"stopped": stopped}


@app.post("/api/settings")
async def save_settings(req: Request):
    body = await req.json()
    global GROQ_API_KEY, OPENROUTER_API_KEY
    if body.get("groq_api_key"):
        GROQ_API_KEY = body["groq_api_key"]
    if body.get("openrouter_api_key"):
        OPENROUTER_API_KEY = body["openrouter_api_key"]
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
