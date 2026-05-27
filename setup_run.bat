@echo off
echo.
echo  Starting maisuclaw...
echo.

:: Activate venv
if not exist "venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

:: Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
