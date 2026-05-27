#!/usr/bin/env bash
# ── maisuclaw setup script ──────────────────────────────────
# Run this once after cloning the repo:
#   chmod +x setup.sh && ./setup.sh

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       maisuclaw  setup  v0.1         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "  [ERROR] python3 not found. Install Python 3.10+ first."
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  [OK] Python $PYVER found"

# 2. Create venv
if [ ! -d "venv" ]; then
    echo "  [..] Creating virtual environment..."
    python3 -m venv venv
fi
echo "  [OK] Virtual environment ready"

# 3. Activate
source venv/bin/activate

# 4. Install Python deps
echo "  [..] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  [OK] Python packages installed"

# 5. Create data directory
mkdir -p data/uploads
echo "  [OK] data/ directories created"

# 6. Check Ollama
echo ""
if command -v ollama &> /dev/null; then
    echo "  [OK] Ollama found"

    # Pull models
    echo "  [..] Pulling models (this may take a while)..."
    for model in qwen2.5-coder:7b gemma2:9b phi3.5 nomic-embed-text; do
        if ollama list | grep -q "$model"; then
            echo "  [OK] $model already present"
        else
            echo "  [..] Pulling $model..."
            ollama pull "$model" 2>&1 | tail -1
        fi
    done

    # Whisper (optional)
    if ollama list | grep -q "whisper"; then
        echo "  [OK] whisper already present"
    else
        echo "  [..] Pulling whisper:small (optional, for voice input)..."
        ollama pull whisper:small 2>&1 | tail -1
    fi
else
    echo "  [WARN] Ollama not found."
    echo "         Install it from https://ollama.ai"
    echo "         Then run: ollama pull qwen2.5-coder:7b gemma2:9b phi3.5 nomic-embed-text"
fi

# 7. Playwright (optional)
echo ""
read -p "  Install Playwright for web search? (y/n): " INSTALL_PW
if [ "$INSTALL_PW" = "y" ]; then
    echo "  [..] Installing Playwright browsers..."
    playwright install chromium 2>&1 | tail -1
    echo "  [OK] Playwright ready"
else
    echo "  [--] Skipping Playwright"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       Setup complete!                ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  To start maisuclaw:"
echo ""
echo "    source venv/bin/activate"
echo "    uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  Then open http://localhost:8000 in your browser."
echo "  From your phone: http://<your-laptop-ip>:8000"
echo ""
