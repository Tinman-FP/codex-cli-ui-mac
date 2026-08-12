#!/usr/bin/env python3
"""P224 regressions for truthful shared verification-count presentation."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


ACTIVE_SOURCE = "abcdef123456"
CURRENT_IDS = ["case-a", "case-b", "case-c"]
INVENTORY_DIGEST = "p224-synthetic-systemic-inventory"


def binding(source=ACTIVE_SOURCE):
    return {
        "kind": "live-smoke-source-binding",
        "version": 1,
        "stable": True,
        "sha256Prefix": source,
        "contentsRecorded": False,
    }


def evaluate(payload):
    return server.evaluate_live_feedback_smoke_receipt(
        payload,
        CURRENT_IDS,
        now=2_000_000_000.0,
        freshness_seconds=7 * 24 * 60 * 60,
        current_source_sha=ACTIVE_SOURCE,
        current_inventory_digest=INVENTORY_DIGEST,
    )


def receipt(*, passed, failed, total, results, source_binding=None, status=None):
    return {
        "schemaVersion": 2,
        "createdAt": 2_000_000_000.0 - 60,
        "status": status or ("fail" if failed else "pass"),
        "suite": "systemic-acceptance",
        "qualifying": True,
        "inventoryDigest": INVENTORY_DIGEST,
        "passed": passed,
        "failed": failed,
        "total": total,
        "tierAggregates": {
            "systemic-acceptance": {
                "passed": passed,
                "failed": failed,
                "total": total,
            }
        },
        "results": results,
        "diagnostics": {"legacyShapeMissCount": 0},
        "sourceBinding": binding() if source_binding is None else source_binding,
    }


all_pass_results = [
    {"id": "case-a", "ok": True},
    {"id": "case-b", "ok": True},
    {"id": "case-c", "ok": True},
]
partial_results = [
    {"id": "case-a", "ok": True},
    {"id": "case-b", "ok": True},
    {"id": "case-c", "ok": False},
]

all_pass = evaluate(
    receipt(passed=3, failed=0, total=3, results=all_pass_results)
)
check(
    "all-pass-uses-total-over-total-only-with-passed-label",
    all_pass.get("status") == "pass"
    and all_pass.get("metric") == "3/3 passed"
    and (all_pass.get("presentation") or {}).get("kind") == "all-pass",
    all_pass,
)

partial = evaluate(
    receipt(passed=2, failed=1, total=3, results=partial_results)
)
check(
    "partial-failure-displays-passed-failed-and-total",
    partial.get("status") == "fail"
    and partial.get("metric") == "2 passed / 3 total; 1 failed"
    and "3/3" not in partial.get("metric", ""),
    partial,
)

unbound = evaluate(
    receipt(
        passed=2,
        failed=1,
        total=3,
        results=partial_results,
        source_binding={},
    )
)
check(
    "source-unbound-retains-exact-historical-counts-and-rerun",
    unbound.get("status") == "warn"
    and unbound.get("metric")
    == "2 passed / 3 total; 1 failed; source unbound"
    and unbound.get("nextAction") == "Run live feedback smoke.",
    unbound,
)

mismatched = evaluate(
    receipt(
        passed=2,
        failed=1,
        total=3,
        results=partial_results,
        source_binding=binding("111111111111"),
    )
)
check(
    "source-mismatch-retains-exact-historical-counts-and-rerun",
    mismatched.get("status") == "warn"
    and mismatched.get("metric")
    == "2 passed / 3 total; 1 failed; source mismatch"
    and mismatched.get("nextAction") == "Run live feedback smoke.",
    mismatched,
)

missing_totals_payload = {
    "schemaVersion": 2,
    "createdAt": 2_000_000_000.0 - 60,
    "status": "fail",
    "suite": "systemic-acceptance",
    "qualifying": True,
    "inventoryDigest": INVENTORY_DIGEST,
    "tierAggregates": {},
    "results": partial_results,
    "diagnostics": {"legacyShapeMissCount": 0},
    "sourceBinding": binding(),
}
missing_totals = evaluate(missing_totals_payload)
check(
    "missing-or-unknown-totals-never-invent-counts",
    missing_totals.get("status") == "fail"
    and missing_totals.get("metric", "").startswith(
        "counts unknown: unknown passed / unknown total; unknown failed"
    )
    and "observed results: 2 passed / 3 total; 1 failed"
    in missing_totals.get("metric", "")
    and (missing_totals.get("presentation") or {}).get("known") is False
    and (missing_totals.get("presentation") or {}).get("receiptConsistent") is False,
    missing_totals,
)

inconsistent_arithmetic = evaluate(
    receipt(passed=3, failed=1, total=3, results=partial_results)
)
check(
    "inconsistent-arithmetic-fails-closed-with-declared-values-visible",
    inconsistent_arithmetic.get("status") == "fail"
    and inconsistent_arithmetic.get("metric", "").startswith(
        "counts inconsistent: 3 passed / 3 total; 1 failed"
    )
    and (inconsistent_arithmetic.get("presentation") or {}).get(
        "arithmeticConsistent"
    )
    is False,
    inconsistent_arithmetic,
)

impossible_negative = evaluate(
    receipt(passed=4, failed=-1, total=3, results=partial_results, status="fail")
)
check(
    "impossible-negative-count-fails-closed-as-unknown",
    impossible_negative.get("status") == "fail"
    and impossible_negative.get("metric", "").startswith(
        "counts unknown: 4 passed / 3 total; unknown failed"
    )
    and (impossible_negative.get("presentation") or {}).get("known") is False,
    impossible_negative,
)

result_count_mismatch = evaluate(
    receipt(passed=3, failed=0, total=3, results=partial_results, status="pass")
)
check(
    "result-versus-summary-mismatch-cannot-render-all-pass",
    result_count_mismatch.get("status") == "fail"
    and result_count_mismatch.get("metric", "").startswith(
        "counts inconsistent: 3 passed / 3 total; 0 failed"
    )
    and "observed results: 2 passed / 3 total; 1 failed"
    in result_count_mismatch.get("metric", "")
    and result_count_mismatch.get("metric") != "3/3 passed",
    result_count_mismatch,
)

production_scale = server.verification_receipt_count_presentation(98, 115, 213)
check(
    "production-scale-partial-counts-preserve-98-115-213-arithmetic",
    production_scale.get("metric") == "98 passed / 213 total; 115 failed"
    and production_scale.get("arithmeticConsistent") is True,
    production_scale,
)

deceptive_metric = "213/213 current cases, 115 failed, source unbound"
safe_metric = "98 passed / 213 total; 115 failed; source unbound"
synthetic_summary = {
    "status": "warn",
    "passed": 0,
    "total": 1,
    "items": [
        {
            "id": "live-feedback-smoke",
            "label": "Live Smoke",
            "status": "warn",
            "metric": deceptive_metric,
            "presentation": {
                **production_scale,
                "metric": safe_metric,
                "sourceState": "unbound",
            },
            "age": "just now",
            "nextAction": "Run live feedback smoke.",
            "path": "",
        }
    ],
}
direct = server.verification_receipts_direct_result(
    [
        {
            "role": "user",
            "text": "Which verification receipts are current, and what needs to be rerun?",
        }
    ],
    summary=synthetic_summary,
)
check(
    "deterministic-direct-answer-consumes-shared-presentation",
    safe_metric in direct.get("answer", "")
    and deceptive_metric not in direct.get("answer", "")
    and "Run live feedback smoke." in direct.get("answer", ""),
    direct.get("answer"),
)

original_summary = server.verification_summary
original_artifacts = server.local_improvement_status_artifacts
try:
    server.verification_summary = lambda: synthetic_summary
    server.local_improvement_status_artifacts = lambda: {
        "smokePassed": 98,
        "smokeFailed": 115,
        "smokeTotal": 213,
        "auditPass": 0,
        "auditPartial": 0,
        "auditReview": 0,
        "auditTotal": 0,
    }
    bundle_answer = server.latest_receipts_bundle_direct_answer(
        [
            {
                "role": "user",
                "text": "Bundle the latest receipts for Codex CLI UI before release.",
            }
        ]
    )
    status_answer = server.codex_ui_improvement_status_direct_answer(
        [
            {
                "role": "user",
                "text": "How are we doing on Codex CLI UI testing and total completion?",
            }
        ]
    )
finally:
    server.verification_summary = original_summary
    server.local_improvement_status_artifacts = original_artifacts
check(
    "other-deterministic-verification-views-consume-shared-presentation",
    safe_metric in bundle_answer
    and safe_metric in status_answer
    and deceptive_metric not in bundle_answer
    and deceptive_metric not in status_answer,
    {"bundle": bundle_answer, "status": status_answer},
)

summary = server.verification_summary()
summary_items = {item.get("id"): item for item in summary.get("items") or []}
live_item = summary_items.get("live-feedback-smoke") or {}
live_metric = server.verification_receipt_item_metric(live_item)
failed_count = (live_item.get("presentation") or {}).get("failed")
check(
    "verification-summary-api-exposes-one-controller-owned-presentation",
    isinstance(live_item.get("presentation"), dict)
    and live_item.get("metric") == live_metric
    and (
        not isinstance(failed_count, int)
        or failed_count == 0
        or re.search(r"\b\d+ passed / \d+ total; \d+ failed\b", live_metric)
        or live_metric.startswith("counts ")
    ),
    live_item,
)

app_text = (ROOT / "app.js").read_text(encoding="utf-8")
check(
    "admin-ui-card-consumes-shared-presentation-helper",
    "function verificationReceiptMetric(item)" in app_text
    and "presentation.metric" in app_text
    and "metric.textContent = verificationReceiptMetric(item);" in app_text,
    "verificationReceiptMetric wiring",
)

for name, evaluation in {
    "partial": partial,
    "unbound": unbound,
    "mismatched": mismatched,
    "missing": missing_totals,
    "inconsistent": inconsistent_arithmetic,
    "impossible": impossible_negative,
    "resultMismatch": result_count_mismatch,
}.items():
    check(
        f"{name}-cannot-visually-claim-total-over-total-beside-failures",
        not re.search(
            r"\b(?P<count>\d+)\s*/\s*(?P=count)\b[^\n]*\b(?:[1-9]\d*) failed\b",
            evaluation.get("metric", ""),
        ),
        evaluation.get("metric"),
    )

failures = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failures else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failures),
    "failed": len(failures),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failures else 1)
