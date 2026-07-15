# Codex CLI UI Public Release Plan

This repo is currently a local Tinman build. Public release must be a curated export, not a raw copy of the working tree.

## Release Boundary

Keep local-only:

- `data/`, `logs/`, generated reports, source-vault files, uploads, chat-derived golden tests, and private machine inventory.
- Local printer IPs, VPN names, SSH paths, usernames, passwords, API keys, and absolute `$HOME` paths.
- Heavy CAD/CFD/FEA outputs unless they are intentionally packaged as example artifacts with approval.

Publishable after scrub:

- App source files.
- Public-safe sample tests.
- Tool installers or install scripts that use Homebrew, standard package managers, or documented manual steps.
- Templates for private machine inventory, source-vault setup, and local profile configuration.
- Attribution, license notes, README, install instructions, and package-health proof.

## Required Gates

Before any GitHub push or public ZIP/DMG:

1. Run `python3 tools/release_privacy_scan.py`.
2. Build the sanitized source export with `python3 tools/build_public_export.py --zip`.
3. Run `python3 tools/release_privacy_scan.py --root build/public-export/codex-cli-ui-public`.
4. Replace any remaining absolute local paths with `$HOME` or install-time paths.
5. Replace private IPs and machine names with placeholders or private config templates.
6. Confirm `data/` and generated artifacts are excluded.
7. Run `python3 -m py_compile server.py run_golden_batch.py tools/verify_golden_hidden_sweep.py tools/release_privacy_scan.py tools/build_public_export.py`.
8. Run package health through the local server.
9. Run a public-safe golden batch: Domain Samples, Manufacturing Samples, and the workflow scenario.
10. Review attribution for OpenAI/Codex, Ollama models, OrcaSlicer/TinmanX-related work, engineering tools, and any bundled third-party assets.
11. Create the public ZIP/DMG from the sanitized export folder, not from the live local working folder.
12. Push only after Tinman approves the final diff and package contents.

## Sanitized Export Dry Run

Use this before any public release packaging:

```bash
python3 tools/build_public_export.py --zip
python3 tools/release_privacy_scan.py --root build/public-export/codex-cli-ui-public
```

The export builder copies the source allowlist, excludes local runtime data, replaces `/Users/<name>` paths with `$HOME`, replaces private LAN IPs with documentation placeholders, and writes `PUBLIC_EXPORT_MANIFEST.json` into the export folder.

## Public Config Shape

Use templates like:

- `config/machines.example.json`
- `config/source-vault.example.json`
- `config/local-tools.example.json`
- `.env.example`

The first-run local setup should copy templates into private `data/` files and let each user enter their own printer hosts, VPN routes, source-vault paths, and model choices.

## Current Local Status

The local Tinman build is intentionally richer than a public release because it contains private machine intelligence and local-history test behavior. That is good for Tinman, but it must be split from public packaging.
