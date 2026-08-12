#!/usr/bin/env python3
"""P218 software/data architecture judgment and follow-up continuity."""

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


prompt = (
    "For a local machine-telemetry system ingesting ten 3D printers at one "
    "sample per second, compare SQLite in WAL mode with PostgreSQL. It will "
    "run on one Mac, there are no remote writers, I need 30 days of history "
    "and simple backups. Which should I choose, why, and what would reverse "
    "your recommendation?"
)
messages = [{"role": "user", "text": prompt}]
route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
frame = route.get("intentFrame") or {}
options = [
    item.get("name")
    for item in frame.get("objectRefs") or []
    if isinstance(item, dict) and item.get("type") == "comparison-option"
]

check(
    "database-architecture-owns-typed-software-data-domain",
    frame.get("domain") == "engineering_advisory"
    and frame.get("advisoryDomain") == "software_data_systems"
    and frame.get("targetSurface")
    == "knowledge.software_data.architecture_decision",
    frame,
)
check(
    "database-comparison-retains-both-options-and-decision-semantics",
    any("sqlite" in str(item).lower() for item in options)
    and any("postgres" in str(item).lower() for item in options)
    and frame.get("comparisonSpeechAct") in {"decision", "recommendation"}
    and isinstance(frame.get("comparisonCriteria"), list),
    {
        "options": options,
        "speechAct": frame.get("comparisonSpeechAct"),
        "criteria": frame.get("comparisonCriteria"),
    },
)

context = server.build_engineering_advisory_context(messages, route)
check(
    "author-contract-uses-real-database-decision-boundaries",
    all(
        phrase in context
        for phrase in (
            "one writer at a time",
            "both provide transactional ACID behavior",
            "online backup API",
            "backup-and-restore drill",
            "Row count alone does not choose",
        )
    ),
    context,
)

bad_answer = (
    "Go with SQLite because its single-process design is simpler. Unlike "
    "SQLite, PostgreSQL provides strict ACID behavior and concurrent "
    "transaction isolation. WAL guarantees durability after a power failure, "
    "and backups should copy the main database and WAL together. If writers "
    "grow, switch to PostgreSQL. Run a test and measure query latency."
)
bad_issues = server.deterministic_coupled_architecture_issues(
    messages, route, bad_answer
)
bad_kinds = {item.get("kind") for item in bad_issues}
check(
    "plausible-database-misconceptions-fail-closed",
    {
        "sqlite-process-model-misstated",
        "database-acid-boundary-misstated",
        "sqlite-backup-method-unsafe",
        "sqlite-wal-durability-overclaimed",
        "sqlite-one-writer-boundary-missing",
        "software-data-backup-restore-incomplete",
    }.issubset(bad_kinds),
    bad_issues,
)

good_answer = (
    "Go with SQLite in WAL mode for this version. Ten samples per second is "
    "a modest ingest rate, and 30 days is about 25.9 million sample rows; "
    "neither figure alone requires a database server. SQLite also matches the "
    "one-Mac, no-remote-writer operating model. WAL permits concurrent readers, "
    "but SQLite still allows only one active writer, which is acceptable while "
    "one collector owns ingestion. Both choices provide transactional ACID "
    "behavior, so that is not the differentiator.\n\n"
    "Use SQLite's online backup API or VACUUM INTO and perform a real restore "
    "drill. Before committing, test a representative ingest and dashboard "
    "query workload and measure write latency, query latency, database "
    "growth, and restore time. That test exposes lock contention or a recovery "
    "failure without adding a server prematurely.\n\n"
    "I would switch to PostgreSQL if independent or remote writers must write "
    "concurrently, automatic failover or replication becomes required, or "
    "server-managed users and access control become part of the design. Those "
    "requirements reverse the operational tradeoff; row count by itself does not."
)
good_issues = server.deterministic_coupled_architecture_issues(
    messages, route, good_answer
)
check(
    "accurate-concise-recommendation-passes-deterministic-architecture-gate",
    not good_issues,
    good_issues,
)

recovered_answer = server.software_data_architecture_recovery_answer(
    messages, route
)
recovered_validation = server.engineering_single_pass_repair_validation(
    messages, route, recovered_answer
)
check(
    "typed-database-recovery-is-human-complete-and-gate-clean",
    recovered_validation.get("ok")
    and recovered_validation.get("taskStatus") == "pass"
    and "Go with SQLite" in recovered_answer
    and "one active writer" in recovered_answer
    and "restore drill" in recovered_answer,
    {"answer": recovered_answer, "validation": recovered_validation},
)


def unexpected_model_call(*_args, **_kwargs):
    raise AssertionError("typed recovery should avoid a second model call")


recovered_audit = server.run_engineering_reasoning_audit(
    messages,
    route,
    bad_answer,
    generate_fn=unexpected_model_call,
)
check(
    "incomplete-primary-recovers-without-slow-review-chain",
    recovered_audit.get("ok")
    and recovered_audit.get("model")
    == "deterministic-software-data-architecture-recovery"
    and recovered_audit.get("modelReviewSkipped") is True
    and "Go with SQLite" in recovered_audit.get("finalAnswer", ""),
    recovered_audit,
)

followup_messages = [
    *messages,
    {"role": "assistant", "text": good_answer},
    {
        "role": "user",
        "text": (
            "Now assume two other workstations must write concurrently and we "
            "need automatic failover. Does your recommendation change?"
        ),
    },
]
followup_route = server.route_manager(
    followup_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
followup_frame = followup_route.get("intentFrame") or {}
followup_options = [
    item.get("name")
    for item in followup_frame.get("objectRefs") or []
    if isinstance(item, dict) and item.get("type") == "comparison-option"
]
check(
    "concurrent-writer-word-does-not-falsely-trigger-current-web-research",
    not server.wants_web_context(followup_messages)
    and server.bounded_ordinary_engineering_decision_review(
        followup_messages, followup_route
    )
    and server.wants_web_context(
        [{"role": "user", "text": "Find the current PostgreSQL release on the web."}]
    ),
    {
        "followupWantsWeb": server.wants_web_context(followup_messages),
        "boundedReview": server.bounded_ordinary_engineering_decision_review(
            followup_messages, followup_route
        ),
    },
)
check(
    "followup-preserves-database-options-and-software-data-ownership",
    followup_frame.get("advisoryDomain") == "software_data_systems"
    and any("sqlite" in str(item).lower() for item in followup_options)
    and any("postgres" in str(item).lower() for item in followup_options)
    and followup_frame.get("comparisonSpeechAct")
    in {"decision", "recommendation"},
    followup_frame,
)
check(
    "followup-constraint-is-retained-as-recommendation-reversal",
    "follow-up" == followup_frame.get("contextRelation")
    or "follow-up-continuity" in (followup_frame.get("frameTags") or []),
    followup_frame,
)

followup_recovery = server.software_data_architecture_recovery_answer(
    followup_messages, followup_route
)
followup_validation = server.engineering_single_pass_repair_validation(
    followup_messages, followup_route, followup_recovery
)
check(
    "concurrent-writer-failover-followup-reverses-the-choice-cleanly",
    followup_validation.get("ok")
    and followup_validation.get("taskStatus") == "pass"
    and "I would use PostgreSQL" in followup_recovery
    and "one active writer" in followup_recovery
    and "failover drill" in followup_recovery,
    {"answer": followup_recovery, "validation": followup_validation},
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
