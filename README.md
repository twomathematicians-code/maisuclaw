# maisuclaw

> Your personal AI assistant — running 100% on your laptop. No cloud, no subscriptions, no data leaving your machine.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Ollama-LLM-orange?logo=docker" alt="Ollama">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License">
</p>

## What it does

**maisuclaw** is a three-layer local AI assistant:

| Layer | What | Tech |
|-------|------|------|
| **Brain** | LLMs for coding, chatting, fast tasks | Ollama (Qwen Coder, Gemma 2, Phi-3.5) |
| **Agent** | Plans, decides which tool to call, loops until done | Python + FastAPI |
| **Clients** | Web UI, voice input from phone/browser | HTML/JS + WebRTC |

### Capabilities

- **Chat** with automatic model routing (code questions → coder model, quick tasks → fast model)
- **Agent loop** — the LLM can call tools, see results, and continue reasoning
- **File management** — list, read, write files on your machine
- **Code execution** — run Python snippets and get output
- **Git integration** — status, log, commit
- **Web search** — via Playwright + DuckDuckGo (optional)
- **Voice input** — speech-to-text via Ollama Whisper
- **Notes** — save, search, delete notes with tags
- **RAG** — index documents, search by semantic similarity
- **Memory** — all conversations saved to SQLite

## Project structure

```
maisuclaw/
├── main.py              # FastAPI server — single entry point
├── config.py            # All settings in one place
├── requirements.txt     # Python dependencies
├── setup.sh             # One-command setup
├── .gitignore           # Keeps your data private
│
├── agent/
│   ├── router.py        # Picks the right LLM for each request
│   └── planner.py       # Agent loop: LLM → tool → LLM → answer
│
├── services/
│   ├── ollama.py        # Ollama HTTP API wrapper
│   ├── whisper.py       # Speech-to-text via Ollama
│   └── memory.py        # SQLite conversation & notes storage
│
├── tools/
│   ├── file_manager.py  # File system operations
│   ├── code_runner.py   # Python code execution
│   ├── git_manager.py   # Git operations
│   ├── browser.py       # Web search via Playwright
│   └── rag.py           # Document indexing & search
│
├── static/
│   ├── index.html       # Web UI
│   ├── style.css        # Dark theme styles
│   └── app.js           # Frontend logic + voice
│
└── data/                # (gitignored) SQLite DB, uploads
    └── uploads/
```

## Quick start

### Prerequisites

- **Python 3.10+**
- **Ollama** — [install from ollama.ai](https://ollama.ai)
- ~8 GB disk space for models

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/maisuclaw.git
cd maisuclaw
```

### 2. Run setup

```bash
chmod +x setup.sh
./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Pull LLM models via Ollama
- Optionally install Playwright

### 3. Start the server

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the UI

- **On your laptop**: [http://localhost:8000](http://localhost:8000)
- **From your phone** (same Wi-Fi): `http://<your-laptop-ip>:8000`

## Configuration

All settings are in `config.py`:

```python
# Change models to whatever you have pulled
MODEL_CODER = "qwen2.5-coder:7b"
MODEL_GENERAL = "gemma2:9b"
MODEL_FAST = "phi3.5:latest"
MODEL_EMBED = "nomic-embed-text"
MODEL_STT = "whisper:small"

# Server settings
HOST = "0.0.0.0"
PORT = 8000
```

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/chat` | Send a message (with agent loop) |
| `POST` | `/chat/stream` | Streaming chat (no tools) |
| `POST` | `/stt` | Upload audio → transcribe |
| `POST` | `/notes` | Create a note |
| `GET` | `/notes?q=` | Search notes |
| `DELETE` | `/notes/{id}` | Delete a note |
| `POST` | `/rag/index` | Index a document |
| `POST` | `/rag/search` | Search indexed documents |
| `POST` | `/tool/list_files` | List directory contents |
| `POST` | `/tool/read_file` | Read a file |
| `POST` | `/tool/run_python` | Execute Python code |
| `POST` | `/tool/git_status` | Git status |
| `POST` | `/tool/git_log` | Git log |
| `GET` | `/info` | Server info + available models |

### Chat request example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List the files on my Desktop", "mode": ""}'
```

## How the agent loop works

```
User message
    │
    ▼
┌──────────────┐
│ Model Router │ → pick best LLM (coder / general / fast)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  LLM + Tools │ → "Do I need a tool? Call it."
│   (loop)     │ → "Got result? Feed back to LLM."
│              │ → "Done? Return answer."
└──────┬───────┘
       │
       ▼
   Reply + save to memory
```

The LLM sees a list of tools and can emit a special `tool` JSON block. The agent executor runs the tool, feeds the result back, and lets the LLM continue — up to 5 rounds.

## Roadmap

- [ ] **Streaming with tool support** — SSE agent loop
- [ ] **File upload UI** — drag & drop documents for RAG
- [ ] **Cron jobs** — scheduled summaries, email checks
- [ ] **PWA** — install on phone home screen
- [ ] **Multi-user** — basic auth for LAN sharing
- [ ] **Plugin system** — drop-in new tools

## License

MIT — use it, modify it, make it yours.

---

*Built with Ollama, FastAPI, and a ThinkPad.*
