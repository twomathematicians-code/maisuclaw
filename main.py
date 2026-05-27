"""
maisuclaw — main.py
The single entry point. Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import HOST, PORT, UPLOAD_DIR
from services.memory import init_db, save_message, get_history, save_note, search_notes, list_notes, delete_note
from services.ollama import chat as ollama_chat, list_models
from agent.router import pick_model
from agent.planner import run_agent

from tools.file_manager import list_files, read_file, write_file
from tools.code_runner import run_python
from tools.git_manager import git_status, git_log, git_commit, git_diff
from tools.browser import search_web
from tools.rag import index_file as rag_index, search_documents

# ── init ──────────────────────────────────────────────────────────
init_db()

app = FastAPI(title="maisuclaw", version="0.1.0")

# Serve the static web UI
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


# ── request / response models ─────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    mode: str = ""   # "" | "code" | "fast"


class NoteRequest(BaseModel):
    title: str
    content: str
    tags: list[str] | None = None


# ── tool dispatcher (used by the agent loop) ─────────────────────

def execute_tool(tool_name: str, params: dict) -> str:
    """Map tool names to their implementations."""
    match tool_name:
        case "list_files":
            return list_files(params.get("path", "."))
        case "read_file":
            return read_file(params["path"])
        case "write_file":
            return write_file(params["path"], params["content"])
        case "run_python":
            return run_python(params["code"])
        case "search_web":
            return search_web(params.get("query", ""))
        case "save_note":
            save_note(params["title"], params["content"], params.get("tags", "").split(",") if params.get("tags") else None)
            return f"Note saved: {params['title']}"
        case "search_notes":
            results = search_notes(params.get("query", ""))
            return "\n".join(f"- {r['title']}: {r['content'][:200]}" for r in results) if results else "(no notes found)"
        case _:
            return f"Unknown tool: {tool_name}"


# ── web UI ────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# ── chat endpoint ─────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]

    # Save user message to memory
    save_message(session_id, "user", req.message)

    # Pick model
    model = pick_model(req.message, req.mode)

    # Load conversation history
    history = get_history(session_id, limit=20)

    # Run the agent (LLM + tools loop)
    reply = run_agent(history, model, execute_tool)

    # Save assistant reply
    save_message(session_id, "assistant", reply, model)

    return {"reply": reply, "session_id": session_id, "model": model}


# ── streaming chat ────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Simple streaming alternative (no tool loop, raw LLM stream)."""
    session_id = req.session_id or str(uuid.uuid4())[:8]
    save_message(session_id, "user", req.message)

    model = pick_model(req.message, req.mode)
    history = get_history(session_id, limit=20)

    from services.ollama import chat_stream as ollama_stream
    from config import SYSTEM_PROMPT

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    def generate():
        full_reply = ""
        for chunk in ollama_stream(model, full_messages):
            full_reply += chunk
            yield f"data: {chunk}\n\n"
        save_message(session_id, "assistant", full_reply, model)
        yield "data: [DONE]\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(generate(), media_type="text/event-stream")


# ── speech-to-text ───────────────────────────────────────────────

@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse({"error": "empty file"}, status_code=400)

    try:
        from services.whisper import transcribe
        text = transcribe(audio_bytes)
        return {"text": text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── notes CRUD ───────────────────────────────────────────────────

@app.post("/notes")
async def create_note(req: NoteRequest):
    save_note(req.title, req.content, req.tags)
    return {"ok": True}

@app.get("/notes")
async def get_notes(q: str = ""):
    if q:
        return search_notes(q)
    return list_notes()

@app.delete("/notes/{note_id}")
async def remove_note(note_id: int):
    delete_note(note_id)
    return {"ok": True}


# ── document indexing (RAG) ──────────────────────────────────────

@app.post("/rag/index")
async def index_document(filepath: str = Form(...)):
    result = rag_index(filepath)
    return {"result": result}

@app.post("/rag/search")
async def rag_search(query: str = Form(...)):
    results = search_documents(query)
    return {"results": results}


# ── direct tool endpoints (for the web UI / API) ─────────────────

@app.post("/tool/list_files")
async def tool_list_files(path: str = Form(".")):
    return {"result": list_files(path)}

@app.post("/tool/read_file")
async def tool_read_file(path: str = Form(...)):
    return {"result": read_file(path)}

@app.post("/tool/run_python")
async def tool_run_python(code: str = Form(...)):
    return {"result": run_python(code)}

@app.post("/tool/git_status")
async def tool_git_status(path: str = Form(".")):
    return {"result": git_status(path)}

@app.post("/tool/git_log")
async def tool_git_log(path: str = Form(".")):
    return {"result": git_log(path)}


# ── info / diagnostics ───────────────────────────────────────────

@app.get("/info")
async def info():
    models = []
    try:
        models = [m["name"] for m in list_models()]
    except Exception:
        pass
    return {
        "name": "maisuclaw",
        "version": "0.1.0",
        "models": models,
    }


# ── run ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
