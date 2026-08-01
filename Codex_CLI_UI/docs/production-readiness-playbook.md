# Codex CLI UI Production Readiness Playbook

This playbook is the local release gate before Tinman publishes a public ZIP, DMG, or GitHub release.

## Release Owner

- Tinman is the launch approver for the local/public package.
- Codex may prepare release artifacts, checks, notes, and diffs, but should not push or publish until Tinman explicitly approves.
- Any release note must say whether the build is local-only, public-safe, experimental, or validated.

## Rollback

- Keep the previous working package or Git commit available before installing a new build.
- Keep private runtime data under `data/` and `logs/`; installer and restart scripts must preserve those folders.
- If a release breaks startup, run `./restart.command`, check `/api/package-health`, then revert to the previous known-good source tree or package.
- If a public export is bad, delete the export folder, rebuild with `python3 tools/build_public_export.py --zip`, rerun the privacy scan, and publish a corrected release only after approval.

## Incident Response

For a serious wrong answer, unsafe tool action, privacy leak, failed package, or broken app startup:

1. Stop risky use first. Do not keep repeating live-machine actions.
2. Save the prompt, answer, attachments, app version, and package-health output.
3. Mark whether private data, live machines, electrical work, printers, or paid services were involved.
4. Reproduce with the smallest safe local prompt or fixture.
5. Patch the smallest systemic code path.
6. Add or update a regression or package-health check.
7. Restart, rerun `/api/package-health`, and run focused `/api/run` verification.
8. Write a checkpoint under `data/work_checkpoints/`.

## Monitoring

- `/api/package-health` is the primary local readiness signal.
- `logs/server-exceptions.log` is the primary startup/runtime crash signal.
- Feedback, Fix-this, self-healing, golden batch, and live smoke receipts are the answer-quality signals.
- Model health and printer health are operational signals, but public release health must not depend on Tinman's private machines being online.

## Privacy And Security

- Run `python3 tools/release_privacy_scan.py` before any public packaging.
- Run `python3 tools/build_public_export.py --zip` and scan the exported source folder, not the private local tree.
- Do not publish `data/`, `logs/`, source-vault files, local printer IPs, SSH paths, passwords, tokens, API keys, chat history, or generated private artifacts.
- Tool access changes require review when they can touch live printers, routers, electrical systems, removable media, or public repositories.

## Public Claims And Legal Review

- Public claims about safety, compliance, compatibility, licensing, cost, performance, or supported platforms must be source-backed and caveated.
- Do not claim the app is certified, legally approved, electrically safe, medically safe, or suitable for high-stakes use unless a qualified review actually happened.
- Tinman must approve public release text, known limitations, attribution, and third-party licensing notes before publication.
- If legal/commercial risk is unclear, treat the item as blocked for public release until a qualified human reviews it.

## Abuse, Safety, And Disclosure

- Public users should report issues through GitHub Issues or the release discussion for the public repository.
- Security-sensitive reports should be handled privately when possible, then summarized publicly after the risk is fixed.
- Safety-critical answers should remain conservative and include verification/qualified-professional boundaries.
- Known serious failures should be documented in release notes until fixed and verified.

## Support Documentation

- Public users need install, start, restart, package-health, troubleshooting, and uninstall/reinstall instructions.
- Public support guidance lives in `docs/support.md`; responsible disclosure and security-sensitive reporting live in `docs/security.md`.
- Support playbooks should say what information to collect without asking users to expose passwords, API keys, or private machine inventory.
- Common user-facing support checks:
  - app opens without launching an unwanted browser
  - `/api/package-health` passes
  - Ollama is running when local models are selected
  - attachments upload or local-path attach correctly
  - generated files are clickable/revealable

## Model And Behavior Updates

- Model, prompt, routing, and answer-shape changes need a focused regression run before release.
- Release notes should name behavior changes that affect research, local tool use, live machine actions, privacy, or answer style.
- New model aliases or tool packs should be free/local by default unless Tinman explicitly chooses a paid/cloud path.

## Launch Checklist

- Package health passes.
- Privacy scan passes on local source and sanitized export.
- Public export builds from the allowlist.
- Accessibility static audit passes and the manual checklist has no unresolved blocker.
- Release notes include known limitations and rollback instructions.
- `docs/release-checklist.md` is reviewed against the current package-health, live-smoke, export, privacy, and approval receipts.
- Tinman approves the final package and GitHub action.
