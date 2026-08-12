#!/usr/bin/env python3
"""Focused offline regression for registered typed local-action response policy."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def evaluate(prompt: str, *, composition: dict | None = None) -> dict:
    messages = [{"role": "user", "text": prompt}]
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    contract = server.task_contract(messages, route)
    active_composition = composition or server.adaptive_answer_composition_profile(messages, route)
    director = server.interaction_director_policy(
        messages,
        route,
        contract=contract,
        composition=active_composition,
    )
    ledger = server.evidence_ledger_policy(
        messages,
        route,
        contract=contract,
        director=director,
    )
    composer = server.response_composer_policy(
        messages,
        route,
        contract=contract,
        composition=active_composition,
        director=director,
    )
    frame = route.get("intentFrame") if isinstance(route.get("intentFrame"), dict) else {}
    plan = frame.get("operationPlan") if isinstance(frame.get("operationPlan"), dict) else {}
    capability = route.get("capabilityPlan") if isinstance(route.get("capabilityPlan"), dict) else {}
    return {
        "messages": messages,
        "route": route,
        "contract": contract,
        "domain": frame.get("domain"),
        "capabilityId": capability.get("id"),
        "registered": capability.get("registered"),
        "allowedNow": plan.get("allowedNow") or [],
        "wantsWeb": server.wants_web_context(messages),
        "fresh": server.route_requires_fresh_external_evidence(messages, route),
        "sourceType": ledger.get("sourceType"),
        "directorMode": director.get("mode"),
        "composerMode": composer.get("mode"),
        "hardGate": contract.get("hardGate"),
        "accessLevel": server.operation_execution_access_level(route, "danger-full-access"),
        "toolGuidance": server.local_action_execution_tool_guidance(route),
    }


def typed_local(result: dict) -> bool:
    return bool(
        result.get("domain") == "local_product_action"
        and result.get("capabilityId") == "local-product-action"
        and result.get("registered") is True
        and server.is_registered_local_product_tool_action(result.get("route"))
    )


def policy_view(result: dict) -> dict:
    return {
        key: result.get(key)
        for key in (
            "domain",
            "capabilityId",
            "registered",
            "allowedNow",
            "wantsWeb",
            "fresh",
            "sourceType",
            "directorMode",
            "composerMode",
            "hardGate",
            "accessLevel",
        )
    }


def main() -> int:
    bambu = evaluate(
        "in the model health for the bambu h2d it is now showing printing, which is good, "
        "but i als want it to display percent complete and time remaining on the print."
    )
    incidental_today = evaluate(
        "Update the Codex CLI UI today so the Run Log shows elapsed task time."
    )
    ebay_research = evaluate(
        "Find the best current eBay listing for a complete 100W JPT MOPA fiber laser."
    )
    typed_web_research = evaluate(
        "Research current web sources, then update the Codex CLI UI Model Health panel "
        "to show the latest public Bambu status fields."
    )
    live_restart = evaluate(
        "Update the Codex CLI UI restart control, then restart Klipper on the live Qidi printer."
    )
    engineering = evaluate(
        "Analyze whether a 6061-T6 aluminum bracket is suitable for this application.",
        composition={"name": "proof-structured"},
    )

    checks = [
        {
            "id": "exact-bambu-request-uses-typed-local-execution-policy",
            "ok": typed_local(bambu)
            and {"inspect", "edit", "test"}.issubset(set(bambu["allowedNow"]))
            and bambu["wantsWeb"] is False
            and bambu["fresh"] is False
            and bambu["sourceType"] == "local"
            and bambu["directorMode"] == "execution"
            and bambu["composerMode"] == "action-result",
            "actual": policy_view(bambu),
        },
        {
            "id": "incidental-today-does-not-promote-typed-local-edit-to-research",
            "ok": typed_local(incidental_today)
            and incidental_today["wantsWeb"] is True
            and "research" not in incidental_today["allowedNow"]
            and incidental_today["fresh"] is False
            and incidental_today["sourceType"] == "local"
            and incidental_today["directorMode"] == "execution"
            and incidental_today["composerMode"] == "action-result",
            "actual": policy_view(incidental_today),
        },
        {
            "id": "explicit-current-ebay-research-remains-current-web-evidence",
            "ok": ebay_research["domain"] == "marketplace_listing_research"
            and ebay_research["capabilityId"] == "ebay-marketplace-research"
            and ebay_research["fresh"] is True
            and ebay_research["sourceType"] == "current-web"
            and ebay_research["directorMode"] == "research"
            and ebay_research["composerMode"] == "evidence",
            "actual": policy_view(ebay_research),
        },
        {
            "id": "typed-local-explicit-web-research-is-not-suppressed",
            "ok": typed_local(typed_web_research)
            and typed_web_research["wantsWeb"] is True
            and "research" in typed_web_research["allowedNow"]
            and typed_web_research["fresh"] is True
            and typed_web_research["sourceType"] == "current-web"
            and typed_web_research["directorMode"] == "research"
            and typed_web_research["composerMode"] == "evidence",
            "actual": policy_view(typed_web_research),
        },
        {
            "id": "live-restart-keeps-safety-and-live-state-precedence",
            "ok": typed_local(live_restart)
            and "restart" in live_restart["allowedNow"]
            and live_restart["hardGate"] is True
            and live_restart["sourceType"] == "live-state"
            and live_restart["directorMode"] == "safety"
            and live_restart["composerMode"] == "action-result"
            and live_restart["accessLevel"] == "read-only"
            and "grant no implied permission: restart" in live_restart["toolGuidance"],
            "actual": policy_view(live_restart),
        },
        {
            "id": "stable-engineering-advisory-retains-expert-direct-policy",
            "ok": engineering["domain"] == "engineering_advisory"
            and engineering["capabilityId"] == "engineering-advisory"
            and engineering["fresh"] is False
            and engineering["directorMode"] == "expert-direct"
            and engineering["composerMode"] == "expert-direct",
            "actual": policy_view(engineering),
        },
    ]
    failed = [item for item in checks if not item["ok"]]
    report = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
