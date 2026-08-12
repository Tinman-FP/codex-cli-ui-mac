#!/usr/bin/env python3
"""Verify typed capability ownership across adversarial first and follow-up turns."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server
from tools.adversarial_understanding_replay import CASES


EXPECTED_BY_DOMAIN = {
    "engineering_power_conversion": "engineering-power-conversion",
    "engineering_advisory": "engineering-advisory",
    "engineering_tradeoff": "engineering-advisory",
    "klipper_config_migration": "klipper-config-migration",
}


CONTEXT_RELATIONSHIP_CASES = (
    {
        "name": "cross-domain-failure-risk-dependency",
        "messages": (
            {"role": "user", "text": "We are choosing LoRa for a remote irrigation sensor network."},
            {"role": "assistant", "text": "That choice trades range against bandwidth and deployment complexity."},
            {"role": "user", "text": "What failure modes should I design around if I use LoRa?"},
        ),
        "expectedRelation": "follow-up",
        "expectedScope": "recent-thread",
    },
    {
        "name": "cross-domain-final-artifact-dependency",
        "messages": (
            {"role": "user", "text": "Map each Northwind service and its deployment dependency."},
            {"role": "assistant", "text": "The service relationships are ready for the deployment artifact."},
            {"role": "user", "text": "What should I verify before creating the final Northwind deployment map?"},
        ),
        "expectedRelation": "follow-up",
        "expectedScope": "recent-thread",
    },
    {
        "name": "cross-domain-prior-option-selection",
        "messages": (
            {"role": "user", "text": "Compare a star schema, snowflake schema, and data vault for this warehouse."},
            {"role": "assistant", "text": "Each has different maintenance and query-complexity tradeoffs."},
            {"role": "user", "text": "Which option would you recommend for the smallest operations team?"},
        ),
        "expectedRelation": "follow-up",
        "expectedScope": "recent-thread",
    },
    {
        "name": "new-subject-risk-request-isolates",
        "messages": (
            {"role": "user", "text": "We are choosing LoRa for a remote irrigation sensor network."},
            {"role": "assistant", "text": "That choice trades range against bandwidth."},
            {"role": "user", "text": "What are the failure modes of a PostgreSQL failover cluster?"},
        ),
        "expectedRelation": "new-topic",
        "expectedScope": "latest-turn",
    },
    {
        "name": "new-subject-final-artifact-isolates",
        "messages": (
            {"role": "user", "text": "Compare welded steel and aluminum extrusion for a router frame."},
            {"role": "assistant", "text": "The frame choices have different assembly tradeoffs."},
            {"role": "user", "text": "Before creating the final Kubernetes config, what should I verify?"},
        ),
        "expectedRelation": "new-topic",
        "expectedScope": "latest-turn",
    },
    {
        "name": "new-subject-explicit-options-isolate",
        "messages": (
            {"role": "user", "text": "Compare welded steel and aluminum extrusion for a router frame."},
            {"role": "assistant", "text": "The frame choices have different assembly tradeoffs."},
            {"role": "user", "text": "Which option is better for the new database: SQLite or PostgreSQL?"},
        ),
        "expectedRelation": "new-topic",
        "expectedScope": "latest-turn",
    },
    {
        "name": "no-context-option-selection-fails-closed",
        "messages": (
            {"role": "user", "text": "Which option should I use?"},
        ),
        "expectedRelation": "standalone",
        "expectedScope": "latest-turn",
    },
)


def main() -> int:
    rows = []
    for case in CASES:
        first_messages = [{"role": "user", "text": case["first"]}]
        followup_messages = first_messages + [
            {"role": "assistant", "text": "Prior answer placeholder."},
            {"role": "user", "text": case["followup"]},
        ]
        for stage, messages in (("first", first_messages), ("followup", followup_messages)):
            route = server.route_manager(
                messages,
                requested_profile="manager",
                web_search=case.get("followupWebSearch", case.get("webSearch", "disabled")) if stage == "followup" else case.get("webSearch", "disabled"),
            )
            frame = route.get("intentFrame") or {}
            decision = route.get("kernelDecision") or {}
            plan = route.get("capabilityPlan") or {}
            explicit_expected_key = (
                "expectedFirstCapability" if stage == "first" else "expectedFollowupCapability"
            )
            expected = case.get(explicit_expected_key) or EXPECTED_BY_DOMAIN.get(
                frame.get("domain"),
                "",
            )
            model_first = decision.get("mode") == "model-first"
            passed = bool(
                expected
                and plan.get("registered") is True
                and plan.get("id") == expected
                and (not model_first or decision.get("allowLegacyDirectAnswer") is False)
            )
            rows.append(
                {
                    "case": case["id"],
                    "stage": stage,
                    "domain": frame.get("domain"),
                    "mode": decision.get("mode"),
                    "allowLegacyDirectAnswer": decision.get("allowLegacyDirectAnswer"),
                    "plan": plan.get("id"),
                    "expected": expected,
                    "passed": passed,
                }
            )
    route_failures = [row for row in rows if not row["passed"]]
    context_rows = []
    for case in CONTEXT_RELATIONSHIP_CASES:
        relationship = server.turn_context_relationship(case["messages"])
        passed = bool(
            relationship.get("contextRelation") == case["expectedRelation"]
            and relationship.get("contextScope") == case["expectedScope"]
        )
        context_rows.append(
            {
                "case": case["name"],
                "stage": "context-relationship",
                "contextRelation": relationship.get("contextRelation"),
                "contextScope": relationship.get("contextScope"),
                "sharedTopicTerms": relationship.get("sharedTopicTerms") or [],
                "reason": relationship.get("reason"),
                "expectedRelation": case["expectedRelation"],
                "expectedScope": case["expectedScope"],
                "passed": passed,
            }
        )
    context_failures = [row for row in context_rows if not row["passed"]]
    failures = route_failures + context_failures
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(rows) - len(route_failures),
        "total": len(rows),
        "registered": sum(1 for row in rows if row.get("plan") != "unregistered"),
        "failures": failures,
        "rows": rows,
        "contextRelationship": {
            "status": "pass" if not context_failures else "fail",
            "passed": len(context_rows) - len(context_failures),
            "total": len(context_rows),
            "rows": context_rows,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
