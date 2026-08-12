#!/usr/bin/env python3
"""P225 adversarial coverage for systemic live-smoke suite semantics."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def load_live_smoke_module():
    path = ROOT / "tools" / "live_feedback_smoke.py"
    spec = importlib.util.spec_from_file_location("p225_live_feedback_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGACY_AUDIT_EVIDENCE = {
    "ordinaryCaseCount": 190,
    "requiredSubstringCount": 2721,
    "presentationLabelOccurrenceCount": 313,
    "presentationLabelCaseCount": 158,
    "remainingExactSubstringCount": 2408,
    "historical-workflow": {
        "total": 83,
        "passed": 32,
        "failed": 51,
        "misses": 1299,
        "routeMismatches": 1,
        "adminMismatches": 17,
        "durationMinutes": 37.9,
    },
    "systemic-acceptance": {
        "total": 130,
        "passed": 66,
        "failed": 64,
        "misses": 228,
        "routeMismatches": 2,
        "adminMismatches": 3,
        "durationMinutes": 51.3,
    },
}


def binding(source):
    return {
        "kind": "live-smoke-source-binding",
        "version": 1,
        "stable": True,
        "sha256Prefix": source,
        "contentsRecorded": False,
    }


def receipt(
    ids,
    *,
    suite="systemic-acceptance",
    digest="inventory-digest",
    source="source-sha",
    failed=0,
    schema_version=2,
    qualifying=True,
    case_filter=None,
    expert=False,
    created_at=2_000_000_000.0 - 60,
):
    rows = [
        {"id": case_id, "ok": index >= failed}
        for index, case_id in enumerate(ids)
    ]
    passed = len(rows) - failed
    payload = {
        "createdAt": created_at,
        "status": "fail" if failed else "pass",
        "passed": passed,
        "failed": failed,
        "total": len(rows),
        "results": rows,
        "sourceBinding": binding(source),
        "caseFilter": list(case_filter or []),
        "expertConversation": expert,
    }
    if schema_version == 2:
        payload.update(
            {
                "schemaVersion": 2,
                "suite": suite,
                "qualifying": qualifying,
                "inventoryDigest": digest,
                "tierAggregates": {
                    suite: {"total": len(rows), "passed": passed, "failed": failed}
                },
                "diagnostics": {
                    "legacyShapeMissCount": 0,
                    "legacyShapeMissCaseCount": 0,
                },
            }
        )
    return payload


def main():
    live_smoke = load_live_smoke_module()
    checks = []

    def add(name, passed, detail=""):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )

    systemic_inventory = live_smoke.live_case_inventory(suite="systemic-acceptance")
    historical_inventory = live_smoke.live_case_inventory(suite="historical-workflow")
    all_inventory = live_smoke.live_case_inventory(suite="all")
    systemic_ids = systemic_inventory.get("defaultCaseIds") or []
    historical_ids = historical_inventory.get("defaultCaseIds") or []
    all_ids = all_inventory.get("defaultCaseIds") or []
    add(
        "inventory-is-exactly-130-systemic-plus-83-historical",
        len(systemic_ids) == 130
        and len(historical_ids) == 83
        and len(all_ids) == 213
        and not (set(systemic_ids) & set(historical_ids))
        and set(all_ids) == set(systemic_ids) | set(historical_ids)
        and historical_ids[0] == "codex-ui-improvement-status-receipts"
        and historical_ids[-1] == "ai-ui-gap-backlog-priority",
        {
            "systemic": len(systemic_ids),
            "historical": len(historical_ids),
            "all": len(all_ids),
        },
    )
    metadata = systemic_inventory.get("caseMetadata") or {}
    add(
        "central-metadata-covers-every-case-and-three-assertion-modes",
        set(metadata) == set(all_ids)
        and {item.get("suiteTier") for item in metadata.values()}
        == {"systemic-acceptance", "historical-workflow"}
        and {item.get("assertionMode") for item in metadata.values()}
        == {"structured", "required-facts", "legacy-exact"}
        and all(metadata[case_id].get("assertionMode") == "legacy-exact" for case_id in historical_ids),
        {"metadataCount": len(metadata)},
    )
    digest = systemic_inventory.get("inventoryDigest") or ""
    add(
        "inventory-digest-is-stable-and-suite-independent",
        len(digest) == 64
        and digest == historical_inventory.get("inventoryDigest")
        and digest == all_inventory.get("inventoryDigest")
        and digest == live_smoke.live_case_inventory().get("inventoryDigest"),
        digest,
    )

    ordinary_cases = live_smoke.live_cases()
    required_phrases = [
        phrase for case in ordinary_cases for phrase in case.get("required", [])
    ]
    presentation_occurrences = [
        phrase
        for phrase in required_phrases
        if phrase in live_smoke.LEGACY_PRESENTATION_ONLY_REQUIRED_PHRASES
    ]
    presentation_cases = [
        case
        for case in ordinary_cases
        if any(
            phrase in live_smoke.LEGACY_PRESENTATION_ONLY_REQUIRED_PHRASES
            for phrase in case.get("required", [])
        )
    ]
    add(
        "independent-required-substring-audit-is-preserved",
        len(ordinary_cases) == LEGACY_AUDIT_EVIDENCE["ordinaryCaseCount"]
        and len(required_phrases) == LEGACY_AUDIT_EVIDENCE["requiredSubstringCount"]
        and len(presentation_occurrences)
        == LEGACY_AUDIT_EVIDENCE["presentationLabelOccurrenceCount"]
        and len(presentation_cases)
        == LEGACY_AUDIT_EVIDENCE["presentationLabelCaseCount"]
        and len(required_phrases) - len(presentation_occurrences)
        == LEGACY_AUDIT_EVIDENCE["remainingExactSubstringCount"],
        LEGACY_AUDIT_EVIDENCE,
    )
    add(
        "legacy-receipt-tier-split-evidence-is-arithmetically-complete",
        LEGACY_AUDIT_EVIDENCE["historical-workflow"]["passed"]
        + LEGACY_AUDIT_EVIDENCE["historical-workflow"]["failed"]
        == 83
        and LEGACY_AUDIT_EVIDENCE["systemic-acceptance"]["passed"]
        + LEGACY_AUDIT_EVIDENCE["systemic-acceptance"]["failed"]
        == 130
        and LEGACY_AUDIT_EVIDENCE["historical-workflow"]["misses"] == 1299
        and LEGACY_AUDIT_EVIDENCE["systemic-acceptance"]["misses"] == 228
        and LEGACY_AUDIT_EVIDENCE["historical-workflow"]["durationMinutes"] == 37.9
        and LEGACY_AUDIT_EVIDENCE["systemic-acceptance"]["durationMinutes"] == 51.3,
        LEGACY_AUDIT_EVIDENCE,
    )

    base_case = {
        "id": "synthetic-systemic-case",
        "required": ["legacy answer shape"],
        "forbidden": ["unsafe disclosure"],
        "expectedProjectId": "expected-route",
        "expectedAdminTopicPath": "Expected / Controller",
        "expectedObjectiveType": "expected-objective",
        "expectedObjectiveResponseKind": "expected-response",
        "suiteTier": "systemic-acceptance",
        "assertionMode": "structured",
        "requiredFacts": [],
    }
    base_evidence = {
        "answer": "A truthful answer using a different presentation.",
        "returnCode": 0,
        "terminalEventSeen": True,
        "finalAssistantProof": live_smoke.final_assistant_proof(
            {
                "type": "assistant",
                "partial": False,
                "answerEnvelope": {
                    "status": "complete",
                    "terminal_state": {
                        "status": "complete",
                        "requestedStatus": "complete",
                        "mayClaimComplete": True,
                        "statusAdjusted": False,
                        "reasonCodes": [],
                    },
                },
            }
        ),
        "route": {
            "projectId": "expected-route",
            "objectivePlan": {
                "objectiveType": "expected-objective",
                "responseKind": "expected-response",
            },
        },
        "adminTopic": {"topicPath": "Expected / Controller"},
        "artifactEvidence": True,
    }

    diagnostic_shape = live_smoke.evaluate_case_evidence(base_case, base_evidence)
    add(
        "legacy-answer-shape-miss-is-diagnostic-for-systemic-results",
        diagnostic_shape.get("ok") is True
        and (diagnostic_shape.get("diagnostics") or {}).get("legacyShapeMisses")
        == ["legacy answer shape"]
        and not diagnostic_shape.get("acceptanceFailures"),
        diagnostic_shape,
    )

    fact_case = {
        **base_case,
        "assertionMode": "required-facts",
        "requiredFacts": ["42 volts"],
    }
    adversarial = {
        "missing-fact": live_smoke.evaluate_case_evidence(fact_case, base_evidence),
        "forbidden-text": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "answer": "Truthful, but unsafe disclosure."}
        ),
        "empty-answer": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "answer": ""}
        ),
        "wrong-route": live_smoke.evaluate_case_evidence(
            base_case,
            {**base_evidence, "route": {**base_evidence["route"], "projectId": "wrong"}},
        ),
        "wrong-controller": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "adminTopic": {"topicPath": "Wrong"}}
        ),
        "wrong-objective": live_smoke.evaluate_case_evidence(
            base_case,
            {
                **base_evidence,
                "route": {
                    **base_evidence["route"],
                    "objectivePlan": {
                        "objectiveType": "wrong",
                        "responseKind": "expected-response",
                    },
                },
            },
        ),
        "missing-terminal": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "terminalEventSeen": False}
        ),
        "bad-return-code": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "returnCode": 1}
        ),
        "bad-artifact": live_smoke.evaluate_case_evidence(
            base_case, {**base_evidence, "artifactEvidence": False}
        ),
    }
    expected_failures = {
        "missing-fact": "missing-required-fact",
        "forbidden-text": "forbidden-text",
        "empty-answer": "empty-answer",
        "wrong-route": "wrong-route",
        "wrong-controller": "wrong-controller",
        "wrong-objective": "wrong-objective",
        "missing-terminal": "missing-terminal-event",
        "bad-return-code": "bad-return-code",
        "bad-artifact": "bad-artifact-evidence",
    }
    for name, result in adversarial.items():
        add(
            f"{name}-fails-closed",
            result.get("ok") is False
            and expected_failures[name] in (result.get("acceptanceFailures") or []),
            result,
        )

    now = 2_000_000_000.0
    current_ids = ["case-a", "case-b"]
    exact = server.evaluate_live_feedback_smoke_receipt(
        receipt(current_ids),
        current_ids,
        now=now,
        freshness_seconds=7 * 24 * 60 * 60,
        current_source_sha="source-sha",
        current_inventory_digest="inventory-digest",
    )
    add(
        "only-exact-schema-v2-suite-digest-coverage-source-can-pass",
        exact.get("status") == "pass"
        and exact.get("acceptanceReady") is True
        and exact.get("schemaV2") is True
        and exact.get("suiteMatch") is True
        and exact.get("inventoryDigestMatch") is True
        and exact.get("exactCoverage") is True
        and exact.get("sourceMatch") is True,
        exact,
    )

    rejection_payloads = {
        "digest": receipt(current_ids, digest="wrong-digest"),
        "coverage": receipt(["case-a"]),
        "source": receipt(current_ids, source="wrong-source"),
        "focused": receipt(current_ids, qualifying=False, case_filter=["case-a"]),
        "expert": receipt(current_ids, qualifying=False, expert=True),
        "historical": receipt(
            current_ids, suite="historical-workflow", qualifying=False
        ),
        "schema-v1": receipt(current_ids, schema_version=1),
    }
    for name, payload in rejection_payloads.items():
        evaluated = server.evaluate_live_feedback_smoke_receipt(
            payload,
            current_ids,
            now=now,
            freshness_seconds=7 * 24 * 60 * 60,
            current_source_sha="source-sha",
            current_inventory_digest="inventory-digest",
        )
        add(
            f"{name}-receipt-never-qualifies-systemic-health",
            evaluated.get("status") != "pass"
            and evaluated.get("acceptanceReady") is not True,
            evaluated,
        )

    historical_failed_receipt = receipt(
        historical_ids,
        suite="historical-workflow",
        digest=digest,
        source="source-sha",
        failed=51,
        qualifying=False,
    )
    historical_evaluation = server.evaluate_live_feedback_smoke_receipt(
        historical_failed_receipt,
        historical_ids,
        now=now,
        freshness_seconds=7 * 24 * 60 * 60,
        current_source_sha="source-sha",
        current_inventory_digest=digest,
        expected_suite="historical-workflow",
    )
    synthetic_summary = {
        "status": "pass",
        "passed": 1,
        "total": 1,
        "items": [
            {
                "id": "live-feedback-smoke",
                "label": "Live Smoke · Systemic Acceptance",
                "status": "pass",
                "metric": "130/130 passed",
                "path": "/tmp/systemic.json",
                "age": "just now",
                "nextAction": "No action needed.",
            },
            {
                "id": "live-feedback-smoke-historical-workflow",
                "label": "Live Smoke · Historical Workflow",
                "status": "fail",
                "metric": historical_evaluation.get("metric"),
                "path": "/tmp/historical.json",
                "age": "just now",
                "nextAction": "Run live feedback smoke --suite historical-workflow.",
                "contributesToHealth": False,
            },
        ],
    }
    historical_answer = server.verification_receipts_direct_result(
        [
            {
                "role": "user",
                "text": "Which verification receipts are current and what needs rerunning?",
            }
        ],
        summary=synthetic_summary,
    ).get("answer", "")
    add(
        "historical-failures-remain-visible-without-contaminating-systemic-pass",
        historical_evaluation.get("status") == "fail"
        and "32 passed / 83 total; 51 failed" in historical_evaluation.get("metric", "")
        and synthetic_summary["status"] == "pass"
        and "130/130 passed" in historical_answer
        and "32 passed / 83 total; 51 failed" in historical_answer,
        {"evaluation": historical_evaluation, "answer": historical_answer},
    )

    old_ids = [f"old-case-{index:03d}" for index in range(213)]
    old_receipt = receipt(old_ids, failed=115, schema_version=1, source="source-sha")
    old_evaluation = server.evaluate_live_feedback_smoke_receipt(
        old_receipt,
        old_ids,
        now=now,
        freshness_seconds=7 * 24 * 60 * 60,
        current_source_sha="source-sha",
        current_inventory_digest=digest,
    )
    add(
        "old-98-of-213-schema-v1-receipt-never-turns-green",
        old_evaluation.get("status") != "pass"
        and old_evaluation.get("receiptClass") == "legacy-unclassified"
        and "98 passed / 213 total; 115 failed" in old_evaluation.get("metric", "")
        and "legacy unclassified" in old_evaluation.get("metric", ""),
        old_evaluation,
    )

    with tempfile.TemporaryDirectory(prefix="p225-selector-") as tmp_dir:
        root = Path(tmp_dir)
        exact_path = root / "20260810T100000Z-exact-live-feedback-smoke.json"
        focused_path = root / "20260810T100100Z-focused-live-feedback-smoke.json"
        historical_path = root / "20260810T100200Z-historical-workflow-live-feedback-smoke.json"
        v1_path = root / "20260810T100300Z-v1-live-feedback-smoke.json"
        exact_path.write_text(json.dumps(receipt(current_ids)) + "\n", encoding="utf-8")
        focused_path.write_text(
            json.dumps(receipt(current_ids, qualifying=False, case_filter=["case-a"])) + "\n",
            encoding="utf-8",
        )
        historical_path.write_text(
            json.dumps(receipt(current_ids, suite="historical-workflow", qualifying=False)) + "\n",
            encoding="utf-8",
        )
        v1_path.write_text(
            json.dumps(receipt(current_ids, schema_version=1)) + "\n",
            encoding="utf-8",
        )
        for index, path in enumerate((exact_path, focused_path, historical_path, v1_path), 1):
            os.utime(path, (1000 + index, 1000 + index))
        selected_systemic = server.latest_full_live_feedback_smoke_receipt(
            root,
            default_count=2,
            suite="systemic-acceptance",
            inventory_digest="inventory-digest",
        )
        selected_historical = server.latest_full_live_feedback_smoke_receipt(
            root,
            default_count=2,
            suite="historical-workflow",
            inventory_digest="inventory-digest",
        )
        selected_legacy = server.latest_legacy_unclassified_live_feedback_smoke_receipt(root)
    add(
        "selectors-separate-systemic-historical-and-legacy-receipts",
        selected_systemic == exact_path
        and selected_historical == historical_path
        and selected_legacy == v1_path,
        {
            "systemic": str(selected_systemic),
            "historical": str(selected_historical),
            "legacy": str(selected_legacy),
        },
    )

    original_fetch = live_smoke.fetch_server_source_identity
    try:
        live_smoke.fetch_server_source_identity = lambda _server: {
            "ok": True,
            "currentSha256": "source-sha",
            "currentSize": 100,
            "startedSha256": "source-sha",
            "startedSize": 100,
            "contentsRecorded": False,
        }
        with tempfile.TemporaryDirectory(prefix="p225-receipt-") as tmp_dir:
            args = SimpleNamespace(
                output_dir=tmp_dir,
                server="offline://p225",
                server_source_start=live_smoke.fetch_server_source_identity("offline://p225"),
                suite="systemic-acceptance",
                include_artifact_cases=False,
                include_source_vault_cases=False,
                include_local_evidence_cases=False,
                include_attachment_edit_case=False,
                include_steering_case=False,
                expert_conversation=False,
                case=[],
            )
            written = live_smoke.write_receipt(
                args,
                [{"id": case_id, "ok": True} for case_id in systemic_ids],
            )
            persisted = json.loads(
                Path(written["receiptPath"]).read_text(encoding="utf-8")
            )
    finally:
        live_smoke.fetch_server_source_identity = original_fetch
    systemic_aggregate = (persisted.get("tierAggregates") or {}).get(
        "systemic-acceptance"
    ) or {}
    add(
        "receipt-writer-emits-qualifying-schema-v2-systemic-identity",
        persisted.get("schemaVersion") == 2
        and persisted.get("suite") == "systemic-acceptance"
        and persisted.get("qualifying") is True
        and persisted.get("inventoryDigest") == digest
        and persisted.get("exactCoverage") is True
        and systemic_aggregate
        == {"total": 130, "passed": 130, "failed": 0}
        and isinstance(persisted.get("diagnostics"), dict)
        and (persisted.get("sourceBinding") or {}).get("stable") is True,
        {
            "schemaVersion": persisted.get("schemaVersion"),
            "suite": persisted.get("suite"),
            "qualifying": persisted.get("qualifying"),
            "aggregate": systemic_aggregate,
        },
    )

    server_text = (ROOT / "server.py").read_text(encoding="utf-8")
    app_text = (ROOT / "app.js").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "admin-and-direct-ui-consume-separate-truthful-tier-metrics",
        "live-feedback-smoke-historical-workflow" in server_text
        and '"contributesToHealth": False' in server_text
        and "qualifying receipt groups are green" in server_text
        and "qualifying receipts" in app_text,
        "separate systemic/historical verification presentation",
    )
    add(
        "p225-is-one-package-health-check-and-public-export-tool",
        '"server:live-smoke-suite-semantics-p225"' in server_text
        and '"p225_live_smoke_suite_semantics_smoke.py"' in server_text
        and export_text.count(
            '"tools/p225_live_smoke_suite_semantics_smoke.py"'
        )
        == 1,
        "one package-health registration and one export allowlist entry",
    )

    failures = [check for check in checks if check.get("status") != "pass"]
    report = {
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "legacyAuditEvidence": LEGACY_AUDIT_EVIDENCE,
        "inventoryDigest": digest,
        "failures": failures,
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
