#!/usr/bin/env python3
"""P249 adversaries for deterministic, quiescent P227/P238 package lanes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=None):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


source_sha256 = server.current_verification_receipt_snapshot_source_sha256()
script_path = Path(__file__).resolve()
input_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
base_env = {"PATH": server.PATH_FOR_CODEX, "P249_FIXTURE": "exclusive"}


def fixture_spec(name, argument, *, timeout=2, path=None):
    selected_path = Path(path or script_path)
    command = [sys.executable, str(selected_path), argument]
    environment_sha256 = server.text_sha256(
        json.dumps(base_env, sort_keys=True, separators=(",", ":"))
    )
    selected_input_sha256 = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    invocation_sha256 = server.text_sha256(
        json.dumps(
            {
                "command": command,
                "cwd": str(ROOT),
                "environmentSha256": environment_sha256,
                "sourceSha256": source_sha256,
                "inputSha256": selected_input_sha256,
                "outputContract": "status-pass:passed-equals-checkCount:failed-zero",
                "timeoutSeconds": timeout,
                "isolation": "process",
                "sideEffectFree": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return {
        "checkName": name,
        "command": command,
        "cwd": str(ROOT),
        "env": dict(base_env),
        "timeout": timeout,
        "sourceSha256": source_sha256,
        "inputSha256": selected_input_sha256,
        "environmentSha256": environment_sha256,
        "invocationSha256": invocation_sha256,
        "outputContract": "status-pass:passed-equals-checkCount:failed-zero",
        "isolation": "process",
        "sideEffectFree": True,
    }


events = []
calls = Counter()
event_lock = threading.Lock()
active_parallel = 0


def ordered_run(command, **kwargs):
    global active_parallel
    argument = str(command[-1])
    with event_lock:
        calls[argument] += 1
        if argument.startswith("parallel-"):
            active_parallel += 1
            events.append(("parallel-start", argument, time.perf_counter()))
        else:
            events.append(
                ("exclusive-start", argument, time.perf_counter(), active_parallel)
            )
    if argument.startswith("parallel-"):
        time.sleep(0.04)
        with event_lock:
            active_parallel -= 1
            events.append(("parallel-end", argument, time.perf_counter()))
    return subprocess.CompletedProcess(
        command,
        0,
        stdout=json.dumps(
            {"status": "pass", "checkCount": 1, "passed": 1, "failed": 0}
        ),
        stderr="",
    )


parallel_specs = [
    fixture_spec(f"parallel-{index}", f"parallel-{index}") for index in range(4)
]
production_exclusive = server.package_health_exclusive_smoke_specs()
exclusive_by_name = {
    str(item.get("checkName") or ""): dict(item) for item in production_exclusive
}
batch = server.start_package_health_parallel_smoke_batch(
    parallel_specs,
    max_workers=4,
    run_fn=ordered_run,
)
exclusive_receipts = []
for name in (
    "server:package-contract-reconciliation-p227",
    "server:verification-snapshot-latency-p238",
):
    completed, receipt = server.run_package_health_exclusive_smoke_after_parallel_batch(
        batch,
        exclusive_by_name[name],
        run_fn=ordered_run,
    )
    exclusive_receipts.append((completed, receipt))

parallel_receipts = []
for item in parallel_specs:
    completed, receipt = server.consume_package_health_parallel_smoke(
        batch,
        item["command"],
        cwd=item["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=item["timeout"],
        env=item["env"],
    )
    parallel_receipts.append((completed, receipt))
summary = server.finish_package_health_parallel_smoke_batch(batch)

parallel_end_times = [row[2] for row in events if row[0] == "parallel-end"]
exclusive_starts = [row for row in events if row[0] == "exclusive-start"]
check(
    "p238-cannot-overlap-any-parallel-future",
    len(parallel_end_times) == 4
    and len(exclusive_starts) == 2
    and max(parallel_end_times) <= exclusive_starts[0][2]
    and all(row[3] == 0 for row in exclusive_starts)
    and all(
        receipt.get("schedulingBarrier", {}).get("parallelCompletedBeforeStart")
        is True
        for _, receipt in exclusive_receipts
    ),
    {
        "parallelEndCount": len(parallel_end_times),
        "exclusiveActiveCounts": [row[3] for row in exclusive_starts],
    },
)
exclusive_names = [receipt.get("checkName") for _, receipt in exclusive_receipts]
check(
    "p227-and-p238-run-once-in-deterministic-exclusive-order",
    exclusive_names
    == [
        "server:package-contract-reconciliation-p227",
        "server:verification-snapshot-latency-p238",
    ]
    and [receipt.get("exclusiveSequence") for _, receipt in exclusive_receipts]
    == [1, 2]
    and summary.get("exclusiveExecutedOrder") == exclusive_names
    and summary.get("exclusiveRegisteredOrder") == exclusive_names
    and calls[str(exclusive_by_name[exclusive_names[0]]["command"][-1])] == 1
    and calls[str(exclusive_by_name[exclusive_names[1]]["command"][-1])] == 1,
    {"names": exclusive_names, "calls": dict(calls)},
)

duplicate_rejected = False
try:
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        batch,
        exclusive_by_name["server:verification-snapshot-latency-p238"],
        run_fn=ordered_run,
    )
except RuntimeError:
    duplicate_rejected = True
check(
    "duplicate-exclusive-execution-fails-before-subprocess-run",
    duplicate_rejected
    and calls[
        str(
            exclusive_by_name["server:verification-snapshot-latency-p238"][
                "command"
            ][-1]
        )
    ]
    == 1,
    {"duplicateRejected": duplicate_rejected, "calls": dict(calls)},
)

out_of_order_batch = server.start_package_health_parallel_smoke_batch(
    [fixture_spec("order-parallel", "parallel-order")],
    max_workers=1,
    run_fn=ordered_run,
)
out_of_order_rejected = False
try:
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        out_of_order_batch,
        exclusive_by_name["server:verification-snapshot-latency-p238"],
        run_fn=ordered_run,
    )
except RuntimeError:
    out_of_order_rejected = True
server.finish_package_health_parallel_smoke_batch(out_of_order_batch)
check(
    "p238-cannot-bypass-p227-exclusive-order",
    out_of_order_rejected,
    {"outOfOrderRejected": out_of_order_rejected},
)

check(
    "original-receipts-are-source-input-invocation-bound-without-reuse",
    all(
        completed.returncode == 0
        and receipt.get("sourceSha256") == source_sha256
        and receipt.get("inputSha256")
        and receipt.get("invocationSha256")
        and receipt.get("derived") is False
        and receipt.get("reused") is False
        for completed, receipt in exclusive_receipts + parallel_receipts
    )
    and summary.get("derivedCount") == 0
    and summary.get("reusedCount") == 0,
    summary,
)
check(
    "parallel-and-exclusive-timing-and-totals-remain-monotonic",
    summary.get("registeredCount") == 4
    and summary.get("consumedCount") == 4
    and summary.get("completedCount") == 4
    and summary.get("failedCount") == 0
    and int(summary.get("elapsedMs") or 0) >= 0
    and int(summary.get("taskDurationMs") or 0) >= int(summary.get("elapsedMs") or 0)
    and all(int(receipt.get("durationMs") or 0) >= 0 for _, receipt in exclusive_receipts),
    summary,
)


def one_parallel_batch(label):
    return server.start_package_health_parallel_smoke_batch(
        [fixture_spec(f"{label}-parallel", f"parallel-{label}")],
        max_workers=1,
        run_fn=ordered_run,
    )


def nonzero_run(command, **_kwargs):
    return subprocess.CompletedProcess(
        command,
        7,
        stdout=json.dumps(
            {
                "status": "fail",
                "checkCount": 1,
                "passed": 0,
                "failed": 1,
                "failures": [
                    {"name": "original-latency-predicate", "detail": "over budget"}
                ],
            }
        ),
        stderr="private stderr must not be copied",
    )


failure_batch = one_parallel_batch("failure")
failure_completed, failure_receipt = (
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        failure_batch,
        fixture_spec("fixture-exclusive-failure", "exclusive-failure"),
        run_fn=nonzero_run,
    )
)
server.finish_package_health_parallel_smoke_batch(failure_batch)
check(
    "nonzero-exclusive-result-is-not-promoted-and-keeps-diagnostics",
    failure_completed.returncode == 7
    and failure_receipt.get("returnCode") == 7
    and failure_receipt.get("derived") is False
    and failure_receipt.get("reused") is False
    and (failure_receipt.get("childDiagnostics") or {}).get(
        "failedChecks", [{}]
    )[0].get("name")
    == "original-latency-predicate"
    and "private stderr"
    not in json.dumps(failure_receipt.get("childDiagnostics") or {}),
    {key: value for key, value in failure_receipt.items() if key != "completed"},
)


def malformed_run(command, **_kwargs):
    return subprocess.CompletedProcess(command, 2, stdout="not-json", stderr="secret")


malformed_batch = one_parallel_batch("malformed")
malformed_completed, malformed_receipt = (
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        malformed_batch,
        fixture_spec("fixture-exclusive-malformed", "exclusive-malformed"),
        run_fn=malformed_run,
    )
)
server.finish_package_health_parallel_smoke_batch(malformed_batch)
check(
    "malformed-exclusive-output-remains-original-nonzero-failure",
    malformed_completed.returncode == 2
    and malformed_receipt.get("returnCode") == 2
    and (malformed_receipt.get("childDiagnostics") or {}).get("malformed") is True
    and malformed_receipt.get("derived") is False
    and malformed_receipt.get("reused") is False,
    {key: value for key, value in malformed_receipt.items() if key != "completed"},
)


def timeout_run(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)


timeout_batch = one_parallel_batch("timeout")
timeout_failed_closed = False
timeout_receipt = {}
try:
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        timeout_batch,
        fixture_spec("fixture-exclusive-timeout", "exclusive-timeout", timeout=1),
        run_fn=timeout_run,
    )
except subprocess.TimeoutExpired as exc:
    timeout_failed_closed = True
    timeout_receipt = getattr(exc, "package_health_timing", {})
server.finish_package_health_parallel_smoke_batch(timeout_batch)
check(
    "exclusive-timeout-fails-closed-with-original-deadline",
    timeout_failed_closed
    and timeout_receipt.get("status") == "timed-out"
    and timeout_receipt.get("deadlineMs") == 1000
    and timeout_receipt.get("derived") is False
    and timeout_receipt.get("reused") is False,
    {key: value for key, value in timeout_receipt.items() if key != "exception"},
)


original_source_reader = server.current_verification_receipt_snapshot_source_sha256
original_registry_reader = server.package_health_exclusive_smoke_specs
source_drift_batch = one_parallel_batch("source-drift")
server.quiesce_package_health_parallel_smoke_batch(source_drift_batch)
source_drift_failed_closed = False
source_drift_receipt = {}
source_reads = iter((source_sha256, "f" * 64))
try:
    server.package_health_exclusive_smoke_specs = lambda: []
    server.current_verification_receipt_snapshot_source_sha256 = lambda: next(
        source_reads, "f" * 64
    )
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        source_drift_batch,
        fixture_spec("fixture-source-drift", "exclusive-source-drift"),
        run_fn=ordered_run,
    )
except RuntimeError as exc:
    source_drift_failed_closed = True
    source_drift_receipt = getattr(exc, "package_health_timing", {})
finally:
    server.current_verification_receipt_snapshot_source_sha256 = original_source_reader
    server.package_health_exclusive_smoke_specs = original_registry_reader
server.finish_package_health_parallel_smoke_batch(source_drift_batch)
check(
    "exclusive-source-drift-fails-closed",
    source_drift_failed_closed
    and source_drift_receipt.get("status") == "source-drift"
    and source_drift_receipt.get("sourceStable") is False,
    {key: value for key, value in source_drift_receipt.items() if key != "completed"},
)


with tempfile.TemporaryDirectory(prefix="p249-input-drift-") as temp_dir:
    mutable_path = Path(temp_dir) / "fixture.py"
    mutable_path.write_text("print('original')\n", encoding="utf-8")
    input_drift_spec = fixture_spec(
        "fixture-input-drift",
        "exclusive-input-drift",
        path=mutable_path,
    )

    def mutate_input_run(command, **_kwargs):
        Path(command[1]).write_text("print('changed')\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {"status": "pass", "checkCount": 1, "passed": 1, "failed": 0}
            ),
            stderr="",
        )

    input_drift_batch = one_parallel_batch("input-drift")
    input_drift_failed_closed = False
    input_drift_receipt = {}
    try:
        server.run_package_health_exclusive_smoke_after_parallel_batch(
            input_drift_batch,
            input_drift_spec,
            run_fn=mutate_input_run,
        )
    except RuntimeError as exc:
        input_drift_failed_closed = True
        input_drift_receipt = getattr(exc, "package_health_timing", {})
    server.finish_package_health_parallel_smoke_batch(input_drift_batch)
check(
    "exclusive-input-drift-fails-closed",
    input_drift_failed_closed
    and input_drift_receipt.get("status") == "input-drift"
    and input_drift_receipt.get("inputStable") is False,
    {key: value for key, value in input_drift_receipt.items() if key != "completed"},
)


parallel_registry = server.package_health_parallel_smoke_specs()
exclusive_registry = server.package_health_exclusive_smoke_specs()
quiescent_registry = server.package_health_quiescent_smoke_specs()
parallel_names = [str(item.get("checkName") or "") for item in parallel_registry]
exclusive_names = [str(item.get("checkName") or "") for item in exclusive_registry]
quiescent_names = [str(item.get("checkName") or "") for item in quiescent_registry]
check(
    "production-registry-has-one-p238-only-in-exclusive-lane",
    len(parallel_registry) == 24
    and len(set(parallel_names)) == 24
    and parallel_names.count("server:verification-telemetry-isolation-p257") == 1
    and parallel_names.count("reasoning:contextual-clarification-contract-p258") == 1
    and "server:verification-snapshot-latency-p238" not in parallel_names
    and "routing:typed-output-authority-p191" not in parallel_names
    and quiescent_names == ["routing:typed-output-authority-p191"]
    and exclusive_names
    == [
        "server:package-contract-reconciliation-p227",
        "server:verification-snapshot-latency-p238",
    ]
    and not set(parallel_names).intersection(exclusive_names + quiescent_names),
    {
        "parallel": parallel_names,
        "quiescent": quiescent_names,
        "exclusive": exclusive_names,
    },
)

server_source = (ROOT / "server.py").read_text(encoding="utf-8")
package_start = server_source.index("def package_health_report():")
package_end = server_source.index("def persist_isolated_package_health_report", package_start)
package_source = server_source[package_start:package_end]
p238_start = package_source.index("verification_snapshot_latency_contract =")
p238_end = package_source.index(
    'add("server:verification-snapshot-latency-p238", "fail"', p238_start
)
p238_block = package_source[p238_start:p238_end]
export_source = (ROOT / "tools" / "build_public_export.py").read_text(encoding="utf-8")
p227_source = (ROOT / "tools" / "p227_package_contract_reconciliation_smoke.py").read_text(encoding="utf-8")
p238_source = (ROOT / "tools" / "p238_verification_snapshot_latency_smoke.py").read_text(encoding="utf-8")
check(
    "package-report-invokes-one-exclusive-p238-and-registers-p249",
    "package_smoke_run(" not in p238_block
    and p238_block.count(
        'package_exclusive_smoke_run(\n            "server:verification-snapshot-latency-p238"'
    )
    == 1
    and package_source.count('"server:exclusive-package-lane-p249"') == 2
    and export_source.count('"tools/p249_exclusive_package_lane_smoke.py"') == 1,
    "one original exclusive P238 call, one P249 result path, one export entry",
)
check(
    "p227-p238-and-p220-deadline-contracts-are-unchanged",
    "PACKAGE_WORKER_RUNTIME_BUDGET_MS = 15000" in p227_source
    and "runtime_ms <= PACKAGE_WORKER_RUNTIME_BUDGET_MS" in p227_source
    and '"budgetMs": 15000' in p238_source
    and "all(duration <= 15000 for duration in real_durations)" in p238_source
    and server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS >= 30
    and "max(\n    30," in server_source[
        server_source.index("PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS") :
        server_source.index("PACKAGE_HEALTH_PROGRESS_PATH_ENV")
    ],
    {
        "p227BudgetMs": 15000,
        "p238BudgetMs": 15000,
        "focusedTimeoutSeconds": server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS,
    },
)


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "suite": "p249-exclusive-package-lane",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failures": failed,
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
