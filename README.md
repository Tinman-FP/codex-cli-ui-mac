# Codex CLI UI for Mac

A local browser UI for Codex CLI in local OSS mode with Ollama.

This is a community package for Mac users who want a simple local Codex-style chat UI around the Codex CLI. It installs a small Python web UI, a LaunchAgent, local Codex profiles, and a red `Codex CLI UI.app` launcher.

## One-File Download

Download the current public ZIP from the `release/` folder or the GitHub Release:

```text
Codex_CLI_UI_Public_v2026.07.15.zip
```

Unzip it and double-click:

```text
install.command
```

The installer copies files into your user account:

- `~/Applications/Codex CLI UI.app`
- `~/Applications/Codex_CLI_UI`
- `~/Library/LaunchAgents/com.tinmanfp.codex-cli-ui.plist`
- `~/.codex/local-fast.config.toml`
- `~/.codex/local-oss.config.toml`

## Requirements

- macOS
- Codex Desktop installed at `/Applications/Codex.app`
- Ollama installed
- The `gpt-oss:20b` model pulled in Ollama

Helpful commands:

```bash
ollama pull gpt-oss:20b
codex --profile local-fast --search
```

## What You Get

- Local web UI at `http://127.0.0.1:8765`
- New Chat, Projects, and Chats sidebar
- Stationary prompt bar with compact controls for Mode, Access, Reasoning, and Web
- Fast and Careful local Codex profiles
- Red rounded app icon to distinguish it from the official Codex app
- Startup inventory card for private machine records, SSH aliases, tailnet hosts, and local tool resources
- Safe working notes while Codex CLI is running
- Drag/drop, paste, and `+` button file attachments for STL/CAD workflows
- Admin Improvement Lab for weak-answer feedback, tool gaps, and saved golden regression tests
- Golden Test Generator that turns Improvement Lab items into runnable prompt tests and feeds failures back into the lab
- One-click `Fix this` capture and safer Manager fallback when review/polish fails
- Tool Recovery Engine for missing commands, Git remote gaps, disabled web paths, and safe retry guidance
- Autonomy Supervisor that catches missing web evidence, tool gaps, CAD artifact gaps, and weak refusal answers before final delivery
- CAD design routing that avoids live-printer status traps and can stage Fusion 360/OpenSCAD artifacts
- Deterministic CAD artifact fallback for Fusion/CPAP duct requests when local model loading fails
- Analytical CAD answers with airflow sizing, material cooling guidance, CFD validation limits, and lightweight web source checks
- Direct CPAP hose sizing answers so measurement questions do not generate CAD artifacts
- Cooling-duct research mode that learns from CFD papers, Printables, GitHub, and material-cooling guidance before CAD generation
- STL-aware CFD/duct preflight that finds attached or named STL files, inspects mesh geometry, captures clearance/wall constraints, and detects OpenFOAM/Docker capability before answering
- Inferred STL duct design worker that generates editable SCAD, duct STL, airway STL, port-inference JSON, preview images, and OpenFOAM surface checks
- 3D Printing Expert Pack with printer profiles, filament/material guidance, OrcaSlicer calibration order, BTT EBB42 docs retention, and a local manual/spec source vault
- Admin 3D Printing Expert Pack card with source-vault counts and one-click source refresh
- Local Research, Coder, Review, and Manager modes for a fuller free local workflow
- Optional local history importer for your own `~/.codex/sessions`

## Privacy

No personal Codex chat history or machine inventory is bundled in this release. The installer creates local `data/` and `logs/` folders on each Mac.

Each install gets a private startup inventory at:

```text
~/Applications/Codex_CLI_UI/data/private/machines.json
```

Use that file for machine names, hostnames, SSH aliases, usernames, key paths, and macOS Keychain references. Do not store raw SSH passwords in it.

## Gatekeeper

This package is ad-hoc signed, not Apple-notarized. If macOS blocks the app, right-click the app or installer and choose **Open**, or allow it in System Settings.

## Uninstall

Open the DMG and run:

```text
Uninstall Codex CLI UI.command
```

The uninstaller removes the app, runtime, and LaunchAgent. It intentionally leaves Codex profiles and shell shims in place.
