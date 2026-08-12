#!/usr/bin/env python3
"""Focused adversarial regression for typed specialist-answer relevance."""

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
    answer_relevance_contract,
    build_template_ownership_receipt,
    synthetic_envelope_check,
)


def ownership(
    *,
    run_id,
    template_id,
    intent,
    contract,
    owner_domain,
    concepts,
    supported_domains=None,
    cross_domain=False,
    bridge_concepts=None,
):
    return build_template_ownership_receipt(
        receipt_id=f"receipt-{run_id}",
        run_id=run_id,
        template_id=template_id,
        latest_user_intent=intent,
        task_contract=contract,
        owner_domain=owner_domain,
        supported_domains=supported_domains or [owner_domain],
        concepts=concepts,
        cross_domain=cross_domain,
        bridge_concepts=bridge_concepts or [],
    )


def relevance(
    answer,
    *,
    run_id,
    intent,
    domain,
    contract,
    owner,
    prior=(),
    evidence=(),
    required=True,
):
    return answer_relevance_contract(
        answer,
        run_id=run_id,
        latest_user_intent=intent,
        intent_domain=domain,
        task_contract=contract,
        template_ownership=owner,
        prior_intent_concepts=prior,
        evidence_concepts=evidence,
        require_template_ownership=required,
    )


def main() -> int:
    evidence_intent = (
        "With Web Access disabled, does a URL written by the model count as "
        "retrieved evidence?"
    )
    evidence_contract = {
        "kind": "answer-task-contract",
        "domains": ["evidence-provenance"],
        "mustDo": ["answer the retrieval and confidence boundary"],
        "requiredProof": ["structured source receipt"],
    }
    wrong_answer = (
        "For the lightweight vehicle, use a 72 V motor controller and set the "
        "battery current limit conservatively."
    )
    wrong_owner = ownership(
        run_id="wrong-domain",
        template_id="vehicle-controller-guide",
        intent=evidence_intent,
        contract=evidence_contract,
        owner_domain="vehicle-motion-control",
        concepts=["lightweight vehicle", "motor controller", "battery current limit"],
    )
    wrong_domain = relevance(
        wrong_answer,
        run_id="wrong-domain",
        intent=evidence_intent,
        domain="evidence-provenance",
        contract=evidence_contract,
        owner=wrong_owner,
    )
    mislabeled_owner = ownership(
        run_id="mislabeled-domain",
        template_id="vehicle-controller-guide",
        intent=evidence_intent,
        contract=evidence_contract,
        owner_domain="evidence-provenance",
        concepts=["lightweight vehicle", "motor controller", "battery current limit"],
    )
    mislabeled_domain = relevance(
        wrong_answer,
        run_id="mislabeled-domain",
        intent=evidence_intent,
        domain="evidence-provenance",
        contract=evidence_contract,
        owner=mislabeled_owner,
    )
    wrong_draft = AnswerEnvelope.from_text(
        wrong_answer,
        objective=evidence_intent,
        run_id="wrong-domain",
    ).with_relevance_context(
        latest_user_intent=evidence_intent,
        intent_domain="evidence-provenance",
        task_contract=evidence_contract,
        template_ownership=wrong_owner,
    )
    finalization_blocked = False
    try:
        wrong_draft.finalize("complete")
    except AnswerRelevanceError as exc:
        finalization_blocked = bool(
            "requires replan" in str(exc)
            and exc.receipt.get("status") == "replan"
        )

    specialist_intent = (
        "How should I size a motor controller from battery voltage and current limit?"
    )
    specialist_contract = {
        "kind": "answer-task-contract",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["relate controller voltage to battery voltage and current limit"],
    }
    specialist_answer = (
        "Choose a motor controller above maximum battery voltage, then keep its "
        "current limit within the battery rating."
    )
    specialist_owner = ownership(
        run_id="same-domain",
        template_id="vehicle-controller-guide",
        intent=specialist_intent,
        contract=specialist_contract,
        owner_domain="vehicle-motion-control",
        concepts=["motor controller", "battery voltage", "current limit"],
    )
    same_domain = relevance(
        specialist_answer,
        run_id="same-domain",
        intent=specialist_intent,
        domain="vehicle-motion-control",
        contract=specialist_contract,
        owner=specialist_owner,
    )
    same_domain_final = AnswerEnvelope.from_text(
        specialist_answer,
        objective=specialist_intent,
        run_id="same-domain",
    ).with_relevance_context(
        latest_user_intent=specialist_intent,
        intent_domain="vehicle-motion-control",
        task_contract=specialist_contract,
        template_ownership=specialist_owner,
    ).finalize("complete")

    comparison_intent = (
        "Compare source provenance controls with safety-case traceability for release decisions."
    )
    comparison_contract = {
        "kind": "comparison-task-contract",
        "allowedDomains": ["evidence-provenance", "safety-assurance"],
        "mustDo": ["connect source receipts to safety-case traceability"],
    }
    comparison_answer = (
        "Source receipts establish evidence provenance; safety-case traceability "
        "connects that evidence to release decisions."
    )
    comparison_owner = ownership(
        run_id="cross-domain",
        template_id="cross-domain-evidence-comparison",
        intent=comparison_intent,
        contract=comparison_contract,
        owner_domain="evidence-provenance",
        supported_domains=["evidence-provenance", "safety-assurance"],
        concepts=["source receipts", "evidence provenance", "safety-case traceability"],
        cross_domain=True,
        bridge_concepts=["evidence", "traceability", "release decisions"],
    )
    cross_domain = relevance(
        comparison_answer,
        run_id="cross-domain",
        intent=comparison_intent,
        domain="evidence-provenance",
        contract=comparison_contract,
        owner=comparison_owner,
    )

    incomplete_cross_owner = ownership(
        run_id="cross-incomplete",
        template_id="cross-domain-evidence-comparison",
        intent=comparison_intent,
        contract=comparison_contract,
        owner_domain="evidence-provenance",
        supported_domains=["evidence-provenance"],
        concepts=["source receipts", "evidence provenance", "safety-case traceability"],
        cross_domain=True,
        bridge_concepts=["evidence", "traceability"],
    )
    incomplete_cross = relevance(
        comparison_answer,
        run_id="cross-incomplete",
        intent=comparison_intent,
        domain="evidence-provenance",
        contract=comparison_contract,
        owner=incomplete_cross_owner,
    )

    followup_intent = "What about 96 V instead?"
    followup_contract = {
        "kind": "follow-up-task-contract",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["update the prior controller recommendation for 96 V"],
    }
    followup_answer = (
        "At 96 V, choose a motor controller with voltage headroom and recheck the "
        "battery current limit."
    )
    followup_owner = ownership(
        run_id="followup",
        template_id="vehicle-controller-guide",
        intent=followup_intent,
        contract=followup_contract,
        owner_domain="vehicle-motion-control",
        concepts=["motor controller", "voltage headroom", "battery current limit"],
    )
    followup = relevance(
        followup_answer,
        run_id="followup",
        intent=followup_intent,
        domain="vehicle-motion-control",
        contract=followup_contract,
        owner=followup_owner,
        prior=["motor controller", "battery voltage", "current limit"],
    )

    stale_owner = ownership(
        run_id="stale",
        template_id="vehicle-controller-guide",
        intent="How should I size the original controller?",
        contract=followup_contract,
        owner_domain="vehicle-motion-control",
        concepts=["motor controller", "voltage headroom", "battery current limit"],
    )
    stale_intent = relevance(
        followup_answer,
        run_id="stale",
        intent=followup_intent,
        domain="vehicle-motion-control",
        contract=followup_contract,
        owner=stale_owner,
        prior=["motor controller", "battery voltage", "current limit"],
    )

    missing_owner = relevance(
        specialist_answer,
        run_id="missing-owner",
        intent=specialist_intent,
        domain="vehicle-motion-control",
        contract=specialist_contract,
        owner={},
    )
    optional_general = relevance(
        "Yes, I can help you design it once you want execution rather than capability confirmation.",
        run_id="general",
        intent="Do you have the capability to help me design it?",
        domain="capability-introspection",
        contract={"kind": "capability-question", "domains": ["capability-introspection"]},
        owner={},
        required=False,
    )
    health = synthetic_envelope_check()

    checks = {
        "wrongDomainTemplateRequestsReplan": bool(
            wrong_domain.get("status") == "replan"
            and not wrong_domain.get("mayFinalize")
            and "template-owner-domain-not-allowed" in wrong_domain.get("issues", [])
            and "answer-has-no-active-contract-concept" in wrong_domain.get("issues", [])
            and {"controller", "battery", "motor"}
            <= set(wrong_domain.get("unsupportedSpecialistConcepts", []))
        ),
        "wrongDomainCannotFinalize": finalization_blocked,
        "matchingDomainLabelCannotMaskConceptDrift": bool(
            mislabeled_domain.get("status") == "replan"
            and "template-owner-domain-not-allowed"
            not in mislabeled_domain.get("issues", [])
            and "answer-has-no-active-contract-concept"
            in mislabeled_domain.get("issues", [])
            and {"controller", "battery", "motor"}
            <= set(mislabeled_domain.get("unsupportedSpecialistConcepts", []))
        ),
        "sameDomainSpecialistPasses": bool(
            same_domain.get("status") == "pass"
            and same_domain.get("mayFinalize")
            and same_domain_final.answer_relevance.get("status") == "pass"
        ),
        "declaredCrossDomainComparisonPasses": bool(
            cross_domain.get("status") == "pass"
            and cross_domain.get("crossDomain")
            and set(cross_domain.get("allowedDomains", []))
            == {"evidence-provenance", "safety-assurance"}
        ),
        "incompleteCrossDomainOwnershipRejected": bool(
            incomplete_cross.get("status") == "replan"
            and "cross-domain-support-incomplete" in incomplete_cross.get("issues", [])
        ),
        "ellipticalFollowupRetainsPriorDomain": bool(
            followup.get("status") == "pass"
            and {"controller", "battery"}
            <= set(followup.get("supportOverlapConcepts", []))
        ),
        "staleIntentReceiptRejected": bool(
            stale_intent.get("status") == "replan"
            and "template-ownership-intent-mismatch" in stale_intent.get("issues", [])
        ),
        "missingRequiredOwnershipFailsClosed": bool(
            missing_owner.get("status") == "replan"
            and "missing-template-ownership-receipt" in missing_owner.get("issues", [])
        ),
        "nonSpecialistGeneralAnswerRemainsAvailable": bool(
            optional_general.get("status") == "not-evaluated"
            and optional_general.get("mayFinalize")
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
            "wrongDomain": wrong_domain,
            "mislabeledDomain": mislabeled_domain,
            "sameDomain": same_domain,
            "crossDomain": cross_domain,
            "incompleteCrossDomain": incomplete_cross,
            "followup": followup,
            "staleIntent": stale_intent,
            "missingOwner": missing_owner,
        },
        "envelopeHealth": health,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
