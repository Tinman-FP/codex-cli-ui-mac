#!/usr/bin/env python3
"""Focused P183 single-owner final-review regressions."""

from __future__ import annotations

import contextlib
import hashlib
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


@contextlib.contextmanager
def patched(**replacements):
    originals = {name: getattr(server, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(server, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(server, name, value)


def route_for(review_policy="reasoning-audit", capability_id="conversation-reasoning", registered=True):
    request_hash = hashlib.sha256(b"synthetic-review-owner").hexdigest()
    return {
        "intentFrame": {
            "source": "generic-intelligence-kernel",
            "domain": "knowledge_question",
            "actionType": "reason_and_answer",
        },
        "kernelDecision": {"mode": "model-first"},
        "capabilityPlan": {
            "registered": registered,
            "id": capability_id,
            "review_policy": review_policy,
        },
        "_answerObligationLedger": {
            "kind": "answer-obligation-ledger",
            "version": getattr(server, "ANSWER_OBLIGATION_VERSION", 1),
            "requestSha256": request_hash,
            "ledgerSha256": request_hash,
            "obligations": [],
            "requiredForCompletion": False,
            "requiresClarification": False,
        },
        "_testRun": True,
    }


def run_synthetic_supervision(
    *,
    route,
    candidate,
    analytical_status="fail",
    package_mutation="",
    audit_result=None,
    engineering_result=None,
):
    messages = [{"role": "user", "text": "Explain the tradeoff and recommend a direction."}]
    calls = {"coach": [], "package": [], "audit": [], "engineering": []}

    def analytical(*_args, **_kwargs):
        return {
            "status": analytical_status,
            "score": 95 if analytical_status == "pass" else 40,
            "gaps": [] if analytical_status == "pass" else [{"kind": "synthetic-gap", "reason": "test"}],
        }

    def coach(_messages, _route, answer, **_kwargs):
        calls["coach"].append(answer)
        return {"text": "COACH MUTATION: " + answer}

    def package(_messages, _route, answer, **_kwargs):
        calls["package"].append(answer)
        text = package_mutation or answer
        return {
            "text": text,
            "contractGate": {"status": "pass", "failed": []},
            "preSendReview": {
                "sourceTextSha256": hashlib.sha256(str(answer).encode()).hexdigest(),
                "revisionApplied": text != answer,
                "flags": ["synthetic-contract-rewrite"] if text != answer else [],
            },
        }

    def audit(_messages, _route, answer, emit=None):
        calls["audit"].append(answer)
        if audit_result is not None:
            return dict(audit_result)
        return {
            "ok": True,
            "verdict": "sound",
            "issues": [],
            "finalAnswer": answer,
            "obligationRows": [],
            "repairApplied": False,
            "verificationCompleted": True,
            "deepReviewSkipped": False,
        }

    def engineering(_messages, _route, answer, emit=None):
        calls["engineering"].append(answer)
        if engineering_result is not None:
            return dict(engineering_result)
        return {
            "ok": True,
            "verdict": "sound",
            "issues": [],
            "finalAnswer": answer,
            "verificationCompleted": True,
            "finalVerificationPassed": True,
            "resolvedDeterministicIssues": True,
        }

    with patched(
        autonomy_supervisor_recover_answer=lambda *_args, **_kwargs: {"text": candidate, "recovered": False},
        analytical_answer_score=analytical,
        response_package=package,
        apply_last_mile_answer_guards=lambda _messages, _route, answer, **_kwargs: answer,
        deterministic_engineering_reasoning_issues=lambda *_args, **_kwargs: [],
        deterministic_engineering_decision_issues=lambda *_args, **_kwargs: [],
        deterministic_safety_control_issues=lambda *_args, **_kwargs: [],
        deterministic_engineering_scope_issues=lambda *_args, **_kwargs: [],
    ):
        answer = server.supervise_answer_before_emit(
            messages,
            route,
            "",
            candidate,
            web_search="disabled",
            quality_coach_fn=coach,
            reasoning_audit_fn=audit,
            engineering_audit_fn=engineering,
        )
    return answer, calls


candidate = "Use the simpler option because its failure mode is visible; validate the choice with one controlled trial."

strong_route = route_for()
strong_answer, strong_calls = run_synthetic_supervision(route=strong_route, candidate=candidate)
check(
    "reasoning-audit-strong-skips-quality-coach",
    len(strong_calls["coach"]) == 0,
    json.dumps(strong_calls, sort_keys=True),
)
check(
    "reasoning-audit-strong-runs-exactly-one-final-audit",
    strong_calls["audit"] == [candidate],
    json.dumps(strong_calls, sort_keys=True),
)
check(
    "reasoning-audit-strong-preserves-original-candidate",
    strong_answer == candidate,
    strong_answer,
)

rewrite_route = route_for()
rewritten = "PACKAGE MUTATION: " + candidate
rewrite_answer, rewrite_calls = run_synthetic_supervision(
    route=rewrite_route,
    candidate=candidate,
    analytical_status="pass",
    package_mutation=rewritten,
)
check(
    "reasoning-audit-skips-pre-send-contract-rewrite",
    rewrite_calls["package"] == [] and rewrite_calls["audit"] == [candidate] and rewrite_answer == candidate,
    json.dumps({"answer": rewrite_answer, "calls": rewrite_calls}, sort_keys=True),
)

weak_route = route_for()
weak_audit = {
    "ok": True,
    "verdict": "revise",
    "issues": [{
        "claim": "Unsupported conclusion",
        "kind": "reasoning-integrity",
        "reason": "The conclusion is not supported by the stated reasoning.",
    }],
    "finalAnswer": "",
    "lastRepairCandidate": candidate,
    "obligationRows": [],
    "repairApplied": False,
}
weak_answer, weak_calls = run_synthetic_supervision(
    route=weak_route,
    candidate=candidate,
    audit_result=weak_audit,
)
check(
    "weak-reasoning-draft-keeps-single-typed-review",
    weak_calls["coach"] == [] and weak_calls["audit"] == [candidate],
    json.dumps(weak_calls, sort_keys=True),
)
check(
    "failed-typed-audit-preserves-draft-and-bounds-truthfully",
    weak_route.get("_supervisionStatus") == "bounded"
    and weak_answer.startswith(candidate)
    and "remaining boundary" in weak_answer.lower(),
    json.dumps({"status": weak_route.get("_supervisionStatus"), "answer": weak_answer}),
)

unowned_route = route_for(registered=False)
_, unowned_calls = run_synthetic_supervision(route=unowned_route, candidate=candidate)
check(
    "no-review-skip-without-registered-full-surface-owner",
    len(unowned_calls["coach"]) == 1 and unowned_calls["audit"] == [],
    json.dumps(unowned_calls, sort_keys=True),
)

engineering_route = route_for("engineering-contract", "engineering-advisory")
engineering_answer, engineering_calls = run_synthetic_supervision(
    route=engineering_route,
    candidate=candidate,
    analytical_status="pass",
)
check(
    "engineering-contract-keeps-existing-owner",
    engineering_calls["engineering"] == [candidate]
    and engineering_calls["audit"] == []
    and engineering_calls["coach"] == []
    and engineering_answer == candidate,
    json.dumps({"answer": engineering_answer, "calls": engineering_calls}, sort_keys=True),
)

calculation_route = route_for("calculation-contract", "engineering-calculation")
calculation_answer, calculation_calls = run_synthetic_supervision(
    route=calculation_route,
    candidate=candidate,
)
check(
    "calculation-contract-keeps-existing-owner",
    calculation_calls["coach"] == []
    and calculation_calls["audit"] == [candidate]
    and calculation_answer == candidate,
    json.dumps({"answer": calculation_answer, "calls": calculation_calls}, sort_keys=True),
)

numeric_messages = [{
    "role": "user",
    "text": (
        "For a portable environmental chamber spanning -20 C to +80 C, compare thermoelectric and vapor compression. "
        "Recovery time matters most. Which direction would you choose, when would you reverse it, and what would you test first?"
    ),
}]
numeric_route = server.route_manager(
    numeric_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
numeric_route["_testRun"] = True
numeric_candidate = (
    "Choose vapor compression because recovery time is the dominant constraint and it provides 30% more recovery capacity. "
    "Reverse to thermoelectric only if package size and quiet operation outweigh recovery time. "
    "First test a controlled pull-down and heat-recovery cycle across the required temperature span."
)
numeric_spans = server.reasoning_candidate_evidence_spans(numeric_candidate)
numeric_payload = {
    "verdict": "sound",
    "issues": [],
    "notes": "",
    "obligations": [{"id": "choice", "status": "satisfied", "evidence": [numeric_spans[0]["id"]]}],
}
evidence_shape = server.validate_reasoning_review_evidence(numeric_payload, numeric_spans)
unsupported = server.unsupported_precision_claims_not_in_prompt(
    numeric_messages[0]["text"],
    numeric_candidate,
)
generic_numeric_route = route_for()
numeric_validation = server.engineering_single_pass_repair_validation(
    numeric_messages,
    generic_numeric_route,
    numeric_candidate,
)
check(
    "candidate-span-alone-does-not-prove-unsupported-numeric-claim",
    evidence_shape.get("ok") is True
    and any("30%" in item for item in unsupported)
    and numeric_validation.get("ok") is False
    and any(
        str(item.get("kind") or "") in {"unsupported-technical-precision", "unsupported-numeric-claim"}
        for item in numeric_validation.get("issues") or []
        if isinstance(item, dict)
    ),
    json.dumps({
        "evidenceShape": evidence_shape,
        "unsupported": unsupported,
        "validation": numeric_validation,
    }, sort_keys=True),
)

nonnumerical_messages = [{
    "role": "user",
    "text": (
        "Compare event sourcing and CRUD for an audit-heavy inventory service, recommend a direction, "
        "state when you would reverse it, and name the first test you would run."
    ),
}]
nonnumerical_route = server.route_manager(
    nonnumerical_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "event-token-does-not-trigger-vent-engineering-owner",
    (nonnumerical_route.get("intentFrame") or {}).get("domain") == "knowledge_comparison"
    and (nonnumerical_route.get("capabilityPlan") or {}).get("id") == "expert-comparison",
    json.dumps({
        "frame": nonnumerical_route.get("intentFrame"),
        "plan": nonnumerical_route.get("capabilityPlan"),
    }, sort_keys=True),
)


failed = [item for item in checks if item["status"] != "pass"]
print(json.dumps({
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}, indent=2, sort_keys=True))
raise SystemExit(1 if failed else 0)
