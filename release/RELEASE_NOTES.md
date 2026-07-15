# Codex CLI UI for Mac v2026.07.15

Sanitized public ZIP release.

## Download

Download one file:

```text
Codex_CLI_UI_Public_v2026.07.15.zip
```

Unzip it and double-click `install.command`.

## Fixed

- Added a crash shield for `/api/run` so local worker failures return a useful recovery answer instead of an empty or broken response.
- Added a server crash self-repair work order path so repeated failures can be captured as actionable local repair tasks.
- Kept generated answers cleaner by suppressing bulky supporting-file dumps from the normal reply body.

## Added

- Public-safe ZIP export with private `data/`, `logs/`, generated CAD/CFD/FEA outputs, source-vault documents, machine inventory, and private history tests excluded.
- Privacy scanner for release artifacts and exported source.
- Public manifest documenting the exact files copied and sanitizers applied.
- Built-in public manufacturing question bank for CAD and CNC regression checks.
- RatOS Raspberry Pi 5 experimental builder helper kept as a tool template, not as a bundled private image.

## Included

- Local browser UI runtime and native Mac wrapper source.
- Local OSS/Ollama-oriented server and UI files.
- Manager, Local Research, Coder, Review, access, reasoning, friendliness, humor, and web controls.
- Improvement Lab, golden-test runner, package health check, crash recovery, and public release tooling.
- 3D printing, CAD, manufacturing, engineering diagram, aero/CFD, and structural workflow scaffolding.
- Example config files only; no private machines, passwords, IP inventory, chats, logs, or generated work.

## Verification

- Public export privacy scan: pass, 0 findings.
- Package health on exported source: 131 checks, 0 failed, 1 expected warning for private Klipper config absence.
- Release archive SHA-256:

```text
3a0a6e0d45c2f909ff8ab56a6705a77f3b3ddfac7b2e14009502df659cf607e4  Codex_CLI_UI_Public_v2026.07.15.zip
```

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

Optional engineering tools are detected when present; large tools, models, printer configs, private manuals, and machine inventories are not bundled.

## Notes

No personal chat history, machine inventory, raw passwords, local network details, generated design outputs, printer backups, or private source-vault documents are bundled. Private machine and printer details live only under each user's local `data/private/` folder after install.

This is an ad-hoc signed community package and is not Apple-notarized. Use right-click **Open** if macOS Gatekeeper blocks the installer or app.
