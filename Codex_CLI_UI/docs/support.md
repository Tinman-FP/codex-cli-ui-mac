# Codex CLI UI Support Guide

This guide is for a public-safe Codex CLI UI package. Do not include passwords, API keys, private printer inventory, VPN hostnames, local source-vault documents, or private generated artifacts in support reports.

## First Checks

1. Open the app from the installed launcher or run `./start.command`.
2. Check the local status page or run `/api/package-health`.
3. If the app was just updated, run `./restart.command`.
4. If local model answers are enabled, confirm Ollama is running and the selected model exists.
5. If attachments fail, try a small file first, then use native local-path attach for large files.

## What To Include In A Report

- The task you asked.
- The final answer or visible blocker.
- The package-health status and receipt path.
- Whether the issue involved private files, live machines, electrical work, printers, or paid/cloud services.
- The smallest safe reproduction prompt.

## What Not To Include

- Passwords, tokens, API keys, session cookies, SSH keys, private IPs, VPN names, or router credentials.
- Source-vault PDFs, manuals, uploaded private files, or generated customer/project artifacts.
- Live printer access details unless the maintainer explicitly requests a redacted example.

## Common Recovery Paths

- Startup issue: run `./restart.command`, then check `/api/package-health`.
- Wrong answer: use Fix this or file a report with the prompt, answer, and expected behavior.
- Failed tool action: stop repeating the action, save the receipt, and include whether a live machine was involved.
- Privacy concern: stop sharing/exporting, run the privacy scan, and report the exact local artifact or export path.
- Public export issue: rebuild with `python3 tools/build_public_export.py --zip` and scan the exported folder.

## Escalation

Use the public issue tracker or release discussion for ordinary bugs. Use the responsible-disclosure path in `docs/security.md` for security-sensitive or privacy-sensitive reports.
