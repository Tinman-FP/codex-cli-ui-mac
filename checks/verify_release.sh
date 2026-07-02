#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Checking scripts"
bash -n "$ROOT/install/Install Codex CLI UI.command"
bash -n "$ROOT/install/Uninstall Codex CLI UI.command"

echo "Checking Python"
/usr/bin/python3 -m py_compile "$ROOT/Codex_CLI_UI/server.py" "$ROOT/Codex_CLI_UI/import_codex_history.py"

if [ -x /Applications/Codex.app/Contents/Resources/cua_node/bin/node ]; then
  /Applications/Codex.app/Contents/Resources/cua_node/bin/node --check "$ROOT/Codex_CLI_UI/app.js"
elif command -v node >/dev/null 2>&1; then
  node --check "$ROOT/Codex_CLI_UI/app.js"
else
  echo "Warning: node not found, skipping app.js syntax check"
fi

echo "Checking public-package privacy patterns"
if find "$ROOT" -name .git -prune -o -type f \( -name 'codex_history_index.jsonl' -o -name 'codex_history_summary.json' \) -print | grep -q .; then
  echo "Private history files are present"
  exit 1
fi

if rg -n --hidden --glob '!.git' --glob '!.git/**' --glob '!**/checks/verify_release.sh' --glob '!release/*.dmg' --glob '!*.icns' --glob '!*.png' \
  'williamtinney|/Users/williamtinney|192\.168\.|makersvpn|gho_|QIDI@|Flightops_Tracker' "$ROOT"; then
  echo "Privacy scan found a blocked pattern"
  exit 1
fi

echo "Checking app signature if present"
if [ -d "$ROOT/app/Codex CLI UI.app" ]; then
  codesign --verify --deep --strict "$ROOT/app/Codex CLI UI.app"
fi

echo "Release verification passed"
