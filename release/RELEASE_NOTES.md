# Codex CLI UI for Mac v2026.07.15

World-class response-quality and manufacturing-test release.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_Public_Bundle_2026-07-03.zip
```

Unzip it, then open the included DMG or double-click `install/Install Codex CLI UI.command`.

## Fixed

- Printer/material/component knowledge questions now answer directly instead of falling into generic CAD, Moonraker, or printer-status fallbacks.
- Package health now catches 3D-printing expert-pack, Orca tuning, and printer-profile regressions before release.
- CAD and CNC knowledge questions now route to manufacturing expertise instead of generic CAD artifact staging.
- Complex Codex CLI UI/TinmanX1 requests now route to the local-agent workflow lane instead of getting pulled sideways by filament keywords.
- `Fix this` feedback now creates a lesson, a golden regression test, and a self-healing repair candidate with evidence.

## Added

- Public 100-question Manufacturing Samples golden-test bank: 50 CAD questions and 50 CNC machining questions.
- TinmanX1/Polymaker/Fiberon workflow scenario covering test-bank import, Steer/Edit UI, self-healing, GitHub release, and zip packaging behavior.
- `Edit question` message action for user prompts. It reloads the question into the composer and reruns from that point.
- `Steer` message action for assistant answers. It preloads a correction prompt so Tinman can redirect the answer without starting over.
- Package-health checks for manufacturing-sample tests and workflow-scenario tests.
- README commands for running manufacturing samples and the workflow scenario through the live `/api/run` test bench.
- 3D Printing Expert Pack with printer profiles for Bambu H2D/X1C, Creality K2 Plus, Qidi Plus 4, Snapmaker U1, Rat Rig V-Core 4.1 IDEX Klipper, Sovol SV08 Max, and ELEGOO Centauri Carbon.
- Filament/material library for PLA, PETG, PCTG, ABS, ASA, PA, PA-CF, PET-CF, PC, and TPU with drying, use-case, strength, and caution notes.
- OrcaSlicer tuning coach using the practical calibration order: temperature tower, flow pass 1, flow pass 2, pressure advance, max volumetric speed, retraction/stringing, then VFA/speed.
- Local 3D-printing source vault at `data/source-vault/3d-printing` for official specs, manuals, GitHub docs, wiki pages, and extracted text.
- BTT EBB42 source retention from GitHub/wiki/PDF references so future toolboard questions can use local cached docs.
- `GET /api/3d-printing/expert-pack` and `POST /api/3d-printing/refresh-sources` for source-vault visibility and refresh.
- Admin 3D Printing Expert Pack card with printer/material/source-vault counts and a Refresh Sources button.
- Package-health checks for the expert pack, Orca filament tuning answers, and direct printer-profile architecture/limit answers.
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
- Public CAD/CNC manufacturing regression fixture
- Steer/Edit chat controls and self-healing Fix-this queue
- Tool Recovery Engine and Capability Manager
- Autonomy Supervisor help-needed checker
- Klipper config discovery and macro-staging helpers
- CAD artifact staging helper for Fusion 360/OpenSCAD workflows
- Aero/CFD preflight helpers for OpenFOAM/OpenVSP/XFOIL/SU2 workflows
- Mechanical/structural real-geometry FEA helper for Gmsh/CalculiX-backed workflows
- Visible Engineering Analysis Pack status and one-click deeper-analysis controls
- 3D Printing Expert Pack with Orca tuning, printer profiles, filament guidance, and local source-vault refresh
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
