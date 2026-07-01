#!/bin/bash
set -euo pipefail

SERVICE_ID="com.tinmanfp.codex-cli-ui"
PLIST="$HOME/Library/LaunchAgents/$SERVICE_ID.plist"

echo "Stopping Codex CLI UI service"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true

echo "Removing app and runtime"
rm -rf "$HOME/Applications/Codex CLI UI.app"
rm -rf "$HOME/Applications/Codex_CLI_UI"
rm -f "$PLIST"

echo "Leaving ~/.codex profiles and ~/.local/bin shims in place."
echo "Done."
