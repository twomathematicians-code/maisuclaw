# maisuclaw

> Your personal AI assistant — running 100% on your laptop. Multimodal. Streaming. Research. Voice. Remote access.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Ollama-LLM-orange?logo=docker" alt="Ollama">
  <img src="https://img.shields.io/badge/v0.3.0-f0883e?style=flat" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License">
</p>

## What's in v0.3.0

| Feature | Description |
|---------|-------------|
| **8 model tiers** | From instant (0.5B) to powerful (14B) + vision + reasoning |
| **Multimodal** | Upload images, PDFs, screenshots — AI analyzes them |
| **Screenshot paste** | Ctrl+V to paste from clipboard |
| **Deep research** | Multi-step web browsing + synthesis |
| **ETA display** | See estimated response time before answer arrives |
| **Streaming** | Tokens appear live as generated |
| **GitHub backup** | Auto-save chats to a private repo |
| **Remote access** | Cloudflare Tunnel — use from anywhere |
| **GitHub Pages** | Host the UI at `username.github.io/maisuclaw` |
| **Voice input** | Speech-to-text via Whisper |
| **File management** | Browse, read, write files on your machine |
| **Code execution** | Run Python code and see output |
| **Git integration** | Status, log, commit |
| **Notes** | Save, search, tag your notes |
| **RAG** | Index documents, semantic search |

## Model tiers

| Tier | Model | Size | Speed | Best for |
|------|-------|------|-------|----------|
| Instant | qwen2.5:0.5b | 0.5B | ~1-2s | Quick math, greetings |
| Fast | phi3.5 | 3.8B | ~3-5s | Simple questions |
| Balanced | gemma2:9b | 9B | ~8-15s | General tasks |
| Coder | qwen2.5-coder:7b | 7B | ~8-15s | Programming |
| Powerful | qwen2.5:14b | 14B | ~15-30s | Complex analysis, writing |
| Reasoning | deepseek-r1:8b | 8B | ~15-25s | Step-by-step thinking |
| Vision | llava:13b | 13B | ~20-60s | Image & PDF analysis |

## Quick start

### Prerequisites

- **Python 3.10+**
- **Ollama** — [ollama.com](https://ollama.com)
- **~15 GB disk** for all 8 models

### 1. Clone

```bash
git clone https://github.com/twomathematicians-code/maisuclaw.git
cd maisuclaw
```

### 2. Setup

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

### 3. Start

**Windows:**
```cmd
setup_run.bat
```

**Linux/macOS:**
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open

- **Browser:** `http://localhost:8000`
- **Phone (same Wi-Fi):** `http://<your-laptop-ip>:8000`
- **Phone (anywhere):** Run `scripts/cloudflare_tunnel.bat`, then open the URL

## Features guide

### Upload images & PDFs

- Click the upload button (top bar) or drag & drop files onto the page
- Paste screenshots with **Ctrl+V**
- Images are analyzed by the vision model (llava:13b)
- PDFs are extracted and analyzed by the powerful model
- Preview thumbnails appear before sending

### Deep research

1. Type your research question
2. Click the **Research** button
3. Watch as maisuclaw:
   - Breaks your question into sub-questions
   - Searches the web for each
   - Extracts content from top results
   - Synthesizes a comprehensive report with sources

### ETA display

When you send a message, an estimated response time appears (e.g. "~8s"). This is based on:
- Model size (larger = slower)
- Input length
- Whether images are attached
- Whether tools are needed

### Voice input

Click the microphone button to record. Audio is transcribed via Whisper and sent as text.

### Remote access from anywhere

See [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md) for full guide.

**Quickest method — Cloudflare Tunnel:**
1. Install [cloudflared](https://github.com/cloudflare/cloudflared/releases)
2. Run `scripts/cloudflare_tunnel.bat`
3. Open the URL on any device

### GitHub Pages

Host the UI at a nice URL:
```
https://username.github.io/maisuclaw
```
See [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md) for setup.

### GitHub cloud backup

Edit `config.py`:
```python
GITHUB_BACKUP_ENABLED = True
GITHUB_TOKEN = "ghp_your_token"
GITHUB_USERNAME = "your_username"
GITHUB_REPO = "maisuclaw-chats"
```

Then: `curl -X POST http://localhost:8000/backup`

## Project structure

```
maisuclaw/
├── main.py                  # FastAPI server (entry point)
├── config.py                # All settings
├── requirements.txt         # Dependencies
├── setup.bat / setup.sh     # One-command setup
├── setup_run.bat            # One-command start (Windows)
├── LICENSE                  # MIT
├── .gitignore
│
├── agent/
│   ├── router.py            # 8-tier model routing + multimodal detection
│   └── planner.py           # Agent loop with streaming
│
├── services/
│   ├── ollama.py            # Ollama API (chat, stream, vision, embed)
│   ├── vision.py            # Image/screenshot analysis
│   ├── pdf_extractor.py     # PDF text + image extraction
│   ├── research.py          # Deep research agent
│   ├── eta.py               # Response time estimation
│   ├── whisper.py           # Speech-to-text
│   ├── memory.py            # SQLite storage
│   └── github_backup.py     # GitHub cloud backup
│
├── tools/
│   ├── file_manager.py      # File operations
│   ├── code_runner.py       # Python execution
│   ├── git_manager.py       # Git operations
│   ├── browser.py           # Web search
│   └── rag.py               # Document indexing
│
├── static/
│   ├── index.html           # Web UI
│   ├── style.css            # Dark theme
│   └── app.js               # Frontend logic
│
├── docs/
│   └── REMOTE_ACCESS.md     # Deployment guide
│
└── scripts/
    └── cloudflare_tunnel.bat # Remote access
```

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/chat` | Streaming chat (SSE) |
| `POST` | `/upload` | Upload image/PDF for analysis |
| `POST` | `/screenshot` | Paste screenshot for analysis |
| `POST` | `/research` | Deep research (SSE) |
| `POST` | `/stt` | Audio transcription |
| `POST` | `/notes` | Create note |
| `GET` | `/notes?q=` | Search notes |
| `DELETE` | `/notes/{id}` | Delete note |
| `POST` | `/rag/index` | Index document |
| `POST` | `/rag/search` | Search documents |
| `POST` | `/backup` | GitHub backup |
| `GET` | `/backup/status` | Backup config check |
| `POST` | `/tool/*` | Direct tool access |
| `GET` | `/info` | Server info + features |

## Configuration

All in `config.py`:
```python
# Models
MODEL_INSTANT   = "qwen2.5:0.5b"
MODEL_FAST      = "phi3.5"
MODEL_CODER     = "qwen2.5-coder:7b"
MODEL_GENERAL   = "gemma2:9b"
MODEL_POWERFUL  = "qwen2.5:14b"
MODEL_REASONING = "deepseek-r1:8b"
MODEL_VISION    = "llava:13b"

# Performance
CHAT_HISTORY_LIMIT = 10

# Remote access
REMOTE_ACCESS_ENABLED = False
PUBLIC_URL = ""

# GitHub backup
GITHUB_BACKUP_ENABLED = False
GITHUB_TOKEN = ""
GITHUB_USERNAME = ""
GITHUB_REPO = "maisuclaw-chats"
```

## Performance tips

1. **Use Instant mode** for trivial questions (~1-2s)
2. **Use model selector** — don't default to Powerful for everything
3. **Reduce history** — `CHAT_HISTORY_LIMIT = 6`
4. **Close unused apps** — free RAM for Ollama
5. **Keep only needed models** — `ollama rm <model>` to free disk

## License

MIT — use it, modify it, make it yours.

---

*Built with Ollama, FastAPI, and a ThinkPad.*
