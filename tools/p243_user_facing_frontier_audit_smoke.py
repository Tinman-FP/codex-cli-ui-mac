#!/usr/bin/env python3
"""P243 adversaries for latest-turn routing and user-facing context isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=None):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def route_summary(messages, *, web_search="disabled"):
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web_search,
    )
    frame = route.get("intentFrame") or {}
    plan = route.get("objectivePlan") or {}
    capability = route.get("capabilityPlan") or {}
    scoped = server.scope_messages_for_intent(messages, frame)
    return route, frame, plan, capability, scoped


engineering_prefix = [
    {
        "role": "user",
        "text": "A printed electronics enclosure flexes beside its long vent.",
    },
    {
        "role": "assistant",
        "text": "Add ribs parallel to the vent and preserve the airflow path.",
    },
]

capability_query = (
    "Can this app inspect files in its current local workspace without installing "
    "anything? Report capability only; do not inspect a file."
)
capability_messages = [
    *engineering_prefix,
    {"role": "user", "text": capability_query},
]
capability_relation = server.turn_context_relationship(capability_messages)
capability_route, capability_frame, _, capability_plan, capability_scoped = (
    route_summary(capability_messages)
)
check(
    "explicit-current-app-surface-is-a-new-topic",
    capability_relation.get("contextRelation") == "new-topic"
    and capability_relation.get("contextScope") == "latest-turn",
    capability_relation,
)
check(
    "current-app-capability-outranks-stale-engineering-history",
    capability_frame.get("domain") == "agent_runtime_capabilities"
    and capability_route.get("projectId") == "codex-cli-ui-local-agent"
    and capability_plan.get("executor") == "deterministic"
    and capability_plan.get("handler_key") == "runtime_capability_introspection",
    {
        "domain": capability_frame.get("domain"),
        "projectId": capability_route.get("projectId"),
        "executor": capability_plan.get("executor"),
        "handler": capability_plan.get("handler_key"),
    },
)
capability_operations = capability_frame.get("operationPlan") or {}
check(
    "capability-only-question-preserves-no-inspection-boundary",
    (capability_frame.get("outputContract") or {}).get("mode")
    == "conversation-answer"
    and capability_operations.get("allowedNow") == []
    and "inspect" in (capability_operations.get("prohibited") or [])
    and capability_operations.get("readOnly") is True,
    {
        "outputContract": capability_frame.get("outputContract"),
        "operationPlan": capability_operations,
    },
)
check(
    "current-app-worker-sees-only-latest-topic",
    len(capability_scoped) == 1
    and capability_scoped[0].get("text") == capability_query,
    capability_scoped,
)


market_query = (
    "What is the live spot price of copper right now? Do not use the web and do "
    "not guess."
)
market_messages = [
    *engineering_prefix,
    {"role": "user", "text": market_query},
]
market_route, market_frame, _, market_plan, market_scoped = route_summary(
    market_messages
)
latest_market_route, latest_market_frame, _, latest_market_plan, _ = route_summary(
    [{"role": "user", "text": market_query}]
)
check(
    "current-fact-topic-switch-keeps-current-evidence-owner",
    market_frame.get("domain") == "current_market_research"
    and market_route.get("projectId") == "research-parts-reference"
    and market_plan.get("executor") == "research"
    and market_frame.get("contextRelation") == "new-topic",
    {
        "domain": market_frame.get("domain"),
        "projectId": market_route.get("projectId"),
        "executor": market_plan.get("executor"),
        "relation": market_frame.get("contextRelation"),
    },
)
check(
    "full-thread-and-latest-only-current-fact-routing-agree",
    (
        market_frame.get("domain"),
        market_route.get("projectId"),
        market_plan.get("handler_key"),
    )
    == (
        latest_market_frame.get("domain"),
        latest_market_route.get("projectId"),
        latest_market_plan.get("handler_key"),
    ),
    {
        "full": [
            market_frame.get("domain"),
            market_route.get("projectId"),
            market_plan.get("handler_key"),
        ],
        "latest": [
            latest_market_frame.get("domain"),
            latest_market_route.get("projectId"),
            latest_market_plan.get("handler_key"),
        ],
    },
)
excluded_market_concepts = set(
    ((market_frame.get("semanticExclusions") or {}).get("excludedConcepts") or [])
)
check(
    "web-disabled-current-fact-keeps-evidence-and-no-guess-boundary",
    market_route.get("engine") == "local"
    and {"web", "guess"}.issubset(excluded_market_concepts)
    and len(market_scoped) == 1
    and market_scoped[0].get("text") == market_query,
    {
        "engine": market_route.get("engine"),
        "excludedConcepts": sorted(excluded_market_concepts),
        "workerCount": len(market_scoped),
    },
)


urgent_query = (
    "Someone has sudden facial droop and slurred speech. What should I do right now?"
)
urgent_messages = [
    *engineering_prefix,
    {"role": "user", "text": urgent_query},
]
urgent_route, urgent_frame, _, urgent_plan, urgent_scoped = route_summary(
    urgent_messages
)
check(
    "urgent-safety-topic-switch-keeps-registered-specialist",
    urgent_frame.get("domain") == "bounded_specialist_capability"
    and urgent_frame.get("specialistOwner") == "medical-emergency-boundary"
    and "high-stakes-boundary" in (urgent_route.get("matched") or [])
    and urgent_plan.get("executor") == "deterministic",
    {
        "domain": urgent_frame.get("domain"),
        "owner": urgent_frame.get("specialistOwner"),
        "matched": urgent_route.get("matched"),
        "executor": urgent_plan.get("executor"),
    },
)
check(
    "urgent-safety-worker-cannot-see-unrelated-design-advice",
    urgent_frame.get("contextRelation") == "new-topic"
    and len(urgent_scoped) == 1
    and urgent_scoped[0].get("text") == urgent_query,
    urgent_scoped,
)


pronoun_messages = [
    *engineering_prefix,
    {"role": "user", "text": "What should I change first on it?"},
]
pronoun_relation = server.turn_context_relationship(pronoun_messages)
_, pronoun_frame, _, _, pronoun_scoped = route_summary(pronoun_messages)
check(
    "true-pronoun-followup-keeps-recent-context",
    pronoun_relation.get("contextRelation") == "follow-up"
    and pronoun_frame.get("contextRelation") == "follow-up"
    and len(pronoun_scoped) == len(pronoun_messages),
    {
        "relationship": pronoun_relation,
        "frameRelation": pronoun_frame.get("contextRelation"),
        "workerCount": len(pronoun_scoped),
    },
)

app_with_object_messages = [
    *engineering_prefix,
    {"role": "user", "text": "Can this app compare it without changing it?"},
]
app_with_object_relation = server.turn_context_relationship(
    app_with_object_messages
)
check(
    "active-surface-phrase-does-not-hide-a-second-pronoun",
    app_with_object_relation.get("contextRelation") == "follow-up"
    and app_with_object_relation.get("contextScope") == "recent-thread",
    app_with_object_relation,
)

artifact_history = [
    {
        "role": "user",
        "text": "Rename the editable diagram to Utility Interlock Overview.",
    },
    {
        "role": "assistant",
        "text": (
            "I revised the generated artifact and saved the new copy here: "
            "`/tmp/utility-interlock_revised.drawio`.\n\n"
            "Changed: draw.io diagram tab name set to `Utility Interlock Overview`. "
            "Original left unchanged: `/tmp/utility-interlock.drawio`.\n\n"
            "Other prior outputs left unchanged:\n"
            "- SVG preview: `/tmp/utility-interlock.svg`\n"
        ),
    },
]
artifact_followups = (
    "Sync the SVG output as well.",
    "Update the preview to use the same label.",
    "Make the editable source match also.",
)
for index, query in enumerate(artifact_followups, start=1):
    messages = [*artifact_history, {"role": "user", "text": query}]
    relationship = server.turn_context_relationship(messages)
    route, frame, _, _, scoped = route_summary(messages)
    check(
        f"elliptical-artifact-revision-{index}-keeps-recent-context",
        relationship.get("contextRelation") == "follow-up"
        and relationship.get("contextScope") == "recent-thread"
        and frame.get("contextRelation") == "follow-up"
        and len(scoped) == len(messages),
        {
            "query": query,
            "relationship": relationship,
            "frameRelation": frame.get("contextRelation"),
            "workerCount": len(scoped),
        },
    )
    check(
        f"elliptical-artifact-revision-{index}-keeps-diagram-owner",
        route.get("projectId") == "engineering-diagrams"
        and "generated-artifact-revision" in (route.get("matched") or []),
        {
            "query": query,
            "projectId": route.get("projectId"),
            "matched": route.get("matched"),
        },
    )

self_contained_artifact_messages = [
    *engineering_prefix,
    {
        "role": "user",
        "text": "Update an SVG preview to 1200 pixels wide for a new weather dashboard.",
    },
]
self_contained_artifact_relation = server.turn_context_relationship(
    self_contained_artifact_messages
)
_, self_contained_artifact_frame, _, _, self_contained_artifact_scoped = (
    route_summary(self_contained_artifact_messages)
)
check(
    "self-contained-artifact-request-without-ellipsis-is-new-topic",
    self_contained_artifact_relation.get("contextRelation") == "new-topic"
    and self_contained_artifact_relation.get("contextScope") == "latest-turn"
    and self_contained_artifact_frame.get("contextRelation") == "new-topic"
    and len(self_contained_artifact_scoped) == 1,
    {
        "relationship": self_contained_artifact_relation,
        "frameRelation": self_contained_artifact_frame.get("contextRelation"),
        "workerCount": len(self_contained_artifact_scoped),
    },
)

application_query = "Can this application report its current access level?"
application_messages = [
    *engineering_prefix,
    {"role": "user", "text": application_query},
]
application_relation = server.turn_context_relationship(application_messages)
_, application_frame, _, application_plan, application_scoped = route_summary(
    application_messages
)
check(
    "application-synonym-uses-the-same-current-surface-contract",
    application_relation.get("contextRelation") == "new-topic"
    and application_frame.get("domain")
    in {"agent_runtime_capabilities", "bounded_specialist_capability"}
    and (
        application_plan.get("handler_key") == "runtime_capability_introspection"
        or application_frame.get("specialistOwner") == "access-status"
    )
    and application_plan.get("executor") == "deterministic"
    and len(application_scoped) == 1,
    {
        "relationship": application_relation,
        "domain": application_frame.get("domain"),
        "handler": application_plan.get("handler_key"),
    },
)


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
kernel_source = (ROOT / "intelligence_kernel.py").read_text(encoding="utf-8")
route_start = server_source.index("def route_manager(")
route_end = server_source.index("\ndef format_manager_context", route_start)
route_source = server_source[route_start:route_end]
check(
    "route-scope-is-computed-before-intent-selection",
    route_source.index("context_relationship = turn_context_relationship(messages)")
    < route_source.index("legacy_intent_frame = build_intent_frame(messages")
    and route_source.index("messages = scope_messages_for_intent(")
    < route_source.index("legacy_intent_frame = build_intent_frame(messages")
    and "intent_frame = {**intent_frame, **context_relationship}" in route_source,
    "new-topic scope and authoritative relationship binding precede route ownership",
)
check(
    "current-surface-recognition-is-shared-not-query-specific",
    "_CONTEXT_SELF_CONTAINED_ACTIVE_SURFACE_RE" in kernel_source
    and "this (?:app|application)" in kernel_source
    and "p243-frontier-audit" not in kernel_source,
    "shared app/application/workspace/repository/conversation/session surface contract",
)


export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "p243-package-and-export-registration",
    server_source.count(
        '("server:user-facing-frontier-context-p243", "p243_user_facing_frontier_audit_smoke.py"'
    )
    == 1
    and server_source.count(
        'add(\n            "server:user-facing-frontier-context-p243"'
    )
    == 1
    and server_source.count(
        'add("server:user-facing-frontier-context-p243", "fail"'
    )
    == 1
    and export_source.count(
        '"tools/p243_user_facing_frontier_audit_smoke.py"'
    )
    == 1,
    "one package spec/result/failure row and one export allowlist entry",
)


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "suite": "p243-user-facing-frontier-context",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failures": failed,
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
