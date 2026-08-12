#!/usr/bin/env python3
"""P223 regressions for full-object referent resolution and ambiguity controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


def route_for(messages):
    return server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )


def unresolved(query, prior=None):
    messages = [*(prior or []), {"role": "user", "text": query}]
    route = route_for(messages)
    return server.material_unresolved_referent(messages, route), route, messages


p222_prompt = (
    "Before I trust the current Codex CLI UI build, verify the package-health "
    "and live-feedback receipts and tell me exactly what is still failing."
)
p222_unresolved, p222_route, p222_messages = unresolved(p222_prompt)
p222_frame = p222_route.get("intentFrame") or {}
check(
    "qualified-codex-cli-ui-build-does-not-truncate-to-current-codex",
    p222_unresolved == ""
    and not server.unresolved_referent_preflight_response(p222_messages, p222_route)
    and p222_route.get("projectId") == "codex-cli-ui-local-agent",
    {
        "unresolved": p222_unresolved,
        "projectId": p222_route.get("projectId"),
        "domain": p222_frame.get("domain"),
    },
)
check(
    "qualified-object-preserves-verification-intent-and-objective",
    p222_frame.get("actionType") == "summarize_local_verification_receipt_status"
    and p222_frame.get("contextRelation") == "standalone"
    and any(
        ref.get("type") == "local-verification-summary"
        for ref in p222_frame.get("objectRefs") or []
        if isinstance(ref, dict)
    )
    and (p222_route.get("objectivePlan") or {}).get("target")
    == "codex-cli-ui-local-agent",
    {
        "intentFrame": p222_frame,
        "objectivePlan": p222_route.get("objectivePlan"),
    },
)

qualified_cases = (
    "Verify the current Flight Ops Tracker build before release.",
    "Inspect the current TinManX slicer project build and summarize its state.",
    "Review the current Atlas product release for regressions.",
    "Check the current Northwind desktop application deployment.",
    "Summarize the current Warehouse Telemetry service build.",
)
qualified_results = {query: unresolved(query)[0] for query in qualified_cases}
check(
    "multiple-qualified-product-project-build-phrases-resolve",
    all(value == "" for value in qualified_results.values()),
    qualified_results,
)

compound_query = (
    "Compare the current Atlas Controller build with the current Boreal Dashboard "
    "release, then report their receipt states."
)
compound_unresolved, _, _ = unresolved(compound_query)
check(
    "multiple-qualified-identities-in-one-turn-remain-self-contained",
    compound_unresolved == "",
    compound_unresolved,
)

keyword_only_query = "The word build appears in this sentence. Inspect the current one."
keyword_unresolved, keyword_route, keyword_messages = unresolved(keyword_only_query)
check(
    "unrelated-build-keyword-cannot-bypass-bare-current-one-guard",
    keyword_unresolved == "the current one"
    and server.unresolved_referent_preflight_response(
        keyword_messages, keyword_route
    ).get("handled")
    is True,
    keyword_unresolved,
)

adjective_only_query = "Inspect the current fast stable build."
adjective_unresolved, _, _ = unresolved(adjective_only_query)
check(
    "object-head-with-only-generic-adjectives-is-not-a-named-identity",
    bool(adjective_unresolved),
    adjective_unresolved,
)

generic_current_results = {
    query: unresolved(query)[0]
    for query in (
        "Inspect the current Codex.",
        "Inspect the current product.",
        "Inspect the current setup.",
    )
}
check(
    "generic-current-nouns-still-fail-closed",
    all(value for value in generic_current_results.values()),
    generic_current_results,
)

bare_results = {
    query: unresolved(query)[0]
    for query in (
        "Inspect the current one.",
        "Inspect this.",
        "Inspect it.",
        "Review that now.",
    )
}
check(
    "contextless-bare-anaphora-still-clarify",
    bare_results
    == {
        "Inspect the current one.": "the current one",
        "Inspect this.": "this",
        "Inspect it.": "it",
        "Review that now.": "that",
    },
    bare_results,
)

qualified_demonstrative, _, _ = unresolved("Inspect this file in server.py.")
check(
    "demonstrative-with-explicit-file-object-is-not-bare",
    qualified_demonstrative == "",
    qualified_demonstrative,
)

single_target_prior = [
    {"role": "user", "text": "Inspect the Atlas Controller build."},
    {"role": "assistant", "text": "I inspected the Atlas Controller build."},
]
linked_it, linked_route, _ = unresolved("Inspect it again.", single_target_prior)
linked_current, linked_current_route, _ = unresolved(
    "Inspect the current one.", single_target_prior
)
check(
    "one-named-prior-object-resolves-followup-pronouns",
    linked_it == ""
    and linked_current == ""
    and (linked_route.get("intentFrame") or {}).get("contextRelation") == "follow-up"
    and (linked_current_route.get("intentFrame") or {}).get("contextRelation")
    == "follow-up",
    {
        "it": linked_it,
        "currentOne": linked_current,
        "itRelation": (linked_route.get("intentFrame") or {}).get("contextRelation"),
        "currentRelation": (linked_current_route.get("intentFrame") or {}).get(
            "contextRelation"
        ),
    },
)

ambiguous_prior = [
    {"role": "user", "text": "Compare Atlas and Boreal builds."},
    {"role": "assistant", "text": "Atlas passes and Boreal is stale."},
]
ambiguous_it, ambiguous_route, ambiguous_messages = unresolved(
    "Inspect it again.", ambiguous_prior
)
ambiguous_preflight = server.unresolved_referent_preflight_response(
    ambiguous_messages, ambiguous_route
)
check(
    "two-prior-objects-do-not-create-false-followup-resolution",
    ambiguous_it == "it"
    and ambiguous_preflight.get("handled") is True
    and ambiguous_preflight.get("mode") == "unresolved-referent-clarification"
    and (ambiguous_route.get("_unresolvedReferentPreflight") or {}).get(
        "toolCalls"
    )
    == 0,
    {"unresolved": ambiguous_it, "preflight": ambiguous_preflight},
)

failures = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failures else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failures),
    "failed": len(failures),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failures else 1)
