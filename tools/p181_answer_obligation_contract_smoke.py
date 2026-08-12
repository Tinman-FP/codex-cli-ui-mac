#!/usr/bin/env python3
"""Focused P181 obligation, ambiguity, and terminal-truth regressions."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


CHECKS = []


def check(name, passed, detail=""):
    CHECKS.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


def route_for(messages, web="disabled"):
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web,
    )
    route["_testRun"] = True
    return route


thermal_prompt = (
    "A 6061-T6 rail is 420 mm long and warms from 20 C to 65 C while rigidly fixed at both ends; "
    "use E = 69 GPa and alpha = 23.6e-6/C. Calculate compressive thermal stress, "
    "released-end free expansion, and the limiting assumption."
)
thermal_messages = [{"role": "user", "text": thermal_prompt}]
thermal_route = route_for(thermal_messages)
thermal_ledger = server.build_answer_obligation_ledger(thermal_messages, thermal_route)
thermal_route["_answerObligationLedger"] = thermal_ledger
thermal_outputs = [
    item for item in thermal_ledger["obligations"] if item.get("kind") == "requested-output"
]
check(
    "typed-distinct-requested-outputs",
    len(thermal_outputs) == 3
    and {item["text"] for item in thermal_outputs}
    == {"stress", "released-end free expansion", "limiting assumption"}
    and len({item["id"] for item in thermal_outputs}) == 3,
    json.dumps([(item["id"], item["text"]) for item in thermal_outputs]),
)

intermediate_answer = "The intermediate thermal strain is 0.001062. The limiting assumption is perfect restraint."
forged_rows = [
    {
        "id": item["id"],
        "status": "satisfied",
        "evidence": "The intermediate thermal strain is 0.001062.",
    }
    for item in thermal_ledger["obligations"]
]
forged_receipt = server.answer_obligation_completion_receipt(
    thermal_messages,
    thermal_route,
    intermediate_answer,
    forged_rows,
    review_success=True,
)
check(
    "intermediate-value-cannot-satisfy-requested-results",
    forged_receipt["status"] == "block"
    and all(item["status"] != "satisfied" for item in forged_receipt["items"] if item["id"] in {row["id"] for row in thermal_outputs}),
    json.dumps(forged_receipt["missingIds"]),
)

complete_answer = (
    "Compressive thermal stress = 73.3 MPa in compression. Released-end free expansion = 0.446 mm. "
    "The limiting assumption is perfectly rigid end restraint with uniform 6061-T6 properties over the 20 C to 65 C change. "
    "Using the supplied 420 mm length, E = 69 GPa, and alpha = 23.6e-6/C, the substitutions are "
    "sigma = E alpha delta-T and delta-L = alpha L delta-T. These results are the ideal fully restrained and fully released bounds."
)
output_evidence = {
    "stress": "Compressive thermal stress = 73.3 MPa in compression.",
    "released-end free expansion": "Released-end free expansion = 0.446 mm.",
    "limiting assumption": "The limiting assumption is perfectly rigid end restraint with uniform 6061-T6 properties over the 20 C to 65 C change.",
}
complete_rows = []
for item in thermal_ledger["obligations"]:
    evidence = output_evidence.get(item["text"])
    if not evidence:
        evidence = (
            "Using the supplied 420 mm length, E = 69 GPa, and alpha = 23.6e-6/C, the substitutions are sigma = E alpha delta-T and delta-L = alpha L delta-T."
            if item["kind"] in {"constraint", "evidence"}
            else "These results are the ideal fully restrained and fully released bounds."
        )
    complete_rows.append({"id": item["id"], "status": "satisfied", "evidence": evidence})
complete_receipt = server.answer_obligation_completion_receipt(
    thermal_messages,
    thermal_route,
    complete_answer,
    complete_rows,
    review_success=True,
)
check(
    "all-obligations-evidenced-pass",
    complete_receipt["status"] == "pass"
    and complete_receipt["satisfiedCount"] == complete_receipt["obligationCount"],
    json.dumps(complete_receipt["missingIds"]),
)

failed_review_receipt = server.answer_obligation_completion_receipt(
    thermal_messages,
    thermal_route,
    complete_answer,
    complete_rows,
    review_success=False,
)
check(
    "failed-review-cannot-complete",
    failed_review_receipt["status"] == "block" and failed_review_receipt["reviewSuccessful"] is False,
)

duplicate_rows = list(complete_rows) + [dict(complete_rows[0])]
duplicate_receipt = server.answer_obligation_completion_receipt(
    thermal_messages,
    thermal_route,
    complete_answer,
    duplicate_rows,
    review_success=True,
)
check(
    "duplicate-or-unknown-obligation-rows-fail-closed",
    duplicate_receipt["status"] == "block" and duplicate_receipt["duplicateIds"] == [complete_rows[0]["id"]],
    json.dumps(duplicate_receipt["duplicateIds"]),
)

best_draft = "The rail develops compressive stress if both ends remain fixed, and it expands if one end is released."
bounded_route = route_for(thermal_messages)
bounded_route["_answerObligationLedger"] = server.build_answer_obligation_ledger(thermal_messages, bounded_route)


def failed_audit(_messages, _route, _answer, emit=None):
    return {
        "ok": True,
        "verdict": "revise",
        "issues": [
            {
                "claim": "The requested numerical outputs are incomplete.",
                "kind": "answer-obligation-missing",
                "reason": "Stress and free expansion are not both explicitly reported.",
            }
        ],
        "finalAnswer": "",
        "lastRepairCandidate": best_draft,
        "obligationRows": [],
    }


bounded_answer = server.apply_generic_reasoning_final_gate(
    thermal_messages,
    bounded_route,
    best_draft,
    audit_fn=failed_audit,
)
check(
    "failed-rebuild-preserves-best-usable-draft",
    bounded_answer.startswith(best_draft)
    and "remaining boundary" in bounded_answer.lower()
    and bounded_route.get("_supervisionStatus") == "bounded",
    bounded_answer,
)

ambiguous_prompt = "Match Riverstone to the newer setup."
ambiguous_messages = [{"role": "user", "text": ambiguous_prompt}]
ambiguous_route = route_for(ambiguous_messages)
preflight = server.unresolved_referent_preflight_response(ambiguous_messages, ambiguous_route)
check(
    "exact-blind-ambiguity-intercepted-before-tools",
    preflight.get("handled") is True
    and preflight.get("returnCode") == 0
    and preflight.get("answer", "").count("?") == 1
    and server.answer_is_focused_clarification(preflight.get("answer"))
    and (ambiguous_route.get("_unresolvedReferentPreflight") or {}).get("toolCalls") == 0
    and (ambiguous_route.get("_unresolvedReferentPreflight") or {}).get("modelCalls") == 0,
    preflight.get("answer", ""),
)

cross_domain_messages = [
    {"role": "user", "text": "Why are my basil leaves curling upward?"},
    {"role": "assistant", "text": "Check light, heat, watering, and pests."},
    {"role": "user", "text": ambiguous_prompt},
]
cross_domain_route = route_for(cross_domain_messages)
cross_domain_route.setdefault("intentFrame", {})["contextRelation"] = "standalone"
check(
    "cross-domain-history-does-not-resolve-referent",
    bool(server.material_unresolved_referent(cross_domain_messages, cross_domain_route)),
)

linked_route = route_for(cross_domain_messages)
linked_route.setdefault("intentFrame", {})["contextRelation"] = "follow-up"
check(
    "linked-context-without-unique-target-still-clarifies",
    bool(server.material_unresolved_referent(cross_domain_messages, linked_route)),
)

decision_risk_messages = [
    {
        "role": "user",
        "text": "Compare a sealed enclosure and a vented enclosure for a dusty cabinet.",
    },
    {
        "role": "assistant",
        "text": "I would choose the sealed enclosure with a closed-loop heat exchanger.",
    },
    {
        "role": "user",
        "text": "What could make it wrong?",
    }
]
decision_risk_route = route_for(decision_risk_messages)
check(
    "decision-risk-question-does-not-become-missing-referent",
    not server.material_unresolved_referent(decision_risk_messages, decision_risk_route)
    and not server.unresolved_referent_preflight_response(decision_risk_messages, decision_risk_route),
)

prospective_decision_messages = [
    {
        "role": "user",
        "text": (
            "Compare two arbitrary architectures. Which direction would you take, "
            "what could make it wrong, and what should I test first?"
        ),
    }
]
prospective_decision_route = route_for(prospective_decision_messages)
check(
    "same-turn-decision-target-binds-its-risk-question",
    not server.material_unresolved_referent(prospective_decision_messages, prospective_decision_route),
)

prospective_ordinal_messages = [
    {
        "role": "user",
        "text": (
            "Compare two arbitrary service architectures, recommend a direction, state when you would reverse it, "
            "and name the first test you would run."
        ),
    }
]
prospective_ordinal_route = route_for(prospective_ordinal_messages)
check(
    "requested-first-test-is-a-prospective-output-not-a-missing-referent",
    not server.material_unresolved_referent(prospective_ordinal_messages, prospective_ordinal_route)
    and not server.unresolved_referent_preflight_response(
        prospective_ordinal_messages,
        prospective_ordinal_route,
    ),
)

closed_ordinal_messages = [{"role": "user", "text": "What is the first step?"}]
closed_ordinal_route = route_for(closed_ordinal_messages)
check(
    "self-contained-first-step-question-is-not-anaphoric",
    not server.material_unresolved_referent(closed_ordinal_messages, closed_ordinal_route)
    and not server.unresolved_referent_preflight_response(
        closed_ordinal_messages,
        closed_ordinal_route,
    ),
)

missing_ordered_set_messages = [{"role": "user", "text": "Open the first one."}]
missing_ordered_set_route = route_for(missing_ordered_set_messages)
check(
    "first-one-without-an-ordered-set-clarifies",
    bool(server.material_unresolved_referent(missing_ordered_set_messages, missing_ordered_set_route))
    and server.unresolved_referent_preflight_response(
        missing_ordered_set_messages,
        missing_ordered_set_route,
    ).get("handled") is True,
)

ambiguous_change_messages = [
    {"role": "user", "text": "Compare the Atlas controller and the Boreal controller."},
    {"role": "assistant", "text": "Atlas is quieter; Boreal is faster. Both remain viable."},
    {"role": "user", "text": "Change it."},
]
ambiguous_change_route = route_for(ambiguous_change_messages)
check(
    "two-plausible-prior-objects-do-not-resolve-change-it",
    bool(server.material_unresolved_referent(ambiguous_change_messages, ambiguous_change_route))
    and server.unresolved_referent_preflight_response(
        ambiguous_change_messages,
        ambiguous_change_route,
    ).get("handled") is True,
)

missing_match_messages = [{"role": "user", "text": "Make it match."}]
missing_match_route = route_for(missing_match_messages)
check(
    "make-it-match-without-prior-target-clarifies-before-work",
    bool(server.material_unresolved_referent(missing_match_messages, missing_match_route))
    and server.unresolved_referent_preflight_response(missing_match_messages, missing_match_route).get("handled") is True,
)

clarification_resolution_messages = [
    {"role": "user", "text": ambiguous_prompt},
    {"role": "assistant", "text": preflight.get("answer", "")},
    {
        "role": "user",
        "text": (
            "I mean a local configuration file that I have not attached yet. "
            "Do you have the capability to compare it once I attach it, without modifying anything?"
        ),
    },
]
clarification_resolution_context = server.previous_failed_answer_context(
    clarification_resolution_messages
)
check(
    "clarification-resolution-does-not-queue-self-repair",
    clarification_resolution_context is not None
    and not server.should_record_natural_correction(
        clarification_resolution_messages,
        clarification_resolution_context,
    ),
)


class CaptureHandler:
    def __init__(self):
        self.current_run_id = "p181-terminal-failed"
        self.current_web_search = "disabled"
        self.current_cwd = str(ROOT)
        self.current_friendliness_level = "warm"
        self.current_humor_level = "light"
        self.current_run_steering_applied = True
        self.wfile = io.BytesIO()

    def send_response(self, *_args):
        return None

    def send_header(self, *_args):
        return None

    def end_headers(self):
        return None


clarification_route = route_for(ambiguous_messages)
clarification_result = server.unresolved_referent_preflight_response(
    ambiguous_messages,
    clarification_route,
)
clarification_handler = CaptureHandler()
clarification_handler.current_run_id = "p181-ambiguity-terminal"
original_audit = server.run_generic_reasoning_audit


def forbidden_clarification_audit(*_args, **_kwargs):
    raise AssertionError("a deterministic clarification must not enter the model audit")


server.run_generic_reasoning_audit = forbidden_clarification_audit
try:
    server.emit_typed_capability_response(
        clarification_handler,
        ambiguous_messages,
        clarification_route,
        {"testRun": True},
        clarification_result,
        cwd=str(ROOT),
        profile="manager",
        effective_profile="manager",
        reasoning_level="medium",
        web_search="disabled",
        manager_depth=1,
        friendliness_level="warm",
        humor_level="light",
        free_only_redirect=False,
    )
finally:
    server.run_generic_reasoning_audit = original_audit
clarification_events = [
    json.loads(line)
    for line in clarification_handler.wfile.getvalue().decode("utf-8").splitlines()
    if line.strip()
]
clarification_assistant = next(
    (event for event in clarification_events if event.get("type") == "assistant"),
    {},
)
clarification_done = next(
    (event for event in clarification_events if event.get("type") == "done"),
    {},
)
check(
    "clarification-terminal-bypasses-model-audit",
    clarification_assistant.get("text") == clarification_result.get("answer")
    and (clarification_assistant.get("answerEnvelope") or {}).get("status") == "complete"
    and clarification_done.get("returnCode") == 0
    and not any(
        event.get("type") in {"command", "file", "tool"}
        for event in clarification_events
    ),
    json.dumps(
        {
            "types": [event.get("type") for event in clarification_events],
            "terminal": (clarification_assistant.get("answerEnvelope") or {}).get("status"),
            "returnCode": clarification_done.get("returnCode"),
        }
    ),
)


terminal_messages = [{"role": "user", "text": "Explain the observed result clearly."}]
terminal_route = route_for(terminal_messages)
terminal_route["_executionReturnCode"] = 1
terminal_route["_supervisionStatus"] = "pass"
handler = CaptureHandler()
server.emit_assistant_answer(
    handler,
    terminal_messages,
    terminal_route,
    {"testRun": True},
    "The useful draft explains the observed result, but the worker failed its final review.",
    normalize=False,
    text_locked=True,
)
events = [json.loads(line) for line in handler.wfile.getvalue().decode("utf-8").splitlines() if line.strip()]
assistant = next((event for event in events if event.get("type") == "assistant"), {})
envelope = assistant.get("answerEnvelope") or {}
check(
    "nonzero-execution-cannot-publish-complete",
    envelope.get("status") == "failed"
    and (envelope.get("terminal_state") or {}).get("mayClaimComplete") is False
    and server.supervision_completion_code(terminal_route, 0) == 1,
    json.dumps(envelope),
)

review_route = route_for(terminal_messages)
review_route["_executionReturnCode"] = 0
review_route["_answerReviewOutcome"] = "failed"
review_route["_supervisionStatus"] = "pass"
review_handler = CaptureHandler()
review_handler.current_run_id = "p181-terminal-review-failed"
server.emit_assistant_answer(
    review_handler,
    terminal_messages,
    review_route,
    {"testRun": True},
    "The best usable draft is retained even though final review failed.",
    normalize=False,
    text_locked=True,
)
review_events = [
    json.loads(line)
    for line in review_handler.wfile.getvalue().decode("utf-8").splitlines()
    if line.strip()
]
review_envelope = next(
    (event.get("answerEnvelope") or {} for event in review_events if event.get("type") == "assistant"),
    {},
)
check(
    "failed-review-envelope-cannot-publish-complete",
    review_envelope.get("status") == "failed"
    and (review_envelope.get("terminal_state") or {}).get("helpfulPartialPreserved") is True,
    json.dumps(review_envelope),
)

package = server.response_package(
    thermal_messages,
    thermal_route,
    complete_answer,
    web_search="disabled",
    text_locked=True,
)
check(
    "personality-and-composition-scorecards-remain-visible",
    isinstance(package.get("etiquette"), dict)
    and isinstance(package.get("conversationalPresence"), dict)
    and isinstance(package.get("answerObligations"), dict),
)

failed = [item for item in CHECKS if item["status"] != "pass"]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": len(failed),
    "checks": CHECKS,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
