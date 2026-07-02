# Codex CLI UI for Mac v2026.07.05

Bugfix and capability release for CAD/design routing and local CAD artifact staging.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.05.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- CAD/CPAP duct design prompts no longer get mistaken for live printer status or Moonraker checks.
- CAD design requests now route to the CAD/Modeling specialist with the local artifact-capable engine.
- Printer-status context is suppressed when the request is clearly about CAD geometry, Fusion 360, STEP/STL, ducts, CFD, or part-cooling design.

## Added

- Local CAD artifact endpoint: `POST /api/tools/cad-artifact`.
- Fusion 360 Python script, OpenSCAD model, and README staging for CPAP duct design requests.
- OpenSCAD and FreeCAD entries in the free-tool capability catalog, with storage and approval rules.
- Package-health checks for CAD routing, CAD prompt context, and CAD artifact generation.

## Included

- `Codex CLI UI.app` launcher with red rounded icon
- Local browser UI runtime
- User LaunchAgent installer
- Fast, Careful, Coder, Review, Manager, and Local Research modes
- Web Access, access level, reasoning, friendliness, and humor controls
- Admin Improvement Lab, Golden Test Generator, Test Bench history, and package health checks
- Tool Recovery Engine and Capability Manager
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
