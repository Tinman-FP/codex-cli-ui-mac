# Changelog

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
