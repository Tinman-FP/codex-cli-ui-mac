# Codex CLI UI for Mac v2026.07.08

Response-quality release for CAD engineering answers.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.08.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- CAD/Fusion design prompts no longer return a file-staging receipt as the whole answer.
- CAD answers now show the engineering decision behind the geometry instead of only listing generated files.
- CAD web/industry requests no longer silently skip source checking when Web Access is enabled.

## Added

- Visible CAD working notes for constraint parsing, airflow sizing, outlet selection, and CFD status.
- Airflow sizing for CPAP duct requests: CFM to L/s, inlet area, outlet area, ideal inlet velocity, ideal outlet velocity, and area ratio.
- Material-specific cooling guidance for PLA, PCTG, and ABS/ASA.
- Lightweight web source checks for CAD duct/part-cooling prompts when Web Access is enabled.
- Package-health regression for analytical CAD answers.

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
