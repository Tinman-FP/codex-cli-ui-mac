#!/usr/bin/env python3
"""P220 regressions for package-health timeout headroom and state isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


source = (ROOT / "server.py").read_text(encoding="utf-8")
package_start = source.index("def package_health_report():")
package_end = source.index("def persist_isolated_package_health_report", package_start)
package_source = source[package_start:package_end]

check(
    "slow-focused-smokes-have-contention-headroom",
    server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS >= 30
    and '"p186_nonnumeric_comparison_contract_smoke.py"' in package_source
    and 'package_quiescent_smoke_run(\n            "routing:typed-output-authority-p191"' in package_source
    and [
        item.get("checkName")
        for item in server.package_health_quiescent_smoke_specs()
    ]
    == ["routing:typed-output-authority-p191"]
    and "routing:typed-output-authority-p191" not in {
        item.get("checkName")
        for item in server.package_health_parallel_smoke_specs()
    }
    and package_source.count(
        "timeout=PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS"
    )
    >= 3,
    {
        "timeoutSeconds": server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS,
    },
)

clean_receipt = server.run_isolated_package_health_boolean_check(
    "typed_engineering_capability_coverage_synthetic_check"
)
check(
    "allowlisted-synthetic-runs-in-clean-interpreter",
    clean_receipt.get("ok") is True
    and clean_receipt.get("returnCode") == 0
    and clean_receipt.get("timedOut") is False
    and clean_receipt.get("contentsRecorded") is False,
    clean_receipt,
)

original_check = server.typed_engineering_capability_coverage_synthetic_check
try:
    def contaminated_parent_check():
        raise TypeError("can only join an iterable")

    server.typed_engineering_capability_coverage_synthetic_check = (
        contaminated_parent_check
    )
    contaminated_parent_receipt = server.run_isolated_package_health_boolean_check(
        "typed_engineering_capability_coverage_synthetic_check"
    )
finally:
    server.typed_engineering_capability_coverage_synthetic_check = original_check

check(
    "parent-state-contamination-cannot-change-isolated-result",
    contaminated_parent_receipt.get("ok") is True
    and contaminated_parent_receipt.get("returnCode") == 0
    and not contaminated_parent_receipt.get("error"),
    contaminated_parent_receipt,
)

denied_receipt = server.run_isolated_package_health_boolean_check(
    "arbitrary_unregistered_synthetic"
)
check(
    "isolation-runner-is-explicitly-allowlisted",
    denied_receipt.get("ok") is False
    and denied_receipt.get("returnCode") == 1
    and denied_receipt.get("durationMs") == 0
    and "not allowlisted" in denied_receipt.get("error", ""),
    denied_receipt,
)

check(
    "package-row-consumes-isolated-receipt",
    '"server:package-health-harness-isolation-p220"' in package_source
    and "typed_engineering_check = run_isolated_package_health_boolean_check(" in package_source
    and '"typed_engineering_capability_coverage_synthetic_check"' in package_source
    and '"pass" if typed_engineering_check.get("ok") else "fail"' in package_source,
)

export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "p220-smoke-is-in-public-export-contract",
    '"tools/p220_package_health_harness_smoke.py"' in export_source,
)

check(
    "verification-summary-does-not-promote-prior-receipt-during-worker",
    server.verification_package_receipt_status(
        "552/552",
        0,
        worker_active=True,
    )
    == "unknown"
    and server.verification_package_receipt_status(
        "552/552",
        0,
        worker_active=False,
    )
    == "pass",
)

failed_checks = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed_checks else "fail",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed_checks),
            "failed": len(failed_checks),
            "failures": failed_checks,
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed_checks else 0)
