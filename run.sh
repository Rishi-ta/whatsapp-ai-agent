#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

VENV_BIN="$(pwd)/venv/bin"
if [ ! -x "$VENV_BIN/python" ]; then
  echo "Virtual environment is missing or not executable. Recreating..."
  rm -rf venv
  python3 -m venv venv
fi

# Activate virtual environment for this script
source "$VENV_BIN/activate"

if [ ! -f requirements.txt ]; then
  echo "requirements.txt not found. Cannot install dependencies."
  exit 1
fi

pip install --upgrade pip
pip install -r requirements.txt
pip install --force-reinstall "fastapi==0.111.0" "starlette==0.37.2" "uvicorn[standard]==0.30.1"

echo "Starting uvicorn from the virtual environment..."
exec "$VENV_BIN/uvicorn" app.main:app --reload --port 8000