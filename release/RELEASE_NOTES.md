# Codex CLI UI for Mac v2026.07.11

Bugfix release for STL attachments and STL-aware CFD/duct preflight.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.11.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- STL/CAD requests no longer silently proceed when macOS only pasted a filename.
- STL-based CPAP duct prompts no longer fall into the generic Fusion/OpenSCAD CPAP duct template.
- The app now exposes whether CFD can actually run instead of saying "no CFD was run" as a generic afterthought.

## Added

- Chat-bar file attachments by drag/drop, paste, or `+` attach button.
- Local upload storage for attached files and visible attachment chips in the chat.
- Filename-only STL fallback search in the current project and app input folders.
- STL-aware CFD/duct preflight that reads mesh geometry, connected components, clearance/wall constraints, and OpenFOAM/Docker capability.
- Package-health regression for STL duct requests so they inspect geometry before answering.

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
