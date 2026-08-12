#!/usr/bin/env python3
"""Offline adversarial coverage for typed local-action completion receipts."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import answer_envelope  # noqa: E402
import capability_execution  # noqa: E402
import capability_registry  # noqa: E402


BEFORE_SHA = "1" * 64
AFTER_SHA = "2" * 64
TEST_SHA = "3" * 64


def local_plan() -> dict:
    return capability_registry.build_capability_plan(
        {"domain": "local_product_action"},
        {"mode": "model-first", "selectedCapability": "local_code_agent"},
    )


def operation_plan(*allowed: str) -> dict:
    return {
        "allowedNow": list(allowed),
        "readOnly": not any(item in {"edit", "fix", "change"} for item in allowed),
    }


def edit_receipt() -> dict:
    return {
        "id": "edit-1",
        "kind": "file-change",
        "status": "completed",
        "verified": True,
        "exitCode": 0,
        "paths": ["module.py"],
        "beforeSha256": BEFORE_SHA,
        "afterSha256": AFTER_SHA,
        "beforeByteCount": 20,
        "afterByteCount": 21,
        "mutationMarkers": ["controller-owned-edit"],
        "proposalContentsRecorded": False,
    }


def test_receipt(*, passed: bool = True) -> dict:
    return {
        "id": "test-1",
        "kind": "focused-test",
        "status": "passed" if passed else "failed",
        "verified": passed,
        "exitCode": 0 if passed else 7,
        "paths": ["tools/focused_smoke.py"],
        "outputSha256": TEST_SHA,
        "mutationMarkers": [],
    }


def reconciliation_receipt(*, verified: bool = True) -> dict:
    return {
        "id": "reconcile-1",
        "kind": "local-action-file-reconciliation",
        "status": "verified" if verified else "failed",
        "verified": verified,
        "exitCode": 0 if verified else 1,
        "changedPaths": [] if verified else ["module.py"],
        "mutationMarkers": [] if verified else ["unreported-file-mutation"],
        "contentsRecorded": False,
    }


def rollback_receipt() -> dict:
    return {
        "id": "rollback-1",
        "kind": "file-rollback",
        "status": "completed",
        "verified": True,
        "exitCode": 0,
        "paths": ["module.py"],
        "beforeSha256": AFTER_SHA,
        "afterSha256": BEFORE_SHA,
        "restoredSha256": BEFORE_SHA,
        "mutationMarkers": ["controller-owned-rollback"],
    }


def noop_receipt(*, test_run: bool = False) -> dict:
    return {
        "id": "noop-1",
        "kind": "local-action-verified-noop",
        "status": "verified",
        "verified": True,
        "exitCode": 0,
        "result": "requested-state-already-satisfied",
        "paths": ["module.py"],
        "changedPaths": [],
        "requestSha256": "4" * 64,
        "sourceSha256": BEFORE_SHA,
        "contextStart": 4,
        "contextEnd": 24,
        "contextSha256": "5" * 64,
        "proposalSha256": "6" * 64,
        "testRequested": True,
        "testRun": test_run,
        "sourceEvidenceVerified": True,
        "controllerOwned": True,
        "sourceContentsRecorded": False,
        "proposalContentsRecorded": False,
        "mutationMarkers": [],
    }


def satisfaction_receipt() -> dict:
    return {
        "id": "satisfaction-1",
        "kind": "local-action-source-satisfaction",
        "status": "verified",
        "verified": True,
        "verdict": "satisfied",
        "path": "module.py",
        "requestSha256": "4" * 64,
        "typedRequestSha256": "7" * 64,
        "sourceSha256": BEFORE_SHA,
        "contextStart": 4,
        "contextEnd": 24,
        "contextSha256": "5" * 64,
        "verdictSha256": "8" * 64,
        "controllerBound": True,
        "verdictContentsRecorded": False,
    }


def normalization_receipt() -> dict:
    return {
        "id": "normalization-1",
        "kind": "local-action-proposal-normalization",
        "status": "verified",
        "reasonCode": "identical-edit-to-verified-noop",
        "inputKind": "local-product-edit-proposal",
        "outputKind": "local-product-verified-noop-proposal",
        "path": "module.py",
        "proposalSha256": "9" * 64,
        "outputProposalSha256": "6" * 64,
        "controllerBound": True,
        "proposalContentsRecorded": False,
    }


MESSAGES = [{"role": "user", "text": "Update the local panel and run its focused test."}]


def normalize(receipts: list[dict], allowed: tuple[str, ...] = ("inspect", "edit", "test")) -> dict:
    semantic = capability_execution.build_semantic_completion_receipt(
        MESSAGES,
        "The controller edit was retained and verified.",
        [item["id"] for item in receipts],
    )
    return capability_execution._normalize_handler_result(
        local_plan(),
        {
            "answer": "The bounded local change and focused verification completed.",
            "outcome": "completed",
            "returnCode": 0,
            "accessLevel": "local-workspace-and-tools",
            "commandReceipts": receipts,
            "semanticReceipt": semantic,
        },
        executor_name="local-agent",
        handler_key="local_product_action",
        context={
            "messages": MESSAGES,
            "intentFrame": {"operationPlan": operation_plan(*allowed)},
        },
    )


def terminal_status(result: dict) -> str:
    return (
        answer_envelope.AnswerEnvelope.from_text(
            result.get("answer"),
            objective=MESSAGES[0]["text"],
            run_id="p177-typed-local-action",
        )
        .with_terminal_context(
            semantic_contract=result.get("commandContract"),
            semantic_proof_required=True,
        )
        .finalize("complete")
        .status
    )


def main() -> int:
    valid_receipts = [edit_receipt(), test_receipt(), reconciliation_receipt()]
    valid = normalize(valid_receipts)
    missing_reconciliation = normalize([edit_receipt(), test_receipt()])
    rolled_back = normalize(
        [edit_receipt(), test_receipt(passed=False), rollback_receipt(), reconciliation_receipt()]
    )
    failed_reconciliation = normalize(
        [edit_receipt(), test_receipt(), reconciliation_receipt(verified=False)]
    )
    missing_test = normalize([edit_receipt(), reconciliation_receipt()])
    wrong_order = normalize([reconciliation_receipt(), edit_receipt(), test_receipt()])
    forged_edit_receipt = edit_receipt()
    forged_edit_receipt["afterSha256"] = BEFORE_SHA
    forged = normalize([forged_edit_receipt, test_receipt(), reconciliation_receipt()])
    edit_without_test_authorization = normalize(
        [edit_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    verified_noop = normalize(
        [noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit", "test"),
    )
    verified_noop_with_test = normalize(
        [noop_receipt(test_run=True), test_receipt(), reconciliation_receipt()],
    )
    satisfaction_verified_noop = normalize(
        [satisfaction_receipt(), noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit", "test"),
    )
    normalized_verified_noop = normalize(
        [normalization_receipt(), noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    noop_with_edit = normalize(
        [noop_receipt(), edit_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    stale_noop = noop_receipt()
    stale_noop["sourceEvidenceVerified"] = False
    invalid_noop = normalize(
        [stale_noop, reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    noop_test_flag_mismatch = normalize(
        [noop_receipt(), test_receipt(), reconciliation_receipt()],
    )
    noop_wrong_order = normalize(
        [reconciliation_receipt(), noop_receipt()],
        allowed=("inspect", "edit"),
    )
    tampered_satisfaction = satisfaction_receipt()
    tampered_satisfaction["contextSha256"] = "not-a-hash"
    invalid_satisfaction = normalize(
        [tampered_satisfaction, noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    orphaned_satisfaction = normalize(
        [satisfaction_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    mismatched_satisfaction = satisfaction_receipt()
    mismatched_satisfaction.update({
        "path": "other.py",
        "requestSha256": "a" * 64,
        "sourceSha256": "b" * 64,
        "contextStart": 30,
        "contextEnd": 40,
        "contextSha256": "c" * 64,
    })
    cross_unbound_satisfaction = normalize(
        [mismatched_satisfaction, noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    mismatched_normalization = normalization_receipt()
    mismatched_normalization.update({
        "path": "other.py",
        "outputProposalSha256": "d" * 64,
    })
    cross_unbound_normalization = normalize(
        [mismatched_normalization, noop_receipt(), reconciliation_receipt()],
        allowed=("inspect", "edit"),
    )
    ordinary = capability_execution.command_completion_contract(
        command_receipts=[
            {"id": "inspect-1", "command": "python3 -V", "status": "completed", "exitCode": 0}
        ],
        semantic_receipt=capability_execution.build_semantic_completion_receipt(
            MESSAGES, "The requested read-only inspection completed.", ["inspect-1"]
        ),
        latest_user_intent=MESSAGES[0]["text"],
        access_level="local-files",
        completed=True,
    )

    checks = [
        {
            "id": "registry-declares-local-action-proof-requirements",
            "ok": local_plan().get("proof_requirements") == [
                "controller-edit-if-mutation-authorized",
                "verified-noop-alternative-controller-resolution",
                "focused-test-if-test-authorized",
                "verified-final-reconciliation",
                "rollback-precludes-completion",
            ],
        },
        {
            "id": "verified-edit-test-reconciliation-completes",
            "ok": valid.get("outcome") == "completed"
            and valid.get("returnCode") == 0
            and valid.get("localActionProof", {}).get("status") == "pass"
            and valid.get("localActionProof", {}).get("retainedMutation") is True
            and terminal_status(valid) == "complete",
            "actual": valid.get("localActionProof"),
        },
        {
            "id": "metadata-only-reconciliation-is-not-withheld",
            "ok": valid.get("commandReceipts", [])[-1].get("verified") is True
            and valid.get("commandReceipts", [])[-1].get("command") == "",
        },
        {
            "id": "missing-reconciliation-cannot-complete",
            "ok": "missing-final-reconciliation" in missing_reconciliation.get("contractIssues", [])
            and missing_reconciliation.get("outcome") == "failed"
            and terminal_status(missing_reconciliation) == "failed",
        },
        {
            "id": "rollback-cannot-be-composed-as-complete",
            "ok": "controller-edit-was-rolled-back" in rolled_back.get("contractIssues", [])
            and rolled_back.get("outcome") == "failed"
            and terminal_status(rolled_back) == "failed",
        },
        {
            "id": "failed-reconciliation-cannot-complete",
            "ok": "final-reconciliation-not-verified" in failed_reconciliation.get("contractIssues", [])
            and failed_reconciliation.get("outcome") == "failed",
        },
        {
            "id": "authorized-focused-test-is-required",
            "ok": "missing-focused-test-receipt" in missing_test.get("contractIssues", [])
            and missing_test.get("outcome") == "failed",
        },
        {
            "id": "proof-order-is-enforced",
            "ok": "final-reconciliation-precedes-controller-edit" in wrong_order.get("contractIssues", [])
            and wrong_order.get("outcome") == "failed",
        },
        {
            "id": "forged-edit-hash-is-rejected",
            "ok": "controller-edit-hash-invalid" in forged.get("contractIssues", [])
            and forged.get("outcome") == "failed",
        },
        {
            "id": "test-is-not-invented-when-not-authorized",
            "ok": edit_without_test_authorization.get("outcome") == "completed"
            and edit_without_test_authorization.get("localActionProof", {}).get("status") == "pass",
        },
        {
            "id": "ordinary-command-contract-remains-unchanged",
            "ok": ordinary.get("status") == "pass"
            and ordinary.get("localActionProof", {}).get("applicable") is False,
        },
        {
            "id": "explicit-verified-noop-is-an-alternative-controller-resolution",
            "ok": verified_noop.get("outcome") == "completed"
            and verified_noop.get("localActionProof", {}).get("status") == "pass"
            and verified_noop.get("localActionProof", {}).get("verifiedNoOp") is True
            and verified_noop.get("localActionProof", {}).get("retainedMutation") is False
            and terminal_status(verified_noop) == "complete",
            "actual": verified_noop.get("localActionProof"),
        },
        {
            "id": "verified-noop-may-bind-one-explicit-passing-test",
            "ok": verified_noop_with_test.get("outcome") == "completed"
            and verified_noop_with_test.get("localActionProof", {}).get("verifiedNoOp") is True,
        },
        {
            "id": "source-satisfaction-evidence-can-precede-explicit-noop",
            "ok": satisfaction_verified_noop.get("outcome") == "completed"
            and satisfaction_verified_noop.get("localActionProof", {}).get("verifiedNoOp") is True,
        },
        {
            "id": "identical-edit-normalization-can-precede-explicit-noop",
            "ok": normalized_verified_noop.get("outcome") == "completed"
            and normalized_verified_noop.get("localActionProof", {}).get("verifiedNoOp") is True,
        },
        {
            "id": "verified-noop-cannot-coexist-with-an-edit",
            "ok": "verified-noop-with-controller-edit" in noop_with_edit.get("contractIssues", [])
            and noop_with_edit.get("outcome") == "failed",
        },
        {
            "id": "unverified-noop-evidence-fails-closed",
            "ok": "verified-noop-receipt-invalid" in invalid_noop.get("contractIssues", [])
            and invalid_noop.get("outcome") == "failed",
        },
        {
            "id": "noop-test-receipt-must-match-controller-test-flag",
            "ok": "verified-noop-test-flag-mismatch" in noop_test_flag_mismatch.get("contractIssues", [])
            and noop_test_flag_mismatch.get("outcome") == "failed",
        },
        {
            "id": "noop-must-precede-final-reconciliation",
            "ok": "final-reconciliation-precedes-verified-noop" in noop_wrong_order.get("contractIssues", [])
            and noop_wrong_order.get("outcome") == "failed",
        },
        {
            "id": "tampered-source-satisfaction-evidence-fails-closed",
            "ok": "source-satisfaction-hash-invalid" in invalid_satisfaction.get("contractIssues", [])
            and invalid_satisfaction.get("outcome") == "failed",
        },
        {
            "id": "source-satisfaction-cannot-substitute-for-explicit-noop",
            "ok": "noop-evidence-without-verified-noop" in orphaned_satisfaction.get("contractIssues", [])
            and orphaned_satisfaction.get("outcome") == "failed",
        },
        {
            "id": "valid-shape-source-satisfaction-must-bind-to-the-same-noop",
            "ok": {
                "source-satisfaction-noop-path-mismatch",
                "source-satisfaction-noop-request-mismatch",
                "source-satisfaction-noop-source-mismatch",
                "source-satisfaction-noop-context-mismatch",
            }.issubset(set(cross_unbound_satisfaction.get("contractIssues", [])))
            and cross_unbound_satisfaction.get("outcome") == "failed",
        },
        {
            "id": "valid-shape-normalization-must-bind-to-the-same-noop",
            "ok": {
                "noop-normalization-path-mismatch",
                "noop-normalization-output-mismatch",
            }.issubset(set(cross_unbound_normalization.get("contractIssues", [])))
            and cross_unbound_normalization.get("outcome") == "failed",
        },
    ]
    failed = [item for item in checks if not item.get("ok")]
    report = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
