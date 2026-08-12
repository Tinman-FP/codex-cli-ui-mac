#!/usr/bin/env python3
"""Focused P190 presentation-neutral golden/answer contract."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import harvest_history_golden_tests as harvest  # noqa: E402
import server  # noqa: E402
from golden_test_contract import (  # noqa: E402
    golden_test_presentation_inventory,
    normalize_golden_test_presentation,
    semantic_answer_coverage,
    semantic_required_terms,
)
from tools.p190_migrate_golden_presentation import migrate  # noqa: E402


checks = []


def add(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)[:500]})


positive = normalize_golden_test_presentation(
    {
        "id": "positive",
        "directAnswer": True,
        "requiredTerms": ["This is why:", "bearing load"],
        "directTerms": ["You should also consider:", "Use the larger bearing"],
        "anyTerms": ["This is why", "fatigue"],
        "forbiddenTerms": ["This is why:", "You should also consider:"],
    },
    enforce_direct_answer_coverage=True,
)
add(
    "positive-fields-filter-exact-presentation-only",
    positive["requiredTerms"] == ["bearing load"]
    and positive["directTerms"] == ["use the larger bearing"]
    and positive["anyTerms"] == ["fatigue"]
    and positive["forbiddenTerms"] == ["This is why:", "You should also consider:"],
    positive,
)
add(
    "semantic-answer-coverage-is-visible-answer-only",
    semantic_answer_coverage(positive)["answerCovered"]
    and not semantic_answer_coverage(positive)["contractCovered"]
    and positive["directAnswer"] is True
    and positive["semanticCoverage"]["status"] == "semantic-answer",
    positive.get("semanticCoverage"),
)

contract_only = normalize_golden_test_presentation(
    {
        "id": "contract-only",
        "directAnswer": True,
        "requiredTerms": ["This is why", "You should also consider"],
        "requiredContractProof": ["verified source receipt"],
    },
    legacy=True,
    enforce_direct_answer_coverage=True,
)
add(
    "contract-only-does-not-claim-answer-substance",
    contract_only["semanticCoverage"]["status"] == "contract-only"
    and contract_only["directAnswer"] is False
    and semantic_answer_coverage(contract_only)["contractCovered"]
    and not semantic_answer_coverage(contract_only)["answerCovered"],
    contract_only,
)

route_only = normalize_golden_test_presentation(
    {
        "id": "route-only",
        "directAnswer": True,
        "requiredTerms": ["This is why", "You should also consider"],
        "expectedProjectId": "general",
    },
    legacy=True,
    enforce_direct_answer_coverage=True,
)
add(
    "route-only-legacy-is-explicit-and-demoted",
    route_only["semanticCoverage"]["status"] == "route-only-legacy"
    and route_only["directAnswer"] is False
    and route_only.get("legacyDirectAnswerClaim") is True,
    route_only,
)

six_terms = harvest.normalize_required_terms(
    ["This is why", "You should also consider", "one", "two", "three", "four", "five", "six"],
    limit=6,
)
add("required-term-limit-keeps-six-semantic-slots", six_terms == ["one", "two", "three", "four", "five", "six"], six_terms)

event = json.loads((APP_DIR / "data" / "golden_test_migrations" / "p190-natural-presentation.json").read_text())
event_row = event.get("event") or {}
add(
    "immutable-migration-event-preserves-original-evidence",
    event.get("immutableEvent") is True
    and event_row.get("presentationBoundCount") == 900
    and event_row.get("presentationTermCount") == 1799
    and event_row.get("presentationTermCountByField") == {"requiredTerms": 1791, "directTerms": 8, "anyTerms": 0}
    and event_row.get("semanticAnswerCount") == 575
    and event_row.get("contractOnlyCount") == 187
    and event_row.get("routeOnlyLegacyCount") == 138
    and event_row.get("directAnswerClaimsDemoted") == 310
    and event_row.get("backfilledCount") == 0,
    event_row,
)

verification = json.loads((APP_DIR / "data" / "golden_test_migrations" / "p190-natural-presentation-latest-verification.json").read_text())
add(
    "latest-persisted-verification-is-clean-and-honest",
    verification.get("status") == "pass"
    and verification.get("testCount") == 1891
    and verification.get("presentationBoundCount") == 0
    and verification.get("uncoveredDirectAnswerClaimIds") == []
    and verification.get("directAnswerClaimsDemotedTotal") == 344,
    verification,
)

report = server.golden_test_presentation_contract_report()
add("raw-effective-corpus-parity", report.get("ok") is True, report)
add("improvement-generator-cannot-create-presentation-proof", server.golden_test_generator_synthetic_check())
add(
    "sample-producers-are-presentation-neutral-route-guards",
    server.domain_sample_golden_tests_synthetic_check() and server.fusion_orca_sample_golden_tests_synthetic_check(),
)

comparison_messages = [{"role": "user", "text": "Which queue is better here, SQLite or an in-memory queue?"}]
comparison_route = server.route_manager(comparison_messages, requested_profile="manager", web_search="disabled")
comparison_profile = server.adaptive_answer_composition_profile(comparison_messages, comparison_route)
comparison_director = server.interaction_director_policy(comparison_messages, comparison_route)
research_messages = [{"role": "user", "text": "Research current 2 TB NVMe prices and cite the exact listings."}]
research_route = server.route_manager(research_messages, requested_profile="manager", web_search="disabled")
research_director = server.interaction_director_policy(research_messages, research_route)
research_decoys = [
    [{"role": "user", "text": "What does research mean?"}],
    [{"role": "user", "text": "Summarize this old research paper."}],
    [{"role": "user", "text": "Compare SQLite and an in-memory queue for durable work."}],
]
research_decoy_domains = [
    server.route_manager(messages, requested_profile="manager", web_search="disabled")
    .get("intentFrame", {})
    .get("domain")
    for messages in research_decoys
]
current_price_prompts = (
    "How much does a 2 TB NVMe SSD cost today?",
    "What's the current price of a 2 TB NVMe SSD?",
    "What does a Bambu H2D cost today?",
    "What's a 2 TB NVMe SSD going for right now?",
    "What should I expect to pay for a 2 TB NVMe SSD today?",
    "How much are 2 TB NVMe SSDs right now?",
)
current_price_routes = [
    server.route_manager(
        [{"role": "user", "text": prompt}],
        requested_profile="manager",
        web_search="disabled",
    )
    for prompt in current_price_prompts
]
current_price_decoys = (
    "What is the current draw of this 11 kW motor at 48 V?",
    "What is the current cost of this algorithm?",
    "How much does this function cost to run today?",
    "What is the computational cost of this sorting algorithm?",
    "When will the current Codex CLI UI project be finished?",
)
current_price_decoy_domains = [
    server.route_manager(
        [{"role": "user", "text": prompt}],
        requested_profile="manager",
        web_search="disabled",
    )
    .get("intentFrame", {})
    .get("domain")
    for prompt in current_price_decoys
]
add(
    "natural-presentation-does-not-flatten-interaction-modes",
    comparison_profile.get("forceLabeledSections") is False
    and comparison_profile.get("visibleLabelPolicy") == "no-fixed-reason-or-caveat-labels"
    and research_route.get("intentFrame", {}).get("domain") == "current_market_research"
    and research_route.get("intentFrame", {}).get("evidenceNeed") == "current-web-evidence"
    and not server.plan_allows_legacy_fallback(
        research_route.get("capabilityPlan"),
        research_route.get("kernelDecision"),
    )
    and all(domain != "current_market_research" for domain in research_decoy_domains)
    and comparison_director.get("mode") != research_director.get("mode"),
    {
        "comparison": comparison_director.get("mode"),
        "research": research_director.get("mode"),
        "domain": research_route.get("intentFrame", {}).get("domain"),
        "evidenceNeed": research_route.get("intentFrame", {}).get("evidenceNeed"),
        "decoyDomains": research_decoy_domains,
    },
)
add(
    "current-commerce-price-questions-require-evidence-with-technical-decoys",
    all(
        route.get("intentFrame", {}).get("domain") == "current_market_research"
        and route.get("intentFrame", {}).get("evidenceNeed") == "current-web-evidence"
        and server.interaction_director_policy(
            [{"role": "user", "text": prompt}], route
        ).get("mode")
        == "research"
        for prompt, route in zip(current_price_prompts, current_price_routes)
    )
    and all(domain != "current_market_research" for domain in current_price_decoy_domains),
    {
        "positiveDomains": [route.get("intentFrame", {}).get("domain") for route in current_price_routes],
        "decoyDomains": current_price_decoy_domains,
    },
)
market_followup_messages = [
    {"role": "user", "text": "Research current 2 TB NVMe prices and cite the exact listings."},
    {"role": "assistant", "text": "I found current exact 2 TB candidates and cited their listing evidence."},
    {"role": "user", "text": "What about 4 TB models?"},
]
market_followup_route = server.route_manager(
    market_followup_messages,
    requested_profile="manager",
    web_search="disabled",
)
market_followup_control = server.route_manager(
    [
        *market_followup_messages[:-1],
        {"role": "user", "text": "How does SQLite durability work?"},
    ],
    requested_profile="manager",
    web_search="disabled",
)
add(
    "current-market-followup-retains-evidence-owner-but-new-topic-leaves",
    market_followup_route.get("intentFrame", {}).get("domain") == "current_market_research"
    and market_followup_route.get("intentFrame", {}).get("contextRelation") == "follow-up"
    and market_followup_route.get("intentFrame", {}).get("evidenceNeed") == "current-web-evidence"
    and market_followup_route.get("capabilityPlan", {}).get("id") == "current-web-research"
    and market_followup_control.get("intentFrame", {}).get("domain") != "current_market_research",
    {
        "followup": market_followup_route.get("intentFrame"),
        "controlDomain": market_followup_control.get("intentFrame", {}).get("domain"),
    },
)

natural = (
    "SQLite is the safer default for this workload.\n\n"
    "It persists queued work across a process restart, so recovery does not depend on memory surviving.\n\n"
    "Use the in-memory queue only if losing queued work is acceptable or another durable system already owns replay."
)
thin = "Use SQLite."
canned = "Use SQLite.\n\nThis is why: It is better.\n\nYou should also consider: Real-world fit."
natural_evidence_boundary = (
    "The supplied operating point narrows the choice, but it does not yet prove which option can sustain the complete workload.\n\n"
    "The unresolved gate is whether all streams run concurrently. Verify that workload before choosing the platform."
)
natural_mechanism_boundary = (
    "The controlling limit is the weakest part of the assembled stack. Interfaces must accommodate differential expansion, "
    "and retention layers must resist creep or softening.\n\n"
    "If those conditions are not met, expect dimensional drift. Thermal-cycle the complete assembly and measure flatness."
)
natural_negative_evidence_boundary = (
    "The datasheet is not enough to approve the option because it does not establish hot flatness under the stated cycle.\n\n"
    "Until both options clear every named outcome, neither is a defensible winner."
)
natural_sufficiency_boundary = (
    "That wall is stiff enough for the stated load without making the part bulky.\n\n"
    "Use the thinner section only for short protected spans."
)
natural_coverage_boundary = (
    "The app has static and browser smoke coverage for visible controls and focusable logs.\n\n"
    "A real assistive-technology walkthrough is still required before PASS."
)
natural_accountability_boundary = (
    "Local code and liability questions need someone accountable to the jurisdiction and facts, not just a general assistant answer.\n\n"
    "When the outcome could affect rights or safety, use qualified review."
)
natural_comparative_boundary = (
    "ASA has better UV and heat resistance than PETG for this outdoor part.\n\n"
    "Use it only if the printer can hold the required enclosure temperature."
)
thin_feature_claim = "Choose option A.\n\nIt has features."
thin_generic_boundary = "This depends.\n\nVerify it."
thin_generic_paragraphs = "Option A is a possible choice for this task.\n\nOption B is another possible choice for this task."
add(
    "semantic-depth-accepts-natural-and-rejects-thin-canned",
    server.direct_answer_has_reason_and_boundary(natural)
    and server.direct_answer_has_reason_and_boundary(natural_evidence_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_mechanism_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_negative_evidence_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_sufficiency_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_coverage_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_accountability_boundary)
    and server.direct_answer_has_reason_and_boundary(natural_comparative_boundary)
    and not server.direct_answer_has_reason_and_boundary(thin)
    and not server.direct_answer_has_reason_and_boundary(canned)
    and not server.direct_answer_has_reason_and_boundary(thin_feature_claim)
    and not server.direct_answer_has_reason_and_boundary(thin_generic_boundary)
    and not server.direct_answer_has_reason_and_boundary(thin_generic_paragraphs),
)

normalized = server.normalize_direct_answer_shape(
    comparison_messages,
    comparison_route,
    "Use SQLite.\n\nThis is why: It survives restarts.\n\nYou should also consider: Verify the write rate before committing.",
)
thin_normalized = server.normalize_direct_answer_shape(comparison_messages, comparison_route, thin)
inline_normalized = server.normalize_direct_answer_shape(
    comparison_messages,
    comparison_route,
    "Use SQLite. Why: it survives restarts. Caveats: verify the write rate before committing.",
)
add(
    "normalizer-removes-wrapper-without-manufacturing-substance",
    "This is why:" not in normalized
    and "You should also consider:" not in normalized
    and "survives restarts" in normalized
    and "Why:" not in inline_normalized
    and "Caveats:" not in inline_normalized
    and "survives restarts" in inline_normalized
    and "verify the write rate" in inline_normalized.lower()
    and thin_normalized == thin,
    {"normalized": normalized, "inline": inline_normalized, "thin": thin_normalized},
)

simple_messages = [{"role": "user", "text": "What is 2 + 2? Answer in one short sentence."}]
status_messages = [{"role": "user", "text": "How is the UI coming?"}]
simple_route = server.route_manager(simple_messages, requested_profile="manager", web_search="disabled")
status_route = server.route_manager(status_messages, requested_profile="manager", web_search="disabled")
add(
    "semantic-depth-is-required-only-when-earned",
    not server.answer_requires_reason_and_boundary(simple_messages, simple_route)
    and not server.answer_requires_reason_and_boundary(status_messages, status_route)
    and server.answer_requires_reason_and_boundary(comparison_messages, comparison_route, "Expert comparison"),
)

legacy_fixture = {
    "version": 1,
    "tests": [
        {"id": "a", "directAnswer": True, "requiredTerms": ["This is why", "fact"]},
        {"id": "b", "directAnswer": True, "requiredTerms": ["This is why"], "requiredContractProof": ["receipt"]},
    ],
}
first_output, first_receipt = migrate(legacy_fixture)
second_output, second_receipt = migrate(first_output)
add(
    "in-memory-two-pass-migration-is-stable",
    first_output["tests"] == second_output["tests"]
    and first_receipt["directAnswerClaimsDemoted"] == 1
    and second_receipt["directAnswerClaimsDemoted"] == 0
    and sum(bool(row.get("legacyDirectAnswerClaim")) for row in second_output["tests"]) == 1,
    {"first": first_receipt["directAnswerClaimsDemoted"], "second": second_receipt["directAnswerClaimsDemoted"]},
)

failed = [check for check in checks if not check["passed"]]
result = {"status": "pass" if not failed else "fail", "total": len(checks), "passed": len(checks) - len(failed), "failed": len(failed), "checks": checks}
print(json.dumps(result, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
