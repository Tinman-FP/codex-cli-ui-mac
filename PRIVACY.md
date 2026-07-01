# Privacy

This release is built to avoid shipping private local state.

Bundled:

- UI source files
- Red app icon
- Installer and uninstaller
- Empty `data/` and `logs/` folders

Not bundled:

- Imported Codex chat history
- `~/.codex/sessions`
- Printer/VPN endpoints
- Local logs from the developer machine
- API keys or tokens

The UI runs on `127.0.0.1` and stores optional imported history under the installing user's `~/Applications/Codex_CLI_UI/data` folder.
