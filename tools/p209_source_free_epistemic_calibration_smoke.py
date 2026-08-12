#!/usr/bin/env python3
"""Focused P209 source-free assurance and authority calibration regressions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


messages = [
    {
        "role": "user",
        "text": (
            "Compare event sourcing and CRUD for an audit-heavy inventory service, "
            "recommend a direction, state when you would reverse it, and name the "
            "first test you would run."
        ),
    }
]
route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)

guarantee_answer = (
    "Event sourcing guarantees that every inventory change is retained for audit."
)
guarantee_issues = server.stable_comparison_epistemic_overclaim_issues(
    messages,
    route,
    guarantee_answer,
)
check(
    "source-free-absolute-guarantee-is-rejected",
    any(item.get("kind") == "source-free-absolute-assurance" for item in guarantee_issues),
    guarantee_issues,
)

negated_answer = (
    "Event sourcing does not guarantee a correct audit trail; implementation and validation still matter."
)
negated_issues = server.stable_comparison_epistemic_overclaim_issues(
    messages,
    route,
    negated_answer,
)
check(
    "explicit-no-guarantee-caveat-is-not-overblocked",
    not negated_issues,
    negated_issues,
)

authority_answer = (
    "Event sourcing satisfies regulatory compliance for an inventory service."
)
authority_issues = server.stable_comparison_epistemic_overclaim_issues(
    messages,
    route,
    authority_answer,
)
check(
    "unsupplied-regulatory-authority-is-rejected",
    any(item.get("kind") == "source-free-authority-claim" for item in authority_issues),
    authority_issues,
)

authority_messages = [
    {
        "role": "user",
        "text": (
            "Compare event sourcing and CRUD for our stated regulatory compliance "
            "requirement, but do not claim certification."
        ),
    }
]
authority_route = server.route_manager(
    authority_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
allowed_authority_issues = server.stable_comparison_epistemic_overclaim_issues(
    authority_messages,
    authority_route,
    "Event sourcing supports the stated regulatory compliance requirement but does not certify the system.",
)
check(
    "user-supplied-authority-remains-visible-with-caveat",
    not allowed_authority_issues,
    allowed_authority_issues,
)

cautious_answer = (
    "Event sourcing supports reconstruction of prior state, while CRUD can support auditability through a separate history mechanism."
)
cautious_issues = server.stable_comparison_epistemic_overclaim_issues(
    messages,
    route,
    cautious_answer,
)
check(
    "conditional-mechanism-language-passes",
    not cautious_issues,
    cautious_issues,
)

calibrated = server.calibrate_stable_comparison_epistemic_overclaims(
    messages,
    route,
    (
        "Event sourcing guarantees that every change is retained and satisfies "
        "regulatory requirements."
    ),
)
check(
    "calibrator-downgrades-certainty-and-outside-authority",
    calibrated.get("applied") is True
    and "guarantee" not in calibrated.get("text", "").lower()
    and "regulatory" not in calibrated.get("text", "").lower()
    and "supports the conclusion that" in calibrated.get("text", "").lower()
    and "stated audit requirement" in calibrated.get("text", "").lower(),
    calibrated,
)

polished_calibration = server.calibrate_stable_comparison_epistemic_overclaims(
    messages,
    route,
    (
        "Event sourcing gives stronger guarantees and naturally satisfies the need "
        "for complete, tamper-proof traceability. Its history is always available, and it can "
        "report exact quantities at any moment. It gives a complete, tamper-proof audit trail."
    ),
)
check(
    "calibrator-keeps-human-grammar-and-removes-absolute-outcomes",
    polished_calibration.get("applied") is True
    and "gives stronger support" in polished_calibration.get("text", "").lower()
    and "naturally supports the need for traceability" in polished_calibration.get("text", "").lower()
    and "recorded quantities" in polished_calibration.get("text", "").lower()
    and "gives an audit trail" in polished_calibration.get("text", "").lower()
    and "always available" not in polished_calibration.get("text", "").lower()
    and "stronger supports" not in polished_calibration.get("text", "").lower()
    and not server.stable_comparison_epistemic_overclaim_issues(
        messages,
        route,
        polished_calibration.get("text", ""),
    ),
    polished_calibration,
)

candidate = (
    "I recommend event sourcing for the audit-heavy inventory service because it "
    "guarantees that every inventory change is retained for audit. CRUD is simpler "
    "to operate, but it needs a separate history mechanism to preserve the same trail. "
    "I would reverse this recommendation if regulatory requirements can be met by "
    "the simpler CRUD history path. My first test would replay the same failed and "
    "successful inventory changes through both approaches and compare reconstructed state."
)
candidate_gate = server.stable_expert_comparison_candidate_gate(
    messages,
    route,
    candidate,
)
check(
    "stable-comparison-gate-rejects-unsupported-assurance-and-authority",
    candidate_gate.get("accepted") is False
    and {item.get("kind") for item in candidate_gate.get("epistemicIssues") or []}
    == {"source-free-absolute-assurance", "source-free-authority-claim"},
    candidate_gate,
)

cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    candidate,
)
check(
    "epistemic-calibration-preserves-complete-comparison-contract",
    cleanup.get("applied") is True
    and cleanup.get("cleanupMode") == "epistemic-calibration"
    and cleanup.get("gate", {}).get("accepted") is True
    and "guarantee" not in cleanup.get("text", "").lower()
    and "regulatory" not in cleanup.get("text", "").lower()
    and "my first test would" in cleanup.get("text", "").lower(),
    cleanup,
)

combined_candidate = candidate.replace(
    "the same failed and successful inventory changes",
    "one million inventory changes",
)
combined_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    combined_candidate,
)
check(
    "quantity-and-authority-calibration-compose-before-one-gate",
    combined_cleanup.get("applied") is True
    and combined_cleanup.get("cleanupMode")
    == "written-magnitude-and-epistemic-calibration"
    and combined_cleanup.get("gate", {}).get("accepted") is True
    and "one million" not in combined_cleanup.get("text", "").lower()
    and "guarantee" not in combined_cleanup.get("text", "").lower()
    and "regulatory" not in combined_cleanup.get("text", "").lower(),
    combined_cleanup,
)

parameter_candidate = (
    "I recommend event sourcing for the audit-heavy inventory service because it "
    "supports replay and reconstruction of prior state. CRUD is simpler to operate, "
    "but it needs a separate history mechanism for the same audit trail. I would "
    "reverse this recommendation if read latency must be sub-millisecond or the "
    "simpler CRUD history path meets the stated "
    "audit need. My first test would run 10 000 inventory updates per second over "
    "one hour and compare reconstructed state."
)
parameter_claims = server.unsupported_precision_claims_not_in_prompt(
    messages[0]["text"],
    parameter_candidate,
)
check(
    "invented-comparison-test-rate-and-window-are-detected",
    "10 000 inventory updates per second" in parameter_claims
    and "one hour" in parameter_claims
    and any("sub" in item.lower() and "millisecond" in item.lower() for item in parameter_claims),
    parameter_claims,
)
parameter_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    parameter_candidate,
)
check(
    "comparison-test-parameters-generalize-without-losing-the-test",
    parameter_cleanup.get("applied") is True
    and parameter_cleanup.get("cleanupMode") == "test-parameter-generalization"
    and parameter_cleanup.get("gate", {}).get("accepted") is True
    and "representative inventory updates rate" in parameter_cleanup.get("text", "").lower()
    and "representative test window" in parameter_cleanup.get("text", "").lower()
    and "read latency must be very low" in parameter_cleanup.get("text", "").lower()
    and "my first test would" in parameter_cleanup.get("text", "").lower(),
    parameter_cleanup,
)

sample_candidate = parameter_candidate.replace(
    "10 000 inventory updates per second over one hour",
    "10,000 sequential events",
)
sample_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    sample_candidate,
)
check(
    "fixed-comparison-sample-count-generalizes-without-losing-the-test",
    sample_cleanup.get("applied") is True
    and sample_cleanup.get("cleanupMode") == "test-parameter-generalization"
    and sample_cleanup.get("gate", {}).get("accepted") is True
    and "10,000" not in sample_cleanup.get("text", "")
    and "representative set of sequential events" in sample_cleanup.get("text", "").lower()
    and "my first test would" in sample_cleanup.get("text", "").lower(),
    sample_cleanup,
)

supplied_parameter_messages = [
    {
        "role": "user",
        "text": (
            "Compare event sourcing and CRUD at 10,000 inventory updates per second "
            "over one hour with a sub-millisecond read-latency requirement, recommend "
            "a direction, and name the first test."
        ),
    }
]
supplied_parameter_route = server.route_manager(
    supplied_parameter_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
supplied_parameter_cleanup = server.generalize_unsupported_comparison_test_parameters(
    supplied_parameter_messages[0]["text"],
    parameter_candidate,
)
check(
    "user-supplied-test-rate-and-window-remain-exact",
    supplied_parameter_cleanup.get("applied") is False
    and "10 000 inventory updates per second" in supplied_parameter_cleanup.get("text", "")
    and "one hour" in supplied_parameter_cleanup.get("text", "")
    and "sub-millisecond" in supplied_parameter_cleanup.get("text", "")
    and not server.unsupported_precision_claims_not_in_prompt(
        supplied_parameter_messages[0]["text"],
        parameter_candidate,
    )
    and (supplied_parameter_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison",
    {
        "cleanup": supplied_parameter_cleanup,
        "capabilityPlan": supplied_parameter_route.get("capabilityPlan"),
    },
)

parameter_authority_candidate = candidate.replace(
    "the same failed and successful inventory changes",
    "10,000 inventory updates per second over one hour",
)
parameter_authority_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    parameter_authority_candidate,
)
check(
    "test-parameter-and-authority-calibration-compose-before-one-gate",
    parameter_authority_cleanup.get("applied") is True
    and parameter_authority_cleanup.get("cleanupMode")
    == "test-parameter-and-epistemic-calibration"
    and parameter_authority_cleanup.get("gate", {}).get("accepted") is True
    and "10,000" not in parameter_authority_cleanup.get("text", "")
    and "one hour" not in parameter_authority_cleanup.get("text", "").lower()
    and "guarantee" not in parameter_authority_cleanup.get("text", "").lower()
    and "regulatory" not in parameter_authority_cleanup.get("text", "").lower(),
    parameter_authority_cleanup,
)

review_calls = []


def forbidden_review(*_args, **_kwargs):
    review_calls.append(True)
    raise AssertionError("controller calibration should avoid a second model")


audited = server.run_generic_reasoning_audit(
    messages,
    route,
    combined_candidate,
    review_fn=forbidden_review,
)
check(
    "shared-audit-publishes-only-controller-revalidated-calibration",
    audited.get("ok") is True
    and audited.get("repairModel") == "deterministic-comparison-evidence-calibration"
    and audited.get("precisionCleanupMode")
    == "written-magnitude-and-epistemic-calibration"
    and audited.get("reviewAttemptCount", 0) == 0
    and not review_calls
    and "one million" not in audited.get("finalAnswer", "").lower()
    and "guarantee" not in audited.get("finalAnswer", "").lower()
    and "regulatory" not in audited.get("finalAnswer", "").lower(),
    audited,
)

programming_messages = [
    {
        "role": "user",
        "text": (
            "Implement a stable topological sort in Python and prove the ordering "
            "guarantee with executable tests."
        ),
    }
]
programming_route = server.route_manager(
    programming_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "formal-programming-guarantee-keeps-its-specialist-proof-contract",
    not server.stable_comparison_epistemic_overclaim_issues(
        programming_messages,
        programming_route,
        "The implementation guarantees stable order because the tests cover every ready-set transition.",
    ),
    {
        "capabilityPlan": programming_route.get("capabilityPlan"),
        "epistemicIssues": server.stable_comparison_epistemic_overclaim_issues(
            programming_messages,
            programming_route,
            "The implementation guarantees stable order because the tests cover every ready-set transition.",
        ),
    },
)

server.answer_obligation_prompt_rows(messages, route)
typed_prompt = server.build_stable_comparison_primary_author_handoff_prompt(
    messages,
    route,
).get("prompt", "")
check(
    "typed-author-prompt-prohibits-unsupported-assurance-and-authority",
    "Do not claim an option guarantees, ensures, proves, certifies" in typed_prompt
    and "legal or regulatory compliance" in typed_prompt
    and "traceability exact, complete, tamper-proof, or always available" in typed_prompt
    and "Do not invent workload rates, fixed sample counts, test durations, or latency thresholds" in typed_prompt,
    typed_prompt[:1200],
)

failed = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
