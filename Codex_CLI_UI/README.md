# Codex CLI UI Runtime

Local browser UI for Codex CLI profiles backed by Ollama.

This folder is installed to:

```text
~/Applications/Codex_CLI_UI
```

The installer creates a user LaunchAgent that runs:

```text
http://127.0.0.1:8765
```

The UI provides:

- Chat-style browser interface for `codex exec`
- Sidebar for New Chat, Projects, and Chats
- Compact composer controls for Mode, Access, Reasoning, and Web
- Optional imported Codex history index stored locally in `data/`

Private chat history is not bundled. Users can import their own history after install with:

```bash
cd ~/Applications/Codex_CLI_UI
/usr/bin/python3 import_codex_history.py
```
