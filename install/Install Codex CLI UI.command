#!/bin/bash
set -euo pipefail

APP_NAME="Codex CLI UI"
SERVICE_ID="com.tinmanfp.codex-cli-ui"
PORT="8765"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/Codex_CLI_UI" ]; then
  BUNDLE_ROOT="$SCRIPT_DIR"
elif [ -d "$SCRIPT_DIR/../Codex_CLI_UI" ]; then
  BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  echo "Could not find Codex_CLI_UI next to this installer."
  exit 1
fi

RUNTIME_SRC="$BUNDLE_ROOT/Codex_CLI_UI"
APP_SRC="$BUNDLE_ROOT/$APP_NAME.app"
INSTALL_ROOT="$HOME/Applications"
RUNTIME_DEST="$INSTALL_ROOT/Codex_CLI_UI"
APP_DEST="$INSTALL_ROOT/$APP_NAME.app"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENT_DIR/$SERVICE_ID.plist"
CODEX_HOME="$HOME/.codex"
LOCAL_BIN="$HOME/.local/bin"
DEFAULT_CWD="$HOME/Documents/Codex"

echo "Installing $APP_NAME for $USER"
mkdir -p "$INSTALL_ROOT" "$LAUNCH_AGENT_DIR" "$CODEX_HOME" "$LOCAL_BIN" "$DEFAULT_CWD"

if [ ! -d "$APP_SRC" ]; then
  echo "Missing $APP_SRC"
  exit 1
fi

echo "Copying runtime to $RUNTIME_DEST"
rm -rf "$RUNTIME_DEST"
/usr/bin/ditto "$RUNTIME_SRC" "$RUNTIME_DEST"
mkdir -p "$RUNTIME_DEST/data" "$RUNTIME_DEST/logs"

echo "Copying app to $APP_DEST"
rm -rf "$APP_DEST"
/usr/bin/ditto "$APP_SRC" "$APP_DEST"

CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
if [ -x "$CODEX_BIN" ]; then
  ln -sf "$CODEX_BIN" "$LOCAL_BIN/codex"
else
  echo
  echo "Warning: Codex Desktop was not found at $CODEX_BIN"
  echo "Install the Codex app first, then rerun this installer or update PATH manually."
fi

cat > "$LOCAL_BIN/codex-fast" <<'SCRIPT'
#!/bin/bash
exec codex --profile local-fast "$@"
SCRIPT
cat > "$LOCAL_BIN/codex-careful" <<'SCRIPT'
#!/bin/bash
exec codex --profile local-oss "$@"
SCRIPT
chmod +x "$LOCAL_BIN/codex-fast" "$LOCAL_BIN/codex-careful"

PROFILE_PATH_VALUE="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/Applications/Codex.app/Contents/Resources:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin"

create_profile_if_missing() {
  local file="$1"
  local reasoning="$2"
  local comment="$3"
  if [ -f "$file" ]; then
    echo "Keeping existing profile: $file"
    return
  fi
  cat > "$file" <<PROFILE
# $comment
model = "gpt-oss-20b"
model_provider = "ollama"
oss_provider = "ollama"
model_reasoning_effort = "$reasoning"
hide_agent_reasoning = true
sandbox_mode = "danger-full-access"
approval_policy = "on-request"
web_search = "live"

[shell_environment_policy]
inherit = "core"
set = { PATH = "$PROFILE_PATH_VALUE" }

[projects."$DEFAULT_CWD"]
trust_level = "trusted"
PROFILE
  echo "Created profile: $file"
}

create_profile_if_missing "$CODEX_HOME/local-fast.config.toml" "low" "Fast local OSS Codex profile. Use with: codex --profile local-fast"
create_profile_if_missing "$CODEX_HOME/local-oss.config.toml" "medium" "Careful local OSS Codex profile. Use with: codex --profile local-oss"

PATH_MARKER="# Codex CLI UI local bin"
for shell_file in "$HOME/.zprofile" "$HOME/.zshrc"; do
  touch "$shell_file"
  if ! grep -q "$PATH_MARKER" "$shell_file"; then
    {
      echo ""
      echo "$PATH_MARKER"
      echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$shell_file"
  fi
done

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$SERVICE_ID</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$RUNTIME_DEST/server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$RUNTIME_DEST</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CODEX_PROFILE</key>
    <string>local-fast</string>
    <key>CODEX_CWD</key>
    <string>$DEFAULT_CWD</string>
    <key>CODEX_WEB_SEARCH</key>
    <string>live</string>
    <key>CODEX_UI_HOST</key>
    <string>127.0.0.1</string>
    <key>CODEX_UI_PORT</key>
    <string>$PORT</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$RUNTIME_DEST/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$RUNTIME_DEST/logs/launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || launchctl load "$PLIST" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/$SERVICE_ID" >/dev/null 2>&1 || true

echo
echo "Dependency check:"
if [ -x "$CODEX_BIN" ] || command -v codex >/dev/null 2>&1; then
  echo "  ✓ Codex CLI found"
else
  echo "  ! Codex CLI not found. Install Codex Desktop from OpenAI."
fi

if command -v ollama >/dev/null 2>&1; then
  echo "  ✓ Ollama found"
  if ollama list 2>/dev/null | grep -Eq 'gpt-oss.*20b|gpt-oss-20b'; then
    echo "  ✓ gpt-oss 20B model found"
  else
    echo "  ! gpt-oss 20B model not found. Run: ollama pull gpt-oss:20b"
  fi
else
  echo "  ! Ollama not found. Install Ollama, then run: ollama pull gpt-oss:20b"
fi

echo
echo "Opening $APP_NAME..."
open "$APP_DEST"
echo "Installed. UI URL: http://127.0.0.1:$PORT"
