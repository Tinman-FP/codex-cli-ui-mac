#!/usr/bin/env python3
"""P256 adversaries for the bounded CPU-isolated package resource lane."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


parser = argparse.ArgumentParser()
parser.add_argument("--run-production", action="store_true")
args = parser.parse_args()

checks = []


def check(name, passed, detail=None):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


baseline_path = ROOT / "data" / "package_health_latest.json"
baseline_bytes = baseline_path.read_bytes()
baseline_sha256 = hashlib.sha256(baseline_bytes).hexdigest()
baseline = json.loads(baseline_bytes)
baseline_checks = baseline.get("checks") or []
baseline_names = [str(item.get("name") or "") for item in baseline_checks]
preserved_baseline_names = sorted(
    name
    for name in baseline_names
    if name
    not in {
        "server:package-resource-scheduler-p256",
        "server:verification-telemetry-isolation-p257",
    }
)
preserved_inventory_sha256 = hashlib.sha256(
    json.dumps(preserved_baseline_names, separators=(",", ":")).encode("utf-8")
).hexdigest()
check(
    "prior-authoritative-inventory-is-unique-and-complete-without-green-circularity",
    len(baseline_names) == len(set(baseline_names))
    and len(preserved_baseline_names) == 579
    and preserved_inventory_sha256
    == "0beae1d19d0dfcf7234e836a97d8a8ce16232528b6d8f9635e5de943d949b3b1",
    {
        "receiptSha256": baseline_sha256,
        "status": baseline.get("status"),
        "total": baseline.get("total"),
        "uniqueNames": len(set(baseline_names)),
        "preservedInventorySha256": preserved_inventory_sha256,
    },
)


resource_specs = server.package_health_resource_smoke_specs()
resource_names = [str(item.get("checkName") or "") for item in resource_specs]
resource_invocations = [str(item.get("invocationSha256") or "") for item in resource_specs]
resource_functions = [str((item.get("command") or ["", "", ""])[2]) for item in resource_specs]
check(
    "resource-inventory-preserves-all-original-package-row-identities",
    len(resource_specs) == 23
    and len(set(resource_names)) == len(resource_specs)
    and set(resource_names).issubset(set(baseline_names))
    and len(set(resource_invocations)) == len(resource_specs)
    and set(resource_functions) == set(server.PACKAGE_HEALTH_RESOURCE_SYNTHETIC_CHECKS)
    and all(
        item.get("sourceSha256")
        == server.current_verification_receipt_snapshot_source_sha256()
        and item.get("inputSha256")
        and item.get("isolation") == "process"
        and item.get("sideEffectFree") is True
        and item.get("timeout")
        == server.PACKAGE_HEALTH_RESOURCE_SMOKE_TIMEOUT_SECONDS
        for item in resource_specs
    ),
    {
        "baselineInventory": len(baseline_names),
        "resourceInventory": len(resource_names),
        "resourceFunctions": len(resource_functions),
    },
)


parallel_names = {
    str(item.get("checkName") or "")
    for item in server.package_health_parallel_smoke_specs()
}
quiescent_names = {
    str(item.get("checkName") or "")
    for item in server.package_health_quiescent_smoke_specs()
}
exclusive_names = {
    str(item.get("checkName") or "")
    for item in server.package_health_exclusive_smoke_specs()
}
check(
    "production-lanes-are-disjoint-and-resource-concurrency-is-bounded",
    not set(resource_names).intersection(parallel_names)
    and not set(resource_names).intersection(quiescent_names)
    and not set(resource_names).intersection(exclusive_names)
    and quiescent_names == {"routing:typed-output-authority-p191"}
    and exclusive_names
    == {
        "server:package-contract-reconciliation-p227",
        "server:verification-snapshot-latency-p238",
    }
    and 2 <= server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS <= 4
    and server.PACKAGE_HEALTH_RESOURCE_SMOKE_TIMEOUT_SECONDS == 120,
    {
        "parallel": len(parallel_names),
        "resource": len(resource_names),
        "quiescent": sorted(quiescent_names),
        "exclusive": sorted(exclusive_names),
        "resourceMaxWorkers": server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS,
    },
)


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
server_tree = ast.parse(server_source)
package_report = next(
    node
    for node in server_tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "package_health_report"
)
scheduled_names = []
for node in ast.walk(package_report):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "package_resource_boolean_check"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ):
        scheduled_names.append(str(node.args[0].value))
check(
    "package-report-schedules-each-resource-row-exactly-once",
    Counter(scheduled_names) == Counter(resource_names)
    and 'raise RuntimeError(f"duplicate CPU resource package smoke: {check_name}")'
    in server_source
    and "CPU resource lane cannot start before P191 completes" in server_source
    and "CPU resource lane requires the shared lane to be quiescent" in server_source,
    {
        "scheduledCount": len(scheduled_names),
        "uniqueScheduledCount": len(set(scheduled_names)),
    },
)


active = 0
max_active = 0
calls = Counter()
lock = threading.Lock()


def bounded_fake_run(command, **kwargs):
    global active, max_active
    function_name = str(command[-1])
    with lock:
        active += 1
        max_active = max(max_active, active)
        calls[function_name] += 1
    time.sleep(0.008 + (len(function_name) % 4) * 0.004)
    with lock:
        active -= 1
    payload = {
        "suite": "p256-fixture",
        "function": function_name,
        "status": "pass",
        "ok": True,
        "contentsRecorded": False,
    }
    return subprocess.CompletedProcess(
        command,
        0,
        stdout=json.dumps(payload),
        stderr="",
    )


fixture_batch = server.start_package_health_parallel_smoke_batch(
    specs=resource_specs,
    max_workers=server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS,
    run_fn=bounded_fake_run,
)
fixture_results = []
for spec in resource_specs:
    completed, timing = server.consume_package_health_parallel_smoke(
        fixture_batch,
        spec.get("command"),
        cwd=spec.get("cwd"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=spec.get("timeout"),
        env=spec.get("env"),
    )
    fixture_results.append((completed, timing))
fixture_summary = server.finish_package_health_parallel_smoke_batch(fixture_batch)
check(
    "bounded-resource-lane-preserves-inventory-totals-without-duplicates",
    len(fixture_results) == len(resource_specs)
    and fixture_summary.get("registeredCount") == len(resource_specs)
    and fixture_summary.get("consumedCount") == len(resource_specs)
    and fixture_summary.get("completedCount") == len(resource_specs)
    and fixture_summary.get("failedCount") == 0
    and fixture_summary.get("derivedCount") == 0
    and fixture_summary.get("reusedCount") == 0
    and set(calls) == set(resource_functions)
    and all(count == 1 for count in calls.values())
    and max_active <= server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS,
    {
        "summary": fixture_summary,
        "uniqueExecutions": len(calls),
        "maxActive": max_active,
    },
)


def timeout_run(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)


timeout_receipt = server._run_package_health_parallel_smoke(
    resource_specs[0],
    timeout_run,
)
stale_source_spec = dict(resource_specs[0])
stale_source_spec["sourceSha256"] = "0" * 64
stale_source_receipt = server._run_package_health_parallel_smoke(
    stale_source_spec,
    bounded_fake_run,
)
stale_input_spec = dict(resource_specs[0])
stale_input_spec["inputSha256"] = "1" * 64
stale_input_receipt = server._run_package_health_parallel_smoke(
    stale_input_spec,
    bounded_fake_run,
)
check(
    "resource-timeout-and-source-input-drift-fail-closed",
    timeout_receipt.get("status") == "timed-out"
    and timeout_receipt.get("returnCode") == 124
    and timeout_receipt.get("deadlineMs") == 120000
    and timeout_receipt.get("derived") is False
    and timeout_receipt.get("reused") is False
    and stale_source_receipt.get("status") == "rejected"
    and "source binding is stale" in str(stale_source_receipt.get("error") or "")
    and stale_input_receipt.get("status") == "rejected"
    and "input binding is stale" in str(stale_input_receipt.get("error") or ""),
    {
        "timeout": {
            key: timeout_receipt.get(key)
            for key in ("status", "returnCode", "deadlineMs", "derived", "reused")
        },
        "sourceDrift": stale_source_receipt.get("status"),
        "inputDrift": stale_input_receipt.get("status"),
    },
)


baseline_durations = {
    str(item.get("name") or ""): int(item.get("durationMs") or 0)
    for item in baseline_checks
}
candidate_task_ms = sum(baseline_durations.get(name, 0) for name in resource_names)
largest_candidate_ms = max(
    (baseline_durations.get(name, 0) for name in resource_names),
    default=0,
)
ideal_projection_ms = int(baseline.get("durationMs") or 0) - candidate_task_ms + max(
    largest_candidate_ms,
    (candidate_task_ms + server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS - 1)
    // server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS,
)
check(
    "p255-profile-proves-material-shared-lane-opportunity",
    candidate_task_ms >= 250000
    and largest_candidate_ms < server.PACKAGE_HEALTH_RESOURCE_SMOKE_TIMEOUT_SECONDS * 1000
    and ideal_projection_ms < server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS * 1000,
    {
        "p255DurationMs": baseline.get("durationMs"),
        "candidateTaskDurationMs": candidate_task_ms,
        "largestCandidateMs": largest_candidate_ms,
        "idealBoundedProjectionMs": ideal_projection_ms,
    },
)


export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "resource-summary-export-and-worker-budget-truth-remain-visible",
    '"resourceClassSubprocessBatch": resource_subprocess_batch' in server_source
    and 'snapshot["workerBudgetExceeded"]' in server_source
    and "worker_duration_ms > worker_budget * 1000" in server_source
    and server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS == 1020
    and server.PACKAGE_HEALTH_SUPERVISOR_HEADROOM_SECONDS == 300
    and export_source.count('"tools/p256_package_resource_scheduler_smoke.py"')
    == 1
    and export_source.count('"tools/p256_package_synthetic_worker.py"') == 1,
    {
        "workerBudgetSeconds": server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS,
        "supervisorHeadroomSeconds": server.PACKAGE_HEALTH_SUPERVISOR_HEADROOM_SECONDS,
        "resourceSummaryRegistered": "resourceClassSubprocessBatch"
        in server_source,
    },
)


production_profile = None
if args.run_production:
    started = time.perf_counter()
    production_batch = server.start_package_health_parallel_smoke_batch(
        specs=resource_specs,
        max_workers=server.PACKAGE_HEALTH_RESOURCE_SMOKE_MAX_WORKERS,
    )
    production_results = []
    for spec in resource_specs:
        completed, timing = server.consume_package_health_parallel_smoke(
            production_batch,
            spec.get("command"),
            cwd=spec.get("cwd"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=spec.get("timeout"),
            env=spec.get("env"),
        )
        payload = server.parse_model_json_object(completed.stdout)
        production_results.append(
            {
                "name": spec.get("checkName"),
                "status": payload.get("status"),
                "ok": payload.get("ok"),
                "returnCode": completed.returncode,
                "durationMs": timing.get("durationMs"),
            }
        )
    production_summary = server.finish_package_health_parallel_smoke_batch(
        production_batch
    )
    production_wall_ms = round((time.perf_counter() - started) * 1000)
    production_profile = {
        "wallMs": production_wall_ms,
        "summary": production_summary,
        "results": production_results,
        "projectedPackageDurationMs": int(baseline.get("durationMs") or 0)
        - candidate_task_ms
        + production_wall_ms,
    }
    check(
        "measured-production-resource-lane-is-green-and-projects-under-base-budget",
        all(
            item.get("status") == "pass"
            and item.get("ok") is True
            and item.get("returnCode") == 0
            for item in production_results
        )
        and production_summary.get("registeredCount") == len(resource_specs)
        and production_summary.get("consumedCount") == len(resource_specs)
        and production_summary.get("completedCount") == len(resource_specs)
        and production_summary.get("failedCount") == 0
        and production_summary.get("derivedCount") == 0
        and production_summary.get("reusedCount") == 0
        and production_profile["projectedPackageDurationMs"]
        < server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS * 1000,
        production_profile,
    )


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "suite": "p256-package-resource-scheduler",
            "status": "pass" if not failed else "fail",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "productionProfile": production_profile,
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
