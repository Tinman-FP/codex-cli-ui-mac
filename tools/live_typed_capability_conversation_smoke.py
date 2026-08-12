#!/usr/bin/env python3
"""Exercise typed engineering capabilities through the live streaming API."""

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


def base_payload(messages: list[dict]) -> dict:
    return {
        "profile": "manager",
        "cwd": str(ROOT),
        "accessLevel": "danger-full-access",
        "reasoningLevel": "high",
        "managerDepth": "balanced",
        "friendlinessLevel": "warm",
        "humorLevel": "light",
        "webSearch": "disabled",
        "testRun": True,
        "messages": messages,
    }


def provenance_capabilities(envelope: dict) -> list[str]:
    capabilities = []
    for item in envelope.get("provenance") or []:
        if not isinstance(item, dict):
            continue
        value = str(item.get("capability") or item.get("capabilityId") or item.get("id") or "").strip()
        if value:
            capabilities.append(value)
    return capabilities


def reasoning_audit_provenance(envelope: dict) -> dict:
    for item in envelope.get("provenance") or []:
        if isinstance(item, dict) and item.get("kind") == "engineering-reasoning-audit":
            return item
    return {}


def run_turn(server: str, messages: list[dict], expected_capability: str, timeout: int) -> dict:
    started = time.monotonic()
    events = post_stream(f"{server.rstrip('/')}/api/run", base_payload(messages), timeout)
    status = next((event for event in events if event.get("type") == "status"), {})
    assistant = next((event for event in reversed(events) if event.get("type") == "assistant"), {})
    route = status.get("route") or {}
    plan = route.get("capabilityPlan") or {}
    decision = route.get("kernelDecision") or {}
    envelope = assistant.get("answerEnvelope") or {}
    answer = str(assistant.get("text") or "").strip()
    capabilities = provenance_capabilities(envelope)
    reasoning_audit = reasoning_audit_provenance(envelope)
    route_ok = bool(
        plan.get("registered") is True
        and plan.get("id") == expected_capability
        and decision.get("mode") == "model-first"
        and decision.get("allowLegacyDirectAnswer") is False
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

    cnc_first_prompt = (
        "For a production 4x8 CNC router, are closed-loop steppers good enough or should I spend for AC servos?"
    )
    cnc_first_messages = [{"role": "user", "text": cnc_first_prompt}]
    cnc_first = run_turn(args.server, cnc_first_messages, "engineering-advisory", args.timeout)
    cnc_follow_messages = cnc_first_messages + [
        {"role": "assistant", "text": cnc_first["answer"]},
        {"role": "user", "text": "If I only cut foam and plywood but run 8 hours a day, does that change the answer?"},
    ]
    cnc_follow = run_turn(args.server, cnc_follow_messages, "engineering-advisory", args.timeout)

    power_first_prompt = (
        "I found a 72 V BLDC motor listed at 6.5 kW continuous and 18 kW peak. "
        "What is the real horsepower and what size controller would you pair with it for a lightweight kart?"
    )
    power_first_messages = [{"role": "user", "text": power_first_prompt}]
    power_first = run_turn(args.server, power_first_messages, "engineering-power-conversion", args.timeout)
    power_follow_messages = power_first_messages + [
        {"role": "assistant", "text": power_first["answer"]},
        {"role": "user", "text": "If the controller is only rated 150 A battery current, is that limiting continuous power or just peak torque?"},
    ]
    power_follow = run_turn(args.server, power_follow_messages, "engineering-power-conversion", args.timeout)

    cnc_first_lower = cnc_first["answer"].lower()
    cnc_follow_lower = cnc_follow["answer"].lower()
    power_first_lower = power_first["answer"].lower()
    power_follow_lower = power_follow["answer"].lower()
    cnc_unsound_patterns = (
        r"(?:microstepp\w*|1\s*/\s*\d+)[^.\n]{0,160}(?:(?:prevent|avoid|reduce)[^.\n]{0,50}(?:missed|lost)\s+steps|(?:missed|lost)\s+steps[^.\n]{0,50}(?:unlikely|prevented|avoided))",
        r"(?:foam|plywood)[^.\n]{0,120}(?:current\s+(?:stays?|is|remains?)\s+low|low\s+current)",
        r"acceleration[^.\n]{0,120}(?:below|under|within)[^.\n]{0,80}current\s+rat",
        r"(?:feed\s*rates?|speeds?|accelerations?)[^.\n]{0,100}(?:below|under|above|over)[^.\n]{0,60}(?:resonant\s+)?frequenc",
    )
    semantic_checks = {
        "cncFirstNamedOptions": "stepper" in cnc_first_lower and "servo" in cnc_first_lower,
        "cncFirstDecisionCriteria": sum(
            term in cnc_first_lower for term in ("speed", "torque", "duty", "inertia", "fault", "cost")
        ) >= 2,
        "cncFollowPreservesMaterialAndDuty": (
            contains_any(cnc_follow_lower, ("foam", "plywood"))
            and contains_any(cnc_follow_lower, ("8 hour", "eight hour", "duty", "production"))
            and "stepper" in cnc_follow_lower
            and "servo" in cnc_follow_lower
        ),
        "cncFirstReasoningIntegrity": not any(
            re.search(pattern, cnc_first_lower) for pattern in cnc_unsound_patterns
        ),
        "cncFollowReasoningIntegrity": not any(
            re.search(pattern, cnc_follow_lower) for pattern in cnc_unsound_patterns
        ),
        "cncFirstReasoningAuditReceipt": bool(
            (cnc_first.get("envelope") or {}).get("reasoningAudit")
        ),
        "cncFollowReasoningAuditReceipt": bool(
            (cnc_follow.get("envelope") or {}).get("reasoningAudit")
        ),
        "powerFirstConvertsBothRatings": (
            contains_any(power_first_lower, ("8.7 hp", "8.72 hp"))
            and contains_any(power_first_lower, ("24.1 hp", "24.14 hp"))
            and "continuous" in power_first_lower
            and "peak" in power_first_lower
        ),
        "powerFirstSizesControllerBoundary": (
            "controller" in power_first_lower
            and "battery current" in power_first_lower
            and "phase current" in power_first_lower
        ),
        "powerFollowPreserves150ABoundary": (
            "150" in power_follow_lower
            and "battery current" in power_follow_lower
            and "continuous" in power_follow_lower
            and contains_any(power_follow_lower, ("phase current", "torque"))
        ),
    }
    turns = {
        "cncFirst": cnc_first,
        "cncFollowup": cnc_follow,
        "powerFirst": power_first,
        "powerFollowup": power_follow,
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
