# Install Guide

1. Install Codex Desktop from OpenAI.
2. Install Ollama.
3. Pull the local OSS model:

   ```bash
   ollama pull gpt-oss:20b
   ```

4. Open `Codex_CLI_UI_Mac_v2026.07.06.dmg`.
5. Double-click `Install Codex CLI UI.command`.
6. Open `Codex CLI UI.app` from `~/Applications`.

The UI runs locally at:

```text
http://127.0.0.1:8765
```

If the app does not start, run:

```bash
launchctl kickstart -k gui/$(id -u)/com.tinmanfp.codex-cli-ui
open ~/Applications/Codex\ CLI\ UI.app
```
