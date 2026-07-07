# Changelog

## v2026.07.15

- Adds the Task Contract Gate so hard tasks define done, required proof, reject conditions, and gate status before an answer is accepted as complete.
- Adds contract-aware response scorecards and live `/api/run` payload fields for task contracts, deliverables, assumptions, scorecards, and gate failures.
- Adds a 50-question Fusion & Orca Samples regression pack covering Fusion 360 CAD/CAM workflows, OrcaSlicer Codex app/preset repair, Orca profile workflow, and Orca filament calibration.
- Fixes Fusion 360 user-parameter prompts being mistaken for Orca pressure-advance or local slicer-profile pulls.
- Fixes conceptual Orca filament/profile questions so they answer the workflow directly instead of dumping unrelated local profile data.
- Runs and verifies the full local regression gauntlet: 12 hard cases, 50 Fusion/Orca samples, 100 manufacturing samples, 56 domain samples, and the TinmanX1 Polymaker workflow scenario.

## v2026.07.14

- Adds the 3D Printing Expert Pack with printer profiles for Bambu H2D/X1C, Creality K2 Plus, Qidi Plus 4, Snapmaker U1, Rat Rig V-Core 4.1 IDEX Klipper, Sovol SV08 Max, and ELEGOO Centauri Carbon.
- Adds a filament/material library for PLA, PETG, PCTG, ABS, ASA, PA, PA-CF, PET-CF, PC, and TPU with drying, use-case, strength, and caution notes.
- Adds an OrcaSlicer filament-tuning coach that answers in calibration order: temperature, flow pass 1, flow pass 2, pressure advance, max volumetric speed, retraction, then VFA/speed.
- Adds a local 3D-printing source vault that can cache official specs, manuals, GitHub docs, and component references under each user's local `data/source-vault/3d-printing` folder.
- Adds BTT EBB42 source retention from GitHub/wiki/PDF references so future toolboard questions can use local cached docs.
- Adds `GET /api/3d-printing/expert-pack` and `POST /api/3d-printing/refresh-sources` for UI/admin source-vault visibility and refresh.
- Adds an Admin 3D Printing Expert Pack card with printer/material/source-vault counts and a Refresh Sources button.
- Adds package-health regressions for the expert pack, Orca filament tuning answers, and direct printer-profile architecture/limit answers.

## v2026.07.13

- Adds OpenVSP/VSPAERO, XFOIL, SU2, QBlade Linux launcher, and CalculiX to the free-tool capability catalog.
- Creates the `qblade-import`, `qblade-linux`, `qblade-runner-build`, and `qblade` helpers so QBlade CE downloads are validated before use and run through a Linux Docker runner on macOS.
- Accepts official Safari-extracted QBlade folders, rejects incomplete `Unconfirmed*.crdownload` downloads, and runs QBlade through Xvfb with the Qt runtime libraries it needs.
- Adds mechanical/structural design detection for brackets, mounts, holders, loads, stress, deflection, FEA, FEM, and safety-factor prompts.
- Upgrades the structural FEA endpoint from seed-case-only to attached STL/STEP geometry meshing with Gmsh, CalculiX solving, result parsing, and a seed fallback when real meshing fails.
- Adds automatic fixed/load face selection, printed-part material allowables/process notes, stress/deflection/safety-factor summaries, and PNG result previews.
- Makes generated `.inp`, `.msh`, `.dat`, `.frd`, and `.geo` engineering files clickable in chat responses.
- Adds a compact Engineering strip below the chat bar with Aero, Structural, and Tools readiness plus one-click Run Deeper, Aero, and FEA actions.
- Adds an Admin Engineering Analysis Packs card showing exact tool availability and pack-level run buttons.
- Adds `POST /api/tools/deeper-analysis` so UI buttons can select the best engineering path and return normal chat responses with clickable reports/results.
- Routes mechanical and structural design prompts into CAD/Modeling instead of printer status or generic CAD fallbacks.
- Adds package-health regressions for aero toolchain visibility, real structural FEA output, structural reports/previews, and structural routing.

## v2026.07.12

- Upgrades STL/CPAP duct handling from preflight-only to a real inferred design worker.
- Infers likely CPAP inlet/outlet bodies from STL mesh geometry when Fusion component names are not preserved.
- Generates editable OpenSCAD, printable duct STL, internal-airway STL, inferred-port JSON, and a design-preview image.
- Uses a flattened split-duct path to respect 1 mm wall thickness, 1.5 mm clearance intent, 5 mm growth, and zero-Y-growth requests.
- Runs OpenFOAM Docker `surfaceCheck` on generated duct STL when available.
- Updates package-health regression so STL duct prompts must produce a duct artifact instead of only a preflight report.

## v2026.07.11

- Adds chat-bar file attachments through drag/drop, paste, and the `+` attach button.
- Saves uploaded files into local runtime storage and sends attachment metadata with each prompt.
- Adds filename-only STL fallback search for cases where macOS pastes only the file name.
- Adds STL-aware CPAP/part-cooling duct preflight before generic CAD artifact generation.
- Inspects STL mesh geometry, connected components, clearance/wall constraints, and OpenFOAM/Docker CFD capability.
- Adds package-health regression so STL duct prompts cannot fall back to the generic Fusion/OpenSCAD CPAP duct template.

## v2026.07.10

- Fixes cooling-duct research prompts being misrouted into CAD artifact generation.
- Adds `cad-research-direct-answer` for part-cooling duct research and reusable design rules.
- Routes Printables/GitHub/inspiration/practical-technique duct prompts through Local Research instead of local CAD staging.
- Adds reusable source-backed playbook guidance for pressure loss, plenum balance, CPAP outlet area, material-specific cooling, and CFD validation.
- Adds a package-health regression for both the initial research prompt and the follow-up correction prompt.

## v2026.07.09

- Fixes CPAP hose inner-diameter questions being misrouted into CAD artifact generation.
- Adds a direct CPAP hose sizing answer: standard hose 19 mm ID, slimline 15 mm ID, common cuff/connector 22 mm.
- Routes CPAP hose sizing to Research, Parts & Cross-Reference instead of CAD/Modeling.
- Adds a package-health regression so CPAP hose ID questions cannot produce Fusion/OpenSCAD artifacts.

## v2026.07.08

- Upgrades CAD artifact answers from file receipts into engineering first-pass responses.
- Adds airflow sizing for CPAP duct requests, including inlet/outlet area and ideal velocity estimates.
- Adds PLA/PCTG/ABS cooling guidance, CFD validation limits, visible CAD working notes, and lightweight web source checks when Web Access is enabled.
- Adds a package-health regression so CAD artifact answers must include design reasoning, airflow math, and CFD limits.

## v2026.07.07

- Makes CAD/Fusion artifact staging deterministic before the local model path for CAD design requests.
- Fixes CAD load-failure fallbacks so they stage Fusion 360/OpenSCAD/README artifacts instead of generic runtime recovery text.
- Adds a package-health regression for CAD load failures returning artifact paths without Moonraker/config recovery wording.

## v2026.07.06

- Adds the Autonomy Supervisor help reflex before final answer delivery.
- Detects missing web evidence, wrong CAD/printer-status behavior, missing tools, unfinished runtimes, and weak unsupported refusals.
- Adds `POST /api/tools/autonomy-supervisor` so local workers can check draft answers for help-needed conditions.
- Lets the supervisor recover CAD design mistakes by staging Fusion 360/OpenSCAD artifacts before answering.
- Adds package-health regressions for web-evidence gaps, CAD artifact gaps, and missing-tool detection.

## v2026.07.05

- Fixes CAD/CPAP duct design prompts being mistaken for live printer status checks.
- Adds CAD design intent detection, CAD-first analytical context, and a prompt contract for Fusion 360/importable artifacts.
- Adds a local CAD artifact endpoint that stages a Fusion 360 Python script, OpenSCAD model, and README.
- Adds OpenSCAD and FreeCAD to the free-tool capability catalog with storage/approval policy checks.
- Adds package-health regressions for CAD routing, CAD context, and CAD artifact staging.

## v2026.07.04

- Makes `Fix this` a one-click feedback capture instead of relying on a prompt dialog.
- Routes public printer hardware/spec questions such as Fibreseek continuous-fiber toolheads through Local Research when web is enabled.
- Tolerates obvious technical typos such as `hotted` when `hotend` is the likely meaning.
- Keeps Manager review, polish, and Quality Coach failures from discarding a valid primary worker answer.
- Adds health checks for public-printer research routing and knowledge-question recovery wording.

## v2026.07.03

- Adds the Golden Test Generator so Improvement Lab items become saved runnable regression tests.
- Records Test Bench pass/fail history in local `data/golden_test_results.json`.
- Feeds failed golden tests back into the Improvement Lab as high-priority regression items.
- Shows saved golden-test and failing-test counts in the Admin UI.
- Keeps public package defaults generic while preserving local-only runtime data.

## v2026.07.02

- Adds Manager, Coder, Review, Local Research, and Cloud Research mode wiring in the UI runtime.
- Adds the Admin Improvement Lab for `Fix this` feedback, tool gaps, review/archive actions, and regression-test candidates.
- Adds the Tool Recovery Engine for missing commands, missing Git remotes, disabled web paths, Klipper config discovery, local load failures, and permission boundaries.
- Adds local capability APIs for free allowlisted tool recovery, Klipper config discovery, and package-health checks.
- Keeps public package defaults generic and private printer/network data local-only.

## v2026.07.01.1

- Adds a private startup inventory card for machines, SSH aliases, tailnet hosts, and Mac resources.
- Adds safe working notes while Codex CLI is running.
- Creates a local-only `data/private/machines.json` template during install.
- Keeps private machine inventory, chat history, passwords, and local network details out of the public package.

## v2026.07.01

- Initial public Mac release.
- Adds a local browser UI for Codex CLI.
- Adds Fast and Careful local OSS profiles.
- Adds compact chat composer controls for Mode, Access, Reasoning, and Web.
- Adds red rounded app icon.
- Ships as a single DMG installer bundle.
