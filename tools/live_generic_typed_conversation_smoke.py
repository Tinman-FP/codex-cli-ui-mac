#!/usr/bin/env python3
"""Exercise generic reasoning, clarification, and source use through live /api/run."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAILURE_PHRASES = (
    "load failed",
    "local research could not find",
    "i can design the part",
    "state the currency and tax",
    "i need the project or prior item",
    "tool recovery:",
)


def post_stream(url: str, payload: dict, timeout: int) -> list[dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict] = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = json.loads(line)
            if isinstance(event, dict):
                events.append(event)
    return events


def base_payload(messages: list[dict], web_search: str = "disabled") -> dict:
    return {
        "profile": "manager",
        "cwd": str(ROOT),
        "accessLevel": "danger-full-access",
        "reasoningLevel": "high",
        "managerDepth": "balanced",
        "friendlinessLevel": "warm",
        "humorLevel": "light",
        "webSearch": web_search,
        "messages": messages,
    }


def provenance_capabilities(envelope: dict) -> list[str]:
    capabilities: list[str] = []
    for item in envelope.get("provenance") or []:
        if not isinstance(item, dict):
            continue
        value = str(item.get("capability") or item.get("capabilityId") or item.get("id") or "").strip()
        if value:
            capabilities.append(value)
    return capabilities


def provenance_by_kind(envelope: dict, kind: str) -> dict:
    for item in envelope.get("provenance") or []:
        if isinstance(item, dict) and item.get("kind") == kind:
            return item
    return {}


def run_turn(
    server: str,
    messages: list[dict],
    expected_capability: str,
    expected_mode: str,
    timeout: int,
    web_search: str = "disabled",
) -> dict:
    started = time.monotonic()
    events = post_stream(f"{server.rstrip('/')}/api/run", base_payload(messages, web_search), timeout)
    status = next((event for event in events if event.get("type") == "status"), {})
    assistant = next((event for event in reversed(events) if event.get("type") == "assistant"), {})
    route = status.get("route") or {}
    plan = route.get("capabilityPlan") or {}
    decision = route.get("kernelDecision") or {}
    envelope = assistant.get("answerEnvelope") or {}
    answer = str(assistant.get("text") or "").strip()
    capabilities = provenance_capabilities(envelope)
    reasoning_audit = provenance_by_kind(envelope, "generic-reasoning-audit")
    source_audit = provenance_by_kind(envelope, "source-fidelity-audit")
    allow_legacy = expected_mode == "deterministic-capability"
    route_ok = bool(
        plan.get("registered") is True
        and plan.get("id") == expected_capability
        and decision.get("mode") == expected_mode
        and bool(decision.get("allowLegacyDirectAnswer")) is allow_legacy
    )
    envelope_ok = bool(
        envelope.get("status") in {"complete", "blocked"}
        and envelope.get("final_text_sha256")
        and expected_capability in capabilities
    )
    return {
        "elapsedSeconds": round(time.monotonic() - started, 2),
        "answer": answer,
        "route": {
            "projectId": route.get("projectId"),
            "domain": (route.get("intentFrame") or {}).get("domain"),
            "capability": plan.get("id"),
            "registered": plan.get("registered"),
            "mode": decision.get("mode"),
            "allowLegacyDirectAnswer": decision.get("allowLegacyDirectAnswer"),
        },
        "envelope": {
            "status": envelope.get("status"),
            "stage": envelope.get("stage"),
            "finalTextSha256": envelope.get("final_text_sha256"),
            "provenanceCapabilities": capabilities,
            "reasoningAudit": reasoning_audit,
            "sourceAudit": source_audit,
        },
        "routePassed": route_ok,
        "envelopePassed": envelope_ok,
        "failurePhrasePassed": not any(phrase in answer.lower() for phrase in FAILURE_PHRASES),
    }


def contains_any(text: str, values: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(value in lower for value in values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    causal_prompt = (
        "Why can controlling for a collider bias a causal estimate even when the collider "
        "is strongly predictive of the outcome?"
    )
    causal_messages = [{"role": "user", "text": causal_prompt}]
    causal = run_turn(
        args.server,
        causal_messages,
        "conversation-reasoning",
        "model-first",
        args.timeout,
    )
    causal_follow_messages = causal_messages + [
        {"role": "assistant", "text": causal["answer"]},
        {"role": "user", "text": "Give me a concrete hiring example and name the path that becomes opened."},
    ]
    causal_follow = run_turn(
        args.server,
        causal_follow_messages,
        "conversation-reasoning",
        "model-first",
        args.timeout,
    )

    clarification = run_turn(
        args.server,
        [{"role": "user", "text": "Can I use a standard lever-arm single-pole microswitch for this?"}],
        "focused-clarification",
        "deterministic-capability",
        args.timeout,
    )

    probability = run_turn(
        args.server,
        [
            {
                "role": "user",
                "text": (
                    "A production line sends every part through two identical independent vision inspectors. "
                    "Each catches 90% of defective parts and falsely flags 5% of good parts. The line rejects "
                    "a part if either inspector flags it. What are the combined defect-detection and false-reject "
                    "rates, and what assumption could make the detection number too optimistic?"
                ),
            }
        ],
        "conversation-reasoning",
        "model-first",
        args.timeout,
    )

    source = run_turn(
        args.server,
        [
            {
                "role": "user",
                "text": (
                    "According to https://docs.python.org/3/library/asyncio-task.html, what does "
                    "TaskGroup do when one child task fails?"
                ),
            }
        ],
        "source-backed-reasoning",
        "model-first",
        args.timeout,
        web_search="live",
    )

    causal_lower = causal["answer"].lower()
    follow_lower = causal_follow["answer"].lower()
    causal_arrows = (
        causal_lower.replace("\\rightarrow", "->")
        .replace("\\leftarrow", "<-")
        .replace("→", "->")
        .replace("←", "<-")
        .replace("‑", "-")
    )
    follow_arrows = (
        follow_lower.replace("\\rightarrow", "->")
        .replace("\\leftarrow", "<-")
        .replace("→", "->")
        .replace("←", "<-")
        .replace("‑", "-")
    )
    clarification_lower = clarification["answer"].lower()
    probability_lower = probability["answer"].lower()
    source_lower = source["answer"].lower()
    invalid_hiring_directions = (
        r"(?:offer|hiring decision|being hired|hired status)[^.!?\n]{0,35}"
        r"\b(?:influences?|causes?|drives?|determines?)\b[^.!?\n]{0,50}interview(?:-| )score",
        r"interview(?:-| )score\s*(?:<-|\u2190)\s*(?:offer|hiring decision|hired)",
    )
    semantic_checks = {
        "causalExplainsConditioningMechanism": (
            "collider" in causal_lower
            and contains_any(causal_lower, ("condition", "control", "adjust"))
            and contains_any(causal_lower, ("open", "induce", "noncausal", "spurious"))
            and "bias" in causal_lower
        ),
        "causalDoesNotInventPredictiveDirection": not re.search(
            r"\bc\s*(?:->|\u2192)\s*y\b",
            causal_lower,
        ),
        "causalColliderDirectionIsValid": (
            contains_any(causal_lower, ("arrowheads point into", "arrows point into"))
            or (
                "collider" in causal_lower
                and contains_any(causal_lower, ("between its parents", "common effect"))
            )
            or bool(
                re.search(
                    r"\b[a-z][a-z0-9 _-]{0,35}\s*->\s*[a-z][a-z0-9 _-]{0,35}\s*<-\s*[a-z]",
                    causal_arrows,
                )
            )
        )
        and not re.search(
            r"opened path[^.!?\n]{0,120}<-\s*(?:c\b|collider)[^.!?\n]{0,40}->",
            causal_arrows,
        )
        and not re.search(
            r"collider[^.!?\n]{0,60}\b(?:is|becomes) (?:a )?common cause\b",
            causal_lower,
        ),
        "causalOutcomeIsNotRecastAsColliderParent": not re.search(
            r"\bx\s*->\s*c\s*<-\s*y\b",
            causal_arrows,
        ),
        "causalColliderPathIsNotMisnamedBackdoor": not (
            "backdoor" in causal_lower
            and bool(re.search(r"\bx\s*->\s*c\s*<-\s*u\s*->\s*y\b", causal_arrows))
        ),
        "causalRolesAreClassifiedPrecisely": not contains_any(
            causal_lower,
            (
                "unmeasured confounder",
                "confounding influence of u",
                "mediated by u",
                "mediated by the opened collider",
            ),
        )
        and not re.search(
            r"(?:directed|(?<!non-)causal)\s+path[^.!?\n]{0,100}\bx\s*->\s*c\s*<-\s*u\s*->\s*y\b",
            causal_arrows,
        ),
        "followupPreservesCausalContext": (
            contains_any(follow_lower, ("hiring", "hire", "selected", "selection"))
            and "collider" in follow_lower
            and contains_any(follow_lower, ("path", "open", "association"))
        ),
        "followupCausalRolesStayConsistent": (
            not any(re.search(pattern, follow_lower) for pattern in invalid_hiring_directions)
            and contains_any(follow_lower, ("experience", "skill", "education", "qualification"))
            and contains_any(follow_lower, ("hiring", "hired", "offer"))
            and contains_any(follow_lower, ("condition", "adjust", "control"))
            and "bias" in follow_lower
            and "collider" in follow_lower
            and not re.search(
                r"opened path[^.!?\n]{0,120}<-\s*(?:c\b|collider)[^.!?\n]{0,40}->",
                follow_arrows,
            )
            and not re.search(r"\bx\s*->\s*c\s*<-\s*y\b", follow_arrows)
            and not (
                "backdoor" in follow_lower
                and bool(re.search(r"\bx\s*->\s*c\s*<-\s*u\s*->\s*y\b", follow_arrows))
            )
            and not contains_any(
                follow_lower,
                (
                    "unmeasured confounder",
                    "confounding influence of u",
                    "mediated by u",
                    "mediated by the opened collider",
                ),
            )
            and not re.search(
                r"(?:directed|(?<!non-)causal)\s+path[^.!?\n]{0,100}\bx\s*->\s*c\s*<-\s*u\s*->\s*y\b",
                follow_arrows,
            )
        ),
        "causalReasoningAuditReceipt": bool(
            (causal.get("envelope") or {}).get("reasoningAudit", {}).get("completed")
        ),
        "followupReasoningAuditReceipt": bool(
            (causal_follow.get("envelope") or {}).get("reasoningAudit", {}).get("completed")
        ),
        "causalAuditRevisionResolved": bool(
            (causal.get("envelope") or {}).get("reasoningAudit", {}).get("verdict") != "revise"
            or (
                (causal.get("envelope") or {}).get("reasoningAudit", {}).get("repairApplied")
                and (causal.get("envelope") or {}).get("reasoningAudit", {}).get("verificationCompleted")
            )
        ),
        "followupAuditRevisionResolved": bool(
            (causal_follow.get("envelope") or {}).get("reasoningAudit", {}).get("verdict") != "revise"
            or (
                (causal_follow.get("envelope") or {}).get("reasoningAudit", {}).get("repairApplied")
                and (causal_follow.get("envelope") or {}).get("reasoningAudit", {}).get("verificationCompleted")
            )
        ),
        "clarificationAsksOneFocusedQuestion": (
            clarification["answer"].count("?") == 1
            and contains_any(clarification_lower, ("this", "refer", "switch", "circuit", "load", "use"))
            and len(clarification["answer"].split()) <= 45
        ),
        "parallelInspectionMathIsCorrect": (
            bool(re.search(r"\b99(?:\.0+)?\s*%", probability_lower))
            and bool(re.search(r"\b(?:9\.75|9\.8)\s*%", probability_lower))
            and "independ" in probability_lower
        ),
        "parallelInspectionDependenceIsQualified": (
            "correlat" in probability_lower
            and contains_any(probability_lower, ("miss", "detection", "detect"))
            and not re.search(
                r"correlat[^.!?\n]{0,140}(?:both\s+)?(?:rates|numbers|metrics)[^.!?\n]{0,100}(?:less|too|overly)\s+optimistic",
                probability_lower,
            )
        ),
        "parallelInspectionReasoningAuditReceipt": bool(
            (probability.get("envelope") or {}).get("reasoningAudit", {}).get("completed")
        ),
        "sourceExplainsTaskGroupFailure": (
            "taskgroup" in source_lower
            and contains_any(source_lower, ("cancel", "cancellation"))
            and contains_any(source_lower, ("exceptiongroup", "exception group"))
            and not contains_any(source_lower, ("propagates the first exception", "only one task failed it propagates that single exception"))
        ),
        "sourceFidelityAuditReceipt": bool(
            (source.get("envelope") or {}).get("sourceAudit", {}).get("completed")
        ),
        "answersAreNotClippedMidThought": all(
            not turn["answer"].rstrip().endswith("...")
            for turn in (causal, causal_follow, clarification, probability, source)
        ),
    }
    turns = {
        "causalFirst": causal,
        "causalFollowup": causal_follow,
        "focusedClarification": clarification,
        "parallelInspection": probability,
        "officialSource": source,
    }
    structural_ok = all(
        turn["routePassed"] and turn["envelopePassed"] and turn["failurePhrasePassed"]
        for turn in turns.values()
    )
    passed = structural_ok and all(semantic_checks.values())
    report = {
        "status": "pass" if passed else "fail",
        "structuralPassed": structural_ok,
        "semanticChecks": semantic_checks,
        "turns": turns,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
