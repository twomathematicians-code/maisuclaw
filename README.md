# MAISUCLAW

Agent Swarm System v2.1 — 7 free AI providers (including Ollama), auto-failover, 7 specialized agents, zero cost.

```
    ∫ f(x)dx

    ∇ · Agent Swarm System
    │  ├─ ∫ Chat     — General assistant
    │  ├─ ∇ Research — Deep analysis
    │  ├─ λ Code     — Production code
    │  ├─ Δ Write    — Human-like writing
    │  ├─ Σ Analyze  — Data & business
    │  ├─ ∂ Tutor    — Step-by-step teaching
    │  └─ ⊕ Swarm   — Multi-agent orchestration

    ∞ Free Providers with Auto-Failover
    │  ├─ Groq        — ~500 tok/s (cloud)
    │  ├─ OpenRouter  — 50+ free models (cloud)
    │  ├─ Cerebras    — ~1200 tok/s (cloud)
    │  ├─ Together AI — Free credits (cloud)
    │  ├─ SambaNova   — Free tier (cloud)
    │  ├─ Cohere      — Free tier (cloud)
    │  └─ Ollama      — ALL free, NO key, local GPU
```

## What's New in v2.1

**Ollama support added!** Now you can use Ollama as a 7th provider — completely free, no API key needed, no rate limits. Just run `ollama serve` and all your local models are available. Includes auto-detection of installed Ollama models via the in-app settings.

**No more rate limits.** MaisuClaw uses 7 AI providers simultaneously. When one provider hits its rate limit, it automatically switches to the next available provider — seamlessly, in real-time.

## Features

- **7 Free AI Providers** — Groq, OpenRouter, Cerebras, Together AI, SambaNova, Cohere, **Ollama**
- **Auto-Failover** — When one provider rate-limits (429), automatically switches to the next
- **Ollama Support** — Local models, no API key, 100% free, auto-detect installed models
- **7 Specialized Agents** — Pick one or use Swarm for multi-agent collaboration
- **45+ Models** — All free: Llama 3.3 70B, DeepSeek R1, Qwen, Gemini, Phi-4, Mistral, Command R+, CodeLlama...
- **File Upload** — Photos, PDFs, code files, any type (up to 20MB)
- **Audio Chat** — Record or upload audio clips
- **Video Upload** — Attach short videos (up to 20MB)
- **Link Attachments** — Add reference URLs directly in chat
- **Screenshot Paste** — Ctrl+V to paste screenshots directly
- **Drag & Drop** — Drop files anywhere on the page
- **Image Preview** — Thumbnails in chat for uploaded images
- **Agentic Mode Controls** — Configure Swarm agent count
- **Stop Generation** — Halt streaming responses mid-generation
- **Chat History** — All conversations saved with sidebar navigation
- **Mathematical Design** — Clean monospace UI with grid background and math symbols
- **Custom Provider Endpoints** — Override API base URLs in settings
- **One-Click Deploy** — Push to GitHub, connect to Render, done
- **Zero Cost** — Runs on Render.com free tier forever

## Deploy (5 minutes)

### Step 1: Get free API keys

You need at least **one** API key (or Ollama installed), but **more = better** (auto-failover works with multiple).

| Provider | Speed | Free Tier | Sign Up |
|----------|-------|-----------|---------|
| **Groq** | ~500 tok/s | 30 req/min, 14400/day | [console.groq.com/keys](https://console.groq.com/keys) |
| **OpenRouter** | varies | 50+ free models | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Cerebras** | ~1200 tok/s | Unlimited free | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| **Together AI** | ~150 tok/s | $5 free credits | [api.together.xyz](https://api.together.xyz/settings/api-keys) |
| **SambaNova** | ~200 tok/s | Free tier | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cohere** | ~100 tok/s | Free (rate limited) | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| **Ollama** | local GPU | 100% free, no key | [ollama.com](https://ollama.com) |

**Best setup**: Groq + Ollama + Cerebras + OpenRouter (local + cloud + speed + coverage)

### Step 2: Push to GitHub

Upload all files from this repo to your GitHub repository.

### Step 3: Deploy to Render

1. Go to [dashboard.render.com](https://dashboard.render.com) — sign up with GitHub
2. Click **New** → **Web Service**
3. Connect your repository
4. Render auto-detects `render.yaml` — leave defaults
5. Add environment variables for your API keys:
   - `GROQ_API_KEY` = your key
   - `OPENROUTER_API_KEY` = your key
   - `CEREBRAS_API_KEY` = your key (optional but recommended)
   - `TOGETHER_API_KEY` = your key (optional)
   - `SAMBANOVA_API_KEY` = your key (optional)
   - `COHERE_API_KEY` = your key (optional)
   - `OLLAMA_BASE_URL` = your URL (optional, for remote Ollama)
6. Click **Create Web Service**

Your app is live at `https://your-service.onrender.com`.

### Using Ollama (no API key needed!)

1. Install Ollama: [ollama.com](https://ollama.com)
2. Pull some models:
   ```bash
   ollama pull llama3.3:70b    # Large model
   ollama pull deepseek-r1:70b # Reasoning
   ollama pull mistral:7b       # Fast
   ollama pull qwen2.5:72b     # Big Chinese model
   ```
3. Start Ollama: `ollama serve` (default: `http://localhost:11434`)
4. MaisuClaw auto-detects Ollama at localhost — no configuration needed!
5. You can change the Ollama URL in Settings (gear icon)

**Tip**: Ollama is the best zero-config option. Install it, pull models, and it just works.

### Adding cloud provider keys later

You can add/remove API keys anytime from the in-app settings (gear icon) — no redeployment needed. Or add them in the Render dashboard Environment tab.

## How Auto-Failover Works

1. You send a message using model X on provider A
2. If provider A returns 429 (rate limited) or connection fails, MaisuClaw marks it as "cooling down" for 60 seconds
3. It automatically finds an equivalent model from provider B and retries
4. This happens transparently — you see a brief "Switching to..." message in the chat
5. After the cooldown period, provider A becomes available again

More API keys = more reliability. With all 7 providers configured, you effectively get unlimited free inference.

## Project Structure

```
maisuclaw/
├── app.py              # FastAPI + 7 providers + auto-failover + agents + swarm + uploads
├── static/
│   └── index.html      # Complete UI (multi-provider settings, Ollama auto-detect)
├── requirements.txt    # 5 pip packages
├── Procfile            # Render start command
├── render.yaml         # Auto-deploy config (7 env vars)
├── Dockerfile          # Docker option
├── runtime.txt         # Python version
├── .gitignore
└── README.md           # This file
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve UI |
| GET | `/api/status` | Provider status, available models, agents |
| GET | `/api/providers` | All provider info (for settings UI) |
| GET | `/api/ollama/models` | Auto-detect installed Ollama models |
| GET | `/api/conversations` | List all conversations |
| GET | `/api/conversations/{id}` | Get conversation + messages |
| POST | `/api/conversations` | Create new conversation |
| DELETE | `/api/conversations/{id}` | Delete conversation |
| POST | `/api/conversations/{id}/clear` | Clear messages |
| POST | `/api/upload` | Upload file (returns base64) |
| POST | `/api/chat` | Send message (SSE stream with auto-failover) |
| POST | `/api/stop` | Stop current generation |
| POST | `/api/settings` | Save API keys (all providers) |

## Models

### Groq (fastest cloud inference)
| Model | Speed | Tier |
|-------|-------|------|
| Llama 3.3 70B | ~500 tok/s | 3 |
| DeepSeek R1 70B | ~400 tok/s | 3 |
| Qwen QWQ 32B | ~400 tok/s | 3 |
| Llama 3 70B | ~500 tok/s | 3 |
| Mixtral 8x7B | ~450 tok/s | 2 |
| Gemma 2 9B | ~550 tok/s | 2 |
| Llama 3.1 8B | ~600 tok/s | 1 |

### Cerebras (ultra fast cloud)
| Model | Speed | Tier |
|-------|-------|------|
| Llama 3.3 70B | ~1200 tok/s | 3 |
| DeepSeek R1 70B | ~1200 tok/s | 3 |
| Llama 3.1 8B | ~1200 tok/s | 2 |

### OpenRouter (most cloud models, includes Gemini)
| Model | Tier | Vision |
|-------|------|--------|
| Gemini 2.0 Flash | 3 | Yes |
| DeepSeek R1 0528 | 3 | — |
| DeepSeek V3 | 3 | — |
| Qwen3 235B | 3 | — |
| Llama 4 Maverick | 3 | — |
| Mistral Small 3.1 | 2 | — |
| Gemma 3 27B | 2 | — |
| Phi-4 | 2 | — |

### Together AI (cloud)
| Model | Speed | Tier |
|-------|-------|------|
| Llama 3.3 70B Turbo | ~150 tok/s | 3 |
| DeepSeek R1 70B | ~150 tok/s | 3 |
| Qwen 2.5 72B Turbo | ~150 tok/s | 3 |
| Llama 3 70B | ~150 tok/s | 3 |
| Mixtral 8x7B | ~150 tok/s | 2 |

### SambaNova (cloud)
| Model | Speed | Tier |
|-------|-------|------|
| Llama 3.3 70B | ~200 tok/s | 3 |
| DeepSeek R1 70B | ~200 tok/s | 3 |
| Llama 3.1 8B | ~200 tok/s | 1 |

### Ollama (100% free, local GPU, no key)
| Model | Tier | Size |
|-------|------|------|
| Llama 3.3 70B | 3 | ~40GB |
| Qwen 2.5 72B | 3 | ~41GB |
| DeepSeek R1 70B | 3 | ~40GB |
| Gemma 2 27B | 2 | ~16GB |
| Mistral 7B | 2 | ~4.1GB |
| Phi-4 14B | 2 | ~7.6GB |
| CodeLlama 13B | 2 | ~7.4GB |
| Dolphin Mixtral 8x7B | 2 | ~26GB |
| Llama 3.1 8B | 1 | ~4.7GB |
| Starling LM 7B | 1 | ~4.1GB |
| TinyLlama 1.1B | 0 | ~0.7GB |

Any model pulled via `ollama pull <name>` will also work. Use the model name as the model ID.

### Cohere (cloud)
| Model | Speed | Tier |
|-------|-------|------|
| Command R+ | ~100 tok/s | 3 |
| Command R | ~100 tok/s | 2 |

## Local Development

```bash
pip install -r requirements.txt

# Option A: Use Ollama (easiest, no API keys)
ollama serve  # Start Ollama first
python app.py
# Open http://localhost:8000 — Ollama models auto-detected!

# Option B: Use cloud providers
export GROQ_API_KEY=gsk_xxx
export OPENROUTER_API_KEY=sk-or-xxx
export CEREBRAS_API_KEY=xxx
python app.py
# Open http://localhost:8000

# Option C: Mix both!
export GROQ_API_KEY=gsk_xxx
python app.py
# Ollama (localhost) + Groq (cloud) = auto-failover between local & cloud
```

## License

MIT
