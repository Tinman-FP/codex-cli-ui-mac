# Codex CLI UI Security And Responsible Disclosure

Codex CLI UI can interact with local files, local models, generated artifacts, and optionally local tools. Security reports should avoid exposing secrets or private machine details.

## Report Privately When Possible

Use a private maintainer contact or security advisory channel when a security-sensitive report includes:

- API keys, passwords, tokens, cookies, SSH keys, or private certificates.
- Private IP addresses, VPN hostnames, printer credentials, or router details.
- A privacy leak involving local files, generated artifacts, source-vault documents, or chat history.
- A tool-action path that could affect live machines, removable media, electrical systems, or public repositories.

If only a public issue tracker is available, post a minimal public summary and ask for a private channel before sharing sensitive details.

## Report Publicly When Safe

Public issues are appropriate for:

- Install or startup failures that do not expose private paths or credentials.
- UI bugs, accessibility issues, broken links, or package-health failures.
- Documentation mistakes.
- Reproducible wrong-answer behavior using synthetic data.

## Triage Process

1. Acknowledge the report and classify severity.
2. Preserve the prompt, answer, logs, receipt, version, and package-health output.
3. Stop risky live-machine or public-repository actions if they are involved.
4. Reproduce with the smallest safe local fixture.
5. Patch the smallest systemic path.
6. Add or update a regression, static audit, live smoke case, or package-health check.
7. Restart and rerun focused verification.
8. Write a checkpoint with the fix, receipt, and any remaining limits.

## Disclosure Notes

Do not claim certification, legal approval, electrical safety, medical safety, or high-stakes suitability unless qualified review actually happened. Public disclosure should say what was fixed, what remains limited, and which versions or package receipts are affected.
