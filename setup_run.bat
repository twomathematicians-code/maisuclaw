@echo off
title MaisuClaw v0.3.0
echo ============================================
echo   MaisuClaw v0.3.0 Starting...
echo ============================================
echo.

call venv\Scripts\activate.bat

:: Load .env if exists
if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set "%%a=%%b"
    )
)

echo [INFO] Starting server on http://localhost:8000
echo [INFO] Press Ctrl+C to stop
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
