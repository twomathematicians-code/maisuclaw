@echo off
chcp 65001 >nul 2>&1
echo.
echo  ====================================================
echo         maisuclaw  setup  v0.1  (Windows)
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

    echo  [..] Pulling models (this may take a while)...
    ollama pull qwen2.5-coder:7b 2>nul
    ollama pull gemma2:9b 2>nul
    ollama pull phi3.5 2>nul
    ollama pull nomic-embed-text 2>nul
    echo  [OK] Core models pulled

    echo  [..] Pulling whisper:small (optional, for voice)...
    ollama pull whisper:small 2>nul
    echo  [OK] Whisper pulled
) else (
    echo  [WARN] Ollama not found.
    echo         Download it from https://ollama.com/download
    echo         Then open Ollama and run:
    echo           ollama pull qwen2.5-coder:7b
    echo           ollama pull gemma2:9b
    echo           ollama pull phi3.5
    echo           ollama pull nomic-embed-text
    echo           ollama pull whisper:small
)

:: 7. Playwright (optional)
echo.
set /p INSTALL_PW="  Install Playwright for web search? (y/n): "
if /i "%INSTALL_PW%"=="y" (
    echo  [..] Installing Playwright browsers...
    playwright install chromium
    echo  [OK] Playwright ready
) else (
    echo  [--] Skipping Playwright
)

echo.
echo  ====================================================
echo         Setup complete!
echo  ====================================================
echo.
echo  To start maisuclaw, run:
echo.
echo    setup_run.bat
echo.
echo  Or manually:
echo    venv\Scripts\activate
echo    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo  Then open http://localhost:8000 in your browser.
echo  From your phone: http://YOUR-LAP-IP:8000
echo.
pause
