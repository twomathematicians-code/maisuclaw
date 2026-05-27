"""
maisuclaw — main.py  v0.3.0
Full-stack AI assistant: streaming chat, multimodal, research, GitHub backup, ETA.
"""
import os, uuid, json, time, base64, shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from config import (
    HOST, PORT, UPLOAD_DIR, CHAT_HISTORY_LIMIT,
    GITHUB_BACKUP_ENABLED, MODEL_OPTIONS,
    MAX_UPLOAD_SIZE_MB, ALLOWED_IMAGE_TYPES, ALLOWED_DOC_TYPES,
    REMOTE_ACCESS_ENABLED, PUBLIC_URL,
)
from services.memory import init_db, save_message, get_history, save_note, search_notes, list_notes, delete_note
from services.ollama import chat as ollama_chat, list_models, chat_with_images, chat_with_base64_images
from agent.router import pick_model, is_research_request
from agent.planner import run_agent, run_agent_stream
from services.eta import estimate_eta
from services.pdf_extractor import extract_text, page_count
from services.vision import analyze_image, analyze_screenshot
from services.research import ResearchAgent

from tools.file_manager import list_files, read_file, write_file
from tools.code_runner import run_python
from tools.git_manager import git_status, git_log, git_commit, git_diff
from tools.browser import search_web
from tools.rag import index_file as rag_index, search_documents

# ── init ──────────────────────────────────────────────────────────
init_db()
research_agent = ResearchAgent(ollama_chat, search_web)

app = FastAPI(title="maisuclaw", version="0.3.0")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


# ── request models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    mode: str = ""
    images: list[str] | None = None  # base64 images

class NoteRequest(BaseModel):
    title: str
    content: str
    tags: list[str] | None = None


# ── tool dispatcher ───────────────────────────────────────────────

def execute_tool(tool_name: str, params: dict) -> str:
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
            save_note(params["title"], params["content"],
                       params.get("tags", "").split(",") if params.get("tags") else None)
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


# ── streaming chat (PRIMARY) ───────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]
    save_message(session_id, "user", req.message)

    has_images = bool(req.images)
    has_tools = _needs_tools(req.message)
    model = pick_model(req.message, req.mode, has_image=has_images)
    eta = estimate_eta(model, len(req.message), has_image=has_images, has_tools=has_tools)

    # If images attached, use vision model directly
    if has_images and req.images:
        async def generate_vision():
            full_reply = chat_with_base64_images(model, req.message, req.images)
            yield f"data: {json.dumps({'type': 'eta', 'seconds': eta['seconds'], 'label': eta['label']})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': full_reply})}\n\n"
            save_message(session_id, "assistant", full_reply, model)
            yield f"data: {json.dumps({'type': 'done', 'model': model, 'session_id': session_id})}\n\n"
        return StreamingResponse(generate_vision(), media_type="text/event-stream")

    history = get_history(session_id, limit=CHAT_HISTORY_LIMIT)

    async def generate():
        yield f"data: {json.dumps({'type': 'eta', 'seconds': eta['seconds'], 'label': eta['label']})}\n\n"
        full_reply = ""
        try:
            for event in run_agent_stream(history, model, execute_tool):
                if event["type"] == "token":
                    full_reply += event["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
                elif event["type"] == "tool":
                    yield f"data: {json.dumps({'type': 'tool', 'name': event['name']})}\n\n"
                elif event["type"] == "tool_result":
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': event['name'], 'result': event['result'][:300]})}\n\n"
                elif event["type"] == "done":
                    full_reply = event.get("full_reply", full_reply)
                    model_used = event.get("model", model)
                    save_message(session_id, "assistant", full_reply, model_used)
                    yield f"data: {json.dumps({'type': 'done', 'model': model_used, 'session_id': session_id})}\n\n"
                    return
        except Exception as e:
            full_reply = f"Error: {e}"
            yield f"data: {json.dumps({'type': 'error', 'content': full_reply})}\n\n"

        if full_reply:
            save_message(session_id, "assistant", full_reply, model)
            yield f"data: {json.dumps({'type': 'done', 'model': model, 'session_id': session_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── file upload (images + PDFs + docs) ────────────────────────────

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), prompt: str = Form("Analyze this file")):
    """Upload an image or PDF and get an AI analysis."""
    # Validate size
    content = await file.read()
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        return JSONResponse({"error": f"File too large (max {MAX_UPLOAD_SIZE_MB}MB)"}, status_code=400)

    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    filepath = UPLOAD_DIR / file.filename
    filepath.write_bytes(content)

    # Images → vision model
    if ext in ALLOWED_IMAGE_TYPES:
        model = "llava:13b"
        eta = estimate_eta(model, len(prompt), has_image=True)
        try:
            reply = analyze_image(str(filepath), prompt, model)
            return {"type": "image", "reply": reply, "model": model, "eta": eta, "filename": file.filename}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # PDFs → extract text then analyze
    if ext == "pdf":
        try:
            pages = page_count(str(filepath))
            text = extract_text(str(filepath))
            model = pick_model(prompt, "powerful")
            eta = estimate_eta(model, len(text), has_tools=False)

            # Use powerful model for long documents
            messages = [
                {"role": "system", "content": "You are a document analyst. Analyze the provided document text thoroughly."},
                {"role": "user", "content": f"Document: {file.filename} ({pages} pages)\n\n{text[:8000]}\n\n{prompt}"},
            ]
            reply = ollama_chat(model, messages)
            return {"type": "pdf", "reply": reply, "model": model, "eta": eta, "filename": file.filename, "pages": pages}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # Text files → read and analyze
    if ext in ALLOWED_DOC_TYPES or ext in {"txt", ""}:
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            model = pick_model(prompt, "")
            eta = estimate_eta(model, len(text))
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Analyze the provided file content."},
                {"role": "user", "content": f"File: {file.filename}\n\n{text[:8000]}\n\n{prompt}"},
            ]
            reply = ollama_chat(model, messages)
            return {"type": "file", "reply": reply, "model": model, "eta": eta, "filename": file.filename}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"error": f"Unsupported file type: .{ext}"}, status_code=400)


# ── screenshot paste (base64 from clipboard) ──────────────────────

@app.post("/screenshot")
async def analyze_screenshot_endpoint(req: dict):
    """Analyze a screenshot pasted from clipboard."""
    b64 = req.get("image", "")
    prompt = req.get("prompt", "Describe what is shown in this screenshot.")
    if not b64:
        return JSONResponse({"error": "No image data"}, status_code=400)

    model = "llava:13b"
    eta = estimate_eta(model, len(prompt), has_image=True)
    try:
        reply = analyze_screenshot(b64, prompt, model)
        return {"reply": reply, "model": model, "eta": eta}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── deep research ─────────────────────────────────────────────────

@app.post("/research")
async def research(query: str = Form(...)):
    """Run deep research on a topic. Streams progress."""
    async def generate():
        try:
            for event in research_agent.research_stream(query):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e), 'done': True})}\n\n"

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
    return search_notes(q) if q else list_notes()

@app.delete("/notes/{note_id}")
async def remove_note(note_id: int):
    delete_note(note_id)
    return {"ok": True}


# ── RAG ──────────────────────────────────────────────────────────

@app.post("/rag/index")
async def index_document(filepath: str = Form(...)):
    return {"result": rag_index(filepath)}

@app.post("/rag/search")
async def rag_search(query: str = Form(...)):
    return {"results": search_documents(query)}


# ── direct tools ─────────────────────────────────────────────────

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


# ── GitHub backup ────────────────────────────────────────────────

@app.post("/backup")
async def trigger_backup():
    try:
        from services.github_backup import run_backup
        return run_backup()
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/backup/status")
async def backup_status():
    from config import GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPO, GITHUB_BACKUP_ENABLED
    return {
        "enabled": GITHUB_BACKUP_ENABLED,
        "configured": bool(GITHUB_TOKEN and GITHUB_USERNAME and GITHUB_REPO),
        "repo": f"{GITHUB_USERNAME}/{GITHUB_REPO}" if GITHUB_USERNAME else "(not set)",
    }


# ── info ─────────────────────────────────────────────────────────

@app.get("/info")
async def info():
    models = []
    try:
        models = [m["name"] for m in list_models()]
    except Exception:
        pass
    return {
        "name": "maisuclaw",
        "version": "0.3.0",
        "models": models,
        "model_options": MODEL_OPTIONS,
        "backup": await backup_status(),
        "remote_access": {
            "enabled": REMOTE_ACCESS_ENABLED,
            "url": PUBLIC_URL,
        },
        "features": [
            "streaming", "multimodal", "vision", "pdf",
            "research", "voice", "notes", "rag",
            "git", "code_runner", "browser", "github_backup",
        ],
    }


# ── helpers ───────────────────────────────────────────────────────

def _needs_tools(message: str) -> bool:
    lower = message.lower()
    hints = {
        "list file", "read file", "write file", "run code", "execute",
        "search", "save note", "browse", "open", "show me", "what files",
        "git status", "git log", "create file", "my desktop", "my documents",
        "directory", "folder",
    }
    return any(h in lower for h in hints)


# ── run ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
