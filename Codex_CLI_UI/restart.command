#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${CODEX_UI_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
NATIVE_APP_PATH="${CODEX_CLI_UI_NATIVE_APP_PATH:-$APP_DIR/build/Codex CLI UI.app}"
LAUNCH_AGENT_LABEL="${CODEX_CLI_UI_LAUNCH_AGENT_LABEL:-com.localuser.codex-cli-ui}"
LAUNCH_AGENT_DOMAIN="gui/$(id -u)/${LAUNCH_AGENT_LABEL}"

cd "$APP_DIR"
mkdir -p data logs

open_ui_shell() {
  if [ "${CODEX_CLI_UI_OPEN_BROWSER:-0}" = "1" ]; then
    open "$URL" >/dev/null 2>&1 || true
    return
  fi

  if [ "${CODEX_CLI_UI_OPEN_NATIVE:-1}" = "1" ]; then
    if [ -d "$NATIVE_APP_PATH" ]; then
      open "$NATIVE_APP_PATH" >/dev/null 2>&1 || true
      return
    fi
    if open -a "Codex CLI UI" >/dev/null 2>&1; then
      return
    fi
  fi

  echo "Native app window was not opened automatically. URL remains available at $URL"
}

if launchctl print "$LAUNCH_AGENT_DOMAIN" >/dev/null 2>&1; then
  echo "Restarting Codex CLI UI LaunchAgent ${LAUNCH_AGENT_LABEL}..."
  launchctl kickstart -k "$LAUNCH_AGENT_DOMAIN"
  sleep 2
  if curl -fsS "$URL/api/config" >/dev/null 2>&1; then
    LISTENER_PID="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
    if [ -n "$LISTENER_PID" ]; then
      echo "$LISTENER_PID" > data/server.pid
    fi
    echo "Codex CLI UI is running at $URL"
    open_ui_shell
    exit 0
  fi
  echo "LaunchAgent restarted, but the server did not answer yet. Falling back to manual restart."
fi

PIDS="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  for PID in $PIDS; do
    COMMAND="$(ps -p "$PID" -o command= 2>/dev/null || true)"
    PROCESS_CWD="$(lsof -a -p "$PID" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
    if [[ "$COMMAND" == *"$APP_DIR/server.py"* ]] || { [[ "$COMMAND" == *"server.py"* ]] && [ "$PROCESS_CWD" = "$APP_DIR" ]; }; then
      echo "Stopping Codex CLI UI server $PID..."
      kill "$PID" 2>/dev/null || true
    else
      echo "Port $PORT is already used by another process:"
      echo "$COMMAND"
      echo "Not stopping it automatically."
      exit 1
    fi
  done
fi

for _ in {1..30}; do
  if ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo "Starting Codex CLI UI at $URL..."
LAUNCH_PID="$(python3 - <<'PY'
import os
import subprocess

log = open("logs/server.log", "ab", buffering=0)
proc = subprocess.Popen(
    ["python3", "server.py"],
    cwd=os.getcwd(),
    stdout=log,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
)
print(proc.pid)
PY
)"
sleep 2

if curl -fsS "$URL/api/config" >/dev/null 2>&1; then
  LISTENER_PID="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  echo "${LISTENER_PID:-$LAUNCH_PID}" > data/server.pid
  echo "Codex CLI UI is running at $URL"
  open_ui_shell
else
  echo "The server did not answer yet. Check logs/server.log and PID $LAUNCH_PID."
  exit 1
fi
