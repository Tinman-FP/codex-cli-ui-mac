# Codex CLI UI for Mac v2026.07.07

Bugfix release for deterministic CAD artifact fallback on local load failures.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.07.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- CAD/Fusion design prompts now use the local CAD artifact tool before falling into the local model path.
- CAD load failures now stage Fusion 360, OpenSCAD, and README artifacts instead of returning generic runtime recovery text.
- CAD prompt recovery no longer drifts into Moonraker, live-printer status, or config-folder recovery wording.

## Added

- Direct `cad-artifact-tool` run path for CAD design requests.
- CAD load-failure package-health regression.
- CAD recovery answer that reports exact Fusion 360 script, OpenSCAD model, and README paths.

## Included

- `Codex CLI UI.app` launcher with red rounded icon
- Local browser UI runtime
- User LaunchAgent installer
- Fast, Careful, Coder, Review, Manager, and Local Research modes
- Web Access, access level, reasoning, friendliness, and humor controls
- Admin Improvement Lab, Golden Test Generator, Test Bench history, and package health checks
- Tool Recovery Engine and Capability Manager
- Autonomy Supervisor help-needed checker
- Klipper config discovery and macro-staging helpers
- CAD artifact staging helper for Fusion 360/OpenSCAD workflows
- Privacy-safe local data/log folders

## Requirements

- macOS
- Codex Desktop / Codex CLI
- Ollama
- `gpt-oss:20b`

Optional local models for the fuller free workflow:

```bash
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
```

## Notes

No personal chat history, machine inventory, raw passwords, or local network details are bundled. Private machine and printer details live only under each user's local `data/private/` folder.

This is an ad-hoc signed community package and is not Apple-notarized. Use right-click **Open** if macOS Gatekeeper blocks the installer or app.
