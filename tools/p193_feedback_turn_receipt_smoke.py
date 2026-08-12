#!/usr/bin/env python3
"""Adversarial checks for hash-bound feedback learning and correction lineage."""

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def main():
    checks = []

    def check(name, passed, detail=""):
        checks.append({"name": name, "passed": bool(passed), "detail": str(detail or "")})

    original = {
        "DATA_DIR": server.DATA_DIR,
        "QUALITY_FEEDBACK_PATH": server.QUALITY_FEEDBACK_PATH,
        "INTERACTION_FEEDBACK_LEDGER_PATH": server.INTERACTION_FEEDBACK_LEDGER_PATH,
        "RESPONSE_EXAMPLES_PATH": server.RESPONSE_EXAMPLES_PATH,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="p193-feedback-turn-") as tmp:
            root = Path(tmp)
            server.DATA_DIR = root
            server.QUALITY_FEEDBACK_PATH = root / "quality_feedback.jsonl"
            server.INTERACTION_FEEDBACK_LEDGER_PATH = root / "interaction_feedback_ledger.jsonl"
            server.RESPONSE_EXAMPLES_PATH = root / "response_examples.json"

            private_marker = "PRIVATE" + "123"
            prompt = (
                "Compare two control architectures using https://example.com and "
                + "token"
                + "="
                + private_marker
                + "."
            )
            answer = "Use the distributed controller because its failure boundary is smaller."
            messages = [{"role": "user", "text": prompt, "messageId": "source-p193"}]
            route = {
                "projectId": "controls-engineering",
                "project": "Controls Engineering",
                "intentFrame": {
                    "domain": "knowledge_comparison",
                    "actionType": "compare",
                    "contextRelation": "new-request",
                    "evidenceNeed": "grounded",
                    "operationPlan": {
                        "readOnly": True,
                        "requiresConfirmation": False,
                        "allowedNow": ["research", "compare"],
                        "discussed": ["local controller"],
                    },
                },
                "capabilityPlan": {
                    "id": "generic-reasoned-comparison",
                    "handler_key": "model-first-comparison",
                    "executor": "local-model",
                    "review_policy": "reasoning-audit",
                    "access_level": "read-only",
                },
                "objectivePlan": {
                    "objectiveType": "engineering-comparison",
                    "responseKind": "decision-brief",
                    "evidenceNeed": "grounded",
                    "routeCandidates": ["reasoning", "research"],
                },
                "_turnLineageContract": {
                    "transition": "new-domain",
                    "decision": "accept",
                    "currentDomains": ["knowledge_comparison"],
                    "priorDomains": [],
                },
            }
            task = {
                "kind": "Engineering comparison",
                "role": "subject matter expert",
                "engine": "local-model",
                "hardGate": True,
                "mustDo": ["compare tradeoffs"],
                "requiredProof": ["operating assumptions"],
                "rejectIf": ["answers a different component"],
            }
            receipt = server.build_feedback_turn_receipt(
                messages,
                route,
                answer,
                "run-p193",
                "source-p193",
                task,
            )
            receipt_text = json.dumps(receipt, sort_keys=True)
            check("issued receipt is complete", receipt.get("receiptSha256") and receipt.get("taskSnapshotSha256"))
            check(
                "issued receipt is redacted and prose-free",
                prompt not in receipt_text
                and answer not in receipt_text
                and "example.com" not in receipt_text
                and private_marker not in receipt_text,
            )

            payload = {
                "rating": "fix",
                "feedbackProvenance": "human",
                "feedbackCategory": "misunderstood",
                "note": "The comparison used the wrong decision criterion.",
                "prompt": prompt,
                "answer": answer,
                "messages": messages,
                "route": {"projectId": "forged-client-project"},
                "runId": "run-p193",
                "sourceMessageId": "source-p193",
                "feedbackTurnReceipt": receipt,
            }
            validation = server.validate_feedback_turn_receipt(payload, prompt, answer)
            check("exact issued receipt validates", validation.get("status") == "verified")

            adversaries = {
                "wrong answer is rejected": {**payload, "answer": answer + " changed"},
                "wrong request is rejected": {**payload, "prompt": prompt + " changed"},
                "wrong run is rejected": {**payload, "runId": "run-other"},
                "wrong source message is rejected": {**payload, "sourceMessageId": "source-other"},
                "missing run and source binding is rejected": {
                    **payload,
                    "runId": "",
                    "sourceMessageId": "",
                },
            }
            for name, candidate in adversaries.items():
                result = server.validate_feedback_turn_receipt(
                    candidate,
                    candidate.get("prompt"),
                    candidate.get("answer"),
                )
                check(name, result.get("status") == "invalid", result.get("reason"))

            forged_receipt = copy.deepcopy(receipt)
            forged_receipt["taskSnapshot"]["intent"]["domain"] = "product_sourcing"
            forged_payload = {**payload, "feedbackTurnReceipt": forged_receipt}
            forged = server.validate_feedback_turn_receipt(forged_payload, prompt, answer)
            check("forged task snapshot is rejected", forged.get("status") == "invalid", forged.get("reason"))

            record = server.record_quality_feedback(payload)
            check(
                "verified classified correction promotes",
                server.feedback_is_durable_learning_eligible(record)
                and record.get("projectId") == "controls-engineering"
                and (record.get("route") or {}).get("intentDomain") == "knowledge_comparison"
                and (record.get("route") or {}).get("actionType") == "compare"
                and (record.get("route") or {}).get("capabilityId") == "generic-reasoned-comparison"
                and (record.get("taskSnapshot") or {}).get("operation", {}).get("readOnly") is True,
            )

            bare = server.record_quality_feedback(
                {
                    **payload,
                    "feedbackCategory": "",
                    "note": "",
                }
            )
            check(
                "bare Fix remains unclassified and cannot promote",
                bare.get("feedbackSignalClass") == "unclassified-negative"
                and bare.get("durableLearningEligible") is False
                and not bare.get("feedbackCategory")
                and (bare.get("diagnosis") or {}).get("failureKind") == "unclassified-negative-feedback",
            )

            legacy = server.record_quality_feedback(
                {
                    "rating": "fix",
                    "feedbackProvenance": "human",
                    "feedbackCategory": "too-generic",
                    "note": "Add the missing tradeoff.",
                    "prompt": prompt,
                    "answer": answer,
                    "messages": messages,
                    "route": route,
                }
            )
            check(
                "legacy feedback stays auditable but learning-ineligible",
                legacy.get("lineageStatus") == "legacy-insufficient"
                and not server.feedback_is_durable_learning_eligible(legacy)
                and legacy.get("interactionLedger"),
            )

            good = server.record_quality_feedback({**payload, "rating": "good", "feedbackCategory": "", "note": ""})
            check(
                "verified Good can retain structure only",
                server.feedback_is_durable_learning_eligible(good)
                and len(server.load_response_examples().get("items") or []) == 1,
            )

            captured = {}
            original_loop = server.run_wrong_answer_repair_loop
            try:
                def capture_loop(candidate, source="", record=True):
                    captured.update(candidate)
                    return {"ok": True, "record": {}, "diagnosis": {}, "goldenTest": None, "patchItem": None}

                server.run_wrong_answer_repair_loop = capture_loop
                natural = server.record_natural_correction_repair(
                    [
                        messages[0],
                        {
                            "role": "assistant",
                            "text": answer,
                            "runId": "run-p193",
                            "sourceMessageId": "source-p193",
                            "feedbackTurnReceipt": receipt,
                        },
                        {"role": "user", "text": "That was wrong because the load profile was omitted."},
                    ],
                    web_search="disabled",
                )
            finally:
                server.run_wrong_answer_repair_loop = original_loop
            check(
                "natural correction preserves typed lineage",
                natural
                and (captured.get("route") or {}).get("intentFrame", {}).get("domain") == "knowledge_comparison"
                and (captured.get("route") or {}).get("capabilityPlan", {}).get("id") == "generic-reasoned-comparison"
                and captured.get("feedbackTurnReceipt", {}).get("receiptSha256") == receipt.get("receiptSha256"),
            )

            focused = server.should_record_natural_correction(
                [],
                {
                    "correction": "It is the second controller.",
                    "answer": "Which controller do you mean? That choice would change the recommendation.",
                },
            )
            check("focused clarification answer is not failure evidence", focused is False)

            relevant = server.relevant_quality_feedback(messages, route, limit=10)
            relevant_ids = {item.get("id") for item in relevant}
            check(
                "only verified durable records influence future turns",
                record.get("id") in relevant_ids
                and good.get("id") in relevant_ids
                and bare.get("id") not in relevant_ids
                and legacy.get("id") not in relevant_ids,
            )

    finally:
        server.DATA_DIR = original["DATA_DIR"]
        server.QUALITY_FEEDBACK_PATH = original["QUALITY_FEEDBACK_PATH"]
        server.INTERACTION_FEEDBACK_LEDGER_PATH = original["INTERACTION_FEEDBACK_LEDGER_PATH"]
        server.RESPONSE_EXAMPLES_PATH = original["RESPONSE_EXAMPLES_PATH"]

    failed = [item for item in checks if not item["passed"]]
    print(
        json.dumps(
            {
                "suite": "p193-feedback-turn-receipt",
                "status": "pass" if not failed else "fail",
                "checkCount": len(checks),
                "passed": len(checks) - len(failed),
                "failed": len(failed),
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
