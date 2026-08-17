@echo off
title Stock Dashboard Agent
color 0B
cd /d "%~dp0"

echo ============================================
echo   STOCK DASHBOARD AGENT  -  ONE-CLICK START
echo ============================================
echo.

REM ---- check Python ----
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found.
    echo.
    echo 1. Go to https://www.python.org/downloads/
    echo 2. Download and install Python.
    echo 3. DURING INSTALL, TICK THE BOX:  "Add Python to PATH"
    echo 4. Run this file again.
    echo.
    pause
    exit /b 1
)

echo [1/4] Installing core packages (one time only)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [WARNING] Retrying package install with full output...
    python -m pip install -r requirements.txt
)

echo [2/4] Installing optional broker packages (safe to skip)...
python -m pip install -r requirements-optional.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [INFO] Optional broker packages skipped - dashboard will still work.
    echo         Install them later if you connect Zerodha or Angel One.
)

echo [3/4] Starting the dashboard...
echo [4/4] Opening your browser in 4 seconds...
start "Opening browser" cmd /c "timeout /t 4 >nul & start http://localhost:8000"

echo.
echo The dashboard is running at:  http://localhost:8000
echo Keep THIS window open. To stop, press  Ctrl+C
echo ============================================
python app.py

pause
