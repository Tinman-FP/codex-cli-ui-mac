# Codex CLI UI Privacy And Sensitive Data Playbook

This app is local-first, but it can still handle private files, machine inventory, source-vault material, generated logs, and optional cloud research. Treat that data as private unless Tinman explicitly says otherwise.

## User Warning

- The composer must warn users not to paste passwords, API keys, tokens, or private customer data.
- Attachments should be treated as intentionally shared with Codex for the current task.
- The app should explain that local files are read for the requested task and should not be attached unless the user wants Codex to inspect them.

## Storage Defaults

- Runtime data stays under `data/` and `logs/`.
- Private machine inventory stays under `data/private/`.
- Source-vault documents, uploads, generated CAD/CFD/FEA output, and private chat-derived tests are not public-release material.
- Stable learning should store compact lessons and source pointers, not raw transcripts, passwords, tokens, volatile prices, or one-time live status.

## Redaction Rules

- Redact password, passwd, pwd, api key, token, and secret assignments in feedback, improvement items, saved lessons, and public release scans.
- Do not print raw SSH passwords in chat. Use SSH keys, macOS Keychain references, or private inventory metadata.
- Do not publish private LAN IPs, VPN names, usernames, absolute `$HOME` paths, API keys, chat history, or generated private artifacts.

## Public Export Rules

- Public packages must be built from `tools/build_public_export.py`, not from the live local tree.
- `tools/release_privacy_scan.py` must run on both the local source and the sanitized public export.
- Public export must exclude `data/`, `logs/`, `build/`, source-vault material, generated outputs, private inventory, and private chat-history tests.
- Any remaining private data finding blocks the release until reviewed and removed or intentionally templated.

## Optional Cloud Use

- Cloud Research is optional and should stay disabled unless configured.
- Private startup inventory, local project history, SSH aliases, machine passwords, and source-vault documents must not be injected into cloud prompts.
- If a task needs private local machine access, prefer local modes.

## Deletion And Export

- Local runtime files can be reviewed under `data/` and `logs/`.
- Public release exports are reproducible and sanitized; they should not be treated as backups of Tinman's private local app state.
- Before deleting runtime data, preserve anything Tinman wants to keep, then rerun package health after cleanup.
