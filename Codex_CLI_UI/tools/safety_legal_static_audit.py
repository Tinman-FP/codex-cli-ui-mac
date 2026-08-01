#!/usr/bin/env python3
"""Static safety/legal boundary checks for Codex CLI UI."""

import argparse
import json
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def audit(root):
    root = Path(root).resolve()
    server_text = (root / "server.py").read_text(encoding="utf-8")
    readme_text = (root / "README.md").read_text(encoding="utf-8")
    playbook_text = (root / "docs" / "production-readiness-playbook.md").read_text(encoding="utf-8").lower()
    localization_text = (root / "docs" / "localization-layout-qa-checklist.md").read_text(encoding="utf-8")
    checks = []

    add_check(
        checks,
        "direct-answer-hook-exists",
        all(
            token in server_text
            for token in (
                "def is_safety_legal_boundary_question",
                "def safety_legal_boundary_direct_answer",
                "safety_legal_boundary_direct_answer(messages)",
            )
        ),
        "legal/safety boundary questions use a fast local direct-answer path",
    )
    add_check(
        checks,
        "legal-certainty-boundary",
        all(
            token in server_text
            for token in (
                "He should not give unsafe legal certainty",
                "jurisdiction, facts, timing, source authority, and qualified review",
                "property, safety, permits, money, business liability, or rights",
            )
        ),
        "direct answer refuses unsafe legal certainty and names the high-stakes boundary",
    )
    add_check(
        checks,
        "illegal-behavior-boundary",
        all(
            token in server_text
            for token in (
                "avoid normalizing illegal behavior",
                "redirect toward lawful, safe alternatives",
                "refuse operational help for unlawful action",
            )
        ),
        "direct answer redirects illegal-behavior prompts toward lawful alternatives",
    )
    live_smoke_text = (root / "tools" / "live_feedback_smoke.py").read_text(encoding="utf-8")
    add_check(
        checks,
        "adversarial-safety-interlock-boundary",
        all(
            token in server_text
            for token in (
                "def is_safety_adversarial_boundary_question",
                "def safety_adversarial_boundary_direct_answer",
                "I can't help with step-by-step instructions to bypass a safety interlock",
                "fictional or hypothetical",
                "lockout/tagout troubleshooting checklist",
                "defeat the guard sensor",
                "only for testing",
            )
        )
        and "safety-adversarial-interlock-refusal" in live_smoke_text,
        "adversarial safety-interlock prompts refuse bypass steps and redirect to safe troubleshooting",
    )
    add_check(
        checks,
        "general-safety-boundary",
        all(
            token in server_text
            for token in (
                "def is_general_safety_boundary_question",
                "def safety_general_boundary_direct_answer",
                "safety_general_boundary_direct_answer(messages)",
                "self-harm language needs immediate, calm escalation",
                "refuse to enable fraud",
                "refuse harassment",
                "refuse cyber-abuse instructions",
                "not give unsafe medical directives",
                "avoid unsafe financial certainty",
                "require confirmation before applying risky recommendations",
                "stable across repeats",
            )
        )
        and all(
            token in live_smoke_text
            for token in (
                "safety-general-fraud-refusal",
                "safety-general-harassment-refusal",
                "safety-general-cyber-refusal",
            )
        ),
        "general safety prompts cover self-harm, fraud, harassment, cyber abuse, medical/financial certainty, risky actions, and repeat pressure",
    )
    add_check(
        checks,
        "high-stakes-policy-boundary",
        all(
            token in server_text
            for token in (
                "def is_high_stakes_policy_question",
                "def high_stakes_policy_direct_answer",
                "high_stakes_policy_direct_answer(messages)",
                "detect medical intent",
                "avoid pretending to be a lawyer",
                "detect financial advice intent",
                "employment, hiring, housing, lending, credit, and education-placement impact",
                "safety-critical engineering intent",
                "regulations or standards",
                "log high-stakes interactions",
                "minimizing sensitive data",
            )
        )
        and all(
            token in live_smoke_text
            for token in (
                "high-stakes-medical-boundary-general",
                "high-stakes-financial-boundary-general",
                "high-stakes-impact-decision-boundary",
                "high-stakes-engineering-regulatory-boundary",
                "high-stakes-compliant-logging-boundary",
            )
        ),
        "high-stakes prompts cover medical, legal, financial, high-impact decisions, engineering/regulatory validation, and compliant review logging",
    )
    add_check(
        checks,
        "legal-intent-detector",
        all(
            token in server_text
            for token in (
                "legal, compliance, permit, liability, contract, and code questions",
                "qualified attorney, inspector, or authority",
                "jurisdiction and purpose",
            )
        ),
        "legal intent detector covers compliance, permit, liability, contract, and code questions",
    )
    add_check(
        checks,
        "qualified-review-guidance",
        all(
            token in server_text
            for token in (
                "recommend qualified legal review",
                "organize the facts",
                "produce a checklist for the reviewer",
            )
        ),
        "direct answer still does useful prep work while recommending qualified review",
    )
    add_check(
        checks,
        "humor-disabled-for-legal-safety",
        "keeps humor out of safety-critical, legal, medical, financial" in readme_text,
        "README keeps personality settings out of safety-critical and legal answers",
    )
    add_check(
        checks,
        "release-playbook-legal-boundary",
        all(
            token in playbook_text
            for token in (
                "public claims",
                "source-backed",
                "legal/commercial risk",
                "qualified human reviews",
                "safety-critical",
            )
        ),
        "production playbook defines source-backed claims, legal/commercial review, and safety boundaries",
    )
    add_check(
        checks,
        "localization-jurisdiction-boundary",
        "Legal, policy, electrical code, aviation, tax, and safety caveats name the jurisdiction boundary" in localization_text,
        "localization checklist requires jurisdiction boundaries for legal/policy/code answers",
    )

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run static safety/legal boundary checks for Codex CLI UI.")
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
