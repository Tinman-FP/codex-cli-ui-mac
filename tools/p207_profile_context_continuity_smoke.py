#!/usr/bin/env python3
"""P207 regression: profile carryover reuses proven context without guessing."""

from __future__ import annotations

import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
from capability_registry import registry_health  # noqa: E402


def route(messages):
    return server.route_manager(
        messages,
        cwd=str(APP_DIR),
        requested_profile="manager",
        web_search="disabled",
    )


def main() -> int:
    checks = {}
    prior = [
        {
            "role": "user",
            "text": "will you pull the current filament settings for PET-CF for my 0.6 nozzle on my plus 4?",
        },
        {
            "role": "assistant",
            "text": (
                "For the Qidi Plus 4 with a 0.6 mm nozzle, the current QIDI PET-CF "
                "@Qidi X-Plus 4 0.6 nozzle filament profile is: Nozzle temp 300 C, "
                "bed 80 C, flow ratio 1.08, max volumetric speed 4 mm3/s, pressure "
                "advance enabled at 0.025, fan 0%, first-layer fan off for 3 layers, "
                "and filament retraction 0.8 mm at 30 mm/s."
            ),
        },
    ]
    resolved_messages = [
        *prior,
        {"role": "user", "text": "put those settings on the other profile for Max EZ"},
    ]
    resolved = server.resolved_profile_settings_carryover_context(resolved_messages)
    active_route = route(resolved_messages)
    checks["source-target-values-are-bound"] = bool(
        resolved.get("source") == "Qidi Plus 4"
        and resolved.get("target") == "Qidi Max EZ"
        and (resolved.get("values") or {}).get("nozzle_temperature") == "300 C"
        and (resolved.get("values") or {}).get("pressure_advance") == "0.025"
    )
    checks["typed-owner-precedes-generic-conversation"] = bool(
        (active_route.get("capabilityPlan") or {}).get("id")
        == "profile-settings-carryover"
        and (active_route.get("intentFrame") or {}).get("domain")
        == "profile_settings_carryover"
        and (active_route.get("intentFrame") or {}).get("lineageDomain")
        in {"conversation", "knowledge_question"}
    )
    checks["resolved-reference-bypasses-ambiguity-guard"] = not bool(
        server.unresolved_referent_preflight_response(
            resolved_messages,
            active_route,
        ).get("handled")
    )
    checks["resolved-reference-does-not-reopen-in-final-ledger"] = (
        server.material_unresolved_referent(resolved_messages, active_route) == ""
    )

    scoped = server.scope_messages_for_intent(
        resolved_messages,
        active_route.get("intentFrame"),
    )
    lineage = server.bind_response_turn_lineage(
        resolved_messages,
        active_route,
        run_id="p207-profile-continuity",
        active_messages=scoped,
        cwd=str(APP_DIR),
        requested_profile="manager",
        web_search="disabled",
    )
    checks["lineage-retains-prior-values"] = bool(
        lineage.get("transition") == "continuation"
        and lineage.get("decision") == "retain"
        and lineage.get("mayReusePriorEvidence") is True
        and not lineage.get("issues")
    )

    result = server.execute_deterministic_capability(
        scoped,
        active_route,
        fullMessages=resolved_messages,
        webSearch="disabled",
    )
    answer = str(result.get("answer") or "")
    checks["controller-answer-is-complete-and-truthful"] = bool(
        result.get("handled")
        and result.get("outcome") == "completed"
        and result.get("textLocked")
        and all(
            term in answer
            for term in (
                "Qidi Plus 4",
                "Qidi Max EZ",
                "Nozzle temp",
                "300 C",
                "Pressure advance",
                "0.025",
                "not claimed",
                "protected/system preset",
            )
        )
    )
    checks["answer-avoids-canned-scaffold"] = bool(
        "This is why:" not in answer
        and "You should also consider:" not in answer
        and "previous action" not in answer.lower()
    )
    contract = server.task_contract(resolved_messages, active_route)
    checks["task-contract-matches-local-continuation"] = bool(
        contract.get("kind") == "Profile settings carryover"
        and "source URLs" not in " ".join(contract.get("requiredProof") or [])
        and "truthful write boundary" in (contract.get("requiredProof") or [])
    )
    evidence_policy = server.evidence_ledger_policy(
        resolved_messages,
        active_route,
        contract=contract,
    )
    checks["conversation-values-do-not-trigger-web-proof"] = bool(
        evidence_policy.get("sourceType") == "not-needed"
        and evidence_policy.get("terminalRequirement") == "none"
        and evidence_policy.get("required") is False
    )

    unnamed_target = [
        *prior,
        {"role": "user", "text": "put those settings on the other profile"},
    ]
    unnamed_route = route(unnamed_target)
    checks["unnamed-destination-still-clarifies"] = bool(
        not server.resolved_profile_settings_carryover_context(unnamed_target)
        and (unnamed_route.get("capabilityPlan") or {}).get("id")
        == "focused-clarification"
        and server.execute_deterministic_capability(
            unnamed_target,
            unnamed_route,
        ).get("outcome")
        == "needs-input"
    )

    no_values = [
        {"role": "user", "text": "I use a Qidi Plus 4 slicer profile."},
        {"role": "assistant", "text": "Understood."},
        {"role": "user", "text": "put those settings on the other profile for Max EZ"},
    ]
    checks["missing-source-values-do-not-gain-authority"] = bool(
        not server.resolved_profile_settings_carryover_context(no_values)
        and (route(no_values).get("capabilityPlan") or {}).get("id")
        != "profile-settings-carryover"
    )

    standalone = [
        {"role": "user", "text": "put those settings on the other profile for Max EZ"}
    ]
    checks["standalone-pronoun-does-not-gain-authority"] = bool(
        not server.resolved_profile_settings_carryover_context(standalone)
        and (route(standalone).get("capabilityPlan") or {}).get("id")
        != "profile-settings-carryover"
    )

    unrelated = [
        {"role": "user", "text": "We discussed two account profiles."},
        {"role": "assistant", "text": "The account profiles have different permissions."},
        {"role": "user", "text": "copy those settings to the other profile for Max EZ"},
    ]
    checks["unrelated-profile-context-does-not-gain-authority"] = bool(
        not server.resolved_profile_settings_carryover_context(unrelated)
        and (route(unrelated).get("capabilityPlan") or {}).get("id")
        != "profile-settings-carryover"
    )

    checks["registry-health"] = registry_health().get("status") == "pass"
    checks["deterministic-router-health"] = (
        server.deterministic_capability_executor_health().get("status") == "pass"
    )

    failed = [name for name, passed in checks.items() if not passed]
    payload = {
        "status": "pass" if not failed else "fail",
        "checkCount": len(checks),
        "failed": failed,
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
