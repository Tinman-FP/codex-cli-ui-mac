# Changelog

## v2026.07.03

- Adds the Golden Test Generator so Improvement Lab items become saved runnable regression tests.
- Records Test Bench pass/fail history in local `data/golden_test_results.json`.
- Feeds failed golden tests back into the Improvement Lab as high-priority regression items.
- Shows saved golden-test and failing-test counts in the Admin UI.
- Keeps public package defaults generic while preserving local-only runtime data.

## v2026.07.02

- Adds Manager, Coder, Review, Local Research, and Cloud Research mode wiring in the UI runtime.
- Adds the Admin Improvement Lab for `Fix this` feedback, tool gaps, review/archive actions, and regression-test candidates.
- Adds the Tool Recovery Engine for missing commands, missing Git remotes, disabled web paths, Klipper config discovery, local load failures, and permission boundaries.
- Adds local capability APIs for free allowlisted tool recovery, Klipper config discovery, and package-health checks.
- Keeps public package defaults generic and private printer/network data local-only.

## v2026.07.01.1

- Adds a private startup inventory card for machines, SSH aliases, tailnet hosts, and Mac resources.
- Adds safe working notes while Codex CLI is running.
- Creates a local-only `data/private/machines.json` template during install.
- Keeps private machine inventory, chat history, passwords, and local network details out of the public package.

## v2026.07.01

- Initial public Mac release.
- Adds a local browser UI for Codex CLI.
- Adds Fast and Careful local OSS profiles.
- Adds compact chat composer controls for Mode, Access, Reasoning, and Web.
- Adds red rounded app icon.
- Ships as a single DMG installer bundle.
