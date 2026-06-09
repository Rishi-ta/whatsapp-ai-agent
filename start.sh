#!/usr/bin/env bash
set -euo pipefail

# start.sh - convenience script to stop conflicting processes and start uvicorn + ngrok
# Usage: ./start.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Activate or create venv
if [ -f "venv/bin/activate" ]; then
  echo "Activating existing virtualenv..."
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "No virtualenv found. Creating venv and installing dependencies..."
  python3 -m venv venv
  # shellcheck disable=SC1091
  source venv/bin/activate
  if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
  fi
fi

# Free port 8000 if in use
echo "Checking for processes listening on port 8000..."
pkill -f uvicorn || true
PORT_PIDS=$(lsof -t -iTCP:8000 -sTCP:LISTEN || true)
if [ -n "$PORT_PIDS" ]; then
  echo "Killing processes on port 8000: $PORT_PIDS"
  kill $PORT_PIDS || kill -9 $PORT_PIDS || true
else
  echo "Port 8000 is free."
fi

# Stop any running ngrok processes
echo "Stopping any running ngrok processes..."
pkill -f ngrok || true

# Start uvicorn in background and save logs
echo "Starting uvicorn..."
nohup uvicorn app.main:app --reload --port 8000 > uvicorn.log 2>&1 &
UVICORN_PID=$!
sleep 1

# Start ngrok in background if available
if command -v ngrok >/dev/null 2>&1; then
  echo "Starting ngrok..."
  nohup ngrok http 8000 --pooling-enabled > ngrok.log 2>&1 &
  NGROK_PID=$!
  sleep 2
else
  echo "ngrok not installed or not on PATH. Install ngrok or start it manually: https://ngrok.com/download"
fi

# Show status
echo "--- STATUS ---"
echo "Uvicorn PID: ${UVICORN_PID:-N/A}"
if [ -n "${NGROK_PID:-}" ]; then
  echo "ngrok PID: ${NGROK_PID}"
fi

echo "Processes listening on 8000:"
lsof -nP -iTCP:8000 -sTCP:LISTEN || echo "none"

echo "ngrok tunnels (if ngrok running):"
if command -v curl >/dev/null 2>&1; then
  curl --silent http://127.0.0.1:4040/api/tunnels || echo "no ngrok API available"
else
  echo "curl not available to query ngrok API"
fi

echo "Uvicorn log (last 20 lines):"
tail -n 20 uvicorn.log || true

echo "ngrok log (last 20 lines):"
tail -n 20 ngrok.log || true

echo "Done. Use 'tail -f uvicorn.log' and 'tail -f ngrok.log' to follow logs."