# Codex CLI UI for Mac v2026.07.13

Aero and mechanical/structural design-pack release.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.13.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- Mechanical and structural design prompts now route to CAD/Modeling instead of printer status or generic fallbacks.
- Package health now catches structural-routing regressions before release.

## Added

- OpenVSP/VSPAERO, XFOIL, SU2, QBlade Linux launcher, and CalculiX tool visibility in the local capability catalog.
- Installer-created `qblade-import`, `qblade-linux`, `qblade-runner-build`, and `qblade` helpers for validated QBlade CE Linux imports on macOS.
- Structural FEA preflight endpoint for brackets, mounts, holders, loads, stress, deflection, FEA/FEM, and safety-factor prompts.
- Load/material/safety-factor assumption capture before claiming strength.
- CalculiX seed input deck generation and solver smoke run when `ccx` is available.
- Package-health checks for aero toolchain visibility, structural toolchain visibility, structural preflight output, and structural routing.

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
- Aero/CFD preflight helpers for OpenFOAM/OpenVSP/XFOIL/SU2 workflows
- Mechanical/structural preflight helper for CalculiX-backed FEA workflows
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

Optional engineering tools are detected when present. QBlade CE's Linux package must be downloaded from the official QBlade site, then imported with `qblade-import`; partial browser files such as `Unconfirmed*.crdownload` are rejected until the archive validates.

## Notes

No personal chat history, machine inventory, raw passwords, or local network details are bundled. Private machine and printer details live only under each user's local `data/private/` folder.

This is an ad-hoc signed community package and is not Apple-notarized. Use right-click **Open** if macOS Gatekeeper blocks the installer or app.
