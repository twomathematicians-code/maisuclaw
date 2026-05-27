@echo off
title MaisuClaw v0.3.0 Setup
echo ============================================
echo   MaisuClaw v0.3.0 - Setup Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [4/4] Creating .env file...
if not exist .env (
    copy .env.example .env
    echo [INFO] Created .env from .env.example - edit it to add your API keys!
) else (
    echo [INFO] .env already exists, keeping it.
)

echo.
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo   Next steps:
echo   1. Edit .env to add your Groq/OpenRouter API keys (optional)
echo   2. Start Ollama if using local models:  ollama serve
echo   3. Run:  setup_run.bat
echo.
pause
