#!/usr/bin/env python3
"""Focused P208 written-quantity evidence and bounded-cleanup regressions."""

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


def claims(query, answer, evidence=None):
    return server.unsupported_precision_claims_not_in_prompt(
        query,
        answer,
        evidence_claims=evidence,
    )


million_claims = claims(
    "Benchmark both approaches under the same workload.",
    "Benchmark both approaches after ingesting one million events.",
)
check(
    "written-million-workload-is-unsupported-precision",
    any("one million events" == item.lower() for item in million_claims),
    million_claims,
)

compound_claims = claims(
    "Run a representative endurance test.",
    "Use ten thousand cycles, then repeat with one hundred thousand cycles.",
)
check(
    "compound-written-magnitudes-are-detected",
    any("ten thousand cycles" == item.lower() for item in compound_claims)
    and any("one hundred thousand cycles" == item.lower() for item in compound_claims),
    compound_claims,
)

vague_scale_claims = claims(
    "Compare the database choices.",
    "The table may eventually contain millions of records.",
)
check(
    "plural-written-scale-is-not-treated-as-evidence",
    any("millions of records" == item.lower() for item in vague_scale_claims),
    vague_scale_claims,
)

allowed_prompt_claims = claims(
    "Test with one million events.",
    "My first test would ingest one million events.",
)
check(
    "user-supplied-written-scale-remains-allowed",
    not allowed_prompt_claims,
    allowed_prompt_claims,
)

allowed_evidence_claims = claims(
    "Use the checked workload from the evidence.",
    "The checked workload is one million events.",
    evidence=["one million events"],
)
check(
    "checked-written-scale-remains-allowed",
    not allowed_evidence_claims,
    allowed_evidence_claims,
)

ordinary_language_claims = claims(
    "Compare two options and name the first test.",
    "I compared the two options. My first test would use the same workload.",
)
check(
    "ordinary-count-and-first-test-language-is-not-overblocked",
    not ordinary_language_claims,
    ordinary_language_claims,
)

digit_claims = claims(
    "Compare the thermal designs.",
    "The second design is stable at 150 C.",
)
check(
    "existing-digit-unit-precision-guard-remains-active",
    any("150" in item for item in digit_claims),
    digit_claims,
)

generalized = server.generalize_unsupported_written_magnitude_claims(
    "Benchmark both approaches under the same workload.",
    "Benchmark both approaches after ingesting one million events.",
)
check(
    "unsupported-written-workload-is-generalized-without-new-value",
    generalized.get("applied") is True
    and "one million" not in generalized.get("text", "").lower()
    and "a representative number of events" in generalized.get("text", "").lower()
    and generalized.get("generalizedClaims") == ["one million events"],
    generalized,
)

preserved = server.generalize_unsupported_written_magnitude_claims(
    "Benchmark with one million events.",
    "Benchmark both approaches with one million events.",
)
check(
    "generalizer-does-not-change-user-supplied-scale",
    preserved.get("applied") is False
    and "one million events" in preserved.get("text", "").lower(),
    preserved,
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
candidate = (
    "I recommend event sourcing for the audit-heavy inventory service because it "
    "keeps each inventory change as part of the audit history. CRUD is operationally "
    "simpler, but it needs a separate audit path to preserve the same history. "
    "I would reverse this recommendation if operating simplicity matters more than "
    "replayable history. My first test would compare write and read behavior after "
    "ingesting one million events under the same failure scenario."
)
original_gate = server.stable_expert_comparison_candidate_gate(
    messages,
    route,
    candidate,
)
check(
    "stable-comparison-gate-rejects-written-invented-scale",
    original_gate.get("accepted") is False
    and any(
        "one million events" == item.lower()
        for item in original_gate.get("unsupportedPrecision") or []
    ),
    original_gate,
)

cleanup = server.sanitize_stable_comparison_unsupported_precision(
    messages,
    route,
    candidate,
)
check(
    "stable-comparison-preserves-test-by-generalizing-only-scale",
    cleanup.get("applied") is True
    and cleanup.get("cleanupMode") == "written-magnitude-generalization"
    and cleanup.get("gate", {}).get("accepted") is True
    and "one million" not in cleanup.get("text", "").lower()
    and "representative number of events" in cleanup.get("text", "").lower()
    and "my first test would" in cleanup.get("text", "").lower(),
    cleanup,
)

reviewed = server.run_generic_reasoning_audit(
    messages,
    route,
    candidate,
    review_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("the written-scale cleanup should avoid a second model")
    ),
)
check(
    "shared-audit-publishes-only-revalidated-generalized-candidate",
    reviewed.get("ok") is True
    and reviewed.get("repairModel")
    == "deterministic-written-magnitude-generalization"
    and reviewed.get("precisionCleanupMode")
    == "written-magnitude-generalization"
    and reviewed.get("reviewAttemptCount", 0) == 0
    and "one million" not in reviewed.get("finalAnswer", "").lower()
    and "representative number of events"
    in reviewed.get("finalAnswer", "").lower(),
    reviewed,
)

generation_profile = server.conversation_reasoning_generation_profile(
    messages,
    route,
)
check(
    "typed-comparison-author-has-hidden-reasoning-headroom-with-same-wall-cap",
    generation_profile.get("numPredict", 0) >= 2000
    and generation_profile.get("timeout") == 45
    and generation_profile.get("allowFinalRetry") is False,
    generation_profile,
)

truncated_route = dict(route)
truncated_route["_primaryGenerationReceipt"] = {
    "model": server.LOCAL_RESEARCH_MODEL,
    "doneReason": "length",
}
truncated_route["_primaryDraftProvenance"] = {
    "kind": "model-authored-useful-incomplete-draft",
    "doneReason": "length",
}
truncated_candidate = (
    "I recommend event sourcing because it preserves the audit history. "
    "I would reverse this recommendation if"
)
truncated_boundary = server.generic_reasoning_boundary_answer(
    {
        "verdict": "revise",
        "issues": [
            {
                "kind": "reasoning-audit-unavailable",
                "reason": "The reviewer did not return valid JSON.",
            }
        ],
    },
    truncated_candidate,
    route=truncated_route,
)
check(
    "length-truncated-primary-is-withheld-from-user-boundary",
    truncated_candidate not in truncated_boundary
    and "output limit" in truncated_boundary.lower()
    and "no verified repair" in truncated_boundary.lower(),
    truncated_boundary,
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
