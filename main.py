"""
maisuclaw v0.3.0 — Main FastAPI Application
Features:
  - Multi-provider model support (Ollama, Groq, OpenRouter)
  - SSE streaming responses
  - Chat history with stop/new chat
  - Provider status monitoring
  - File upload support
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from config import config, UPLOAD_DIR
from database import (
    create_conversation, get_conversation, list_conversations,
    delete_conversation, update_conversation_title,
    add_message, get_messages, clear_conversation_messages,
    get_stats, save_memory, get_memory, get_all_memory,
)
from services.model_router import model_router


# ── State ──────────────────────────────────────────────
# Track active streaming tasks so we can cancel them
active_streams: dict[str, asyncio.Task] = {}


# ── Lifespan ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    print("=" * 50)
    print("  MaisuClaw v0.3.0 Starting...")
    print("=" * 50)

    # Check provider status
    status = await model_router.get_provider_status()
    print(f"\n  Ollama:     {'CONNECTED' if status['ollama']['available'] else 'NOT RUNNING'}")
    if status["ollama"]["available"]:
        print(f"              Models: {', '.join(status['ollama']['models'][:5])}")
    else:
        print("              Start with: ollama serve")
    print(f"  Groq:       {'READY' if status['groq']['available'] else 'No API key'}")
    print(f"  OpenRouter: {'READY' if status['openrouter']['available'] else 'No API key'}")
    print(f"\n  Access: http://localhost:{config.PORT}")
    print("=" * 50 + "\n")

    yield

    # Cancel all active streams
    for task_id, task in active_streams.items():
        if not task.done():
            task.cancel()
    print("MaisuClaw shutdown complete.")


# ── App ────────────────────────────────────────────────
app = FastAPI(title="MaisuClaw", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = "llama3"


class StopRequest(BaseModel):
    conversation_id: str


class TitleUpdateRequest(BaseModel):
    conversation_id: str
    title: str


# ── Routes ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main UI."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/status")
async def get_status():
    """Get provider status and system info."""
    status = await model_router.get_provider_status()
    stats = get_stats()
    return {
        "version": "0.3.0",
        "providers": status,
        "stats": stats,
        "models": [
            {
                "id": m.id, "name": m.name, "provider": m.provider,
                "tier": m.tier, "supports_vision": m.supports_vision,
                "description": m.description, "is_free": m.is_free,
                "available": (
                    True if m.provider == "ollama" and status["ollama"]["available"]
                    else True if m.provider == "groq" and status["groq"]["available"]
                    else True if m.provider == "openrouter" and status["openrouter"]["available"]
                    else False
                )
            }
            for m in config.models
        ]
    }


@app.get("/api/conversations")
async def api_list_conversations():
    """List all conversations."""
    return {"conversations": list_conversations()}


@app.get("/api/conversations/{conv_id}")
async def api_get_conversation(conv_id: str):
    """Get a conversation and its messages."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = get_messages(conv_id)
    return {"conversation": conv, "messages": messages}


@app.post("/api/conversations")
async def api_create_conversation():
    """Create a new conversation."""
    conv_id = create_conversation()
    return {"conversation_id": conv_id}


@app.put("/api/conversations/title")
async def api_update_title(req: TitleUpdateRequest):
    """Update conversation title."""
    update_conversation_title(req.conversation_id, req.title)
    return {"status": "ok"}


@app.delete("/api/conversations/{conv_id}")
async def api_delete_conversation(conv_id: str):
    """Delete a conversation."""
    delete_conversation(conv_id)
    return {"status": "ok"}


@app.post("/api/conversations/{conv_id}/clear")
async def api_clear_conversation(conv_id: str):
    """Clear messages in a conversation (keep history metadata)."""
    clear_conversation_messages(conv_id)
    return {"status": "ok"}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Main chat endpoint — returns SSE stream.
    If conversation_id is None, creates a new conversation.
    """
    # Create or get conversation
    conv_id = req.conversation_id
    if not conv_id:
        conv_id = create_conversation(model_id=req.model_id)

    # Store user message
    add_message(conv_id, "user", req.message)

    # Build message history
    history = get_messages(conv_id, limit=100)
    api_messages = []
    for msg in history:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    # Generate response via SSE
    async def stream_response():
        start_time = time.time()
        full_response = ""
        stream_id = f"{conv_id}_{start_time}"
        task = asyncio.current_task()
        active_streams[stream_id] = task

        try:
            async for chunk in model_router.chat_stream(
                messages=api_messages,
                model_id=req.model_id,
                system_prompt=config.system_prompt,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

            # Store assistant response
            duration = int((time.time() - start_time) * 1000)
            add_message(
                conv_id, "assistant", full_response,
                model_id=req.model_id, duration_ms=duration
            )

            yield f"data: {json.dumps({'content': '', 'done': True, 'duration_ms': duration})}\n\n"

        except Exception as e:
            error_msg = str(e)
            # Store error in history
            add_message(conv_id, "assistant", f"[Error] {error_msg}", model_id=req.model_id)
            yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"

        finally:
            active_streams.pop(stream_id, None)

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/stop")
async def stop_generation(req: StopRequest):
    """Stop the current stream generation for a conversation."""
    stopped = 0
    to_remove = []
    for stream_id, task in active_streams.items():
        if stream_id.startswith(req.conversation_id):
            if not task.done():
                task.cancel()
                stopped += 1
            to_remove.append(stream_id)
    for sid in to_remove:
        active_streams.pop(sid, None)
    return {"stopped": stopped}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), conversation_id: str = Query("")):
    """Upload a file (PDF, image, etc.)."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    file_type = file.content_type or "unknown"
    size = len(content)

    # Store reference
    if conversation_id:
        add_message(
            conversation_id, "user",
            f"[Uploaded file: {file.filename} ({size:,} bytes, {file_type})]",
        )

    return {
        "filename": file.filename,
        "filepath": file_path,
        "filetype": file_type,
        "size": size,
    }


# ── Memory ─────────────────────────────────────────────

@app.get("/api/memory")
async def api_get_memory():
    return {"memory": get_all_memory()}


@app.post("/api/memory")
async def api_save_memory(req: dict):
    save_memory(req.get("key", ""), req.get("value", ""))
    return {"status": "ok"}


# ── Settings ───────────────────────────────────

@app.post("/api/settings")
async def api_save_settings(req: dict):
    """Save API keys and settings (stored in .env file for persistence)."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []

    # Read existing .env
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

    # Build key-value map
    env_vars = {}
    for line in lines:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()

    # Update with new values
    if req.get("groq_api_key"):
        env_vars["GROQ_API_KEY"] = req["groq_api_key"]
    if req.get("openrouter_api_key"):
        env_vars["OPENROUTER_API_KEY"] = req["openrouter_api_key"]
    if req.get("ollama_base_url"):
        env_vars["OLLAMA_BASE_URL"] = req["ollama_base_url"]

    # Write back
    with open(env_path, "w") as f:
        for key, val in env_vars.items():
            f.write(f"{key}={val}\n")

    # Update runtime config
    if req.get("groq_api_key"):
        from services.cloud_client import groq_client
        groq_client.api_key = req["groq_api_key"]
    if req.get("openrouter_api_key"):
        from services.cloud_client import openrouter_client
        openrouter_client.api_key = req["openrouter_api_key"]

    return {"status": "ok", "message": "Settings saved. Restart for full effect."}


# ── Run ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
