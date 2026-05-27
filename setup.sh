#!/bin/bash
# MaisuClaw v0.3.0 - Setup Script (Linux/Mac)

set -e

echo "============================================"
echo "  MaisuClaw v0.3.0 - Setup"
echo "============================================"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install Python 3.10+"
    exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv venv

echo "[2/4] Activating virtual environment..."
source venv/bin/activate

echo "[3/4] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[INFO] Created .env - edit it to add your API keys!"
else
    echo "[INFO] .env already exists, keeping it."
fi

echo
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo
echo "  Next steps:"
echo "  1. Edit .env to add API keys (optional)"
echo "  2. Start Ollama if using local models: ollama serve"
echo "  3. Run:  bash run.sh"
echo
