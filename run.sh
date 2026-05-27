#!/bin/bash
# MaisuClaw v0.3.0 - Run Script (Linux/Mac)

set -e

# Load .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activate venv
source venv/bin/activate

echo "============================================"
echo "  MaisuClaw v0.3.0 Starting..."
echo "============================================"
echo
echo "  Access: http://localhost:${MAISUCLAW_PORT:-8000}"
echo

exec python -m uvicorn main:app --host 0.0.0.0 --port ${MAISUCLAW_PORT:-8000} --reload
