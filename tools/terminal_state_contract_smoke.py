#!/usr/bin/env python3
"""Focused adversarial regression for truthful answer terminal states."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from answer_envelope import (
    AnswerEnvelope,
    AnswerRelevanceError,
    build_source_receipt,
    build_template_ownership_receipt,
    synthetic_envelope_check,
    text_sha256,
)
from capability_execution import (
    build_semantic_completion_receipt,
    command_completion_contract,
)


def checked_web_receipt(text: str, run_id: str):
    return build_source_receipt(
        receipt_id=f"source-{run_id}",
        run_id=run_id,
        claim_text=text,
        source_type="web",
        locator="https://example.test/primary-source",
        content_sha256=text_sha256("retrieved primary-source content"),
        observed_at="2026-08-06T07:20:00Z",
    )


def relevance_draft(*, terminal: bool):
    intent = "Does model-written URL text count as checked evidence?"
    contract = {
        "kind": "answer-task-contract",
        "domains": ["evidence-provenance"],
        "mustDo": ["answer the checked-evidence boundary"],
    }
    answer = "Choose a motor controller from battery voltage and current limit."
    ownership = build_template_ownership_receipt(
        receipt_id="wrong-owner",
        run_id="relevance-run",
        template_id="controller-sizing",
        latest_user_intent=intent,
        task_contract=contract,
        owner_domain="vehicle-motion-control",
        concepts=["motor controller", "battery voltage", "current limit"],
    )
    envelope = AnswerEnvelope.from_text(
        answer,
        objective=intent,
        run_id="relevance-run",
    ).with_relevance_context(
        latest_user_intent=intent,
        intent_domain="evidence-provenance",
        task_contract=contract,
        template_ownership=ownership,
    )
    return envelope.with_terminal_context() if terminal else envelope


def main() -> int:
    partial_text = (
        "No checked source reached this run, so the current rating remains unverified."
    )
    evidence_bounded = AnswerEnvelope.from_text(
        partial_text,
        objective="Answer from checked evidence",
        run_id="evidence-open",
    ).with_terminal_context(
        evidence_requirement="grounded",
    ).finalize("complete")

    verified_text = "The checked primary source supports this bounded claim."
    verified_complete = AnswerEnvelope.from_text(
        verified_text,
        objective="Answer from checked evidence",
        run_id="evidence-verified",
    ).with_evidence(
        [checked_web_receipt(verified_text, "evidence-verified")]
    ).with_terminal_context(
        evidence_requirement="verified",
    ).finalize("complete")

    ordinary_complete = AnswerEnvelope.from_text(
        "Yes, I can help with that design.",
        objective="Answer a capability question",
        run_id="ordinary",
    ).with_terminal_context().finalize("complete")
    live_state_complete = AnswerEnvelope.from_text(
        "The supplied live-state receipt reports the printer is idle.",
        objective="Report supplied live state",
        run_id="live-state",
    ).with_terminal_context(
        evidence_requirement="none",
    ).finalize("complete")

    steering_blocked = AnswerEnvelope.from_text(
        "The earlier draft is still useful context, but it is not the final answer.",
        objective="Apply the latest steering",
        run_id="steering-pending",
    ).with_terminal_context(
        steering_receipt={
            "status": "accepted",
            "acceptedThrough": 2,
            "appliedThrough": 1,
        },
    ).finalize("complete")
    steering_complete = AnswerEnvelope.from_text(
        "The revised answer applies both steering notes.",
        objective="Apply the latest steering",
        run_id="steering-applied",
    ).with_terminal_context(
        steering_receipt={
            "status": "applied",
            "acceptedThrough": 2,
            "appliedThrough": 2,
        },
    ).finalize("complete")

    task_messages = [{"role": "user", "text": "Count the lines in input.txt."}]
    semantic_receipt = build_semantic_completion_receipt(
        task_messages,
        "Counted the requested file.",
        ["command-1"],
    )
    command_receipts = [
        {
            "id": "command-1",
            "command": "wc -l input.txt",
            "status": "pass",
            "exitCode": 0,
        }
    ]
    semantic_pass = command_completion_contract(
        command_receipts=command_receipts,
        semantic_receipt=semantic_receipt,
        latest_user_intent=task_messages[0]["text"],
        access_level="read-only-local-files",
        completed=True,
    )
    semantic_fail = command_completion_contract(
        command_receipts=command_receipts,
        semantic_receipt={},
        latest_user_intent=task_messages[0]["text"],
        access_level="read-only-local-files",
        completed=True,
    )
    semantic_complete = AnswerEnvelope.from_text(
        "input.txt has 12 lines.",
        objective=task_messages[0]["text"],
        run_id="semantic-pass",
    ).with_terminal_context(
        semantic_contract=semantic_pass,
        semantic_proof_required=True,
    ).finalize("complete")
    semantic_failed = AnswerEnvelope.from_text(
        "The command exited zero, but that alone does not prove the latest intent.",
        objective=task_messages[0]["text"],
        run_id="semantic-fail",
    ).with_terminal_context(
        semantic_contract=semantic_fail,
        semantic_proof_required=True,
    ).finalize("complete")
    semantic_missing = AnswerEnvelope.from_text(
        "No semantic receipt was supplied.",
        objective=task_messages[0]["text"],
        run_id="semantic-missing",
    ).with_terminal_context(
        semantic_proof_required=True,
    ).finalize("complete")

    relevance_blocked = relevance_draft(terminal=True).finalize("complete")
    strict_relevance_still_rejected = False
    try:
        relevance_draft(terminal=False).finalize("complete")
    except AnswerRelevanceError:
        strict_relevance_still_rejected = True

    precedence_failed = AnswerEnvelope.from_text(
        partial_text,
        objective="Complete an evidence-backed steered command task",
        run_id="precedence",
    ).with_terminal_context(
        evidence_requirement="grounded",
        steering_receipt={
            "status": "accepted",
            "acceptedThrough": 1,
            "appliedThrough": 0,
        },
        semantic_contract=semantic_fail,
        semantic_proof_required=True,
    ).finalize("complete")
    preserved_block = AnswerEnvelope.from_text(
        "The safe blocker remains useful.",
        objective="Preserve an existing blocker",
        run_id="preserved-block",
    ).with_terminal_context().finalize("blocked")

    stale_text = "The checked source supports the original answer."
    stale_evidence = AnswerEnvelope.from_text(
        stale_text,
        objective="Answer from checked evidence",
        run_id="stale-evidence",
    ).with_evidence(
        [checked_web_receipt(stale_text, "stale-evidence")]
    ).with_terminal_context(
        evidence_requirement="grounded",
    ).revise(
        "The answer changed after the source receipt was bound.",
        "post-source-rewrite",
    ).finalize("complete")
    health = synthetic_envelope_check()

    checks = {
        "requiredUncheckedEvidenceIsBounded": bool(
            evidence_bounded.status == "bounded"
            and evidence_bounded.text == partial_text
            and evidence_bounded.terminal_state.get("helpfulPartialPreserved")
            and evidence_bounded.terminal_state.get("reasonCodes")
            == ["required-evidence-not-grounded"]
        ),
        "verifiedRequiredEvidenceIsComplete": bool(
            verified_complete.status == "complete"
            and verified_complete.terminal_state.get("mayClaimComplete")
        ),
        "ordinaryAnswerRemainsComplete": ordinary_complete.status == "complete",
        "NonRequiredLiveStateRemainsComplete": live_state_complete.status == "complete",
        "unappliedSteeringIsBlocked": bool(
            steering_blocked.status == "blocked"
            and "accepted-steering-not-applied"
            in steering_blocked.terminal_state.get("reasonCodes", [])
        ),
        "fullyAppliedSteeringIsComplete": steering_complete.status == "complete",
        "matchingSemanticProofIsComplete": semantic_complete.status == "complete",
        "failedSemanticProofIsFailed": bool(
            semantic_failed.status == "failed"
            and "semantic-completion-not-proven"
            in semantic_failed.terminal_state.get("reasonCodes", [])
        ),
        "missingRequiredSemanticProofIsFailed": bool(
            semantic_missing.status == "failed"
            and "missing-semantic-completion-contract"
            in semantic_missing.terminal_state.get("reasonCodes", [])
        ),
        "replanRequiredRelevanceIsBlocked": bool(
            relevance_blocked.status == "blocked"
            and relevance_blocked.answer_relevance.get("status") == "replan"
            and "answer-relevance-replan-required"
            in relevance_blocked.terminal_state.get("reasonCodes", [])
        ),
        "strictP142RelevanceBoundaryRemains": strict_relevance_still_rejected,
        "terminalPrecedenceSelectsFailed": bool(
            precedence_failed.status == "failed"
            and set(precedence_failed.terminal_state.get("reasonCodes", []))
            == {
                "required-evidence-not-grounded",
                "accepted-steering-not-applied",
                "semantic-completion-not-proven",
            }
        ),
        "existingBlockedStateIsNeverUpgraded": preserved_block.status == "blocked",
        "staleEvidenceAfterRevisionIsBounded": bool(
            stale_evidence.status == "bounded"
            and stale_evidence.evidence_provenance.get("status") == "unverified"
        ),
        "allTerminalContentIntegrityPasses": all(
            envelope.verify_final_integrity(envelope.text)
            for envelope in (
                evidence_bounded,
                verified_complete,
                ordinary_complete,
                live_state_complete,
                steering_blocked,
                steering_complete,
                semantic_complete,
                semantic_failed,
                semantic_missing,
                relevance_blocked,
                precedence_failed,
                preserved_block,
                stale_evidence,
            )
        ),
        "packageHealthEnvelopeInvariantPasses": health.get("status") == "pass",
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "receipts": {
            "evidenceBounded": evidence_bounded.terminal_state,
            "verifiedEvidence": verified_complete.terminal_state,
            "steeringBlocked": steering_blocked.terminal_state,
            "semanticFailed": semantic_failed.terminal_state,
            "relevanceBlocked": relevance_blocked.terminal_state,
            "precedence": precedence_failed.terminal_state,
            "staleEvidence": stale_evidence.terminal_state,
        },
        "envelopeHealth": health,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
