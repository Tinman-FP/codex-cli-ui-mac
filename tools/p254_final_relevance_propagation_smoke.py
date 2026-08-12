#!/usr/bin/env python3
"""P254 route-to-final source-bound relevance propagation adversaries."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from answer_envelope import answer_relevance_contract, build_template_ownership_receipt  # noqa: E402


class CaptureHandler:
    def __init__(self, run_id):
        self.current_run_id = run_id
        self.current_web_search = "disabled"
        self.current_cwd = str(ROOT)
        self.path = "/synthetic/p254"
        self.wfile = io.BytesIO()

    def send_response(self, *_args):
        return None

    def send_header(self, *_args):
        return None

    def end_headers(self):
        return None


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

    run_id = "p254-final-propagation"
    messages = [{"role": "user", "text": "Which asset is staged?"}]
    route = {
        "projectId": "synthetic-release-ledger",
        "project": "Synthetic Release Ledger",
        "_liveRunId": run_id,
        "intentFrame": {
            "domain": "bounded_specialist_capability",
            "originalDomain": "release-ledger",
            "lineageDomain": "release-ledger",
            "operationPlan": {
                "readOnly": True,
                "allowedNow": [],
                "prohibited": ["edit"],
                "requiresConfirmation": False,
            },
            "outputContract": {
                "mode": "conversation-answer",
                "binding": "no-authorized-artifact-output",
            },
        },
        "capabilityPlan": {
            "id": "bounded-specialist-capability",
            "registered": True,
            "executor": "deterministic",
            "execution_binding": "router",
            "handler_key": "bounded_specialist_direct",
            "relevance_policy": "template-ownership-required",
            "review_policy": "deterministic",
        },
        "allowLocalWrites": False,
        "_testRun": True,
    }
    server.bind_response_turn_lineage(
        messages,
        route,
        run_id=run_id,
        active_messages=messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    base_answer = (
        "Artifact amber-42 is the staged candidate after manifest verification."
    )
    packet = server.compose_controller_owned_direct_result(
        messages,
        route,
        {
            "mode": "release-ledger-direct-answer",
            "engine": "local-knowledge",
            "accessLevel": "local-read-only",
            "answer": base_answer,
            "returnCode": 0,
            "outcome": "completed",
        },
    )
    source_answer = str(packet.get("answer") or "")
    contract = server.active_answer_relevance_task_contract(messages, route)
    ownership = build_template_ownership_receipt(
        receipt_id="template-p254-final-propagation",
        run_id=run_id,
        template_id="bounded-specialist:release-ledger",
        latest_user_intent=server.latest_user_text(messages),
        task_contract=contract,
        owner_domain="release-ledger",
        supported_domains=["release-ledger"],
        concepts=["release ledger", "artifact amber-42", "staged candidate"],
        turn_lineage_digest=(route.get("_turnLineageContract") or {}).get(
            "lineageDigest"
        ),
        bound_output=source_answer,
    )
    observation_text = (
        "Artifact amber-42 is the staged candidate after manifest verification."
    )
    observation = {
        "kind": "source-observation",
        "sourceType": "runtime-state",
        "locator": "runtime://synthetic/release-ledger",
        "sourceId": "synthetic-release-ledger",
        "text": observation_text,
        "excerpt": observation_text,
        "contentSha256": hashlib.sha256(
            observation_text.encode("utf-8")
        ).hexdigest(),
        "observedAt": "2026-08-11T17:15:00Z",
    }
    packet.update(
        {
            "handled": True,
            "returnCode": 0,
            "outcome": "completed",
            "textLocked": True,
            "templateOwnership": ownership,
            "sourceObservations": [observation],
            "sourceReceipts": [],
        }
    )
    initial_relevance = answer_relevance_contract(
        source_answer,
        run_id=run_id,
        latest_user_intent=server.latest_user_text(messages),
        intent_domain=server.selected_answer_domain(route),
        task_contract=contract,
        template_ownership=ownership,
        turn_lineage=route.get("_turnLineageContract") or {},
        require_template_ownership=True,
    )
    route["_answerRelevanceContract"] = initial_relevance
    route["_capabilityExecution"] = {
        "executor": "deterministic",
        "handlerKey": "bounded_specialist_direct",
        "handled": True,
        "outcome": "completed",
        "missing": [],
        "error": "",
        "templateOwnership": ownership,
        "sourceReceipts": [],
        "answerRelevance": initial_relevance,
    }

    handler = CaptureHandler(run_id)
    server.emit_typed_capability_response(
        handler,
        messages,
        route,
        {"testRun": True},
        packet,
        cwd=str(ROOT),
        profile="manager",
        effective_profile="local-oss",
        reasoning_level="medium",
        web_search="disabled",
        manager_depth="fast",
        friendliness_level="warm",
        humor_level="light",
        free_only_redirect=False,
    )
    events = [
        json.loads(line)
        for line in handler.wfile.getvalue().decode("utf-8").splitlines()
        if line.strip()
    ]
    assistant = next((item for item in events if item.get("type") == "assistant"), {})
    done = next((item for item in events if item.get("type") == "done"), {})
    final_answer = str(assistant.get("text") or "")
    final_relevance = route.get("_answerRelevanceContract") or {}
    rebinding = route.get("_deterministicSourceAnswerRebinding") or {}
    add(
        "route-pass-propagates-through-renderer-to-final-envelope-and-rc0",
        initial_relevance.get("status") == "pass"
        and final_answer.startswith(source_answer)
        and final_answer != source_answer
        and rebinding.get("status") == "pass"
        and rebinding.get("mayRebind") is True
        and final_relevance.get("status") == "pass"
        and final_relevance.get("sourceBoundLatestTurnSatisfied") is True
        and final_relevance.get("templateOutputBound") is True
        and (assistant.get("answerEnvelope") or {}).get("status") == "complete"
        and done.get("returnCode") == 0,
        {
            "routeStatus": initial_relevance.get("status"),
            "rebindingStatus": rebinding.get("status"),
            "finalStatus": final_relevance.get("status"),
            "terminal": (assistant.get("answerEnvelope") or {}).get("status"),
            "returnCode": done.get("returnCode"),
        },
    )

    final_receipts = server.response_source_receipts(
        final_answer,
        route,
        [observation],
        run_id=run_id,
    )
    source_receipt_ids = [
        str(item.get("receiptId") or "") for item in final_receipts
    ]

    def adversary(name, mutate, expected_issue, *, answer=final_answer):
        candidate = copy.deepcopy(route)
        mutate(candidate)
        receipt = candidate.get("_deterministicSourceAnswerRebinding") or {}
        issues = server.deterministic_source_answer_rebinding_issues(
            messages,
            candidate,
            answer,
            run_id=run_id,
            task_contract_value=contract,
            ownership=ownership,
            source_receipt_ids=source_receipt_ids,
        )
        context = server.specialist_answer_relevance_context(
            messages,
            candidate,
            run_id=run_id,
            answer=answer,
            evidence=[observation],
            source_receipts=server.response_source_receipts(
                answer,
                candidate,
                [observation],
                run_id=run_id,
            ),
        )
        relevance = answer_relevance_contract(answer, run_id=run_id, **context)
        add(
            f"{name}-rebinding-fails-closed",
            expected_issue in issues
            and relevance.get("status") == "replan"
            and relevance.get("templateOutputBound") is False,
            {"issues": issues, "relevanceIssues": relevance.get("issues") or []},
        )

    def stale(candidate):
        receipt = candidate["_deterministicSourceAnswerRebinding"]
        receipt["runId"] = "stale-run"
        receipt["bindingSha256"] = server.deterministic_source_answer_rebinding_sha256(
            receipt
        )

    adversary(
        "stale",
        stale,
        "deterministic-source-answer-rebinding-run-mismatch",
    )
    adversary(
        "tampered",
        lambda candidate: candidate["_deterministicSourceAnswerRebinding"].__setitem__(
            "finalAnswerSha256", "0" * 64
        ),
        "deterministic-source-answer-rebinding-integrity-mismatch",
    )

    def wrong_task(candidate):
        receipt = candidate["_deterministicSourceAnswerRebinding"]
        receipt["taskContractDigest"] = "1" * 64
        receipt["bindingSha256"] = server.deterministic_source_answer_rebinding_sha256(
            receipt
        )

    adversary(
        "wrong-task",
        wrong_task,
        "deterministic-source-answer-rebinding-task-mismatch",
    )
    adversary(
        "wrong-answer",
        lambda _candidate: None,
        "deterministic-source-answer-rebinding-answer-mismatch",
        answer=final_answer + " Changed after binding.",
    )

    def write_capable(candidate):
        candidate["intentFrame"]["operationPlan"]["readOnly"] = False

    adversary(
        "write-capable",
        write_capable,
        "deterministic-source-answer-rebinding-not-read-only",
    )

    server_source = (ROOT / "server.py").read_text(encoding="utf-8")
    export_source = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "p254-package-and-export-registration",
        "server:final-relevance-propagation-p254" in server_source
        and "tools/p254_final_relevance_propagation_smoke.py" in export_source,
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
