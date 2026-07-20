#!/usr/bin/env python3
"""Static production-readiness checks for Codex CLI UI public packaging."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def run_cmd(args, cwd):
    return subprocess.run(
        args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def load_production_partials(root):
    audit_path = Path(root) / "tests" / "ai_ui_intent_500_audit.json"
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    partials = []
    for item in items:
        if item.get("status") != "PARTIAL":
            continue
        if item.get("category") != "25. Production Readiness":
            continue
        partials.append(
            {
                "id": item.get("id"),
                "question": item.get("question", ""),
                "note": item.get("note", ""),
                "evidence": item.get("evidence", []),
            }
        )
    return partials


def render_markdown(report):
    lines = [
        "# Production Readiness Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Automated checks: {report['checkCount']}",
        f"- Failed checks: {report['failedCount']}",
        f"- Production human-review holds: {report['productionPartialCount']}",
        "",
        "## Automated Checks",
        "",
    ]
    for check in report["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {mark}: `{check['name']}` - {check['detail']}")
    lines.extend(["", "## Human Review Holds", ""])
    if report["productionPartials"]:
        for item in report["productionPartials"]:
            lines.append(f"- Q{item['id']}: {item['question']}")
            if item.get("note"):
                lines.append(f"  - Hold: {item['note']}")
    else:
        lines.append("- None found in the AI UI intent audit.")
    lines.extend(
        [
            "",
            "## Release Boundary",
            "",
            "- Automated PASS means the local release scaffolding exists and is statically verifiable.",
            "- Human-review holds remain PARTIAL until Tinman approval, release rehearsal, rollback drill, or qualified review is actually completed.",
            "- Do not publish from this report alone; pair it with package health, live smoke, public export privacy, and explicit approval receipts.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report, output_dir, label):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label).strip("-") or "production-readiness"
    base = f"{stamp}-{safe_label}"
    json_path = output_dir / f"{base}.json"
    markdown_path = output_dir / f"{base}.md"
    report_with_paths = dict(report)
    report_with_paths["jsonPath"] = str(json_path)
    report_with_paths["markdownPath"] = str(markdown_path)
    json_path.write_text(json.dumps(report_with_paths, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report_with_paths), encoding="utf-8")
    return report_with_paths


def audit(root):
    root = Path(root).resolve()
    playbook = root / "docs" / "production-readiness-playbook.md"
    release_plan = root / "docs" / "public-release-plan.md"
    support_doc = root / "docs" / "support.md"
    security_doc = root / "docs" / "security.md"
    checklist_doc = root / "docs" / "release-checklist.md"
    readme = root / "README.md"
    server = root / "server.py"
    live_smoke_tool = root / "tools" / "live_feedback_smoke.py"
    production_tool = root / "tools" / "production_readiness_audit.py"
    export_tool = root / "tools" / "build_public_export.py"
    api_run_payload_tool = root / "tools" / "api_run_payload_hardening_smoke.py"
    privacy_tool = root / "tools" / "release_privacy_scan.py"
    privacy_audit_tool = root / "tools" / "privacy_static_audit.py"
    privacy_live_tool = root / "tools" / "privacy_live_storage_audit.py"
    privacy_runtime_tool = root / "tools" / "privacy_runtime_audit.py"
    accessibility_tool = root / "tools" / "accessibility_static_audit.py"
    app_ui_contract_tool = root / "tools" / "app_ui_contract_static_audit.py"
    app_ui_browser_smoke_tool = root / "tools" / "app_ui_browser_smoke.py"
    localization_tool = root / "tools" / "localization_static_audit.py"
    safety_legal_tool = root / "tools" / "safety_legal_static_audit.py"
    ai_intent_human_qa_tool = root / "tools" / "ai_ui_intent_human_qa_lanes.py"
    ai_intent_promotion_tool = root / "tools" / "ai_ui_intent_promotion_candidates.py"
    ai_intent_replay_tool = root / "tools" / "ai_ui_intent_quality_replay.py"
    playbook_text = read_text(playbook).lower()
    release_text = read_text(release_plan).lower()
    support_text = read_text(support_doc).lower()
    security_text = read_text(security_doc).lower()
    checklist_text = read_text(checklist_doc).lower()
    readme_text = read_text(readme).lower()
    server_text = read_text(server)
    live_smoke_text = read_text(live_smoke_tool)
    export_text = read_text(export_tool)
    production_text = read_text(production_tool)
    checks = []

    add_check(
        checks,
        "release-owner",
        "tinman is the launch approver" in playbook_text and "explicitly approves" in playbook_text,
        "playbook names Tinman as launch approver and requires explicit approval",
    )
    add_check(
        checks,
        "rollback-plan",
        all(token in playbook_text for token in ("rollback", "previous working package", "./restart.command", "/api/package-health")),
        "playbook has rollback path, restart command, and package-health gate",
    )
    add_check(
        checks,
        "incident-response",
        all(token in playbook_text for token in ("incident response", "reproduce", "patch", "regression", "checkpoint")),
        "playbook has incident capture, reproduction, patch, regression, and checkpoint steps",
    )
    add_check(
        checks,
        "monitoring-signals",
        all(token in playbook_text for token in ("/api/package-health", "server-exceptions.log", "feedback", "self-healing")),
        "playbook names package health, exception log, feedback, and self-healing monitoring signals",
    )
    add_check(
        checks,
        "privacy-security",
        all(token in playbook_text for token in ("release_privacy_scan.py", "build_public_export.py --zip", "do not publish `data/`", "api keys")),
        "playbook has privacy scan/export process and private-data exclusions",
    )
    add_check(
        checks,
        "public-claims-review",
        all(token in playbook_text for token in ("public claims", "source-backed", "legal/commercial risk", "qualified human reviews")),
        "playbook defines public-claims and legal/commercial review boundary",
    )
    add_check(
        checks,
        "abuse-disclosure",
        all(token in playbook_text for token in ("github issues", "security-sensitive reports", "safety-critical")),
        "playbook defines public issue reporting, private sensitive reports, and safety boundaries",
    )
    add_check(
        checks,
        "support-docs",
        all(token in playbook_text for token in ("install", "restart", "troubleshooting", "uninstall", "ollama")),
        "playbook lists public support documentation and troubleshooting expectations",
    )
    add_check(
        checks,
        "public-support-doc",
        support_doc.exists()
        and all(token in support_text for token in ("package-health", "restart.command", "what not to include", "responsible-disclosure")),
        "public support doc covers package health, restart, safe report content, and escalation",
    )
    add_check(
        checks,
        "responsible-disclosure-doc",
        security_doc.exists()
        and all(token in security_text for token in ("responsible disclosure", "report privately", "security-sensitive", "triage process")),
        "security doc covers private reporting, sensitive reports, and triage",
    )
    add_check(
        checks,
        "release-checklist-doc",
        checklist_doc.exists()
        and all(token in checklist_text for token in ("package health", "live feedback smoke", "tinman explicitly approves", "stop conditions")),
        "release checklist covers gates, approval, and stop conditions",
    )
    add_check(
        checks,
        "model-update-process",
        all(token in playbook_text for token in ("model", "routing", "answer-shape", "regression", "release notes")),
        "playbook covers model/routing/answer behavior changes and release notes",
    )
    add_check(
        checks,
        "public-release-plan",
        release_plan.exists()
        and "public release must be a curated export" in release_text
        and "push only after tinman approves" in release_text,
        "public-release plan requires curated export and Tinman approval",
    )
    add_check(
        checks,
        "release-docs-linked",
        all(token in release_text for token in ("docs/support.md", "docs/security.md", "docs/release-checklist.md"))
        and all(token in playbook_text for token in ("docs/support.md", "docs/security.md", "docs/release-checklist.md")),
        "release plan and playbook link support, security, and release-checklist docs",
    )
    add_check(
        checks,
        "readme-prepackage",
        "pre-package check" in readme_text and "build_public_export.py --zip" in readme_text,
        "README documents package-health and public export flow",
    )
    add_check(
        checks,
        "required-tools-exist",
        all(
            path.exists()
            for path in (
                export_tool,
                api_run_payload_tool,
                privacy_tool,
                privacy_audit_tool,
                privacy_live_tool,
                privacy_runtime_tool,
                accessibility_tool,
                app_ui_contract_tool,
                app_ui_browser_smoke_tool,
                localization_tool,
                safety_legal_tool,
                ai_intent_human_qa_tool,
                ai_intent_promotion_tool,
                ai_intent_replay_tool,
            )
        ),
        "public export, live API payload smoke, privacy scan, privacy audits, live storage sampler, AI intent replay/promotion/human-QA, accessibility, localization, and safety/legal audit tools exist",
    )
    add_check(
        checks,
        "public-export-includes-audit-tools",
        all(
            token in export_text
            for token in (
                '"tools/accessibility_static_audit.py"',
                '"tools/app_ui_contract_static_audit.py"',
                '"tools/app_ui_browser_smoke.py"',
                '"tools/api_run_payload_hardening_smoke.py"',
                '"tools/ai_ui_intent_gap_backlog.py"',
                '"tools/ai_ui_intent_human_qa_lanes.py"',
                '"tools/ai_ui_intent_promotion_candidates.py"',
                '"tools/ai_ui_intent_quality_replay.py"',
                '"tools/localization_static_audit.py"',
                '"tools/privacy_live_storage_audit.py"',
                '"tools/privacy_runtime_audit.py"',
                '"tools/privacy_static_audit.py"',
                '"tools/production_readiness_audit.py"',
                '"tools/safety_legal_static_audit.py"',
            )
        ),
        "public export allowlist includes audit tools required by package health, AI intent promotion safety, and human-QA lane review",
    )
    add_check(
        checks,
        "production-direct-answer-coverage",
        all(
            token in server_text
            for token in (
                "def production_readiness_direct_answer",
                "rollback plan is documented locally",
                "incident-response process is documented",
                "Failed tool actions are monitored",
                "Tinman is the named launch approver",
                "qualified legal/commercial review has not been performed",
                "sanitized public export",
                "Not fully until Tinman signs off",
            )
        ),
        "server has production-readiness direct answers with launch-approval and no-overclaim boundaries",
    )
    add_check(
        checks,
        "production-live-smoke-coverage",
        all(
            token in live_smoke_text
            for token in (
                "production-rollback-plan-direct",
                "production-incident-response-direct",
                "production-failed-tool-monitoring-direct",
                "production-disclosure-direct",
                "production-launch-approver-direct",
                "production-public-claims-review-direct",
                "production-privacy-review-direct",
                "production-security-tool-access-direct",
                "production-public-failure-direct",
            )
        ),
        "live smoke covers production-readiness direct answers and launch/public-failure boundaries",
    )
    add_check(
        checks,
        "production-audit-receipt-mode",
        all(token in production_text for token in ("--write-report", "productionPartialCount", "Human Review Holds", "jsonPath", "markdownPath")),
        "production audit can write durable JSON/Markdown receipts and track human-review holds",
    )

    privacy_scan = run_cmd([sys.executable, str(privacy_tool), "--no-fail", "--json"], root) if privacy_tool.exists() else None
    privacy_ok = privacy_scan is not None and privacy_scan.returncode == 0
    privacy_detail = ""
    if privacy_scan is not None:
        try:
            privacy_report = json.loads(privacy_scan.stdout or "{}")
            privacy_detail = f"{privacy_report.get('findingCount', 0)} local-tree findings; no-fail audit runnable"
        except json.JSONDecodeError:
            privacy_detail = (privacy_scan.stderr or privacy_scan.stdout or "privacy scan output unreadable")[:240]
    add_check(checks, "privacy-scan-runnable", privacy_ok, privacy_detail or "privacy scanner missing")

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
        "productionPartialCount": len(load_production_partials(root)),
        "productionPartials": load_production_partials(root),
    }


def main():
    parser = argparse.ArgumentParser(description="Run static production-readiness checks for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write durable JSON and Markdown audit receipts.")
    parser.add_argument("--output-dir", default=None, help="Directory for --write-report receipts.")
    parser.add_argument("--label", default="production-readiness-audit", help="Receipt filename label for --write-report.")
    args = parser.parse_args()
    report = audit(args.root)
    if args.write_report:
        output_dir = args.output_dir or str(Path(args.root) / "data" / "golden_batch_results")
        report = write_report(report, output_dir, args.label)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        print(f"production human-review holds: {report['productionPartialCount']}")
        if args.write_report:
            print(f"json: {report['jsonPath']}")
            print(f"markdown: {report['markdownPath']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
