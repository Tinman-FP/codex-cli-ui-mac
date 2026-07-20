# Codex CLI UI Release Checklist

Use this checklist before any public ZIP, DMG, GitHub release, or broad handoff. Codex can prepare the package, but Tinman is the launch approver.

## Required Gates

- Package health passes.
- Full live feedback smoke passes.
- AI Intent 500 replay passes.
- Runtime exception log has no current-process traceback.
- Self-healing queue has no open blockers.
- Public export builds from the allowlist.
- Privacy scan passes on the sanitized public export.
- Release notes list behavior changes and known limitations.
- Rollback path is rehearsed or explicitly accepted by Tinman.
- Tinman explicitly approves the publish or push action.

## Human Review Gates

- Production readiness review.
- Accessibility and assistive-tech review.
- Latency and live-progress UX review.
- Public claims and legal/commercial-risk review when claims affect safety, compatibility, licensing, cost, performance, or supported platforms.
- Security/tool-access review for any new capability that can touch live machines, public repositories, removable media, network devices, or private files.

## Release Notes Must Include

- What changed in model routing, prompts, answer shape, tool access, privacy behavior, and recovery behavior.
- Known limitations and high-stakes boundaries.
- Rollback instructions.
- Package-health and live-smoke receipt paths.
- Whether the build is local-only, public-safe, experimental, or validated.

## Stop Conditions

Do not publish if:

- The export contains private runtime data, private IPs, credentials, absolute user paths, source-vault files, or generated private artifacts.
- Package health or live smoke is failing.
- A safety, privacy, or live-machine incident is unresolved.
- The release requires Tinman approval and that approval has not been given.
