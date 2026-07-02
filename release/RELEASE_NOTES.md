# Codex CLI UI for Mac v2026.07.12

Design-worker release for STL-based CPAP cooling duct requests.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.12.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- STL-based CPAP duct prompts no longer stop at a preflight report.
- The CAD path now attempts a real inferred duct design when mesh geometry is available.
- Package health now fails if STL duct prompts return only generic CAD or preflight-only output.

## Added

- Inferred CPAP inlet/outlet body detection from STL connected components.
- Generated duct STL, editable OpenSCAD source, internal-airway STL, inferred-port JSON, and design-preview PNG.
- OpenFOAM Docker `surfaceCheck` for generated duct STL when Docker/OpenFOAM images are present.
- A flattened split-duct strategy for tight Y-growth constraints.

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
