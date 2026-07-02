# Codex CLI UI for Mac v2026.07.09

Bugfix release for direct CPAP hose sizing answers.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.09.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- CPAP hose inner-diameter questions no longer generate Fusion 360/OpenSCAD CAD packages.
- CPAP hose sizing now routes as a parts/spec question rather than CAD/Modeling.
- Direct measurement questions now answer first instead of handing the prompt to the local model.

## Added

- Direct answer for CPAP hose sizing: 19 mm ID standard, 15 mm ID slimline, and 22 mm common cuff/connector.
- `spec-direct-answer` path for CPAP hose measurement questions.
- Package-health regression for CPAP hose ID questions.

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
