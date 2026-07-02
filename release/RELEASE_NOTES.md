# Codex CLI UI for Mac v2026.07.04

Bugfix release for answer recovery, one-click feedback, and public printer-hardware research routing.

## Download

Download one file:

```text
Codex_CLI_UI_Mac_v2026.07.04.dmg
```

Open the DMG and double-click `Install Codex CLI UI.command`.

## Fixed

- `Fix this` now saves a useful feedback lesson with one click instead of depending on a prompt dialog.
- Manager review, final polish, and Quality Coach failures no longer discard a valid primary worker answer.
- Knowledge/research questions no longer receive file/upload/live-printer recovery wording after a local load failure.
- Public printer hardware/spec questions, including Fibreseek/Fiberseek continuous-fiber toolhead questions, route through Local Research when web is enabled.
- Obvious technical typos such as `hotted` are treated as likely `hotend` instead of derailing the answer.

## Included

- `Codex CLI UI.app` launcher with red rounded icon
- Local browser UI runtime
- User LaunchAgent installer
- Fast, Careful, Coder, Review, Manager, and Local Research modes
- Web Access, access level, reasoning, friendliness, and humor controls
- Admin Improvement Lab, Golden Test Generator, Test Bench history, and package health checks
- Tool Recovery Engine and Capability Manager
- Klipper config discovery and macro-staging helpers
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
