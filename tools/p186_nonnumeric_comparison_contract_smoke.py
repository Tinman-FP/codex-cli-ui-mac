#!/usr/bin/env python3
"""Focused P186 stable-comparison ownership, evidence, and latency regressions."""

from __future__ import annotations

import json
import re
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


def route(messages, *, web_search="disabled"):
    return server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web_search,
    )


event_request = (
    "Compare event sourcing and CRUD for an audit-heavy inventory service, "
    "recommend a direction, state when you would reverse it, and name the first "
    "test you would run."
)
event_messages = [{"role": "user", "text": event_request}]
event_route = route(event_messages)
event_frame = event_route.get("intentFrame") or {}
event_plan = event_route.get("capabilityPlan") or {}
event_refs = [
    str(item.get("name") or "").lower()
    for item in event_frame.get("objectRefs") or []
    if isinstance(item, dict) and item.get("type") == "comparison-option"
]
check(
    "stable-software-comparison-has-clean-registered-owner",
    event_frame.get("domain") == "knowledge_comparison"
    and event_plan.get("id") == "expert-comparison"
    and event_plan.get("registered") is True
    and event_plan.get("executor") == "reasoning-worker"
    and (event_route.get("kernelDecision") or {}).get("allowLegacyDirectAnswer")
    is False
    and len(event_refs) == 2
    and any("event sourcing" in item for item in event_refs)
    and any("crud" in item for item in event_refs)
    and not any(
        item in {"recommend a direction", "state", "name the first test you would run"}
        for item in event_refs
    ),
    {"frame": event_frame, "plan": event_plan},
)

event_policy = server.conversation_only_reasoning_policy(event_messages, event_route)
event_prompt = server.build_intelligence_kernel_prompt(
    event_messages, event_route, cwd=str(ROOT)
)
check(
    "stable-comparison-is-no-tool-and-project-isolated",
    event_policy.get("eligible") is True
    and event_policy.get("comparison") is True
    and event_policy.get("accessLevel") == "conversation-context"
    and "Do not inspect the working directory" in event_prompt
    and str(ROOT) not in event_prompt
    and "Working directory:" not in event_prompt,
    {"policy": event_policy, "promptExcerpt": event_prompt[:1200]},
)
check(
    "stable-comparison-task-contract-does-not-demand-web-evidence",
    server.task_contract(event_messages, event_route).get("kind")
    == "Expert comparison"
    and "source URL"
    not in server.task_contract(event_messages, event_route).get("requiredProof", []),
    server.task_contract(event_messages, event_route),
)

sqlite_messages = [
    {
        "role": "user",
        "text": (
            "For two worker processes on one machine, compare using a local SQLite "
            "job table versus an in-memory queue for task handoff. Recommend one, "
            "state what would make you reverse the choice, and name the first test."
        ),
    }
]
sqlite_route = route(sqlite_messages)
check(
    "compare-recommend-machine-lexical-overlap-is-not-live-market",
    not server.is_current_market_ranking_query_text(
        server.latest_user_text(sqlite_messages)
    )
    and (sqlite_route.get("intentFrame") or {}).get("domain")
    == "knowledge_comparison"
    and (sqlite_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and sqlite_route.get("effectiveProfile") != "local-research",
    {
        "frame": sqlite_route.get("intentFrame"),
        "plan": sqlite_route.get("capabilityPlan"),
        "profile": sqlite_route.get("effectiveProfile"),
    },
)

supplied_sqlite_messages = [
    {
        "role": "user",
        "text": (
            "For two worker processes on one machine, compare a local SQLite job "
            "table with an in-memory queue for task handoff. Recommend one using "
            "only the stated facts: work must survive a process restart, throughput "
            "is modest, and we want the simplest failure recovery. State what would "
            "change your choice."
        ),
    }
]
supplied_sqlite_route = route(supplied_sqlite_messages)
supplied_sqlite_refs = [
    str(item.get("name") or "").lower()
    for item in (supplied_sqlite_route.get("intentFrame") or {}).get("objectRefs") or []
    if isinstance(item, dict) and item.get("type") == "comparison-option"
]
check(
    "failure-and-throughput-terms-do-not-steal-supplied-facts-comparison",
    (supplied_sqlite_route.get("intentFrame") or {}).get("domain")
    == "knowledge_comparison"
    and (supplied_sqlite_route.get("intentFrame") or {}).get("actionType")
    == "compare_decision_factors"
    and (supplied_sqlite_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and len(supplied_sqlite_refs) == 2
    and any("sqlite" in item for item in supplied_sqlite_refs)
    and any("in-memory queue" in item for item in supplied_sqlite_refs)
    and server.conversation_only_reasoning_policy(
        supplied_sqlite_messages, supplied_sqlite_route
    ).get("eligible")
    is True,
    {
        "frame": supplied_sqlite_route.get("intentFrame"),
        "plan": supplied_sqlite_route.get("capabilityPlan"),
    },
)

controls_messages = [
    {
        "role": "user",
        "text": (
            "Compare feedback correction with a feedforward trim for a conveyor speed "
            "controller when load changes repeat predictably. Recommend the default "
            "control architecture and state the measurement that could reverse it."
        ),
    }
]
controls_route = route(controls_messages)
check(
    "controls-system-best-architecture-terms-stay-offline",
    (controls_route.get("intentFrame") or {}).get("domain")
    in {"engineering_advisory", "engineering_tradeoff", "knowledge_comparison"}
    and (controls_route.get("intentFrame") or {}).get("evidenceNeed")
    not in {"current-web-evidence", "current-marketplace-item-evidence"}
    and server.conversation_only_reasoning_policy(
        controls_messages, controls_route
    ).get("eligible")
    is True,
    {"frame": controls_route.get("intentFrame"), "plan": controls_route.get("capabilityPlan")},
)

supplied_messages = [
    {
        "role": "user",
        "text": (
            "Alder takes 3 engineer-days and removes a recurring manual approval; "
            "Birch takes 1 engineer-day and reduces a weekly report from 40 minutes "
            "to 10. Compare them using only those supplied facts and recommend which "
            "to schedule first."
        ),
    }
]
supplied_route = route(supplied_messages)
check(
    "supplied-facts-decision-does-not-invent-current-evidence-mode",
    (supplied_route.get("intentFrame") or {}).get("domain")
    in {"decision_support", "knowledge_comparison"}
    and not server.wants_web_context(supplied_messages)
    and not server.is_current_market_ranking_request(supplied_messages),
    supplied_route.get("intentFrame"),
)

follow_messages = [
    *event_messages,
    {
        "role": "assistant",
        "text": (
            "I would start with CRUD plus an append-only audit log. Event sourcing "
            "would become preferable if replay and independent projections became core."
        ),
    },
    {
        "role": "user",
        "text": (
            "Change the priority to operator simplicity and tell me whether your "
            "recommendation reverses."
        ),
    },
]
follow_route = route(follow_messages)
follow_frame = follow_route.get("intentFrame") or {}
check(
    "linked-priority-followup-preserves-comparison-owner-not-evidence-mode",
    follow_frame.get("domain") == "knowledge_comparison"
    and follow_frame.get("contextRelation") == "follow-up"
    and follow_frame.get("actionType") == "reassess_comparison_with_new_priority"
    and follow_frame.get("evidenceNeed")
    == event_frame.get("evidenceNeed")
    and (follow_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and server.conversation_only_reasoning_policy(
        follow_messages, follow_route
    ).get("eligible")
    is True
    and not server.material_unresolved_referent(follow_messages, follow_route),
    {"frame": follow_frame, "plan": follow_route.get("capabilityPlan")},
)

priority_clause_messages = [
    *supplied_sqlite_messages,
    {
        "role": "assistant",
        "text": (
            "Use the local SQLite job table because restart survival is required. "
            "I would switch only if persistence stopped mattering or disk I/O became the verified bottleneck."
        ),
    },
    {
        "role": "user",
        "text": (
            "Change the priority to the lowest possible handoff latency, but keep "
            "the requirement that queued work survive a process restart. Does your "
            "recommendation reverse?"
        ),
    },
]
priority_clause_route = route(priority_clause_messages)
check(
    "explicit-priority-update-clause-does-not-trigger-referent-guard",
    (priority_clause_route.get("intentFrame") or {}).get("domain")
    == "knowledge_comparison"
    and (priority_clause_route.get("intentFrame") or {}).get("actionType")
    == "reassess_comparison_with_new_priority"
    and not server.material_unresolved_referent(
        priority_clause_messages, priority_clause_route
    )
    and not server.unresolved_referent_preflight_response(
        priority_clause_messages, priority_clause_route
    )
    and server.latency_progress_direct_answer(priority_clause_messages)
    and not server.legacy_ai_ui_intent_audit_direct_answer(
        priority_clause_messages,
        allow_legacy=server.plan_allows_legacy_fallback(
            priority_clause_route.get("capabilityPlan"),
            priority_clause_route.get("kernelDecision"),
        ),
    ),
    {
        "frame": priority_clause_route.get("intentFrame"),
        "referent": server.material_unresolved_referent(
            priority_clause_messages, priority_clause_route
        ),
    },
)

invented_measurement_answer = (
    "The recommendation does not reverse: use the local SQLite job table for task "
    "handoff because queued work still has to survive a process restart. An in-memory "
    "queue cannot meet that requirement. SQLite takes 0.2 to 0.8 ms in a local test, "
    "so it also wins on measured latency. I would switch only if restart survival no "
    "longer mattered."
)
invented_measurement_issues = server.deterministic_generic_reasoning_issues(
    invented_measurement_answer,
    messages=priority_clause_messages,
    route=priority_clause_route,
)
check(
    "supplied-facts-comparison-rejects-invented-precision-and-test-proof",
    any(
        str(item.get("kind") or "").startswith("supplied-facts-")
        for item in invented_measurement_issues
        if isinstance(item, dict)
    )
    and server.stable_expert_comparison_candidate_gate(
        priority_clause_messages,
        priority_clause_route,
        invented_measurement_answer,
    ).get("accepted")
    is False,
    invented_measurement_issues,
)

stale_market_history = [
    {
        "role": "user",
        "text": "Find the best currently available 2 TB NVMe drives under $150 this week with exact prices.",
    },
    {
        "role": "assistant",
        "text": "I need current product evidence for that shortlist.",
    },
    *sqlite_messages,
]
stale_route = route(stale_market_history)
check(
    "new-stable-comparison-does-not-inherit-stale-market-mode",
    (stale_route.get("intentFrame") or {}).get("domain")
    == "knowledge_comparison"
    and (stale_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and server.conversation_only_reasoning_policy(
        stale_market_history, stale_route
    ).get("eligible")
    is True,
    {"frame": stale_route.get("intentFrame"), "plan": stale_route.get("capabilityPlan")},
)

market_messages = [
    {
        "role": "user",
        "text": (
            "Compare the best currently available 2 TB NVMe drives under $150 this "
            "week, verify exact prices and stock, and recommend one to buy."
        ),
    }
]
market_route = route(market_messages)
check(
    "true-current-market-requires-temporal-commerce-evidence",
    server.is_current_market_ranking_query_text(
        server.latest_user_text(market_messages)
    )
    and (market_route.get("intentFrame") or {}).get("domain")
    in {"current_market_research", "current_market_ranking"}
    and (market_route.get("capabilityPlan") or {}).get("id")
    == "current-web-research"
    and server.conversation_only_reasoning_policy(
        market_messages, market_route
    ).get("eligible")
    is False,
    {"frame": market_route.get("intentFrame"), "plan": market_route.get("capabilityPlan")},
)

scoped_market_messages = [
    {
        "role": "user",
        "text": (
            "Research current listings and build a shortlist, but do not buy "
            "anything or contact sellers."
        ),
    }
]
scoped_market_route = route(scoped_market_messages, web_search="live")
scoped_market_frame = scoped_market_route.get("intentFrame") or {}
scoped_market_operations = scoped_market_frame.get("operationPlan") or {}
check(
    "current-research-hold-points-survive-ranking-admission",
    scoped_market_frame.get("domain") == "current_market_research"
    and scoped_market_operations.get("allowedNow") == ["research", "create"]
    and scoped_market_operations.get("prohibited") == ["buy", "contact"]
    and (scoped_market_route.get("capabilityPlan") or {}).get("id")
    == "current-web-research",
    {"frame": scoped_market_frame, "plan": scoped_market_route.get("capabilityPlan")},
)

specialist_contract_cases = (
    (
        "Is there a better solution on the market than a rasberry pi to use to control a 3d printer?",
        "3D printer control-stack host architecture",
    ),
    (
        "Would it be better to machine the extruder mount out of aluminum or the same thickness carbon fiber sheet for high-temperature 3D printing?",
        "Extruder mount material choice",
    ),
)
specialist_contract_results = []
for specialist_prompt, expected_kind in specialist_contract_cases:
    specialist_messages = [{"role": "user", "text": specialist_prompt}]
    specialist_route = route(specialist_messages)
    specialist_contract_results.append(
        {
            "expected": expected_kind,
            "actual": server.task_contract(specialist_messages, specialist_route).get("kind"),
            "modelFirst": (specialist_route.get("kernelDecision") or {}).get("mode"),
            "legacyAllowed": (specialist_route.get("kernelDecision") or {}).get(
                "allowLegacyDirectAnswer"
            ),
        }
    )
check(
    "declared-specialist-contract-outranks-generic-comparison-contract",
    all(
        item.get("actual") == item.get("expected")
        and item.get("modelFirst") == "model-first"
        and item.get("legacyAllowed") is False
        for item in specialist_contract_results
    ),
    specialist_contract_results,
)

explicit_web_messages = [
    {
        "role": "user",
        "text": (
            "Search the web for the latest PostgreSQL replication release notes and "
            "compare the changed failover behavior with the prior release."
        ),
    }
]
explicit_web_route = route(explicit_web_messages, web_search="live")
check(
    "explicit-web-comparison-remains-source-backed",
    (explicit_web_route.get("intentFrame") or {}).get("domain")
    in {"research_synthesis", "technical_source_lookup"}
    and (explicit_web_route.get("capabilityPlan") or {}).get("id")
    in {"current-web-research", "source-backed-reasoning"}
    and server.conversation_only_reasoning_policy(
        explicit_web_messages, explicit_web_route
    ).get("eligible")
    is False,
    {"frame": explicit_web_route.get("intentFrame"), "plan": explicit_web_route.get("capabilityPlan")},
)

named_source_messages = [
    {
        "role": "user",
        "text": (
            "Using PostgreSQL 18 official documentation as the named source, compare "
            "logical and physical replication guarantees."
        ),
    }
]
named_source_route = route(named_source_messages, web_search="live")
check(
    "named-official-documentation-stays-source-backed",
    (named_source_route.get("intentFrame") or {}).get("domain")
    == "technical_source_lookup"
    and (named_source_route.get("capabilityPlan") or {}).get("id")
    == "source-backed-reasoning"
    and server.conversation_only_reasoning_policy(
        named_source_messages, named_source_route
    ).get("eligible")
    is False,
    {"frame": named_source_route.get("intentFrame"), "plan": named_source_route.get("capabilityPlan")},
)

local_action_messages = [
    {
        "role": "user",
        "text": "Change server.py so the comparison panel shows the selected route, then run its focused test.",
    }
]
local_action_route = route(local_action_messages)
check(
    "explicit-local-artifact-action-keeps-local-owner",
    (local_action_route.get("intentFrame") or {}).get("domain")
    == "local_file_work"
    and (local_action_route.get("capabilityPlan") or {}).get("id")
    == "local-file-work"
    and server.conversation_only_reasoning_policy(
        local_action_messages, local_action_route
    ).get("eligible")
    is False,
    {"frame": local_action_route.get("intentFrame"), "plan": local_action_route.get("capabilityPlan")},
)

good_answer = (
    "I would start with CRUD plus an append-only audit log. It keeps the write path "
    "and operating model simpler while preserving the audit history this service "
    "needs. Event sourcing becomes the better choice if replay, temporal state, or "
    "independent projections become core requirements; that is the condition that "
    "would reverse my recommendation. The first test I would run is a retried "
    "inventory adjustment that proves current state and the immutable audit record "
    "cannot diverge after a failed write."
)
calibrated_good_answer = server.calibrate_stable_comparison_epistemic_overclaims(
    event_messages,
    event_route,
    good_answer,
).get("text")


def unavailable_review(*_args, **_kwargs):
    return {
        "payload": {},
        "model": server.GENERIC_REASONING_AUDIT_MODEL,
        "attemptedModels": [server.GENERIC_REASONING_AUDIT_MODEL],
        "attemptCount": 1,
        "attemptMetadata": [{"doneReason": "timeout", "bindingValid": False}],
        "durationMs": 40000,
        "attemptDurationsMs": [40000],
        "error": "bounded local review timeout",
    }


audit = server.run_generic_reasoning_audit(
    event_messages,
    event_route,
    good_answer,
    review_fn=unavailable_review,
)
check(
    "controller-proven-comparison-does-not-depend-on-unavailable-review",
    re.sub(r"\s+", " ", audit.get("finalAnswer") or "")
    == re.sub(r"\s+", " ", calibrated_good_answer or "")
    and audit.get("verdict") == "sound"
    and audit.get("deepReviewSkipped") is True
    and audit.get("controllerGateKind") == "stable-comparison-precision-cleanup"
    and audit.get("precisionCleanupMode") == "epistemic-calibration"
    and audit.get("repairApplied") is True
    and audit.get("auditUnavailableAccepted") is False
    and not audit.get("reviewAttemptCount")
    and audit.get("repairAttemptCount", 0) == 0,
    audit,
)

weak_route = route(event_messages)
weak_audit = server.run_generic_reasoning_audit(
    event_messages,
    weak_route,
    "SQLite is better.",
    review_fn=unavailable_review,
)
check(
    "unavailable-review-does-not-promote-thin-or-wrong-primary",
    not weak_audit.get("finalAnswer")
    and weak_audit.get("auditUnavailableAccepted") is not True,
    weak_audit,
)

bounded_route = route(event_messages)
bounded_final = server.apply_generic_reasoning_final_gate(
    event_messages,
    bounded_route,
    good_answer,
    audit_fn=lambda messages, route_value, answer, emit=None: server.run_generic_reasoning_audit(
        messages,
        route_value,
        answer,
        emit=emit,
        review_fn=unavailable_review,
    ),
)
check(
    "controller-proven-primary-publishes-only-with-exact-obligation-proof",
    re.sub(r"\s+", " ", bounded_final or "")
    == re.sub(r"\s+", " ", calibrated_good_answer or "")
    and bounded_route.get("_supervisionStatus") != "bounded"
    and (bounded_route.get("_answerObligationReceipt") or {}).get("status") == "pass"
    and (bounded_route.get("_genericReasoningAudit") or {}).get("deepReviewSkipped") is True
    and (bounded_route.get("_genericReasoningAudit") or {}).get("repairModel")
    == "deterministic-comparison-evidence-calibration"
    and (bounded_route.get("_genericReasoningAudit") or {}).get("reviewAttemptCount") == 0,
    {
        "status": bounded_route.get("_supervisionStatus"),
        "obligation": bounded_route.get("_answerObligationReceipt"),
        "audit": bounded_route.get("_genericReasoningAudit"),
    },
)

profile = server.generic_reasoning_audit_profile(
    event_route, messages=event_messages, draft=good_answer
)
generation_profile = server.conversation_reasoning_generation_profile(
    event_messages, event_route
)
check(
    "stable-comparison-author-and-independent-review-have-one-product-cap",
    profile.get("stableComparisonReview") is True
    and profile.get("reviewTimeout", 999) <= 40
    and profile.get("retryPrimary") is False
    and not profile.get("reviewFallbackModel")
    and profile.get("repairAttempts", 99) <= 1
    and generation_profile.get("timeout", 999) <= 50
    and generation_profile.get("allowFinalRetry") is False,
    {"review": profile, "generation": generation_profile},
)

handoff_route = route(event_messages)
server.answer_obligation_prompt_rows(event_messages, handoff_route)
handoff_calls = []


def successful_handoff(prompt, **kwargs):
    handoff_calls.append({"prompt": prompt, "kwargs": kwargs})
    return {
        "text": good_answer,
        "doneReason": "stop",
        "evalCount": 120,
        "promptEvalCount": 240,
    }


handoff = server.run_stable_comparison_primary_author_handoff(
    event_messages,
    handoff_route,
    generate_fn=successful_handoff,
)
repeated_handoff = server.run_stable_comparison_primary_author_handoff(
    event_messages,
    handoff_route,
    generate_fn=successful_handoff,
)
handoff_receipt = handoff.get("receipt") or {}
check(
    "empty-comparison-primary-gets-one-bound-local-author-handoff",
    handoff.get("text") == good_answer
    and len(handoff_calls) == 1
    and repeated_handoff.get("alreadyAttempted") is True
    and handoff_receipt.get("provider") == "ollama"
    and handoff_receipt.get("baseUrl") == "http://127.0.0.1:11434"
    and handoff_receipt.get("networkMode") == "local-loopback-only"
    and handoff_receipt.get("attemptCount") == 1
    and handoff_receipt.get("maxAttempts") == 1
    and handoff_receipt.get("bindingValid") is True
    and handoff_receipt.get("hiddenFallbackFanout") is False
    and handoff_receipt.get("candidateSha256")
    == server.text_sha256(good_answer)
    and handoff_calls[0]["kwargs"].get("allow_final_retry") is False
    and "Use no tools and no external sources" in handoff_calls[0]["prompt"],
    {"receipt": handoff_receipt, "calls": handoff_calls},
)

cancelled_route = route(event_messages)
server.answer_obligation_prompt_rows(event_messages, cancelled_route)
cancel_calls = []
original_route_cancelled = server.route_run_cancelled
try:
    server.route_run_cancelled = lambda _route: True
    cancelled_handoff = server.run_stable_comparison_primary_author_handoff(
        event_messages,
        cancelled_route,
        generate_fn=lambda *_args, **_kwargs: cancel_calls.append(True),
    )
finally:
    server.route_run_cancelled = original_route_cancelled
check(
    "comparison-author-handoff-honors-cancellation-before-model-call",
    cancelled_handoff.get("cancelled") is True
    and not cancel_calls
    and (cancelled_handoff.get("receipt") or {}).get("attemptCount") == 0,
    cancelled_handoff,
)

malformed_route = route(event_messages)
server.answer_obligation_prompt_rows(event_messages, malformed_route)
malformed_calls = []


def malformed_handoff(*_args, **_kwargs):
    malformed_calls.append(True)
    return None


malformed_result = server.run_stable_comparison_primary_author_handoff(
    event_messages,
    malformed_route,
    generate_fn=malformed_handoff,
)
check(
    "malformed-comparison-author-result-fails-closed-without-crash",
    malformed_result.get("text") == ""
    and len(malformed_calls) == 1
    and (malformed_result.get("receipt") or {}).get("outcome") == "failed"
    and "invalid result"
    in str((malformed_result.get("receipt") or {}).get("error") or "").lower(),
    malformed_result,
)

fallback_route = route(event_messages)
server.answer_obligation_prompt_rows(event_messages, fallback_route)
fallback_text = server.generic_reasoning_boundary_answer(
    {"issues": [{"reason": "bounded local author timeout"}]}
)
server.primary_draft_provenance_receipt(
    event_messages,
    fallback_route,
    fallback_text,
    kind="controller-synthesized-recovery",
    model="deterministic-reasoning-recovery",
    done_reason="timeout",
    error="bounded local author timeout",
)
review_calls = []


def forbidden_fallback_review(*_args, **_kwargs):
    review_calls.append(True)
    return {
        "ok": False,
        "verdict": "revise",
        "issues": [{"kind": "unexpected-review", "reason": "controller text was reviewed"}],
        "finalAnswer": "",
        "reviewAttemptCount": 1,
        "durationMs": 1,
    }


fallback_final = server.apply_generic_reasoning_final_gate(
    event_messages,
    fallback_route,
    fallback_text,
    audit_fn=forbidden_fallback_review,
)
check(
    "controller-known-empty-author-boundary-skips-review-and-repair",
    fallback_final == fallback_text
    and not review_calls
    and (fallback_route.get("_genericReasoningAudit") or {}).get(
        "controllerRecoveryBypass"
    )
    is True
    and fallback_route.get("_supervisionStatus") == "bounded",
    {"audit": fallback_route.get("_genericReasoningAudit"), "provenance": fallback_route.get("_primaryDraftProvenance")},
)

failed = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
