#!/usr/bin/env python3
"""Focused P185 primary-author provenance and bounded recovery regressions."""

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
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def calculation_route(messages):
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    server.answer_obligation_prompt_rows(messages, route)
    return route


wheel_request = (
    "A wheel is 0.65 m in diameter and turns at 420 rpm. Ignoring slip, calculate "
    "its rim speed in m/s and the corresponding vehicle speed in km/h. Show the "
    "equations, units, and label both requested results."
)
wheel_messages = [{"role": "user", "text": wheel_request}]
wheel_route = calculation_route(wheel_messages)
wheel_plan = wheel_route.get("capabilityPlan") or {}
wheel_rows = server.answer_obligation_prompt_rows(wheel_messages, wheel_route)
requested_output_rows = [
    row for row in wheel_rows if row.get("kind") == "requested-output"
]
check(
    "multi-output-calculation-has-distinct-controller-obligations",
    wheel_plan.get("id") == "engineering-calculation"
    and wheel_plan.get("review_policy") == "calculation-contract"
    and len(requested_output_rows) >= 2
    and len({row.get("id") for row in requested_output_rows})
    == len(requested_output_rows),
    {"plan": wheel_plan, "requestedOutputs": requested_output_rows},
)

controller_answer = (
    "I could not close the requested calculation from a usable local-model draft. "
    "The supplied inputs are preserved, but no numerical result is being claimed."
)
controller_receipt = server.primary_draft_provenance_receipt(
    wheel_messages,
    wheel_route,
    controller_answer,
    kind="controller-synthesized-recovery",
    model="deterministic-engineering-recovery",
    done_reason="length",
    error="primary returned no visible answer",
    author_attempt_count=2,
)
check(
    "controller-recovery-marker-is-request-ledger-candidate-bound",
    server.controller_synthesized_calculation_candidate(
        wheel_messages,
        wheel_route,
        controller_answer,
    )
    and controller_receipt.get("controllerSynthesized") is True
    and controller_receipt.get("semanticReviewEligible") is False
    and controller_receipt.get("candidateSha256")
    == server.text_sha256(controller_answer),
    controller_receipt,
)
check(
    "forged-or-mutated-controller-recovery-cannot-bypass-review",
    not server.controller_synthesized_calculation_candidate(
        wheel_messages,
        wheel_route,
        controller_answer + " altered",
    ),
    wheel_route.get("_primaryDraftProvenance"),
)

review_calls = []


def forbidden_recovery_review(*_args, **_kwargs):
    review_calls.append(True)
    raise AssertionError("controller-authored recovery text reached semantic review")


bypass_answer = server.apply_generic_reasoning_final_gate(
    wheel_messages,
    wheel_route,
    controller_answer,
    audit_fn=forbidden_recovery_review,
)
bypass_audit = wheel_route.get("_genericReasoningAudit") or {}
check(
    "controller-known-fallback-bypasses-review-and-repair",
    bypass_answer == controller_answer
    and not review_calls
    and bypass_audit.get("controllerRecoveryBypass") is True
    and bypass_audit.get("reviewAttemptCount") == 0
    and bypass_audit.get("repairAttemptCount") == 0
    and wheel_route.get("_supervisionStatus") == "bounded",
    {"answer": bypass_answer, "audit": bypass_audit},
)

useful_route = calculation_route(wheel_messages)
useful_answer = (
    "Rim speed: v = pi(0.65 m)(420/min)/60 = 14.29 m/s. "
    "Vehicle speed: 14.29 m/s x 3.6 = 51.46 km/h. "
    "The units reduce to distance per time, and the scale is plausible."
)
server.primary_draft_provenance_receipt(
    wheel_messages,
    useful_route,
    useful_answer,
    kind="model-authored-useful-incomplete-draft",
    model=server.LOCAL_RESEARCH_MODEL,
    done_reason="length",
    author_attempt_count=1,
)
useful_review_calls = []


def sound_useful_review(_messages, _route, candidate, emit=None):
    useful_review_calls.append(candidate)
    return {
        "ok": True,
        "verdict": "sound",
        "issues": [],
        "finalAnswer": candidate,
        "obligationRows": [],
        "obligationReceipt": {"status": "pass"},
        "repairApplied": False,
        "reviewAttemptCount": 1,
        "verificationCompleted": True,
        "durationMs": 1,
    }


useful_final = server.apply_generic_reasoning_final_gate(
    wheel_messages,
    useful_route,
    useful_answer,
    audit_fn=sound_useful_review,
)
check(
    "useful-model-draft-retains-independent-review",
    useful_review_calls == [useful_answer]
    and useful_final == useful_answer
    and not (useful_route.get("_genericReasoningAudit") or {}).get(
        "controllerRecoveryBypass"
    ),
    {
        "calls": len(useful_review_calls),
        "provenance": useful_route.get("_primaryDraftProvenance"),
    },
)

handoff_route = calculation_route(wheel_messages)
handoff_calls = []


def successful_handoff(prompt, **kwargs):
    handoff_calls.append({"prompt": prompt, "kwargs": kwargs})
    return {"text": useful_answer, "doneReason": "stop", "evalCount": 220}


handoff = server.run_calculation_primary_author_handoff(
    wheel_messages,
    handoff_route,
    generate_fn=successful_handoff,
)
duplicate = server.run_calculation_primary_author_handoff(
    wheel_messages,
    handoff_route,
    generate_fn=successful_handoff,
)
handoff_receipt = handoff.get("receipt") or {}
check(
    "one-request-bound-local-author-handoff-maximum",
    len(handoff_calls) == 1
    and duplicate.get("alreadyAttempted") is True
    and handoff_receipt.get("attemptCount") == 1
    and handoff_receipt.get("maxAttempts") == 1
    and handoff_receipt.get("hiddenFallbackFanout") is False
    and handoff_calls[0]["kwargs"].get("allow_final_retry") is False,
    {"receipt": handoff_receipt, "calls": len(handoff_calls)},
)
check(
    "handoff-is-free-local-no-tool-and-exactly-bound",
    handoff_receipt.get("provider") == "ollama"
    and handoff_receipt.get("baseUrl") == "http://127.0.0.1:11434"
    and handoff_receipt.get("networkMode") == "local-loopback-only"
    and handoff_receipt.get("model") == server.LOCAL_RESEARCH_MODEL
    and handoff_receipt.get("bindingValid") is True
    and handoff_receipt.get("requestSha256")
    == server.text_sha256(wheel_request)
    and handoff_receipt.get("ledgerSha256")
    == (handoff_route.get("_answerObligationLedger") or {}).get("ledgerSha256")
    and "Use no tools and no external sources" in handoff_calls[0]["prompt"],
    handoff_receipt,
)

malformed_route = calculation_route(wheel_messages)
malformed = server.run_calculation_primary_author_handoff(
    wheel_messages,
    malformed_route,
    generate_fn=lambda *_args, **_kwargs: {
        "text": "",
        "doneReason": "stop",
        "error": "malformed empty author response",
    },
)
check(
    "malformed-empty-author-fails-without-fanout",
    not malformed.get("text")
    and (malformed.get("receipt") or {}).get("outcome") == "failed"
    and (malformed.get("receipt") or {}).get("attemptCount") == 1
    and (malformed.get("receipt") or {}).get("hiddenFallbackFanout") is False,
    malformed.get("receipt"),
)

slow_route = calculation_route(wheel_messages)
slow = server.run_calculation_primary_author_handoff(
    wheel_messages,
    slow_route,
    generate_fn=lambda *_args, **_kwargs: {
        "text": "",
        "doneReason": "timeout",
        "error": "bounded local timeout",
    },
)
check(
    "slow-author-remains-one-honest-failed-attempt",
    not slow.get("text")
    and (slow.get("receipt") or {}).get("doneReason") == "timeout"
    and "timeout" in (slow.get("receipt") or {}).get("error", "")
    and (slow.get("receipt") or {}).get("attemptCount") == 1,
    slow.get("receipt"),
)

stale_route = calculation_route(wheel_messages)


def stale_binding_author(*_args, **_kwargs):
    stale_route["_answerObligationLedger"] = {
        **(stale_route.get("_answerObligationLedger") or {}),
        "ledgerSha256": "stale-ledger-replaced-during-authoring",
    }
    return {"text": useful_answer, "doneReason": "stop"}


stale = server.run_calculation_primary_author_handoff(
    wheel_messages,
    stale_route,
    generate_fn=stale_binding_author,
)
check(
    "changed-request-or-ledger-binding-invalidates-handoff-answer",
    not stale.get("text")
    and (stale.get("receipt") or {}).get("bindingValid") is False
    and (stale.get("receipt") or {}).get("outcome") == "invalidated-binding",
    stale.get("receipt"),
)

cancel_route = calculation_route(wheel_messages)
cancel_calls = []
original_cancelled = server.route_run_cancelled
try:
    server.route_run_cancelled = lambda _route: True
    cancelled = server.run_calculation_primary_author_handoff(
        wheel_messages,
        cancel_route,
        generate_fn=lambda *_args, **_kwargs: cancel_calls.append(True),
    )
finally:
    server.route_run_cancelled = original_cancelled
check(
    "cancellation-is-checked-before-author-handoff",
    cancelled.get("cancelled") is True
    and not cancel_calls
    and (cancelled.get("receipt") or {}).get("attemptCount") == 0
    and cancel_route.get("_supervisionStatus") == "cancelled",
    cancelled.get("receipt"),
)

follow_messages = [
    {"role": "user", "text": wheel_request},
    {
        "role": "assistant",
        "text": (
            "Rim speed: 14.29 m/s. Vehicle speed: 51.46 km/h. "
            "These use v = pi D rpm / 60 and the no-slip assumption."
        ),
    },
    {
        "role": "user",
        "text": (
            "Change only the named wheel speed to 510 rpm and recalculate both requested outputs. "
            "Keep the 0.65 m diameter and the same no-slip assumption."
        ),
    },
]
follow_route = calculation_route(follow_messages)
follow_packet = server.build_calculation_primary_author_handoff_prompt(
    follow_messages,
    follow_route,
)
follow_frame = follow_route.get("intentFrame") or {}
check(
    "named-input-followup-preserves-calculation-owner-and-linked-result",
    follow_frame.get("domain") == "engineering_calculation"
    and follow_frame.get("actionType") == "recompute_with_superseded_constraint"
    and follow_packet.get("linkedPrior") is True
    and follow_packet.get("requestSha256")
    == server.text_sha256(server.latest_user_text(follow_messages))
    and "Change only the named wheel speed to 510 rpm" in follow_packet.get(
        "prompt", ""
    )
    and "Rim speed: 14.29 m/s" in follow_packet.get("prompt", ""),
    {"frame": follow_frame, "packet": follow_packet},
)

nonnumeric_messages = [
    {
        "role": "user",
        "text": (
            "Compare an internal message queue with a shared database table for coordinating two services. "
            "Recommend a default for bursty asynchronous work and name what would reverse the choice."
        ),
    }
]
nonnumeric_route = server.route_manager(
    nonnumeric_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
nonnumeric_calls = []
nonnumeric = server.run_calculation_primary_author_handoff(
    nonnumeric_messages,
    nonnumeric_route,
    generate_fn=lambda *_args, **_kwargs: nonnumeric_calls.append(True),
)
check(
    "nonnumeric-conversation-never-enters-calculation-handoff",
    (nonnumeric_route.get("capabilityPlan") or {}).get("id")
    != "engineering-calculation"
    and nonnumeric.get("ineligible") is True
    and not nonnumeric_calls,
    {
        "frame": nonnumeric_route.get("intentFrame"),
        "plan": nonnumeric_route.get("capabilityPlan"),
    },
)

sidecar = server.compact_answer_provenance(handoff_route)
sidecar_handoff = next(
    (item for item in sidecar if item.get("kind") == "primary-author-handoff"),
    {},
)
check(
    "public-handoff-receipt-is-metadata-only",
    bool(sidecar_handoff)
    and "activeRequest" not in sidecar_handoff
    and "linkedPriorResult" not in sidecar_handoff
    and "prompt" not in sidecar_handoff
    and sidecar_handoff.get("candidateSha256")
    == server.text_sha256(useful_answer),
    sidecar_handoff,
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
