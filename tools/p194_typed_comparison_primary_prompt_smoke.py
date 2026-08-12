#!/usr/bin/env python3
"""P194 typed comparison primary-prompt and reversal-boundary checks."""

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
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


prompt = (
    "Compare event sourcing and CRUD for an audit-heavy inventory service, "
    "recommend a direction, state when you would reverse it, and name the first "
    "test you would run."
)
messages = [{"role": "user", "text": prompt}]
route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
server.answer_obligation_prompt_rows(messages, route)
default_prompt = "generic prompt that should not own a registered stable comparison"
primary_prompt = server.conversation_reasoning_primary_prompt(messages, route, default_prompt)
receipt = route.get("_primaryAuthorPromptReceipt") or {}

check(
    "registered-stable-comparison-uses-bound-typed-primary-packet",
    primary_prompt != default_prompt
    and prompt in primary_prompt
    and '"options":["event sourcing","CRUD"]' in primary_prompt
    and '"criteria":["an audit-heavy inventory service"]' in primary_prompt
    and receipt.get("bindingValid") is True
    and receipt.get("requestSha256") == server.text_sha256(prompt)
    and receipt.get("ledgerSha256") == (route.get("_answerObligationLedger") or {}).get("ledgerSha256")
    and receipt.get("promptSha256") == server.text_sha256(primary_prompt)
    and receipt.get("optionCount") == 2
    and len(receipt.get("obligationIds") or []) >= 3,
    receipt,
)
check(
    "typed-primary-packet-aligns-with-human-presentation-contract",
    all(
        phrase in primary_prompt
        for phrase in (
            "two to four short natural paragraphs under 260 words",
            "Do not use headings, tables, bullets, numbered lists, bold labels",
            "state it before the reversal condition with a direct 'I recommend' sentence",
            "end with exactly one first validation test",
            "I would reverse this recommendation if",
            "merely saying to assess, review, or clarify the requirements is not a test",
            "My first test would",
        )
    ),
    primary_prompt[:700],
)
check(
    "stable-comparison-keeps-a-fast-visible-author-and-diverse-handoff",
    server.conversation_reasoning_primary_model(messages, route, "local-coder")
    == server.LOCAL_CODER_MODEL
    and server.LOCAL_CODER_MODEL != server.LOCAL_RESEARCH_MODEL,
    server.conversation_reasoning_primary_model(messages, route, "local-coder"),
)

ordinary_messages = [{"role": "user", "text": "Why does the sky appear blue?"}]
ordinary_route = server.route_manager(
    ordinary_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "unrelated-reasoning-keeps-its-existing-primary-prompt",
    server.conversation_reasoning_primary_prompt(
        ordinary_messages,
        ordinary_route,
        default_prompt,
    )
    == default_prompt
    and not ordinary_route.get("_primaryAuthorPromptReceipt"),
    ordinary_route.get("_primaryAuthorPromptReceipt"),
)

positive_reversals = (
    "When to reverse it: if the audit requirement can be met by a conventional log and operational simplicity dominates, choose CRUD.",
    "What could reverse the eventual choice is the same evidence: if CRUD passes the reconstruction test with lower operating risk, choose it.",
    "I would reverse this choice if event-log operations become the larger risk and a conventional audit log passes the same reconstruction checks.",
    "I would switch from event sourcing to CRUD if a conventional audit log passes the reconstruction test and projection operations remain the larger risk.",
    "If the audit only requires current-state accountability and a conventional history table passes the same checks, I would reverse the choice.",
    "The recommendation changes when the required audit can be proven without event replay and the team cannot support projections reliably.",
)
negative_reversals = (
    "You asked when to reverse it.",
    "The choice might reverse someday.",
    "There are conditions under which the recommendation could change.",
    "I would reconsider the decision if needed.",
)
check(
    "natural-conditional-reversal-language-is-recognized",
    all(server.answer_has_reversal_condition(item) for item in positive_reversals),
    [server.answer_has_reversal_condition(item) for item in positive_reversals],
)
check(
    "restatement-or-empty-reversal-language-does-not-pass",
    not any(server.answer_has_reversal_condition(item) for item in negative_reversals),
    [server.answer_has_reversal_condition(item) for item in negative_reversals],
)

incomplete_candidate = (
    "I would choose event sourcing for this audit-heavy inventory service because it preserves each change as durable history. "
    "CRUD is simpler for current-state reads but requires a separately enforced audit path. "
    "I would switch to CRUD if that conventional history path passes the same reconstruction checks. "
    "To validate the recommendation, assess the service requirements."
)
check(
    "generic-low-risk-triage-cannot-promote-an-incomplete-stable-comparison",
    server.stable_expert_comparison_candidate_gate(
        messages, route, incomplete_candidate
    ).get("accepted")
    is False
    and server.low_risk_generic_reasoning_triage_eligible(
        messages,
        route,
        incomplete_candidate,
        deterministic_issues=[],
    )
    is False,
    server.stable_expert_comparison_candidate_gate(
        messages, route, incomplete_candidate
    ),
)

late_recommendation = (
    "Event sourcing preserves the audit history while CRUD keeps current-state writes simple. "
    "I would reverse this recommendation if read latency becomes the controlling constraint. "
    "My first test would replay one correction and compare the reconstructed state. "
    "If that test is slow, I recommend CRUD."
)
late_gate = server.stable_expert_comparison_candidate_gate(
    messages, route, late_recommendation
)
check(
    "conditional-late-pick-cannot-substitute-for-the-initial-recommendation",
    late_gate.get("accepted") is False
    and late_gate.get("recommendationPresent") is True
    and late_gate.get("recommendationBeforeBoundary") is False,
    late_gate,
)

candidate = (
    "I would start with event sourcing for this audit-heavy inventory service because the append-only change history "
    "makes reconstruction part of the data model. CRUD is simpler to operate, but it needs a separately enforced "
    "history path to provide the same audit trail.\n\n"
    "I would switch from event sourcing to CRUD if a conventional audit log passes the same reconstruction and actor-trace checks "
    "while projection maintenance becomes the larger operational risk.\n\n"
    "My first test would apply one representative inventory correction to both prototypes, rebuild the resulting state, and compare "
    "the quantity, actor, timestamp, and reason against the original transaction."
)
gate = server.stable_expert_comparison_candidate_gate(messages, route, candidate)
truncated_route = dict(route)
truncated_route["_primaryGenerationReceipt"] = {"doneReason": "length"}
truncated_gate = server.stable_expert_comparison_candidate_gate(
    messages, truncated_route, candidate
)
truncated_syntax_issues = server.deterministic_engineering_reasoning_issues(
    candidate.rstrip(".") + " and compare"
)
check(
    "length-or-timeout-generation-cannot-claim-complete-comparison",
    truncated_gate.get("accepted") is False
    and truncated_gate.get("primaryGenerationComplete") is False
    and bool(truncated_syntax_issues)
    and truncated_syntax_issues[0].get("kind") == "incomplete-final-clause",
    {"gate": truncated_gate, "syntaxIssues": truncated_syntax_issues},
)
review_calls = []
audit = server.run_generic_reasoning_audit(
    messages,
    route,
    candidate,
    review_fn=lambda *_args, **_kwargs: review_calls.append(True) or {},
    triage_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("typed complete comparison should not launch triage")
    ),
)
check(
    "complete-natural-comparison-passes-without-review-fanout",
    gate.get("accepted") is True
    and gate.get("reversalPresent") is True
    and gate.get("testPresent") is True
    and not review_calls
    and audit.get("deepReviewSkipped") is True
    and audit.get("finalAnswer") == candidate,
    {"gate": gate, "auditModel": audit.get("model")},
)

long_candidate = candidate.replace(
    "CRUD is simpler to operate, but it needs a separately enforced history path to provide the same audit trail.",
    "CRUD is simpler to operate, but it needs a separately enforced history path to provide the same audit trail. "
    "Event sourcing also makes historical reconstruction a normal operation, while CRUD must keep its current-state and audit-write paths synchronized. "
    "CRUD can still support the requirement, but only if the audit write, actor identity, and current-state transaction share one enforced failure boundary.",
)
presentation = server.normalize_stable_comparison_presentation(long_candidate)
long_review_calls = []
long_audit = server.run_generic_reasoning_audit(
    messages,
    route,
    long_candidate,
    review_fn=lambda *_args, **_kwargs: long_review_calls.append(True) or {},
    triage_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("presentation-only paragraph split should not launch triage")
    ),
)
check(
    "long-natural-paragraph-is-split-without-semantic-review",
    server.tinman_etiquette_metrics(messages, route, long_candidate).get("status")
    == "review"
    and presentation.get("applied") is True
    and presentation.get("repairedLineCount") == 1
    and server.tinman_etiquette_metrics(
        messages, route, presentation.get("text")
    ).get("status")
    == "pass"
    and not long_review_calls
    and long_audit.get("deepReviewSkipped") is True
    and long_audit.get("structuralCleanupApplied") is True
    and re.sub(r"\s+", " ", long_audit.get("finalAnswer") or "")
    == re.sub(r"\s+", " ", long_candidate),
    {
        "presentation": presentation,
        "auditModel": long_audit.get("model"),
        "reviewCalls": len(long_review_calls),
    },
)

source = (ROOT / "server.py").read_text(encoding="utf-8")
check(
    "api-primary-generation-uses-and-receipts-the-typed-prompt",
    "primary_prompt = conversation_reasoning_primary_prompt(" in source
    and "grounded_representation = bool(" in source
    and "grounded_result = run_local_research(" in source
    and "else:\n                result = run_ollama_generate(\n                    primary_prompt," in source
    and '"_representationGroundingReceipt"' in source
    and '"typedAuthorPrompt": dict(route.get("_primaryAuthorPromptReceipt") or {}),' in source,
)

failed = [item for item in checks if item["status"] == "fail"]
report = {
    "status": "pass" if not failed else "fail",
    "ok": not failed,
    "total": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2, ensure_ascii=True))
raise SystemExit(1 if failed else 0)
