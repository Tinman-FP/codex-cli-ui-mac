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
- Safari-extracted QBlade folders can be imported directly, incomplete browser downloads are rejected, and the Docker runner includes Qt/Xvfb support for headless Linux execution.
- Structural FEA preflight endpoint for brackets, mounts, holders, loads, stress, deflection, FEA/FEM, and safety-factor prompts.
- Attached STL/STEP structural geometry can now be meshed with Gmsh, solved with CalculiX, parsed for stress/deflection/safety factor, and reported with a preview PNG.
- Automatic fixed/load face selection plus printed-part material allowables and process notes for PLA, PETG, ASA, ABS, PCTG, nylon, PA-CF, PET-CF, aluminum, and steel.
- Clickable generated engineering files for `.inp`, `.msh`, `.dat`, `.frd`, and `.geo` outputs.
- Compact Engineering strip below the chat bar showing Aero, Structural, and Tools readiness plus one-click Run Deeper, Aero, and FEA buttons.
- Admin Engineering Analysis Packs card with exact tool availability and pack-level analysis buttons.
- Deeper-analysis endpoint that chooses the right Aero/CFD or Structural FEA path and returns normal chat responses with clickable reports/results.
- Package-health checks for aero toolchain visibility, real structural FEA output, structural reports/previews, and structural routing.

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
- Mechanical/structural real-geometry FEA helper for Gmsh/CalculiX-backed workflows
- Visible Engineering Analysis Pack status and one-click deeper-analysis controls
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

Optional engineering tools are detected when present. QBlade CE's Linux package must be downloaded from the official QBlade site, then imported with `qblade-import`; official extracted folders from Safari are accepted, while partial browser files such as `Unconfirmed*.crdownload` are rejected until the download validates.

## Notes

No personal chat history, machine inventory, raw passwords, or local network details are bundled. Private machine and printer details live only under each user's local `data/private/` folder.

This is an ad-hoc signed community package and is not Apple-notarized. Use right-click **Open** if macOS Gatekeeper blocks the installer or app.
