#!/usr/bin/env python3
"""Focused adversarial regression for latest-turn lineage isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from answer_envelope import (
    AnswerEnvelope,
    answer_relevance_contract,
    build_context_evidence_receipt,
    build_template_ownership_receipt,
    synthetic_envelope_check,
    turn_lineage_contract,
)


def ownership(*, run_id, intent, contract, domain, concepts, lineage, **kwargs):
    return build_template_ownership_receipt(
        receipt_id=f"owner-{run_id}",
        run_id=run_id,
        template_id=f"template-{run_id}",
        latest_user_intent=intent,
        task_contract=contract,
        owner_domain=domain,
        concepts=concepts,
        turn_lineage_digest=lineage.get("lineageDigest"),
        **kwargs,
    )


def relevance(answer, *, run_id, intent, domain, contract, owner, lineage, **kwargs):
    return answer_relevance_contract(
        answer,
        run_id=run_id,
        latest_user_intent=intent,
        intent_domain=domain,
        task_contract=contract,
        template_ownership=owner,
        turn_lineage=lineage,
        **kwargs,
    )


def main() -> int:
    stale_prior = "Size a motor controller for a 72 V kart using battery current limits."
    stale_latest = "Now switch to aircraft corrosion inspection requirements."
    stale_contract = {
        "kind": "stale-controller-task",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["size the controller from battery voltage and current limit"],
    }
    stale_answer = "Use the 72 V battery current limit to size the motor controller."
    legacy_owner = build_template_ownership_receipt(
        receipt_id="owner-legacy-false-pass",
        run_id="legacy-false-pass",
        template_id="vehicle-controller-guide",
        latest_user_intent=stale_latest,
        task_contract=stale_contract,
        owner_domain="vehicle-motion-control",
        concepts=["72 V", "battery", "current limit", "motor controller"],
    )
    legacy_false_pass = answer_relevance_contract(
        stale_answer,
        run_id="legacy-false-pass",
        latest_user_intent=stale_latest,
        intent_domain="vehicle-motion-control",
        task_contract=stale_contract,
        template_ownership=legacy_owner,
        prior_intent_concepts=[stale_prior],
        evidence_concepts=["checked 72 V controller evidence"],
    )
    stale_lineage = turn_lineage_contract(
        run_id="stale-switch",
        latest_user_intent=stale_latest,
        current_domain="airworthiness-maintenance",
        task_contract=stale_contract,
        declared_relation="new-topic",
        prior_user_intent=stale_prior,
        prior_domain="vehicle-motion-control",
    )
    stale_owner = ownership(
        run_id="stale-switch",
        intent=stale_latest,
        contract=stale_contract,
        domain="vehicle-motion-control",
        concepts=["72 V", "battery", "current limit", "motor controller"],
        lineage=stale_lineage,
    )
    stale_switch = relevance(
        stale_answer,
        run_id="stale-switch",
        intent=stale_latest,
        domain="airworthiness-maintenance",
        contract=stale_contract,
        owner=stale_owner,
        lineage=stale_lineage,
        prior_intent_concepts=[stale_prior],
        evidence_concepts=["checked 72 V controller evidence"],
    )

    source_prior = (
        "Find the current manufacturer rating and source for a fictional "
        "FluxDrive X1 controller."
    )
    controller_latest = (
        "Never mind the rating or source. What controller voltage headroom "
        "should I use for a 72 V lightweight kart?"
    )
    controller_contract = {
        "kind": "controller-voltage-sizing-task",
        "domains": ["engineering-power-conversion"],
        "mustDo": ["size controller voltage headroom from the 72 V pack"],
    }
    controller_lineage = turn_lineage_contract(
        run_id="controller-switch",
        latest_user_intent=controller_latest,
        current_domain="engineering-power-conversion",
        task_contract=controller_contract,
        declared_relation="follow-up",
        prior_user_intent=source_prior,
        prior_domain="source-resolution",
    )
    controller_owner = ownership(
        run_id="controller-switch",
        intent=controller_latest,
        contract=controller_contract,
        domain="engineering-power-conversion",
        concepts=["controller", "voltage headroom", "72 V pack"],
        lineage=controller_lineage,
    )
    prior_source_evidence = build_context_evidence_receipt(
        receipt_id="prior-fictional-source",
        run_id="controller-switch",
        intent_text=source_prior,
        domain="source-resolution",
        concepts=["manufacturer", "rating", "source", "FluxDrive X1"],
        source_receipt_ids=["source-receipt-prior-fictional"],
    )
    controller_switch = relevance(
        (
            "For a 72 V kart, select controller voltage headroom from the pack's "
            "maximum charged voltage, not a fictional manufacturer rating."
        ),
        run_id="controller-switch",
        intent=controller_latest,
        domain="engineering-power-conversion",
        contract=controller_contract,
        owner=controller_owner,
        lineage=controller_lineage,
        prior_intent_concepts=[source_prior],
        evidence_contexts=[prior_source_evidence],
    )
    stale_controller_owner = dict(controller_owner)
    stale_controller_owner["turnLineageDigest"] = ""
    stale_controller_ownership = relevance(
        "For a 72 V kart, choose controller voltage headroom from maximum pack voltage.",
        run_id="controller-switch",
        intent=controller_latest,
        domain="engineering-power-conversion",
        contract=controller_contract,
        owner=stale_controller_owner,
        lineage=controller_lineage,
    )
    tampered_controller_lineage = dict(controller_lineage)
    tampered_controller_lineage["decision"] = "retain"
    tampered_lineage = relevance(
        "For a 72 V kart, choose controller voltage headroom from maximum pack voltage.",
        run_id="controller-switch",
        intent=controller_latest,
        domain="engineering-power-conversion",
        contract=controller_contract,
        owner=controller_owner,
        lineage=tampered_controller_lineage,
    )

    same_prior = "Size a motor controller from a 72 V battery and its current limit."
    same_latest = "What about 96 V instead?"
    same_contract = {
        "kind": "controller-follow-up-task",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["update controller sizing for 96 V"],
    }
    same_lineage = turn_lineage_contract(
        run_id="same-domain-follow-up",
        latest_user_intent=same_latest,
        current_domain="vehicle-motion-control",
        task_contract=same_contract,
        declared_relation="elliptical-follow-up",
        prior_user_intent=same_prior,
        prior_domain="vehicle-motion-control",
    )
    same_owner = ownership(
        run_id="same-domain-follow-up",
        intent=same_latest,
        contract=same_contract,
        domain="vehicle-motion-control",
        concepts=["96 V", "motor controller", "voltage headroom", "current limit"],
        lineage=same_lineage,
    )
    same_evidence = build_context_evidence_receipt(
        receipt_id="prior-controller-evidence",
        run_id="same-domain-follow-up",
        intent_text=same_prior,
        domain="vehicle-motion-control",
        concepts=["motor controller", "battery", "current limit"],
        source_receipt_ids=["source-receipt-controller"],
    )
    same_domain = relevance(
        "At 96 V, retain motor-controller voltage headroom and recheck the battery current limit.",
        run_id="same-domain-follow-up",
        intent=same_latest,
        domain="vehicle-motion-control",
        contract=same_contract,
        owner=same_owner,
        lineage=same_lineage,
        prior_intent_concepts=[same_prior],
        evidence_contexts=[same_evidence],
    )
    injected_same_domain_context = relevance(
        "At 96 V, retain motor-controller voltage headroom and recheck the battery current limit.",
        run_id="same-domain-follow-up",
        intent=same_latest,
        domain="vehicle-motion-control",
        contract=same_contract,
        owner=same_owner,
        lineage=same_lineage,
        prior_intent_concepts=[same_prior, "unrelated turbine blade evidence"],
        evidence_contexts=[same_evidence],
    )
    revision_latest = "Use 96 V, not 72 V."
    revision_contract = {
        "kind": "controller-revision-task",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["revise controller sizing to 96 V"],
    }
    revision_lineage = turn_lineage_contract(
        run_id="same-domain-revision",
        latest_user_intent=revision_latest,
        current_domain="vehicle-motion-control",
        task_contract=revision_contract,
        declared_relation="revision",
        prior_user_intent=same_prior,
        prior_domain="vehicle-motion-control",
    )
    revision_owner = ownership(
        run_id="same-domain-revision",
        intent=revision_latest,
        contract=revision_contract,
        domain="vehicle-motion-control",
        concepts=["96 V", "controller", "voltage headroom"],
        lineage=revision_lineage,
    )
    revision_evidence = build_context_evidence_receipt(
        receipt_id="superseded-72-v-evidence",
        run_id="same-domain-revision",
        intent_text=same_prior,
        domain="vehicle-motion-control",
        concepts=["72 V", "battery", "controller"],
        source_receipt_ids=["source-receipt-72-v"],
    )
    same_domain_revision = relevance(
        "Use a 96 V controller rating with appropriate voltage headroom.",
        run_id="same-domain-revision",
        intent=revision_latest,
        domain="vehicle-motion-control",
        contract=revision_contract,
        owner=revision_owner,
        lineage=revision_lineage,
        prior_intent_concepts=[same_prior],
        evidence_contexts=[revision_evidence],
    )

    bridge_prior = "How does a source receipt establish evidence provenance and traceability?"
    bridge_latest = (
        "Compare that evidence traceability with a safety-case release decision."
    )
    bridge_contract = {
        "kind": "cross-domain-comparison-task",
        "allowedDomains": ["evidence-provenance", "safety-assurance"],
        "mustDo": ["compare evidence traceability across the two release controls"],
    }
    bridge_lineage = turn_lineage_contract(
        run_id="explicit-bridge",
        latest_user_intent=bridge_latest,
        current_domain="safety-assurance",
        task_contract=bridge_contract,
        declared_relation="revision",
        prior_user_intent=bridge_prior,
        prior_domain="evidence-provenance",
        explicit_cross_domain=True,
        bridge_concepts=["evidence", "traceability"],
    )
    bridge_owner = ownership(
        run_id="explicit-bridge",
        intent=bridge_latest,
        contract=bridge_contract,
        domain="safety-assurance",
        concepts=["source receipt", "evidence traceability", "safety case", "release decision"],
        lineage=bridge_lineage,
        supported_domains=["safety-assurance", "evidence-provenance"],
        cross_domain=True,
        bridge_concepts=["evidence", "traceability"],
    )
    bridge_evidence = build_context_evidence_receipt(
        receipt_id="prior-provenance-evidence",
        run_id="explicit-bridge",
        intent_text=bridge_prior,
        domain="evidence-provenance",
        concepts=["source receipt", "evidence provenance", "traceability"],
        source_receipt_ids=["source-receipt-provenance"],
    )
    cross_domain = relevance(
        (
            "A source receipt establishes evidence traceability; a safety case "
            "connects that evidence to the release decision."
        ),
        run_id="explicit-bridge",
        intent=bridge_latest,
        domain="safety-assurance",
        contract=bridge_contract,
        owner=bridge_owner,
        lineage=bridge_lineage,
        prior_intent_concepts=[bridge_prior],
        evidence_contexts=[bridge_evidence],
    )

    ambiguous_latest = "What about certification instead?"
    ambiguous_contract = {
        "kind": "certification-question-task",
        "domains": ["airworthiness-regulation"],
        "mustDo": ["clarify which certification target applies"],
    }
    ambiguous_lineage = turn_lineage_contract(
        run_id="ambiguous-switch",
        latest_user_intent=ambiguous_latest,
        current_domain="airworthiness-regulation",
        task_contract=ambiguous_contract,
        declared_relation="ambiguous",
        prior_user_intent=stale_prior,
        prior_domain="vehicle-motion-control",
    )
    ambiguous_owner = ownership(
        run_id="ambiguous-switch",
        intent=ambiguous_latest,
        contract=ambiguous_contract,
        domain="airworthiness-regulation",
        concepts=["certification", "target"],
        lineage=ambiguous_lineage,
    )
    ambiguous_relevance = relevance(
        "The certification target must be clarified before selecting requirements.",
        run_id="ambiguous-switch",
        intent=ambiguous_latest,
        domain="airworthiness-regulation",
        contract=ambiguous_contract,
        owner=ambiguous_owner,
        lineage=ambiguous_lineage,
    )
    ambiguous_terminal = (
        AnswerEnvelope.from_text(
            "The certification target must be clarified before selecting requirements.",
            objective=ambiguous_latest,
            run_id="ambiguous-switch",
        )
        .with_relevance_context(
            latest_user_intent=ambiguous_latest,
            intent_domain="airworthiness-regulation",
            task_contract=ambiguous_contract,
            template_ownership=ambiguous_owner,
            turn_lineage=ambiguous_lineage,
        )
        .with_terminal_context()
        .finalize("complete")
    )

    checks = {
        "preFixUnionReproducedFalsePass": legacy_false_pass.get("status") == "pass",
        "staleTaskTemplateAndFlatEvidenceForceReplan": bool(
            stale_lineage.get("transition") == "domain-switch"
            and stale_lineage.get("decision") == "replan"
            and "task-contract-domain-lineage-mismatch" in stale_lineage.get("issues", [])
            and stale_switch.get("status") == "replan"
            and stale_switch.get("priorIntentConcepts") == []
            and stale_switch.get("evidenceConcepts") == []
            and "unscoped-evidence-concepts" in stale_switch.get("issues", [])
        ),
        "freshControllerSizingSwitchIsolatesPriorSourceContext": bool(
            controller_lineage.get("transition") == "domain-switch"
            and controller_lineage.get("decision") == "isolate"
            and controller_switch.get("status") == "pass"
            and controller_switch.get("priorIntentConcepts") == []
            and controller_switch.get("rejectedEvidenceContextIds")
            == ["prior-fictional-source"]
            and controller_switch.get("acceptedEvidenceContextIds") == []
        ),
        "ownershipMustBeReboundToCurrentLineage": bool(
            stale_controller_ownership.get("status") == "replan"
            and "template-ownership-turn-lineage-mismatch"
            in stale_controller_ownership.get("issues", [])
        ),
        "lineageDigestRejectsMutation": bool(
            tampered_lineage.get("status") == "replan"
            and "turn-lineage-integrity-mismatch"
            in tampered_lineage.get("issues", [])
        ),
        "ellipticalSameDomainFollowUpRetainsTypedContext": bool(
            same_lineage.get("transition") == "continuation"
            and same_lineage.get("decision") == "retain"
            and same_domain.get("status") == "pass"
            and same_domain.get("acceptedEvidenceContextIds")
            == ["prior-controller-evidence"]
            and {"controller", "battery"}
            <= set(same_domain.get("supportOverlapConcepts", []))
        ),
        "continuationRejectsConceptsOutsideBoundPriorTurn": bool(
            injected_same_domain_context.get("status") == "replan"
            and "unscoped-prior-intent-concepts"
            in injected_same_domain_context.get("issues", [])
            and "turbine"
            not in injected_same_domain_context.get("priorIntentConcepts", [])
        ),
        "sameDomainRevisionKeepsConceptsButDropsSupersededEvidence": bool(
            revision_lineage.get("transition") == "revision"
            and revision_lineage.get("decision") == "isolate"
            and revision_lineage.get("mayReusePriorConcepts") is True
            and revision_lineage.get("mayReusePriorEvidence") is False
            and same_domain_revision.get("status") == "pass"
            and same_domain_revision.get("rejectedEvidenceContextIds")
            == ["superseded-72-v-evidence"]
        ),
        "explicitCrossDomainBridgeRetainsDeclaredContext": bool(
            bridge_lineage.get("transition") == "cross-domain-bridge"
            and bridge_lineage.get("decision") == "bridge"
            and cross_domain.get("status") == "pass"
            and set(cross_domain.get("allowedDomains", []))
            == {"evidence-provenance", "safety-assurance"}
            and cross_domain.get("acceptedEvidenceContextIds")
            == ["prior-provenance-evidence"]
        ),
        "ambiguousSwitchRequiresReplanAndCannotComplete": bool(
            ambiguous_lineage.get("transition") == "ambiguous"
            and ambiguous_lineage.get("decision") == "replan"
            and ambiguous_relevance.get("status") == "replan"
            and "turn-lineage-replan-required"
            in ambiguous_relevance.get("issues", [])
            and ambiguous_terminal.status == "blocked"
            and "answer-relevance-replan-required"
            in ambiguous_terminal.terminal_state.get("reasonCodes", [])
        ),
        "packageHealthEnvelopeInvariantPasses": synthetic_envelope_check().get("status")
        == "pass",
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "receipts": {
            "preFixFalsePass": legacy_false_pass,
            "staleSwitchLineage": stale_lineage,
            "staleSwitchRelevance": stale_switch,
            "controllerSwitchLineage": controller_lineage,
            "controllerSwitchRelevance": controller_switch,
            "staleControllerOwnership": stale_controller_ownership,
            "tamperedLineage": tampered_lineage,
            "sameDomainLineage": same_lineage,
            "sameDomainRelevance": same_domain,
            "injectedSameDomainContext": injected_same_domain_context,
            "revisionLineage": revision_lineage,
            "revisionRelevance": same_domain_revision,
            "crossDomainLineage": bridge_lineage,
            "crossDomainRelevance": cross_domain,
            "ambiguousLineage": ambiguous_lineage,
            "ambiguousRelevance": ambiguous_relevance,
            "ambiguousTerminal": ambiguous_terminal.terminal_state,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
