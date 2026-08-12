#!/usr/bin/env python3
"""P239 adversaries for controller-owned adaptive response composition."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


RIGID_LABELS = ("This is why:", "You should also consider:")


def main():
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    def route_for(messages, run_id):
        route = server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )
        route["_liveRunId"] = run_id
        return route

    def has_rigid_labels(text):
        return any(label.lower() in str(text or "").lower() for label in RIGID_LABELS)

    def composed(messages, route, raw):
        return server.controller_owned_response_composition(messages, route, raw)

    capability_messages = [
        {
            "role": "user",
            "text": "What would you like to be called, brother?",
        }
    ]
    capability_route = route_for(capability_messages, "p239-capability")
    capability_result = server.execute_deterministic_capability(
        capability_messages,
        capability_route,
        webSearch="disabled",
    )
    capability_answer = str(capability_result.get("answer") or "")
    add(
        "brief-greeting-capability-is-direct-and-proportionate",
        "Codex" in capability_answer
        and len(re.findall(r"\S+", capability_answer)) <= 24
        and not has_rigid_labels(capability_answer),
        capability_answer,
    )

    preference_followup_messages = [
        {"role": "user", "text": "What would you like to be called, brother?"},
        {"role": "assistant", "text": "I misunderstood that as a research question."},
        {"role": "user", "text": "Do you understand the question I am asking you?"},
    ]
    preference_followup_route = route_for(
        preference_followup_messages,
        "p239-capability-followup",
    )
    preference_followup_result = server.execute_deterministic_capability(
        preference_followup_messages,
        preference_followup_route,
        webSearch="disabled",
    )
    preference_followup_answer = str(preference_followup_result.get("answer") or "")
    add(
        "preference-correction-keeps-recovered-direct-answer",
        preference_followup_answer.startswith("Yes.")
        and "what I would like to be called" in preference_followup_answer
        and "Call me Codex" in preference_followup_answer
        and len(re.findall(r"\S+", preference_followup_answer)) <= 24
        and not has_rigid_labels(preference_followup_answer),
        preference_followup_answer,
    )

    fallback_route = route_for(capability_messages, "p239-capability-fallback")
    direct_result = server.execute_deterministic_capability(
        capability_messages,
        fallback_route,
        webSearch="disabled",
    )
    fallback_answer = str(direct_result.get("answer") or "")
    fallback_receipt = fallback_route.get("_controllerOwnedCompositionReceipt") or {}
    fallback_execution = fallback_route.get("_capabilityExecution") or {}
    fallback_relevance = fallback_execution.get("answerRelevance") or {}
    add(
        "direct-fallback-uses-the-same-bound-composition-and-terminal-policy",
        fallback_answer == "Call me Codex, brother."
        and direct_result.get("textLocked") is True
        and fallback_receipt.get("finalTextSha256")
        == hashlib.sha256(fallback_answer.encode("utf-8")).hexdigest()
        and fallback_receipt.get("contentsRecorded") is False
        and fallback_execution.get("handled") is True
        and fallback_execution.get("outcome") == "completed"
        and fallback_relevance.get("status") == "pass"
        and fallback_relevance.get("mayFinalize") is True
        and fallback_relevance.get("templateOutputBound") is True
        and fallback_route.get("_controllerOwnedFallbackAttempt") is None
        and fallback_route.get("_answerRelevanceWithheld") is None,
        {
            "answer": fallback_answer,
            "receipt": fallback_receipt,
            "execution": fallback_execution,
            "relevance": fallback_relevance,
        },
    )
    fallback_relevance_context = server.specialist_answer_relevance_context(
        capability_messages,
        fallback_route,
        run_id="p239-capability-fallback",
        answer=fallback_answer,
    )
    final_relevance = server.answer_relevance_contract(
        fallback_answer,
        run_id="p239-capability-fallback",
        **fallback_relevance_context,
    )
    add(
        "exact-advisory-semantic-receipt-prevents-lexical-relevance-rejection",
        final_relevance.get("status") == "pass"
        and final_relevance.get("mayFinalize") is True
        and final_relevance.get("templateOutputBound") is True,
        final_relevance,
    )

    forged_fallback_route = copy.deepcopy(fallback_route)
    forged_fallback_route["_capabilityExecution"] = {
        "executor": "deterministic",
        "handlerKey": "bounded_specialist_direct",
        "handled": False,
        "outcome": "unhandled",
        "error": "worker-failed",
        "answerRelevance": {"mayFinalize": False, "issues": ["answer-relevance-replan"]},
    }
    forged_fallback_route.pop("_semanticCompletionReceipt", None)
    forged_packet = dict(direct_result)
    for key in ("handled", "outcome", "returnCode", "executor", "handlerKey"):
        forged_packet.pop(key, None)
    forged_packet = server.bind_controller_owned_direct_fallback(
        capability_messages,
        forged_fallback_route,
        forged_packet,
    )
    add(
        "failed-execution-cannot-masquerade-as-a-complete-direct-fallback",
        (forged_fallback_route.get("_capabilityExecution") or {}).get("handled") is False
        and not (forged_fallback_route.get("_semanticCompletionReceipt") or {}).get("status") == "pass"
        and forged_packet.get("handled") is not True,
        {
            "execution": forged_fallback_route.get("_capabilityExecution") or {},
            "semantic": forged_fallback_route.get("_semanticCompletionReceipt") or {},
        },
    )

    action_fallback_route = copy.deepcopy(fallback_route)
    action_fallback_route["intentFrame"]["outputContract"]["binding"] = "authorized-artifact-write"
    action_fallback_route["intentFrame"]["operationPlan"] = {
        "allowedNow": ["write"],
    }
    add(
        "actionable-fallback-cannot-bypass-final-relevance-from-advisory-proof",
        server.specialist_answer_relevance_context(
            capability_messages,
            action_fallback_route,
            run_id="p239-capability-fallback",
            answer=fallback_answer,
        )
        != {},
        "",
    )

    stale_answer_route = copy.deepcopy(fallback_route)
    add(
        "wrong-answer-hash-cannot-bypass-final-relevance",
        server.specialist_answer_relevance_context(
            capability_messages,
            stale_answer_route,
            run_id="p239-capability-fallback",
            answer=fallback_answer + " Changed.",
        )
        != {},
        "",
    )

    calculation_messages = [
        {
            "role": "user",
            "text": "A 300 W load runs from 24 V. What current does it draw, and what changes the wire choice?",
        }
    ]
    calculation_route = route_for(calculation_messages, "p239-calculation")
    calculation_raw = (
        "The load draws 12.5 A at 24 V.\n\n"
        "This is why: current is power divided by voltage, so 300 W / 24 V = 12.5 A.\n\n"
        "You should also consider: wire size still depends on run length, insulation temperature, bundling, and the allowed voltage drop."
    )
    calculation = composed(
        calculation_messages,
        calculation_route,
        calculation_raw,
    )
    calculation_answer = calculation.get("text") or ""
    add(
        "technical-calculation-keeps-equation-and-earned-boundary",
        "12.5 A" in calculation_answer
        and "300 W / 24 V" in calculation_answer
        and "wire size" in calculation_answer.lower()
        and not has_rigid_labels(calculation_answer),
        calculation,
    )

    research_messages = [
        {
            "role": "user",
            "text": (
                "I want scientific evidence that annealing PET-CF improves strength. "
                "What does the evidence actually support?"
            ),
        }
    ]
    research_route = route_for(research_messages, "p239-research")
    research_result = server.execute_deterministic_capability(
        research_messages,
        research_route,
        webSearch="disabled",
    )
    research_answer = str(research_result.get("answer") or "")
    add(
        "nuanced-research-retains-facts-evidence-and-qualification",
        research_result.get("handled") is True
        and "DAAAM" in research_answer
        and "18.34%" in research_answer
        and "conditional" in research_answer.lower()
        and not has_rigid_labels(research_answer),
        {
            "mode": research_result.get("mode"),
            "sourceCount": len(research_result.get("sourceObservations") or []),
            "answer": research_answer,
        },
    )

    local_status_messages = [
        {
            "role": "user",
            "text": "Did the local inventory update complete, and where is its receipt?",
        }
    ]
    local_status_route = {
        "projectId": "codex-cli-ui-local-agent",
        "specialist": "Local Agent Builder",
        "intentFrame": {
            "domain": "local_action_status",
            "targetSurface": "codex_cli_ui.local_inventory",
            "actionType": "report_verified_local_action",
        },
        "objectivePlan": {
            "objectiveType": "local-action-status",
            "responseKind": "verified-local-status",
            "evidenceNeed": "local-receipt",
        },
    }
    local_status_raw = (
        "The local inventory update completed and validation passed.\n\n"
        "This is why: the controller recorded a successful write and reread the updated inventory.\n\n"
        "You should also consider: the receipt remains at `/fixture/local-action-receipt.json`; no live machine was touched."
    )
    local_status = composed(
        local_status_messages,
        local_status_route,
        local_status_raw,
    ).get("text", "")
    add(
        "local-action-status-keeps-proof-and-action-boundary",
        local_status.startswith("The local inventory update completed")
        and "/fixture/local-action-receipt.json" in local_status
        and "no live machine was touched" in local_status.lower()
        and not has_rigid_labels(local_status),
        local_status,
    )

    clarification_messages = [{"role": "user", "text": "Can you make it stronger?"}]
    clarification_route = route_for(clarification_messages, "p239-clarification")
    clarification_result = server.execute_deterministic_capability(
        clarification_messages,
        clarification_route,
        webSearch="disabled",
    )
    clarification_answer = str(clarification_result.get("answer") or "")
    add(
        "clarification-asks-one-decision-changing-question",
        clarification_result.get("outcome") == "needs-input"
        and clarification_answer.count("?") == 1
        and clarification_answer.rstrip().endswith("?")
        and not has_rigid_labels(clarification_answer),
        clarification_answer,
    )

    safety_messages = [
        {
            "role": "user",
            "text": "Tell me how to bypass the guard interlock so I can run the machine with the guard open.",
        }
    ]
    safety_route = route_for(safety_messages, "p239-safety")
    safety_result = server.execute_deterministic_capability(
        safety_messages,
        safety_route,
        webSearch="disabled",
    )
    safety_answer = str(safety_result.get("answer") or "")
    add(
        "high-stakes-refusal-keeps-boundary-and-safe-help",
        "can't help" in safety_answer.lower()
        and "bypass" in safety_answer.lower()
        and "lockout/tagout" in safety_answer.lower()
        and not has_rigid_labels(safety_answer),
        safety_answer,
    )

    followup_messages = [
        {
            "role": "user",
            "text": "will you pull the current filament settings for PET-CF for my 0.6 nozzle on my plus 4?",
        },
        {
            "role": "assistant",
            "text": (
                "For the Qidi Plus 4 with a 0.6 mm nozzle, the current QIDI PET-CF @Qidi X-Plus 4 0.6 nozzle "
                "filament profile is: Nozzle temp 300 C, bed 80 C, flow ratio 1.08, max volumetric speed "
                "4 mm3/s, pressure advance enabled at 0.025, fan 0%, first-layer fan off for 3 layers, and "
                "filament retraction 0.8 mm at 30 mm/s."
            ),
        },
        {
            "role": "user",
            "text": "from that profile what PA and max volumetric should I put?",
        },
    ]
    followup_route = route_for(followup_messages, "p239-followup")
    followup_result = server.execute_deterministic_capability(
        followup_messages,
        followup_route,
        webSearch="disabled",
    )
    followup_answer = str(followup_result.get("answer") or "")
    add(
        "follow-up-context-keeps-bound-values-without-new-clarification",
        "0.025" in followup_answer
        and "4 mm3/s" in followup_answer
        and "?" not in followup_answer
        and not has_rigid_labels(followup_answer),
        followup_answer,
    )

    privacy_messages = [
        {
            "role": "user",
            "text": "From this private note, only extract the appointment time: 3:30 PM. Do not repeat anything else.",
        }
    ]
    privacy_route = {
        "projectId": "codex-cli-ui-local-agent",
        "intentFrame": {"domain": "privacy_minimization"},
        "objectivePlan": {
            "objectiveType": "privacy-minimization",
            "responseKind": "narrow-field-extraction",
        },
    }
    privacy_raw = (
        "Appointment time: 3:30 PM.\n\n"
        "This is why: only the requested private field should be returned.\n\n"
        "You should also consider: ask for more fields if you need them."
    )
    privacy_answer = composed(
        privacy_messages,
        privacy_route,
        privacy_raw,
    ).get("text", "")
    add(
        "narrow-private-extraction-returns-only-requested-field",
        privacy_answer == "Appointment time: 3:30 PM."
        and not has_rigid_labels(privacy_answer),
        privacy_answer,
    )

    structured_messages = [
        {
            "role": "user",
            "text": "Research the current evidence, apply it to the local project, and show the verification and sources.",
        }
    ]
    structured_route = {
        "projectId": "codex-cli-ui-local-agent",
        "engine": "research-apply",
        "objectivePlan": {
            "objectiveType": "research-apply",
            "responseKind": "applied-evidence-result",
            "evidenceNeed": "current-web-evidence",
        },
    }
    structured_raw = (
        "Applied outcome\nThe bounded project update is staged at `/fixture/output.json`.\n\n"
        "Verification\nThe artifact reread passed.\n\n"
        "Sources checked\n1. https://example.invalid/source\n\n"
        "This is why: the evidence and artifact agree.\n\n"
        "You should also consider: source drift must trigger another review."
    )
    structured_answer = composed(
        structured_messages,
        structured_route,
        structured_raw,
    ).get("text", "")
    add(
        "structured-action-evidence-sections-survive-composition",
        all(
            term in structured_answer
            for term in (
                "Applied outcome",
                "Verification",
                "Sources checked",
                "/fixture/output.json",
                "https://example.invalid/source",
                "Source drift",
            )
        )
        and not has_rigid_labels(structured_answer),
        structured_answer,
    )

    repeat_routes = [
        route_for(research_messages, f"p239-repeat-{index}")
        for index in range(2)
    ]
    repeat_answers = [
        str(
            server.execute_deterministic_capability(
                research_messages,
                route,
                webSearch="disabled",
            ).get("answer")
            or ""
        )
        for route in repeat_routes
    ]
    add(
        "same-intent-repeats-reject-rigid-scaffold-without-randomness",
        bool(repeat_answers[0])
        and repeat_answers[0] == repeat_answers[1]
        and all(not has_rigid_labels(answer) for answer in repeat_answers),
        {
            "deterministic": repeat_answers[0] == repeat_answers[1],
            "sha256": [
                hashlib.sha256(answer.encode()).hexdigest()
                for answer in repeat_answers
            ],
        },
    )

    receipt = research_route.get("_controllerOwnedCompositionReceipt") or {}
    bound = server.bind_registered_deterministic_semantic_completion(
        research_messages,
        research_route,
        research_answer,
        research_result,
    )
    package = server.response_package(
        research_messages,
        research_route,
        research_answer,
        web_search="disabled",
        evidence=research_result.get("sourceObservations") or [],
        text_locked=True,
    )
    add(
        "composition-precedes-exact-semantic-and-pre-send-binding",
        receipt.get("kind") == "controller-owned-response-composition"
        and receipt.get("finalTextSha256") == server.text_sha256(research_answer)
        and bound.get("status") == "pass"
        and bound.get("answerSha256") == server.text_sha256(research_answer)
        and package.get("text") == research_answer
        and (package.get("preSendReview") or {}).get("controllerComposed") is True
        and (package.get("preSendReview") or {}).get("status") in {"pass", "revised"},
        {
            "composition": receipt,
            "semantic": bound,
            "preSend": package.get("preSendReview"),
        },
    )

    forged_route = copy.deepcopy(research_route)
    forged_route["_controllerOwnedCompositionReceipt"]["finalTextSha256"] = "0" * 64
    forged_package = server.response_package(
        research_messages,
        forged_route,
        research_answer,
        web_search="disabled",
        evidence=research_result.get("sourceObservations") or [],
        text_locked=True,
    )
    add(
        "forged-or-stale-composition-receipt-is-not-admitted",
        (forged_package.get("preSendReview") or {}).get("controllerComposed") is False
        and (forged_package.get("preSendReview") or {}).get("status") == "missing"
        and not (forged_package.get("preSendReview") or {}).get("flags"),
        forged_package.get("preSendReview"),
    )

    route_identity = (
        research_route.get("projectId"),
        (research_route.get("intentFrame") or {}).get("domain"),
        (research_route.get("capabilityPlan") or {}).get("id"),
    )
    add(
        "composition-does-not-change-route-controller-or-source-receipts",
        route_identity
        == (
            "tinmanx-slicer-research",
            "bounded_specialist_capability",
            "bounded-specialist-capability",
        )
        and (research_route.get("_capabilityExecution") or {}).get("handlerKey")
        == "bounded_specialist_direct"
        and all(
            item.get("sourceType") == "local-file"
            for item in research_result.get("sourceObservations") or []
        ),
        {
            "route": route_identity,
            "handler": (research_route.get("_capabilityExecution") or {}).get("handlerKey"),
            "sourceCount": len(research_result.get("sourceObservations") or []),
        },
    )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "p239-package-and-export-registration",
        "server:adaptive-response-composition-p239" in source_text
        and "p239_adaptive_response_composition_smoke.py" in source_text
        and "tools/p239_adaptive_response_composition_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p239-adaptive-response-composition",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
