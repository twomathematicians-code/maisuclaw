@echo off
:: maisuclaw — Cloudflare Tunnel (quick tunnel)
:: Creates a public URL to access maisuclaw from anywhere
::
:: Prerequisites:
::   1. Install cloudflared from https://github.com/cloudflare/cloudflared/releases
::   2. Have maisuclaw running (setup_run.bat)

echo.
echo  ====================================================
echo    maisuclaw — Cloudflare Quick Tunnel
echo  ====================================================
echo.
echo  This will create a temporary public URL for your maisuclaw instance.
echo  Anyone with the URL can access it.
echo.

where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] cloudflared not found.
    echo.
    echo  Install it from:
    echo  https://github.com/cloudflare/cloudflared/releases
    echo.
    echo  Download: cloudflared-windows-amd64.msi
    pause
    exit /b 1
)

echo  Starting tunnel...
echo  (Press Ctrl+C to stop)
echo.

cloudflared tunnel --url http://localhost:8000

pause
