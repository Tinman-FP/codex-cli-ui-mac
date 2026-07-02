# Codex CLI UI for Mac v2026.07.10

Bugfix release for cooling-duct research routing.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.10.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- Cooling-duct research prompts no longer generate Fusion 360/OpenSCAD CAD packages.
- Follow-up corrections like "look at Printables and GitHub for inspiration" now route to research instead of staging another weak duct.
- GitHub in this research context is treated as public design evidence, not local repo work.

## Added

- `cad-research-direct-answer` path for part-cooling duct research.
- Reusable source-backed cooling-duct playbook with CFD, Printables, GitHub, CPAP, and material-cooling guidance.
- Autonomy Supervisor recovery for CAD receipts returned to research prompts.
- Package-health regression for cooling-duct research routing.

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
