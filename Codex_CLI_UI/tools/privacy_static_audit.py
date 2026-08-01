#!/usr/bin/env python3
"""Static privacy and sensitive-data checks for Codex CLI UI."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def run_cmd(args, cwd):
    return subprocess.run(
        args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )


def last_function_body(source, name):
    marker = f"def {name}("
    start = source.rfind(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def audit(root):
    root = Path(root).resolve()
    index_text = read_text(root / "index.html")
    styles_text = read_text(root / "styles.css")
    app_text = read_text(root / "app.js")
    server_text = read_text(root / "server.py")
    readme_text = read_text(root / "README.md").lower()
    privacy_doc_text = read_text(root / "docs" / "privacy-data-handling.md").lower()
    release_plan_text = read_text(root / "docs" / "public-release-plan.md").lower()
    release_scan_text = read_text(root / "tools" / "release_privacy_scan.py")
    export_text = read_text(root / "tools" / "build_public_export.py")
    live_smoke_text = read_text(root / "tools" / "live_feedback_smoke.py")
    machine_inventory_loader = last_function_body(server_text, "load_machine_inventory")
    checks = []

    add_check(
        checks,
        "composer-sensitive-data-warning",
        'id="privacyNotice"' in index_text
        and "do not paste passwords, API keys, tokens, or private customer data" in index_text
        and "Attach only files you want Codex to read for the active task" in index_text
        and "native local-path attachments are referenced from this Mac instead of copied when possible" in index_text
        and 'aria-describedby="runState keyboardHelp promptGuidanceSummary privacyNotice privacyStorageSummary privacyControlsSummary"' in index_text,
        "composer warning explains sensitive-data and active-task attachment-use boundaries",
    )
    add_check(
        checks,
        "visible-storage-review-boundary",
        'id="privacyStorageSummary"' in index_text
        and "local conversations and receipts stay on this Mac" in index_text
        and "local review can read the active task" in index_text
        and "cloud review only happens when cloud/research or share/export is chosen" in index_text
        and "keep private files, source vaults, and machine inventory out of shared profiles" in index_text
        and ".privacy-storage-summary" in styles_text,
        "composer-adjacent privacy summary explains storage, review, cloud, and shared-profile boundaries",
    )
    add_check(
        checks,
        "visible-privacy-controls-boundary",
        'id="privacyControlsSummary"' in index_text
        and "ask Codex to locate local task data first" in index_text
        and "keep, export, or remove only the confirmed files" in index_text
        and "local answers are not model-training data here" in index_text
        and "cloud modes follow the selected provider's terms" in index_text
        and "mode, access, web, and style choices persist locally with the saved task" in index_text
        and "confidential work" in index_text
        and ".privacy-controls-summary" in styles_text,
        "composer-adjacent privacy controls explain deletion/export, training-use, persisted settings, and confidential-work caution",
    )
    add_check(
        checks,
        "privacy-playbook",
        all(
            token in privacy_doc_text
            for token in (
                "user warning",
                "storage defaults",
                "redaction rules",
                "public export rules",
                "optional cloud use",
                "deletion and export",
            )
        ),
        "privacy/data-handling playbook covers warning, storage, redaction, export, cloud, and deletion boundaries",
    )
    add_check(
        checks,
        "release-privacy-plan",
        all(
            token in release_plan_text
            for token in (
                "private machine inventory",
                "passwords",
                "api keys",
                "absolute `/users/",
                "sanitized export",
            )
        ),
        "public-release plan names private data classes and sanitized export flow",
    )
    add_check(
        checks,
        "readme-privacy-warning",
        "do not paste api keys into chat" in readme_text
        and "does not include the private startup inventory" in readme_text,
        "README warns about API keys and cloud/private-inventory boundary",
    )
    add_check(
        checks,
        "feedback-redaction-helper",
        all(
            token in server_text
            for token in (
                "def redact_quality_text",
                "password|passwd|pwd",
                "api[_-]?key|token|secret",
                "record_quality_feedback",
            )
        ),
        "feedback and improvement storage route through redaction helper",
    )
    add_check(
        checks,
        "learning-redaction-helper",
        all(
            token in server_text
            for token in (
                "def sanitize_learning_text",
                "def redact_sensitive_inline_text",
                "api[_-]?key|token|secret",
                "stable knowledge",
            )
        ),
        "stable-learning path has secret redaction and durable-knowledge boundary",
    )
    add_check(
        checks,
        "sensitive-trait-inference-boundary",
        all(
            token in server_text
            for token in (
                "def sensitive_trait_inference_direct_answer",
                "religion",
                "race",
                "sexual orientation",
                "medical condition",
                "I should not infer that sensitive trait",
            )
        ),
        "direct-answer path blocks unnecessary sensitive-trait inference from indirect clues",
    )
    add_check(
        checks,
        "privacy-policy-boundary-direct-answer",
        all(
            token in server_text
            for token in (
                "def privacy_policy_boundary_direct_answer",
                "def is_privacy_policy_boundary_question",
                "minors' information",
                "confidential workplace content",
                "private-file use",
                "local conversations and receipts stay on this Mac",
                "not model-training data",
                "local file links as local-only",
                "privacy-preserving defaults",
            )
        )
        and "privacy-policy-minors-boundary" in live_smoke_text
        and "privacy-policy-storage-review-training" in live_smoke_text
        and "privacy-policy-local-link-boundary" in live_smoke_text,
        "direct-answer path explains minors, confidential work, file use, storage/review/training, local links, and privacy-preserving defaults",
    )
    add_check(
        checks,
        "privacy-minimization-extraction-boundary",
        all(
            token in server_text
            for token in (
                "def privacy_minimization_extraction_direct_answer",
                "def privacy_minimization_allowed_summary_direct_answer",
                "def privacy_minimization_field_specs",
                "def privacy_minimization_request_clause",
                "one narrow field from private/sensitive text",
                "did not summarize or repeat unrelated private details",
                "used only the fields you explicitly allowed",
                "Order number",
                "should not extract or repeat credentials",
            )
        )
        and "privacy-minimization-narrow-extraction" in live_smoke_text
        and "privacy-minimization-order-number-extraction" in live_smoke_text
        and "privacy-minimization-allowed-fields-summary" in live_smoke_text
        and "LIVE_SMOKE_FAKE_PRIVATE_VALUE" in live_smoke_text,
        "direct-answer path extracts or summarizes only requested fields without repeating unrelated private details or credentials",
    )
    add_check(
        checks,
        "user-data-boundary-direct-answer",
        all(
            token in server_text
            for token in (
                "def user_data_boundary_direct_answer",
                "def is_user_data_boundary_question",
                "local access is not the same thing as permission",
                "another user's private saved data",
                "separate profiles/workspaces",
            )
        )
        and "api:user-data-boundary-direct-answer" in server_text
        and "privacy-user-data-boundary" in live_smoke_text
        and "LIVE_SMOKE_OTHER_USER_SECRET" in live_smoke_text,
        "direct-answer path refuses to reveal another user's private local data on shared installs",
    )
    add_check(
        checks,
        "local-file-link-sharing-boundary",
        "dataset.localOnly" in app_text
        and "dataset.action" in app_text
        and "finder-reveal" in app_text
        and "Local-only Finder reveal" in app_text
        and "does not create a shareable link" in app_text
        and "Reveal local-only file" in app_text
        and '.local-file-link[data-local-only="true"]::after' in styles_text,
        "generated local file links are labeled as local-only Finder reveal controls instead of shareable links",
    )
    add_check(
        checks,
        "ssh-inventory-sanitizer",
        "def sanitize_ssh_info" in server_text
        and "password_keychain_service" in server_text
        and "raw SSH passwords are not loaded" in server_text
        and "sanitize_ssh_info" in machine_inventory_loader
        and 'safe_machine["ssh"] = sanitize_ssh_info' in machine_inventory_loader,
        "private machine inventory sanitizes SSH info and preserves Keychain references",
    )
    add_check(
        checks,
        "release-privacy-scan-patterns",
        all(
            token in release_scan_text
            for token in (
                '"private_ipv4"',
                '"absolute_user_path"',
                '"secret_assignment"',
                '".git/"',
                '"data/"',
                '"logs/"',
            )
        ),
        "release privacy scanner detects private IPs, user paths, secrets, and skips runtime/private folders",
    )
    add_check(
        checks,
        "public-export-sanitizers",
        all(
            token in export_text
            for token in (
                "ABSOLUTE_USER_PATH_RE",
                "PRIVATE_IPV4_RE",
                'text.replace("localuser", "localuser")',
                '"data/"',
                '"logs/"',
                '"private source-vault documents"',
                '"private chat-history golden tests"',
            )
        ),
        "public export scrubs local usernames, paths, private IPs, and excludes private runtime material",
    )
    add_check(
        checks,
        "public-export-includes-privacy-audit",
        '"tools/privacy_static_audit.py"' in export_text,
        "public export allowlist includes the privacy static audit",
    )

    scanner = root / "tools" / "release_privacy_scan.py"
    scanner_run = run_cmd([sys.executable, str(scanner), "--no-fail", "--json"], root) if scanner.exists() else None
    scanner_ok = scanner_run is not None and scanner_run.returncode == 0
    scanner_detail = "privacy scanner missing"
    if scanner_run is not None:
        try:
            report = json.loads(scanner_run.stdout or "{}")
            scanner_detail = f"{report.get('findingCount', 0)} local-tree findings; scanner runnable in no-fail mode"
        except json.JSONDecodeError:
            scanner_detail = (scanner_run.stderr or scanner_run.stdout or "scanner output unreadable")[:240]
    add_check(checks, "release-privacy-scan-runnable", scanner_ok, scanner_detail)

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run static privacy and sensitive-data checks for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
