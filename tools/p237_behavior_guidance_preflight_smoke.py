#!/usr/bin/env python3
"""P237 adversaries for behavior-guidance ownership before referent blocking."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


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

    def route_for(messages):
        return server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )

    naming_guidance = [
        {
            "role": "user",
            "text": (
                "I have a Vevor inverter and batteries. Please make a block "
                "diagram and wiring diagram for the backup-power system."
            ),
        },
        {
            "role": "assistant",
            "text": (
                "I created an engineering diagram package for Solar, Grid, "
                "and Backup Battery Power Architecture."
            ),
        },
        {
            "role": "user",
            "text": (
                "In the future, can you label the output more professionally? "
                "Instead of the first words of my request, how about Vevor "
                "Inverter wiring, or Back Up power."
            ),
        },
    ]
    naming_route = route_for(naming_guidance)
    naming_frame = naming_route.get("intentFrame") or {}
    naming_objective = naming_route.get("objectivePlan") or {}
    naming_preflight = server.unresolved_referent_preflight_response(
        naming_guidance,
        naming_route,
    )
    naming_packet = server.general_direct_knowledge_answer(
        naming_guidance,
        naming_route,
        web_search="disabled",
    ) or {}
    naming_answer = str(naming_packet.get("answer") or "")

    add(
        "future-output-preference-has-typed-behavior-owner",
        server.is_behavior_guidance_message(naming_guidance)
        and naming_route.get("projectId") == "codex-cli-ui-local-agent"
        and naming_frame.get("specialistOwner") == "behavior-guidance"
        and naming_objective.get("objectiveType") == "behavior-guidance",
        {
            "projectId": naming_route.get("projectId"),
            "specialistOwner": naming_frame.get("specialistOwner"),
            "objectiveType": naming_objective.get("objectiveType"),
        },
    )
    add(
        "typed-behavior-guidance-precedes-generic-referent-guard",
        naming_preflight == {}
        and (naming_route.get("_behaviorGuidancePreflight") or {}).get("status")
        == "pass"
        and not naming_route.get("_unresolvedReferentPreflight"),
        {
            "preflight": naming_preflight,
            "receipt": naming_route.get("_behaviorGuidancePreflight"),
        },
    )
    add(
        "naming-guidance-answers-request-instead-of-asking-where-to-inspect",
        "operating guidance" in naming_answer
        and "Vevor Inverter Backup Power Wiring" in naming_answer
        and "not copy the opening words" in naming_answer
        and "where can I inspect" not in naming_answer,
        naming_answer,
    )
    add(
        "behavior-guidance-preserves-risk-boundary",
        all(
            phrase in naming_answer
            for phrase in (
                "safety boundary",
                "destructive work",
                "live-printer changes",
                "downloads/storage use",
            )
        ),
        naming_answer,
    )

    unrelated_naming_guidance = [
        {
            "role": "user",
            "text": "Create a quarterly deployment report for Northwind.",
        },
        {
            "role": "assistant",
            "text": "I created a report titled Quarterly Deployment Notes.",
        },
        {
            "role": "user",
            "text": (
                "Going forward, use a more professional naming style for future "
                "outputs. How about Northwind Deployment report, or Release Readiness."
            ),
        },
    ]
    unrelated_route = route_for(unrelated_naming_guidance)
    unrelated_preflight = server.unresolved_referent_preflight_response(
        unrelated_naming_guidance,
        unrelated_route,
    )
    unrelated_answer = server.format_behavior_guidance_answer(
        unrelated_naming_guidance
    )
    add(
        "unrelated-domain-guidance-uses-user-supplied-subject-not-fixture-domain",
        server.is_behavior_guidance_message(unrelated_naming_guidance)
        and unrelated_preflight == {}
        and "Northwind Deployment Release Readiness Report" in unrelated_answer
        and "Vevor" not in unrelated_answer
        and "inverter" not in unrelated_answer.lower(),
        unrelated_answer,
    )

    naming_followup = [
        *unrelated_naming_guidance,
        {"role": "assistant", "text": unrelated_answer},
        {
            "role": "user",
            "text": "From now on, use that naming style for future reports too.",
        },
    ]
    followup_route = route_for(naming_followup)
    add(
        "guidance-followup-retains-behavior-owner-without-domain-leakage",
        server.is_behavior_guidance_message(naming_followup)
        and (followup_route.get("intentFrame") or {}).get("specialistOwner")
        == "behavior-guidance"
        and server.unresolved_referent_preflight_response(
            naming_followup,
            followup_route,
        )
        == {}
        and "Vevor"
        not in server.format_behavior_guidance_answer(naming_followup),
        {
            "route": followup_route.get("projectId"),
            "owner": (followup_route.get("intentFrame") or {}).get(
                "specialistOwner"
            ),
        },
    )

    current_artifact_action = [
        {
            "role": "assistant",
            "text": "I created Draft_Report.md and Comparison_Report.md.",
        },
        {
            "role": "user",
            "text": "Rename the output file to Final_Report.md now.",
        },
    ]
    add(
        "current-artifact-rename-is-not-reclassified-as-future-guidance",
        not server.is_behavior_guidance_message(current_artifact_action),
        server.is_behavior_guidance_message(current_artifact_action),
    )

    ambiguous_action = [
        {
            "role": "assistant",
            "text": "I created an operations report and a deployment report.",
        },
        {"role": "user", "text": "Change the first report."},
    ]
    ambiguous_route = route_for(ambiguous_action)
    ambiguous_preflight = server.unresolved_referent_preflight_response(
        ambiguous_action,
        ambiguous_route,
    )
    add(
        "genuine-multi-artifact-referent-still-fails-closed",
        not server.is_behavior_guidance_message(ambiguous_action)
        and ambiguous_preflight.get("handled") is True
        and ambiguous_preflight.get("mode")
        == "unresolved-referent-clarification"
        and (ambiguous_route.get("_unresolvedReferentPreflight") or {}).get(
            "toolCalls"
        )
        == 0,
        ambiguous_preflight,
    )

    bound_action = [
        {
            "role": "assistant",
            "text": "I created the report.md artifact and left it unchanged.",
        },
        {
            "role": "user",
            "text": "Change the title in `report.md` to Final Report.",
        },
    ]
    bound_route = route_for(bound_action)
    add(
        "explicitly-bound-artifact-action-is-neither-guidance-nor-blocked",
        not server.is_behavior_guidance_message(bound_action)
        and server.unresolved_referent_preflight_response(
            bound_action,
            bound_route,
        )
        == {},
        {
            "behaviorGuidance": server.is_behavior_guidance_message(bound_action),
            "unresolved": server.material_unresolved_referent(
                bound_action,
                bound_route,
            ),
        },
    )

    unrelated_domain = [
        {
            "role": "assistant",
            "text": "We were discussing journal metadata and indexing.",
        },
        {
            "role": "user",
            "text": "Explain professional title conventions for journal articles.",
        },
    ]
    unrelated_domain_route = route_for(unrelated_domain)
    add(
        "unrelated-title-question-does-not-acquire-behavior-guidance-owner",
        not server.is_behavior_guidance_message(unrelated_domain)
        and (unrelated_domain_route.get("intentFrame") or {}).get(
            "specialistOwner"
        )
        != "behavior-guidance"
        and not unrelated_domain_route.get("_behaviorGuidancePreflight"),
        {
            "projectId": unrelated_domain_route.get("projectId"),
            "owner": (unrelated_domain_route.get("intentFrame") or {}).get(
                "specialistOwner"
            ),
        },
    )

    untyped_route = {}
    untyped_preflight = server.unresolved_referent_preflight_response(
        naming_guidance,
        untyped_route,
    )
    add(
        "guidance-words-alone-cannot-bypass-referent-guard-without-typed-owner",
        untyped_preflight.get("handled") is True
        and untyped_preflight.get("mode")
        == "unresolved-referent-clarification"
        and not untyped_route.get("_behaviorGuidancePreflight"),
        untyped_preflight,
    )

    fake_owner_route = {
        "intentFrame": {"specialistOwner": "behavior-guidance"},
        "objectivePlan": {"objectiveType": "behavior-guidance"},
    }
    fake_owner_preflight = server.unresolved_referent_preflight_response(
        ambiguous_action,
        fake_owner_route,
    )
    add(
        "typed-owner-alone-cannot-bypass-when-message-is-an-action",
        fake_owner_preflight.get("handled") is True
        and not fake_owner_route.get("_behaviorGuidancePreflight"),
        fake_owner_preflight,
    )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "p237-package-and-export-registration",
        "server:behavior-guidance-preflight-p237" in source_text
        and "p237_behavior_guidance_preflight_smoke.py" in source_text
        and "tools/p237_behavior_guidance_preflight_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p237-behavior-guidance-preflight",
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
