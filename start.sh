#!/bin/bash
# One-click start for Mac / Linux
cd "$(dirname "$0")"

echo "============================================"
echo "  STOCK DASHBOARD AGENT - ONE-CLICK START"
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 not found. Install it first (https://www.python.org/downloads/)"
    exit 1
fi

echo "[1/4] Installing core packages (one time only)..."
python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo "[2/4] Installing optional broker packages (safe to skip)..."
python3 -m pip install -r requirements-optional.txt --quiet --disable-pip-version-check || \
    echo "[INFO] Optional broker packages skipped - dashboard will still work."

echo "[3/4] Starting the dashboard..."
echo "[4/4] Opening your browser in 4 seconds..."
( sleep 4; open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null ) &

echo
echo "Dashboard running at: http://localhost:8000"
echo "Keep this window open. Press Ctrl+C to stop."
echo "============================================"
python3 app.py
