#!/usr/bin/env python3
"""Verify typed ownership for ordinary conversation, source work, and local actions."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


CASES = (
    {
        "id": "ordinary-knowledge",
        "text": "Why do induction motors draw a large inrush current at startup?",
        "domain": "knowledge_question",
        "capability": "conversation-reasoning",
        "project": "general",
        "engine": "local",
        "profile": "local-fast",
    },
    {
        "id": "causal-estimate-not-cad",
        "text": "Why can controlling for a collider bias a causal estimate even when the collider is strongly predictive of the outcome?",
        "domain": "knowledge_question",
        "capability": "conversation-reasoning",
        "project": "general",
        "engine": "local",
        "profile": "local-fast",
    },
    {
        "id": "paradox-not-safety",
        "text": "Why can Simpson's paradox reverse the apparent direction of an association after data are grouped?",
        "domain": "knowledge_question",
        "capability": "conversation-reasoning",
        "project": "general",
        "engine": "local",
        "profile": "local-fast",
    },
    {
        "id": "conversation-acknowledgement",
        "text": "Thanks, that makes sense.",
        "domain": "conversation",
        "capability": "conversation-reasoning",
        "project": "general",
        "engine": "local",
        "profile": "local-fast",
    },
    {
        "id": "supplied-source",
        "text": "What does this page say about the supported input voltage? https://example.com/product/manual",
        "domain": "source_resolution",
        "capability": "source-backed-reasoning",
        "project": "research-parts-reference",
        "engine": "local-research",
        "profile": "local-research",
    },
    {
        "id": "html-url-not-local-file",
        "text": (
            "According to https://docs.python.org/3/library/asyncio-task.html, "
            "what does TaskGroup do when one child task fails?"
        ),
        "domain": "source_resolution",
        "capability": "source-backed-reasoning",
        "project": "research-parts-reference",
        "engine": "local-research",
        "profile": "local-research",
    },
    {
        "id": "technical-source",
        "text": "Find the instruction manual and pinout for a generic motor controller.",
        "domain": "technical_source_lookup",
        "capability": "source-backed-reasoning",
        "project": "research-parts-reference",
        "engine": "local-research",
        "profile": "local-research",
    },
    {
        "id": "compatibility",
        "text": "Will a 24 V inductive proximity sensor work with a 5 V microcontroller input?",
        "domain": "technical_compatibility",
        "capability": "source-backed-reasoning",
        "project": "research-parts-reference",
        "engine": "local-research",
        "profile": "local-research",
    },
    {
        "id": "local-product-action",
        "text": "Fix the spacing in the Codex CLI UI dashboard and verify it.",
        "domain": "local_product_action",
        "capability": "local-product-action",
        "project": "codex-cli-ui-local-agent",
        "engine": "local",
        "profile": "local-coder",
    },
)


def main() -> int:
    rows = []
    for case in CASES:
        messages = [{"role": "user", "text": case["text"]}]
        route = server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="live",
        )
        frame = route.get("intentFrame") or {}
        decision = route.get("kernelDecision") or {}
        plan = route.get("capabilityPlan") or {}
        direct = server.general_direct_knowledge_answer(
            messages,
            route,
            web_search="live",
            allow_legacy=bool(decision.get("allowLegacyDirectAnswer")),
        )
        passed = bool(
            frame.get("domain") == case["domain"]
            and plan.get("registered") is True
            and plan.get("id") == case["capability"]
            and decision.get("mode") == "model-first"
            and decision.get("allowLegacyDirectAnswer") is False
            and route.get("projectId") == case["project"]
            and route.get("engine") == case["engine"]
            and route.get("effectiveProfile") == case["profile"]
            and direct is None
        )
        rows.append(
            {
                "id": case["id"],
                "passed": passed,
                "domain": frame.get("domain"),
                "capability": plan.get("id"),
                "mode": decision.get("mode"),
                "legacyDirect": decision.get("allowLegacyDirectAnswer"),
                "project": route.get("projectId"),
                "engine": route.get("engine"),
                "profile": route.get("effectiveProfile"),
                "directAnswer": (direct or {}).get("mode") if isinstance(direct, dict) else None,
            }
        )

    clarification_messages = [{"role": "user", "text": "Can you fix it?"}]
    clarification_route = server.route_manager(
        clarification_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="live",
    )
    clarification_direct = server.general_direct_knowledge_answer(
        clarification_messages,
        clarification_route,
        web_search="live",
        allow_legacy=True,
    )
    clarification_plan = clarification_route.get("capabilityPlan") or {}
    clarification_answer = str((clarification_direct or {}).get("answer") or "")
    clarification_passed = bool(
        (clarification_route.get("intentFrame") or {}).get("domain") == "clarification"
        and clarification_plan.get("id") == "focused-clarification"
        and clarification_plan.get("registered") is True
        and (clarification_direct or {}).get("mode") == "objective-plan-clarification"
        and clarification_answer.endswith("?")
        and "what" in clarification_answer.lower()
    )
    rows.append(
        {
            "id": "focused-clarification",
            "passed": clarification_passed,
            "domain": (clarification_route.get("intentFrame") or {}).get("domain"),
            "capability": clarification_plan.get("id"),
            "mode": (clarification_route.get("kernelDecision") or {}).get("mode"),
            "project": clarification_route.get("projectId"),
            "profile": clarification_route.get("effectiveProfile"),
            "answer": clarification_answer,
        }
    )

    capability_messages = [
        {"role": "user", "text": "Can you give me a high-level list of your capabilities to help me?"}
    ]
    capability_route = server.route_manager(
        capability_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    capability_route["runtimeCapabilitySnapshot"] = server.build_runtime_capability_snapshot(
        access_level="danger-full-access",
        cwd=str(ROOT),
        web_search="disabled",
    )
    capability_direct = server.general_direct_knowledge_answer(
        capability_messages,
        capability_route,
        web_search="disabled",
        allow_legacy=True,
    ) or {}
    capability_plan = capability_route.get("capabilityPlan") or {}
    capability_answer = str(capability_direct.get("answer") or "")
    inventory_answer = server.runtime_capability_introspection_direct_answer(
        [{"role": "user", "text": "What tools and models are actually installed and available right now?"}],
        capability_route,
    )
    action_route = server.route_manager(
        [{"role": "user", "text": "Can you edit server.py and run its tests?"}],
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    capability_passed = bool(
        (capability_route.get("intentFrame") or {}).get("domain") == "agent_runtime_capabilities"
        and capability_plan.get("id") == "runtime-capability-introspection"
        and capability_plan.get("registered") is True
        and (capability_route.get("kernelDecision") or {}).get("mode") == "deterministic-capability"
        and capability_direct.get("mode") == "runtime-capability-introspection"
        and "Full Access" in capability_answer
        and "Think with you" in capability_answer
        and "work directly on this Mac" in capability_answer
        and "visible commands" not in capability_answer
        and "visible commands" in inventory_answer
        and len(capability_answer) < 1500
        and "do not have direct access" not in capability_answer.lower()
        and (action_route.get("intentFrame") or {}).get("domain") != "agent_runtime_capabilities"
    )
    rows.append(
        {
            "id": "runtime-capability-introspection",
            "passed": capability_passed,
            "domain": (capability_route.get("intentFrame") or {}).get("domain"),
            "capability": capability_plan.get("id"),
            "mode": (capability_route.get("kernelDecision") or {}).get("mode"),
            "project": capability_route.get("projectId"),
            "profile": capability_route.get("effectiveProfile"),
            "directAnswer": capability_direct.get("mode"),
            "actionCollisionDomain": (action_route.get("intentFrame") or {}).get("domain"),
        }
    )

    failures = [row for row in rows if not row.get("passed")]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(rows) - len(failures),
        "total": len(rows),
        "failures": failures,
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
