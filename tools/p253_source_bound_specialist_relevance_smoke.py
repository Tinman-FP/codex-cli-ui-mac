#!/usr/bin/env python3
"""P253 source-bound deterministic specialist relevance adversaries."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from answer_envelope import (  # noqa: E402
    answer_relevance_contract,
    build_context_evidence_receipt,
    build_source_receipt,
    build_template_ownership_receipt,
    turn_lineage_contract,
)


def direct_relevance_case(
    *,
    run_id: str,
    intent: str,
    domain: str,
    contract: dict,
    answer: str,
    evidence_text: str,
):
    lineage = turn_lineage_contract(
        run_id=run_id,
        latest_user_intent=intent,
        current_domain=domain,
        task_contract=contract,
        declared_relation="standalone",
    )
    owner = build_template_ownership_receipt(
        receipt_id=f"owner-{run_id}",
        run_id=run_id,
        template_id=f"source-reader:{domain}",
        latest_user_intent=intent,
        task_contract=contract,
        owner_domain=domain,
        supported_domains=[domain],
        concepts=[domain, evidence_text],
        turn_lineage_digest=lineage.get("lineageDigest"),
        bound_output=answer,
    )
    context = build_context_evidence_receipt(
        receipt_id=f"evidence-{run_id}",
        run_id=run_id,
        intent_text=intent,
        domain=domain,
        concepts=[evidence_text],
        source_receipt_ids=[f"source-{run_id}"],
        answer_text=answer,
        binding_scope="deterministic-read-only-specialist-answer",
        task_contract=contract,
    )

    def evaluate(*, candidate_answer=answer, candidate_owner=owner, contexts=(context,)):
        return answer_relevance_contract(
            candidate_answer,
            run_id=run_id,
            latest_user_intent=intent,
            intent_domain=domain,
            task_contract=contract,
            template_ownership=candidate_owner,
            turn_lineage=lineage,
            evidence_contexts=list(contexts),
            require_template_ownership=True,
        )

    return lineage, owner, context, evaluate


def main() -> int:
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    catalog_contract = {
        "kind": "local-calibration-catalog-task",
        "domains": ["calibration-assets"],
        "mustDo": ["report the controller-read local calibration evidence"],
    }
    catalog_answer = (
        "Bench sensor Alpha is calibrated through 2027-04; fixture Delta is "
        "available in bay three."
    )
    _, catalog_owner, catalog_context, catalog_eval = direct_relevance_case(
        run_id="p253-catalog",
        intent="Which measurement resources can I use right now?",
        domain="calibration-assets",
        contract=catalog_contract,
        answer=catalog_answer,
        evidence_text=(
            "Bench sensor Alpha calibrated through 2027-04; fixture Delta "
            "available in bay three."
        ),
    )
    catalog = catalog_eval()
    add(
        "paraphrased-read-only-source-answer-satisfies-latest-turn",
        catalog.get("status") == "pass"
        and catalog.get("sourceBoundLatestTurnSatisfied") is True
        and not catalog.get("latestIntentOverlapConcepts")
        and catalog.get("acceptedEvidenceContextIds") == ["evidence-p253-catalog"],
        {
            "status": catalog.get("status"),
            "latestOverlap": catalog.get("latestIntentOverlapConcepts"),
            "sourceBound": catalog.get("sourceBoundLatestTurnSatisfied"),
        },
    )

    release_contract = {
        "kind": "local-release-ledger-task",
        "domains": ["release-ledger"],
        "mustDo": ["report the controller-read release evidence"],
    }
    release_answer = (
        "Build amber-42 passed the signed manifest check and remains the staged candidate."
    )
    _, _, _, release_eval = direct_relevance_case(
        run_id="p253-release",
        intent="What is ready to move forward?",
        domain="release-ledger",
        contract=release_contract,
        answer=release_answer,
        evidence_text=(
            "Build amber-42 passed the signed manifest check; staged candidate."
        ),
    )
    release = release_eval()
    add(
        "second-domain-source-bound-specialist-answer-is-generic",
        release.get("status") == "pass"
        and release.get("sourceBoundLatestTurnSatisfied") is True,
        release.get("issues") or [],
    )

    wrong_owner = build_template_ownership_receipt(
        receipt_id="owner-wrong-domain",
        run_id="p253-catalog",
        template_id="source-reader:travel-status",
        latest_user_intent="Which measurement resources can I use right now?",
        task_contract=catalog_contract,
        owner_domain="travel-status",
        supported_domains=["travel-status"],
        concepts=["flight gate", "departure time", "bay three"],
        bound_output=catalog_answer,
    )
    wrong_domain = catalog_eval(candidate_owner=wrong_owner)
    add(
        "wrong-domain-output-remains-blocked",
        wrong_domain.get("status") == "replan"
        and "template-owner-domain-not-allowed" in (wrong_domain.get("issues") or [])
        and wrong_domain.get("sourceBoundLatestTurnSatisfied") is False,
        wrong_domain.get("issues") or [],
    )

    unbound_context = build_context_evidence_receipt(
        receipt_id="evidence-unbound",
        run_id="p253-catalog",
        intent_text="Which measurement resources can I use right now?",
        domain="calibration-assets",
        concepts=["Bench sensor Alpha calibrated through 2027-04"],
        source_receipt_ids=["source-unbound"],
    )
    unbound = catalog_eval(contexts=(unbound_context,))
    add(
        "unbound-evidence-cannot-replace-latest-turn-overlap",
        unbound.get("status") == "replan"
        and "answer-has-no-latest-turn-concept" in (unbound.get("issues") or [])
        and unbound.get("sourceBoundLatestTurnSatisfied") is False,
        unbound.get("issues") or [],
    )

    stale_context = build_context_evidence_receipt(
        receipt_id="evidence-stale",
        run_id="p253-catalog",
        intent_text="What passed last quarter?",
        domain="calibration-assets",
        concepts=["Bench sensor Alpha calibrated through 2027-04"],
        source_receipt_ids=["source-stale"],
        answer_text=catalog_answer,
        binding_scope="deterministic-read-only-specialist-answer",
        task_contract=catalog_contract,
    )
    stale = catalog_eval(contexts=(stale_context,))
    add(
        "stale-request-evidence-is-rejected",
        stale.get("status") == "replan"
        and stale.get("acceptedEvidenceContextIds") == []
        and stale.get("rejectedEvidenceContextIds") == ["evidence-stale"],
        (stale.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or [],
    )

    tampered_context = copy.deepcopy(catalog_context)
    tampered_context["concepts"] = ["tampered unrelated contents"]
    tampered = catalog_eval(contexts=(tampered_context,))
    add(
        "tampered-evidence-receipt-fails-integrity",
        tampered.get("status") == "replan"
        and "context-evidence-integrity-mismatch"
        in ((tampered.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or []),
        (tampered.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or [],
    )

    wrong_task_context = build_context_evidence_receipt(
        receipt_id="evidence-wrong-task",
        run_id="p253-catalog",
        intent_text="Which measurement resources can I use right now?",
        domain="calibration-assets",
        concepts=["Bench sensor Alpha calibrated through 2027-04"],
        source_receipt_ids=["source-wrong-task"],
        answer_text=catalog_answer,
        binding_scope="deterministic-read-only-specialist-answer",
        task_contract={"kind": "different-task", "domains": ["calibration-assets"]},
    )
    wrong_task = catalog_eval(contexts=(wrong_task_context,))
    add(
        "wrong-task-evidence-binding-fails-closed",
        wrong_task.get("status") == "replan"
        and "context-evidence-task-contract-mismatch"
        in ((wrong_task.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or []),
        (wrong_task.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or [],
    )

    wrong_answer_context = build_context_evidence_receipt(
        receipt_id="evidence-wrong-answer",
        run_id="p253-catalog",
        intent_text="Which measurement resources can I use right now?",
        domain="calibration-assets",
        concepts=["Bench sensor Alpha calibrated through 2027-04"],
        source_receipt_ids=["source-wrong-answer"],
        answer_text="A different answer was bound here.",
        binding_scope="deterministic-read-only-specialist-answer",
        task_contract=catalog_contract,
    )
    wrong_answer = catalog_eval(contexts=(wrong_answer_context,))
    add(
        "wrong-answer-evidence-binding-fails-closed",
        wrong_answer.get("status") == "replan"
        and "context-evidence-answer-binding-mismatch"
        in ((wrong_answer.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or []),
        (wrong_answer.get("rejectedEvidenceContexts") or [{}])[0].get("issues") or [],
    )

    empty_owner = build_template_ownership_receipt(
        receipt_id="owner-empty",
        run_id="p253-catalog",
        template_id="source-reader:calibration-assets",
        latest_user_intent="Which measurement resources can I use right now?",
        task_contract=catalog_contract,
        owner_domain="calibration-assets",
        supported_domains=["calibration-assets"],
        concepts=["calibration assets"],
        bound_output="",
    )
    empty = catalog_eval(candidate_answer="", candidate_owner=empty_owner)
    add(
        "empty-output-cannot-use-source-bound-acceptance",
        empty.get("status") == "replan"
        and empty.get("sourceBoundLatestTurnSatisfied") is False,
        empty.get("issues") or [],
    )

    # Exercise the server integration that is allowed to mint the source-bound
    # context. The evidence is synthetic runtime state, not private inventory.
    messages = [{"role": "user", "text": "Which resources can proceed now?"}]
    route = {
        "projectId": "synthetic-resource-audit",
        "project": "Synthetic Resource Audit",
        "_liveRunId": "p253-server-binding",
        "intentFrame": {
            "domain": "bounded_specialist_capability",
            "originalDomain": "resource-audit",
            "lineageDomain": "resource-audit",
            "operationPlan": {"readOnly": True},
        },
        "capabilityPlan": {
            "id": "bounded-specialist-capability",
            "registered": True,
            "executor": "deterministic",
            "handler_key": "bounded_specialist_direct",
            "relevance_policy": "template-ownership-required",
        },
    }
    contract = server.active_answer_relevance_task_contract(messages, route)
    answer = "Artifact amber-42 passed manifest verification and is staged."
    ownership = build_template_ownership_receipt(
        receipt_id="owner-server-binding",
        run_id="p253-server-binding",
        template_id="source-reader:resource-audit",
        latest_user_intent=server.latest_user_text(messages),
        task_contract=contract,
        owner_domain=server.selected_answer_domain(route),
        supported_domains=[server.selected_answer_domain(route)],
        concepts=["artifact amber-42", "manifest verification", "staged"],
        bound_output=answer,
    )
    route["_capabilityExecution"] = {
        "executor": "deterministic",
        "handlerKey": "bounded_specialist_direct",
        "handled": True,
        "outcome": "completed",
        "templateOwnership": ownership,
    }
    evidence_text = "Artifact amber-42 passed manifest verification and is staged."
    observation = {
        "kind": "source-observation",
        "sourceType": "runtime-state",
        "locator": "runtime://synthetic/resource-ledger",
        "sourceId": "synthetic-resource-ledger",
        "text": evidence_text,
        "excerpt": evidence_text,
        "contentSha256": hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
        "observedAt": "2026-08-11T17:00:00Z",
    }
    source_receipt = build_source_receipt(
        receipt_id="source-server-binding",
        run_id="p253-server-binding",
        claim_text=answer,
        source_type="runtime-state",
        locator="runtime://synthetic/resource-ledger",
        content_sha256=observation["contentSha256"],
        observed_at=observation["observedAt"],
        source_id=observation["sourceId"],
    )
    context = server.specialist_answer_relevance_context(
        messages,
        route,
        run_id="p253-server-binding",
        answer=answer,
        evidence=[observation],
        source_receipts=[source_receipt],
    )
    bound_context = (context.get("evidence_contexts") or [{}])[0]
    add(
        "server-mints-bound-context-only-from-current-verified-read-only-source",
        bound_context.get("bindingScope")
        == "deterministic-read-only-specialist-answer"
        and bound_context.get("answerDigest") == server.text_sha256(answer)
        and bound_context.get("taskContractDigest")
        == ownership.get("taskContractDigest"),
        {
            "contextCount": len(context.get("evidence_contexts") or []),
            "bindingScope": bound_context.get("bindingScope"),
        },
    )

    wrong_claim_receipt = build_source_receipt(
        receipt_id="source-wrong-claim",
        run_id="p253-server-binding",
        claim_text="A different claim.",
        source_type="runtime-state",
        locator="runtime://synthetic/resource-ledger",
        content_sha256=observation["contentSha256"],
        observed_at=observation["observedAt"],
        source_id=observation["sourceId"],
    )
    wrong_claim_context = server.specialist_answer_relevance_context(
        messages,
        route,
        run_id="p253-server-binding",
        answer=answer,
        evidence=[observation],
        source_receipts=[wrong_claim_receipt],
    )
    add(
        "wrong-claim-source-receipt-cannot-mint-bound-context",
        wrong_claim_context.get("evidence_contexts") == [],
        {"contextCount": len(wrong_claim_context.get("evidence_contexts") or [])},
    )

    tampered_observation = {**observation, "text": "Unrelated tampered evidence.", "excerpt": "Unrelated tampered evidence."}
    tampered_observation_context = server.specialist_answer_relevance_context(
        messages,
        route,
        run_id="p253-server-binding",
        answer=answer,
        evidence=[tampered_observation],
        source_receipts=[source_receipt],
    )
    add(
        "tampered-evidence-content-cannot-mint-bound-context",
        tampered_observation_context.get("evidence_contexts") == [],
        {"contextCount": len(tampered_observation_context.get("evidence_contexts") or [])},
    )

    unregistered_route = copy.deepcopy(route)
    unregistered_route["capabilityPlan"]["registered"] = False
    unregistered_context = server.specialist_answer_relevance_context(
        messages,
        unregistered_route,
        run_id="p253-server-binding",
        answer=answer,
        evidence=[observation],
        source_receipts=[source_receipt],
    )
    add(
        "deterministic-route-without-registration-does-not-widen-acceptance",
        (unregistered_context.get("evidence_contexts") or [{}])[0].get("bindingScope")
        == "",
        {
            "bindingScope": (unregistered_context.get("evidence_contexts") or [{}])[0].get(
                "bindingScope"
            )
        },
    )

    write_route = copy.deepcopy(route)
    write_route["intentFrame"]["operationPlan"]["readOnly"] = False
    write_context = server.specialist_answer_relevance_context(
        messages,
        write_route,
        run_id="p253-server-binding",
        answer=answer,
        evidence=[observation],
        source_receipts=[source_receipt],
    )
    add(
        "write-capable-route-does-not-use-read-only-source-exception",
        (write_context.get("evidence_contexts") or [{}])[0].get("bindingScope") == "",
        {
            "bindingScope": (write_context.get("evidence_contexts") or [{}])[0].get(
                "bindingScope"
            )
        },
    )

    server_source = (ROOT / "server.py").read_text(encoding="utf-8")
    export_source = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "p253-package-and-export-registration",
        "server:source-bound-specialist-relevance-p253" in server_source
        and "tools/p253_source_bound_specialist_relevance_smoke.py" in export_source,
    )

    failed = [item for item in checks if item["status"] != "pass"]
    report = {
        "status": "pass" if not failed else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
