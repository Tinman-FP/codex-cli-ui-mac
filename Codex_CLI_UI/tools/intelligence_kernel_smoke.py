#!/usr/bin/env python3
"""Focused regression for the generic intelligence front door."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from intelligence_kernel import synthetic_kernel_check  # noqa: E402


def evaluate_case(case_id: str, question: str) -> dict:
    messages = [{"role": "user", "text": question}]
    route = server.route_manager(messages, cwd=str(ROOT), web_search="live")
    decision = route.get("kernelDecision") or {}
    allow_legacy = bool(decision.get("allowLegacyDirectAnswer", True))
    direct = server.general_direct_knowledge_answer(
        messages,
        route=route,
        web_search="live",
        allow_legacy=allow_legacy,
    )
    prompt = (
        server.build_intelligence_kernel_prompt(messages, route=route, cwd=str(ROOT))
        if decision.get("useCompactPrompt")
        else ""
    )
    composition = server.adaptive_answer_composition_profile(messages, route)
    return {
        "id": case_id,
        "projectId": route.get("projectId"),
        "domain": (route.get("intentFrame") or {}).get("domain"),
        "rejectedLegacyDomain": (route.get("intentFrame") or {}).get("rejectedLegacyDomain"),
        "engine": route.get("engine"),
        "mode": decision.get("mode"),
        "allowLegacyDirectAnswer": allow_legacy,
        "directMode": direct.get("mode") if isinstance(direct, dict) else None,
        "promptChars": len(prompt),
        "forceLabeledSections": composition.get("forceLabeledSections"),
        "contractKind": server.task_contract(messages, route).get("kind"),
        "analyticalMode": server.analytical_core_mode(messages, route),
    }


def main() -> int:
    report = synthetic_kernel_check()
    cases = [
        evaluate_case("local-installation", "Do you have Hunyuan3D-2.1 installed?"),
        evaluate_case("clarification", "Can you fix it?"),
        evaluate_case("selection-clarification", "Let's do 1, 4 & 5."),
        evaluate_case("technical-comparison", "What is stronger PET-CF or PCTG-CF?"),
        evaluate_case(
            "current-market",
            "What are the top 10 4 x 8 CNC machines under $20,000 right now?",
        ),
        evaluate_case(
            "local-action",
            "Fix the status panel in Codex CLI UI and verify the change.",
        ),
        evaluate_case(
            "engineering-calculation",
            "What size axial flux motor would produce 250 horsepower at 3500 RPM?",
        ),
        evaluate_case(
            "keyword-conflict-veto",
            "Compare 6061-T6 aluminum and G10/FR4 for an electrically insulating motor-controller mounting plate in a hot, vibrating enclosure.",
        ),
    ]
    by_id = {item["id"]: item for item in cases}
    failures = []
    if report.get("status") != "pass":
        failures.append("generic intent cases failed")
    if by_id["local-installation"]["directMode"] != "local-installation-status":
        failures.append("bounded local installation capability did not run")
    if by_id["clarification"]["directMode"] != "objective-plan-clarification":
        failures.append("missing-referent clarification did not run")
    if by_id["selection-clarification"]["mode"] != "deterministic-capability":
        failures.append("context-free numbered selection did not request clarification")
    for case_id in (
        "technical-comparison",
        "current-market",
        "local-action",
        "engineering-calculation",
        "keyword-conflict-veto",
    ):
        case = by_id[case_id]
        if case["mode"] != "model-first" or case["allowLegacyDirectAnswer"]:
            failures.append(f"{case_id} did not use model-first execution")
        if case["directMode"] is not None:
            failures.append(f"{case_id} leaked into a legacy direct answer")
        if not 0 < case["promptChars"] < 8000:
            failures.append(f"{case_id} compact prompt size is outside the regression bound")
        if case["forceLabeledSections"] is not False:
            failures.append(f"{case_id} still forces canned response labels")
    if by_id["current-market"]["engine"] != "local-research":
        failures.append("current market request did not select local research")
    if by_id["engineering-calculation"]["engine"] != "local":
        failures.append("stable engineering calculation was incorrectly promoted to local research")
    conflict = by_id["keyword-conflict-veto"]
    if (
        conflict["projectId"] != "general"
        or conflict["domain"] != "knowledge_comparison"
        or conflict["rejectedLegacyDomain"] != "engineering_power_conversion"
        or conflict["contractKind"] != "Expert comparison"
        or conflict["analyticalMode"] != "decision"
    ):
        failures.append("full-request conflict veto did not reject a keyword-only power-conversion route")

    output = {
        "status": "pass" if not failures else "fail",
        "kernel": report,
        "cases": cases,
        "failures": failures,
    }
    print(json.dumps(output, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
