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
mkdir -p "$RUNTIME_DEST/data/private" "$RUNTIME_DEST/logs"

PRIVATE_INVENTORY="$RUNTIME_DEST/data/private/machines.json"
if [ ! -f "$PRIVATE_INVENTORY" ]; then
  cat > "$PRIVATE_INVENTORY" <<'JSON'
{
  "preferred_name": "",
  "password_policy": "Do not store raw SSH passwords here. Store passwords in macOS Keychain and reference the Keychain service/account fields instead.",
  "machines": []
}
JSON
  chmod 600 "$PRIVATE_INVENTORY"
fi

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
cat > "$LOCAL_BIN/qblade-import" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

version="${QBLADE_VERSION:-2.0.9.7}"
name="QBladeCE_${version}_linux"
install_root="${QBLADE_LINUX_HOME:-$HOME/.local/aero-tools/qblade-linux}"
downloads_root="${QBLADE_DOWNLOADS_DIR:-$HOME/Downloads}"
archive_store="$HOME/Downloads/codex-aero-installs"
watch=0
timeout=900

usage() {
  cat <<EOF
Usage: qblade-import [--watch] [--timeout seconds] [archive]

Validates and imports the official QBlade CE Linux archive into:
  $install_root

If no archive is supplied it scans:
  $downloads_root
  $archive_store

The official browser download currently comes from:
  https://qblade.org/downloads/

QBlade CE is licensed for non-commercial/evaluation use under QBlade's
Academic Public License. Commercial work requires QBlade EE.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)
      watch=1
      shift
      ;;
    --timeout)
      timeout="${2:-900}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      archive_arg="$1"
      shift
      ;;
  esac
done

candidate_files() {
  if [[ -n "${archive_arg:-}" ]]; then
    printf '%s\n' "$archive_arg"
    return
  fi
  find "$downloads_root" "$archive_store" -maxdepth 2 -type f \
    \( -iname "${name}*" -o -iname "Unconfirmed*.crdownload" -o -iname "*QBladeCE*linux*" \) \
    -print 2>/dev/null | sort -ru
}

archive_ok() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  file "$file" | grep -Eq 'tar archive|Zip archive|data' || return 1
  local list_file error_file
  list_file="$(mktemp /tmp/qblade-import-list.XXXXXX)"
  error_file="$(mktemp /tmp/qblade-import-error.XXXXXX)"
  if ! tar -tf "$file" >"$list_file" 2>"$error_file"; then
    rm -f "$list_file" "$error_file"
    return 1
  fi
  if ! grep -q "QBladeCE_${version}/QBladeCE_${version}$" "$list_file"; then
    rm -f "$list_file" "$error_file"
    return 1
  fi
  if ! grep -q "QBladeCE_${version}/libQBladeCE_${version}.so.1.0.0$" "$list_file"; then
    rm -f "$list_file" "$error_file"
    return 1
  fi
  rm -f "$list_file" "$error_file"
}

import_archive() {
  local file="$1"
  mkdir -p "$install_root" "$archive_store"
  local saved="$archive_store/${name}.tar"
  cp "$file" "$saved"
  rm -rf "$install_root/QBladeCE_${version}" "$install_root/current"
  tar -xf "$saved" -C "$install_root"
  chmod +x "$install_root/QBladeCE_${version}/QBladeCE_${version}" || true
  find "$install_root/QBladeCE_${version}/Binaries" -type f -perm -111 -exec chmod +x {} + 2>/dev/null || true
  {
    echo "version=$version"
    echo "archive=$saved"
    shasum -a 256 "$saved" | awk '{print "sha256="$1}'
    echo "imported_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$install_root/QBladeCE_${version}/IMPORT_OK"
  ln -sfn "$install_root/QBladeCE_${version}" "$install_root/current"
  echo "Imported QBlade CE ${version}: $install_root/QBladeCE_${version}"
  echo "Archive saved: $saved"
}

try_once() {
  local found=0
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    found=1
    if archive_ok "$file"; then
      import_archive "$file"
      return 0
    fi
    size=$(wc -c < "$file" 2>/dev/null || echo 0)
    echo "Not ready or incomplete: $file (${size} bytes)"
  done < <(candidate_files)
  if [[ "$found" -eq 0 ]]; then
    echo "No QBlade archive found yet."
  fi
  return 1
}

if [[ "$watch" -eq 0 ]]; then
  try_once
  exit $?
fi

echo "Watching for a complete official QBlade CE Linux download..."
echo "Open https://qblade.org/downloads/ and download ${name}."
deadline=$((SECONDS + timeout))
while (( SECONDS < deadline )); do
  if try_once; then
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for a complete QBlade archive."
exit 2
SCRIPT
cat > "$LOCAL_BIN/qblade-linux" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

version="${QBLADE_VERSION:-2.0.9.7}"
base="${QBLADE_LINUX_HOME:-$HOME/.local/aero-tools/qblade-linux}"
docker_image="${QBLADE_DOCKER_IMAGE:-tinman/qblade-ce-runner:2.0.9.7}"
candidate=""

for path in \
  "$base/current/QBladeCE_${version}" \
  "$base/QBladeCE_${version}/QBladeCE_${version}" \
  "$base/QBladeCE" \
  "$base/QBladeCE/QBladeCE" \
  "$base/QBladeCE_2.0.9.7_linux/QBladeCE" \
  "$base/QBladeCE_2.0.9.7_linux/QBladeCE/QBladeCE"
do
  if [[ -x "$path" ]]; then
    candidate="$path"
    break
  fi
done

if [[ -n "$candidate" && ! -f "$(dirname "$candidate")/IMPORT_OK" ]]; then
  candidate=""
fi

status() {
  echo "QBlade CE Linux status"
  echo "  base: $base"
  echo "  executable: ${candidate:-missing}"
  if [[ -n "$candidate" ]]; then
    file "$candidate" | sed 's/^/  file: /'
  fi
  if [[ -x "$(command -v docker || true)" ]]; then
    if docker image inspect "$docker_image" >/dev/null 2>&1; then
      echo "  docker runner: $docker_image"
    else
      echo "  docker runner: missing ($docker_image)"
    fi
  else
    echo "  docker: missing"
  fi
}

case "${1:-}" in
  --status)
    status
    exit 0
    ;;
  --install-help)
    cat <<EOF
Download the official QBlade CE Linux package in a browser:
  https://qblade.org/downloads/

Then run:
  qblade-import --watch

QBlade CE is governed by QBlade's Academic Public License and is limited to
non-commercial/evaluation use. Commercial work needs QBlade EE.
EOF
    exit 0
    ;;
esac

if [[ -z "$candidate" ]]; then
  cat <<'EOF'
QBlade Linux package is not installed yet.

Download the official QBlade Community Edition Linux package in a browser:
  https://qblade.org/downloads/

Then run:
  qblade-import

If the browser leaves an Unconfirmed .crdownload file, run:
  qblade-import --watch

Note: QBlade CE is governed by QBlade's Academic Public License and is limited
to non-commercial/evaluation use. Commercial work needs QBlade EE.
EOF
  exit 2
fi

if ! file "$candidate" | grep -q 'ELF 64-bit.*x86-64'; then
  echo "QBlade executable is present but is not the expected Linux x86-64 build:"
  file "$candidate"
  exit 3
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "QBlade CE is a Linux x86-64 binary. Docker is required to run it on this Mac."
    exit 4
  fi
  if ! docker image inspect "$docker_image" >/dev/null 2>&1; then
    cat <<EOF
QBlade is installed, but the Linux runner image is missing:
  $docker_image

Build it with:
  qblade-runner-build
EOF
    exit 5
  fi
  rel_dir="$(dirname "${candidate#$base/}")"
  exec docker run --rm --platform linux/amd64 \
    -e QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
    -e LD_LIBRARY_PATH="/qblade/$rel_dir:/qblade/$rel_dir/Libraries:/qblade/$rel_dir/Binaries" \
    -v "$base:/qblade:ro" \
    -w "/qblade/$rel_dir" \
    "$docker_image" \
    "./$(basename "$candidate")" "$@"
fi

exec "$candidate" "$@"
SCRIPT
cat > "$LOCAL_BIN/qblade-runner-build" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

image="${QBLADE_DOCKER_IMAGE:-tinman/qblade-ce-runner:2.0.9.7}"
context="$(mktemp -d /tmp/qblade-runner-build.XXXXXX)"
trap 'rm -rf "$context"' EXIT

cat > "$context/Dockerfile" <<'EOF'
FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libasound2 \
    libdbus-1-3 \
    libegl1 \
    libfontconfig1 \
    libfreetype6 \
    libgl1 \
    libglib2.0-0 \
    libglu1-mesa \
    libgomp1 \
    libice6 \
    libnss3 \
    libopengl0 \
    libsm6 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-glx0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxext6 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxrender1 \
    libxt6 \
    && rm -rf /var/lib/apt/lists/*
EOF

docker build --platform linux/amd64 -t "$image" "$context"
echo "Built QBlade runner image: $image"
SCRIPT
ln -sf "$LOCAL_BIN/qblade-linux" "$LOCAL_BIN/qblade"
chmod +x "$LOCAL_BIN/codex-fast" "$LOCAL_BIN/codex-careful" "$LOCAL_BIN/qblade-import" "$LOCAL_BIN/qblade-linux" "$LOCAL_BIN/qblade-runner-build"

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
