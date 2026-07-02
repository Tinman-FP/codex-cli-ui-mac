# Codex CLI UI for Mac v2026.07.06

Capability release for the Autonomy Supervisor help reflex.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.06.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- Draft answers that say web access is unavailable while Web Access is enabled are now flagged before final delivery.
- CAD design drafts that drift into live-printer/Moonraker status are intercepted and recovered with local CAD artifact staging.
- Missing-command and no-final-answer patterns are classified as help-needed conditions instead of cold failures.

## Added

- Autonomy Supervisor prompt context in worker, reviewer, finalizer, and quality-coach paths.
- Local supervisor endpoint: `POST /api/tools/autonomy-supervisor`.
- Deterministic post-answer checks for web evidence, source links, CAD artifacts, missing tools, unfinished runtimes, and unsupported refusal answers.
- Package-health checks for the self-rescue reflex.

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
