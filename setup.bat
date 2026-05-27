@echo off
chcp 65001 >nul 2>&1
echo.
echo  ====================================================
echo         maisuclaw  setup  v0.3  (Windows)
echo  ====================================================
echo.

:: 1. Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% found

:: 2. Create virtual environment
if not exist "venv" (
    echo  [..] Creating virtual environment...
    python -m venv venv
) else (
    echo  [OK] Virtual environment already exists
)

:: 3. Activate
call venv\Scripts\activate.bat
echo  [OK] Virtual environment activated

:: 4. Install Python packages
echo  [..] Installing Python packages...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo  [OK] Python packages installed

:: 5. Create data directories
if not exist "data\uploads" mkdir data\uploads
echo  [OK] data\ directories created

:: 6. Check Ollama
echo.
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Ollama found
    echo.
    echo  Pulling model tiers (this will take a while the first time)...
    echo.

    echo  [1/8] qwen2.5:0.5b  (instant - ultra fast)
    ollama pull qwen2.5:0.5b
    echo  [OK] Instant model ready

    echo  [2/8] phi3.5  (fast - quick answers)
    ollama pull phi3.5
    echo  [OK] Fast model ready

    echo  [3/8] gemma2:9b  (balanced - general assistant)
    ollama pull gemma2:9b
    echo  [OK] Balanced model ready

    echo  [4/8] qwen2.5-coder:7b  (coder - programming)
    ollama pull qwen2.5-coder:7b
    echo  [OK] Coder model ready

    echo  [5/8] qwen2.5:14b  (powerful - best quality)
    ollama pull qwen2.5:14b
    echo  [OK] Powerful model ready

    echo  [6/8] llava:13b  (vision - image and PDF analysis)
    ollama pull llava:13b
    echo  [OK] Vision model ready

    echo  [7/8] nomic-embed-text  (embeddings for RAG)
    ollama pull nomic-embed-text
    echo  [OK] Embedding model ready

    echo  [8/8] whisper:small  (voice input)
    ollama pull whisper:small
    echo  [OK] Whisper ready

    echo.
    echo  ====================================================
    echo   All 8 models pulled!
    echo  ====================================================
    echo.
    echo  OPTIONAL - pull these for extra power:
    echo    ollama pull deepseek-r1:8b    (reasoning / thinking)
    echo    ollama pull minicpm-v:8b      (lighter vision model)
    echo    ollama pull llama3.1:8b       (alternative general model)
    echo    ollama pull mistral:7b         (fast and capable)
    echo.

) else (
    echo  [WARN] Ollama not found.
    echo         Download it from https://ollama.com/download
    echo.
    echo         After installing, open Ollama and run:
    echo           ollama pull qwen2.5:0.5b
    echo           ollama pull phi3.5
    echo           ollama pull gemma2:9b
    echo           ollama pull qwen2.5-coder:7b
    echo           ollama pull qwen2.5:14b
    echo           ollama pull llava:13b
    echo           ollama pull nomic-embed-text
    echo           ollama pull whisper:small
)

:: 7. Playwright (optional)
echo.
set /p INSTALL_PW="  Install Playwright for web search and browsing? (y/n): "
if /i "%INSTALL_PW%"=="y" (
    echo  [..] Installing Playwright browsers...
    playwright install chromium
    echo  [OK] Playwright ready
) else (
    echo  [--] Skipping Playwright
)

echo.
echo  ====================================================
echo         Setup complete! (v0.3)
echo  ====================================================
echo.
echo  To start maisuclaw:
echo    setup_run.bat
echo.
echo  For remote access (use from anywhere):
echo    scripts\cloudflare_tunnel.bat
echo.
echo  To upload files, paste screenshots, or do research:
echo    Open http://localhost:8000 and use the UI
echo.
pause
