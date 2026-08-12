#!/usr/bin/env python3
"""Focused P221 coverage for source-bound live-smoke verification receipts."""

import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


INVENTORY_DIGEST = "p221-synthetic-systemic-inventory"


def load_live_smoke_module():
    path = ROOT / "tools" / "live_feedback_smoke.py"
    spec = importlib.util.spec_from_file_location("p221_live_feedback_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_identity(sha="abcdef123456", size=1000, ok=True):
    return {
        "ok": ok,
        "startedSha256": sha,
        "currentSha256": sha,
        "startedSize": size,
        "currentSize": size,
        "reason": "running source matches disk" if ok else "source changed",
        "contentsRecorded": False,
    }


def receipt(binding, *, failed=0):
    results = [
        {"id": "case-a", "ok": True},
        {"id": "case-b", "ok": failed == 0},
    ]
    return {
        "schemaVersion": 2,
        "createdAt": time.time(),
        "status": "fail" if failed else "pass",
        "suite": "systemic-acceptance",
        "qualifying": True,
        "inventoryDigest": INVENTORY_DIGEST,
        "passed": len(results) - failed,
        "failed": failed,
        "total": len(results),
        "tierAggregates": {
            "systemic-acceptance": {
                "passed": len(results) - failed,
                "failed": failed,
                "total": len(results),
            }
        },
        "results": results,
        "diagnostics": {"legacyShapeMissCount": 0},
        "sourceBinding": binding,
    }


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

    stable_binding = live_smoke.live_smoke_source_binding(
        source_identity(),
        source_identity(),
    )
    add(
        "stable-start-and-completion-bind-one-source",
        stable_binding.get("stable") is True
        and stable_binding.get("sha256Prefix") == "abcdef123456"
        and stable_binding.get("contentsRecorded") is False,
        stable_binding,
    )

    changed_binding = live_smoke.live_smoke_source_binding(
        source_identity("abcdef123456"),
        source_identity("111111111111"),
    )
    add(
        "source-change-during-run-fails-binding-closed",
        changed_binding.get("stable") is False
        and not changed_binding.get("sha256Prefix"),
        changed_binding,
    )

    matching_pass = server.evaluate_live_feedback_smoke_receipt(
        receipt(stable_binding),
        ["case-a", "case-b"],
        current_source_sha="abcdef123456",
        current_inventory_digest=INVENTORY_DIGEST,
    )
    add(
        "matching-source-zero-failure-receipt-can-pass",
        matching_pass.get("status") == "pass"
        and matching_pass.get("sourceMatch") is True
        and matching_pass.get("nextAction") == "No action needed.",
        matching_pass,
    )

    matching_failure = server.evaluate_live_feedback_smoke_receipt(
        receipt(stable_binding, failed=1),
        ["case-a", "case-b"],
        current_source_sha="abcdef123456",
        current_inventory_digest=INVENTORY_DIGEST,
    )
    add(
        "matching-source-failure-remains-fail",
        matching_failure.get("status") == "fail"
        and "1 failed" in str(matching_failure.get("metric") or ""),
        matching_failure,
    )

    mismatched_failure = server.evaluate_live_feedback_smoke_receipt(
        receipt(stable_binding, failed=1),
        ["case-a", "case-b"],
        current_source_sha="222222222222",
        current_inventory_digest=INVENTORY_DIGEST,
    )
    add(
        "mismatched-source-failure-is-historical-warning-not-current-fail",
        mismatched_failure.get("status") == "warn"
        and "1 failed" in str(mismatched_failure.get("metric") or "")
        and "source mismatch" in str(mismatched_failure.get("metric") or "")
        and "does not match active source" in str(mismatched_failure.get("detail") or ""),
        mismatched_failure,
    )

    unbound_failure = server.evaluate_live_feedback_smoke_receipt(
        receipt({}, failed=1),
        ["case-a", "case-b"],
        current_source_sha="abcdef123456",
        current_inventory_digest=INVENTORY_DIGEST,
    )
    add(
        "unbound-failure-retains-count-and-requires-rerun",
        unbound_failure.get("status") == "warn"
        and "1 failed" in str(unbound_failure.get("metric") or "")
        and "historical evidence" in str(unbound_failure.get("detail") or "")
        and unbound_failure.get("nextAction") == "Run live feedback smoke.",
        unbound_failure,
    )

    readiness = server.readiness_health_report()
    readiness_source = readiness.get("serverSource") or {}
    add(
        "fast-readiness-exposes-server-source-identity",
        isinstance(readiness_source, dict)
        and bool(readiness_source.get("currentSha256"))
        and readiness_source.get("ok") is True,
        readiness_source,
    )

    original_fetch = live_smoke.fetch_server_source_identity
    try:
        live_smoke.fetch_server_source_identity = lambda _server: source_identity()
        with tempfile.TemporaryDirectory(prefix="p221-live-smoke-receipt-") as tmp_dir:
            args = SimpleNamespace(
                output_dir=tmp_dir,
                server="http://127.0.0.1:8765",
                server_source_start=source_identity(),
                include_artifact_cases=False,
                include_source_vault_cases=False,
                include_local_evidence_cases=False,
                include_attachment_edit_case=False,
                include_steering_case=False,
                expert_conversation=False,
                suite="systemic-acceptance",
                case=["case-a"],
            )
            written = live_smoke.write_receipt(
                args,
                [{"id": "case-a", "ok": True}],
            )
            persisted = json.loads(Path(written["receiptPath"]).read_text(encoding="utf-8"))
        persisted_binding = persisted.get("sourceBinding") or {}
    finally:
        live_smoke.fetch_server_source_identity = original_fetch
    add(
        "receipt-writer-persists-source-binding",
        persisted_binding.get("stable") is True
        and persisted_binding.get("sha256Prefix") == "abcdef123456",
        persisted_binding,
    )

    summary = server.verification_summary()
    summary_items = {item.get("id"): item for item in summary.get("items") or []}
    historical = summary_items.get("live-feedback-smoke-historical-workflow") or {}
    add(
        "existing-unbound-full-receipt-is-truthful-historical-warning",
        historical.get("status") == "warn"
        and "115 failed" in str(historical.get("metric") or "")
        and "legacy unclassified" in str(historical.get("metric") or "")
        and "Schema-v1 receipt migrated" in str(historical.get("detail") or ""),
        historical,
    )

    failures = [check for check in checks if check.get("status") != "pass"]
    report = {
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
