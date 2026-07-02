#!/bin/bash
cd "$HOME/Applications/Codex_CLI_UI" || cd "$(dirname "$0")" || exit 1
python3 server.py
