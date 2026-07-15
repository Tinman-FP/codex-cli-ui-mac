#!/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/Applications/Codex_CLI_UI"
MISSING=()

if ! command -v python3 >/dev/null 2>&1; then
  MISSING+=("python3")
fi

if ! command -v ollama >/dev/null 2>&1; then
  MISSING+=("ollama")
fi

if ! command -v codex >/dev/null 2>&1 && [ ! -x "/Applications/ChatGPT.app/Contents/Resources/codex" ] && [ ! -x "/Applications/Codex.app/Contents/Resources/codex" ]; then
  MISSING+=("Codex CLI")
fi

mkdir -p "$HOME/Applications"

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
  mkdir -p "$TARGET_DIR"
  rsync -a \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'data' \
    --exclude 'logs' \
    --exclude 'build' \
    --exclude '.venv' \
    "$SOURCE_DIR"/ "$TARGET_DIR"/
fi

cd "$TARGET_DIR"
mkdir -p data logs

echo "Codex CLI UI installed at:"
echo "$TARGET_DIR"
echo

if [ "${CODEX_CLI_UI_INSTALL_SKIP_START:-0}" = "1" ]; then
  echo "Install check complete. Skipping server start because CODEX_CLI_UI_INSTALL_SKIP_START=1."
  exit 0
fi

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "Missing prerequisites:"
  for item in "${MISSING[@]}"; do
    echo "- $item"
  done
  echo
  echo "Install the missing free prerequisites, then run:"
  echo "cd \"$TARGET_DIR\" && python3 server.py"
  exit 0
fi

echo "Starting Codex CLI UI..."
python3 server.py &
SERVER_PID=$!
sleep 2

if curl -fsS "http://127.0.0.1:8765/api/config" >/dev/null 2>&1; then
  echo "Codex CLI UI is running at http://127.0.0.1:8765"
  open "http://127.0.0.1:8765" >/dev/null 2>&1 || true
else
  echo "The server did not answer yet. Check this process if needed: $SERVER_PID"
fi
