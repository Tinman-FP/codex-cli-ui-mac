#!/usr/bin/env python3
"""Focused P184 compact-review, no-fanout, and ambiguity regressions."""

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
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


comparison_messages = [{
    "role": "user",
    "text": (
        "Compare two offline queue designs for an internal scheduling API. Recommend one, "
        "state when you would reverse the choice, and name the first validation test."
    ),
}]
comparison_route = {
    "intentFrame": {
        "domain": "knowledge_question",
        "userGoal": "Compare two offline queue designs and recommend one.",
        "expectedOutput": "A recommendation, reversal condition, and validation test.",
        "typedConstraintUpdate": {},
    },
    "capabilityPlan": {"id": "conversation-reasoning", "review_policy": "reasoning-audit"},
}
comparison_draft = (
    "Use a durable client queue with idempotency keys because shop Wi-Fi is intermittent. "
    "Reverse the choice if every workstation has a continuously available local gateway. "
    "First validation test: interrupt the network during a write, reconnect, and verify exactly one committed job."
)
comparison_rows = [
    {"id": "obl-recommend", "kind": "deliverable", "text": "recommend one"},
    {"id": "obl-reverse", "kind": "deliverable", "text": "state when to reverse"},
]
comparison_spans = server.reasoning_candidate_evidence_spans(comparison_draft)
compact_prompt = server.generic_reasoning_audit_prompt(
    comparison_messages,
    comparison_route,
    comparison_draft,
    obligation_rows=comparison_rows,
    evidence_spans=comparison_spans,
)
check(
    "compact-prompt-carries-candidate-once-by-indexed-spans",
    compact_prompt.count(comparison_draft) == 0
    and "Controller-normalized candidate" not in compact_prompt
    and json.dumps(comparison_spans, ensure_ascii=True) in compact_prompt
    and len(compact_prompt) < 6500,
    json.dumps({"promptChars": len(compact_prompt), "spanCount": len(comparison_spans)}),
)
check(
    "nonnumerical-review-omits-inactive-specialist-inventories",
    "For engineering calculations" not in compact_prompt
    and "Programming correctness contract" not in compact_prompt
    and "collider" not in compact_prompt.lower(),
)
check(
    "compact-prompt-contains-only-unresolved-obligation-rows",
    all(row["id"] in compact_prompt for row in comparison_rows)
    and "obl-controller-proven" not in compact_prompt,
)
equation_spans = server.reasoning_candidate_evidence_spans(
    "Cable loss = 18^2 * 0.0996 = 32.27 W. The updated limit fails."
)
check(
    "indexed-spans-preserve-complete-equations",
    any("18^2 * 0.0996 = 32.27 W" in row.get("text", "") for row in equation_spans),
    json.dumps(equation_spans, ensure_ascii=True),
)

profile = server.generic_reasoning_audit_profile(
    comparison_route,
    messages=comparison_messages,
    draft=comparison_draft,
)
calculation_profile = server.generic_reasoning_audit_profile(
    {"intentFrame": {"domain": "engineering_calculation"}},
    messages=[{"role": "user", "text": "Calculate two checked outputs from supplied values."}],
    draft="Result one = 1 unit. Result two = 2 units.",
)
check(
    "accurate-local-reviewer-retained-with-one-hard-capped-attempt",
    profile.get("reviewModel") == server.GENERIC_REASONING_AUDIT_MODEL
    and "deepseek" not in str(profile.get("reviewModel") or "").lower()
    and profile.get("reviewFallbackModel") == ""
    and profile.get("verificationFallbackModel") == ""
    and profile.get("retryPrimary") is False
    and profile.get("reviewTimeout") == 80
    and profile.get("reviewNumCtx") == 6000,
    json.dumps({key: profile.get(key) for key in ("reviewModel", "reviewFallbackModel", "verificationFallbackModel", "retryPrimary", "reviewTimeout", "reviewNumCtx")}),
)
check(
    "numerical-profile-uses-the-accurate-local-deep-reviewer",
    calculation_profile.get("reviewModel") == server.LOCAL_DEEP_REVIEW_MODEL
    and calculation_profile.get("reviewModel") == server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL
    and calculation_profile.get("reviewFallbackModel") == ""
    and calculation_profile.get("retryPrimary") is False
    and calculation_profile.get("reviewTimeout") == 60,
    json.dumps({key: calculation_profile.get(key) for key in ("reviewModel", "reviewFallbackModel", "retryPrimary", "reviewTimeout")}),
)

original_generate = server.run_ollama_generate
generate_calls = []


def valid_generate(_prompt, **kwargs):
    generate_calls.append(kwargs)
    return {
        "text": json.dumps({
            "verdict": "unsafe",
            "issues": [{"claim": "contradiction", "kind": "logical-contradiction", "reason": "The conclusion reverses the stated premise."}],
            "notes": "Unsafe contradiction detected.",
            "obligations": [{"id": "obl-semantic", "status": "uncertain", "evidence": []}],
        }),
        "doneReason": "stop",
        "evalCount": 71,
        "promptEvalCount": 410,
    }


server.run_ollama_generate = valid_generate
try:
    reviewed = server.run_reasoning_json_review(
        compact_prompt,
        server.GENERIC_REASONING_AUDIT_MODEL,
        "",
        timeout=80,
        num_predict=900,
        num_ctx=6000,
        retry_primary=False,
        required_obligation_ids=["obl-semantic"],
        evidence_spans=comparison_spans,
    )
finally:
    server.run_ollama_generate = original_generate
metadata = (reviewed.get("attemptMetadata") or [{}])[0]
check(
    "unsafe-semantic-contradiction-remains-a-valid-independent-decision",
    len(generate_calls) == 1
    and reviewed.get("attemptCount") == 1
    and (reviewed.get("payload") or {}).get("verdict") == "unsafe"
    and metadata.get("promptChars") == len(compact_prompt)
    and len(metadata.get("promptSha256") or "") == 64
    and metadata.get("evidenceSpanCount") == len(comparison_spans)
    and metadata.get("bindingStatus") == "pass",
    json.dumps(metadata, sort_keys=True),
)


def invalid_generate(_prompt, **kwargs):
    invalid_calls.append(kwargs)
    return {"text": "The draft seems fine.", "doneReason": "stop"}


invalid_calls = []
server.run_ollama_generate = invalid_generate
try:
    malformed = server.run_reasoning_json_review(
        compact_prompt,
        server.GENERIC_REASONING_AUDIT_MODEL,
        "",
        timeout=80,
        num_predict=900,
        num_ctx=6000,
        retry_primary=False,
        required_obligation_ids=["obl-semantic"],
        evidence_spans=comparison_spans,
    )
finally:
    server.run_ollama_generate = original_generate
check(
    "malformed-review-fails-closed-without-retry-fanout",
    len(invalid_calls) == 1
    and malformed.get("attemptCount") == 1
    and not malformed.get("payload"),
    malformed.get("error") or "",
)

# Production generic profile supplies no fallback, so malformed/slow output is
# one attempt. Exercise that exact shape independently from the generic runner.
single_calls = []


def slow_error(_prompt, **kwargs):
    single_calls.append(kwargs)
    return {"text": "", "error": "bounded local timeout", "doneReason": "timeout"}


server.run_ollama_generate = slow_error
try:
    slow = server.run_reasoning_json_review(
        compact_prompt,
        profile["reviewModel"],
        profile["reviewFallbackModel"],
        profile["reviewTimeout"],
        profile["reviewNumPredict"],
        profile["reviewNumCtx"],
        retry_primary=profile["retryPrimary"],
        required_obligation_ids=["obl-semantic"],
        evidence_spans=comparison_spans,
    )
finally:
    server.run_ollama_generate = original_generate
check(
    "production-malformed-or-slow-review-is-one-attempt-and-bounded",
    len(single_calls) == 1 and slow.get("attemptCount") == 1 and not slow.get("payload"),
    slow.get("error") or "",
)

controller_messages = [{"role": "user", "text": "Use exactly 5 mm."}]
controller_answer = "Use exactly 5 mm."
controller_route = {
    "intentFrame": {"domain": "knowledge_question", "userGoal": "Preserve the supplied value", "expectedOutput": "A direct answer"},
    "capabilityPlan": {"id": "conversation-reasoning", "review_policy": "reasoning-audit"},
}
controller_ledger = {
    "kind": "answer-obligation-ledger",
    "version": server.ANSWER_OBLIGATION_VERSION,
    "requestSha256": server.text_sha256(server.latest_user_text(controller_messages)),
    "obligations": [{
        "id": "obl-controller-only",
        "kind": "constraint",
        "text": "5 mm",
        "source": "request",
        "labelPattern": "",
        "unitPattern": "",
        "constraintType": "numeric",
    }],
    "requiresClarification": False,
    "requiredForCompletion": True,
    "ledgerSha256": "controller-bound-ledger-fixture",
}
controller_route["_answerObligationLedger"] = controller_ledger
unexpected_review_calls = []
controller_audit = server.run_generic_reasoning_audit(
    controller_messages,
    controller_route,
    controller_answer,
    triage_fn=lambda *_args, **_kwargs: {"attempted": False, "passed": False},
    review_fn=lambda *_args, **_kwargs: unexpected_review_calls.append("review") or {},
)
check(
    "fully-controller-discharged-rows-launch-no-model-review",
    unexpected_review_calls == []
    and controller_audit.get("reviewAttemptCount") == 0
    and ((controller_audit.get("obligationReviewPlan") or {}).get("controllerDischarged") is True)
    and (controller_audit.get("obligationReceipt") or {}).get("status") == "pass",
    json.dumps({
        "calls": unexpected_review_calls,
        "reviewAttemptCount": controller_audit.get("reviewAttemptCount"),
        "plan": controller_audit.get("obligationReviewPlan"),
        "receipt": controller_audit.get("obligationReceipt"),
    }, sort_keys=True),
)

follow_messages = [
    {"role": "user", "text": "Calculate the result with flow = 8 L/min."},
    {"role": "assistant", "text": "The checked result is 12.5 minutes."},
    {"role": "user", "text": "Change the flow to 10 L/min and recalculate."},
]
follow_route = {
    "intentFrame": {
        "domain": "engineering_calculation",
        "userGoal": "Recompute the prior result",
        "expectedOutput": "The updated result and comparison",
        "typedConstraintUpdate": {"kind": "replace-only-named-input", "name": "flow", "value": "10 L/min"},
    },
    "_contextLineage": {"transition": "linked-follow-up"},
}
follow_prompt = server.generic_reasoning_audit_prompt(
    follow_messages,
    follow_route,
    "Updated result = 10 minutes, compared with 12.5 minutes before.",
    obligation_rows=[{"id": "obl-updated", "kind": "requested-output", "text": "updated result"}],
)
check(
    "changed-input-lineage-is-compact-and-explicitly-bound",
    "replace-only-named-input" in follow_prompt
    and "10 L/min" in follow_prompt
    and "12.5 minutes" in follow_prompt
    and "Controller-normalized candidate" not in follow_prompt,
)

ordinal_query = comparison_messages[0]["text"]
ambiguous_query = "Make the replacement configuration match Northwind."
check(
    "prospective-modified-ordinal-does-not-trigger-referent-guard",
    server.material_unresolved_referent([{"role": "user", "text": ordinal_query}], {}) == "",
)
check(
    "undefined-configuration-match-clarifies-before-tools",
    bool(server.material_unresolved_referent([{"role": "user", "text": ambiguous_query}], {}))
    and (server.unresolved_referent_preflight_response([{"role": "user", "text": ambiguous_query}], {}) or {}).get("mode")
    == "unresolved-referent-clarification",
)
check(
    "explicit-artifact-match-remains-local-action-eligible",
    server.material_unresolved_referent([{"role": "user", "text": "Make server.py match config/reference.py."}], {}) == "",
)

passed = sum(item["status"] == "pass" for item in checks)
failed = len(checks) - passed
print(json.dumps({
    "status": "pass" if failed == 0 else "fail",
    "checkCount": len(checks),
    "passed": passed,
    "failed": failed,
    "checks": checks,
}, indent=2))
raise SystemExit(0 if failed == 0 else 1)
