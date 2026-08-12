#!/usr/bin/env python3
"""P240 regressions for truthful, bounded package-smoke concurrency."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
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
base_env = {"PATH": server.PATH_FOR_CODEX, "P240_FIXTURE": "base"}


def spec(
    name,
    argument,
    *,
    env=None,
    timeout=2,
    source_sha=source_sha256,
    input_sha=input_sha256,
    side_effect_free=True,
    output_contract="json-pass-v1",
):
    environment = dict(env or base_env)
    command = [sys.executable, str(script_path), argument]
    environment_sha256 = server.text_sha256(
        json.dumps(environment, sort_keys=True, separators=(",", ":"))
    )
    invocation_sha256 = server.text_sha256(
        json.dumps(
            {
                "command": command,
                "cwd": str(ROOT),
                "environmentSha256": environment_sha256,
                "sourceSha256": source_sha,
                "inputSha256": input_sha,
                "outputContract": output_contract,
                "timeoutSeconds": timeout,
                "isolation": "process",
                "sideEffectFree": side_effect_free,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return {
        "checkName": name,
        "command": command,
        "cwd": str(ROOT),
        "env": environment,
        "timeout": timeout,
        "sourceSha256": source_sha,
        "inputSha256": input_sha,
        "environmentSha256": environment_sha256,
        "invocationSha256": invocation_sha256,
        "outputContract": output_contract,
        "isolation": "process",
        "sideEffectFree": side_effect_free,
    }


calls = []
calls_lock = threading.Lock()


def fake_run(command, **kwargs):
    argument = str(command[-1])
    with calls_lock:
        calls.append(
            {
                "argument": argument,
                "environment": dict(kwargs.get("env") or {}),
                "timeout": kwargs.get("timeout"),
            }
        )
    if argument == "timeout":
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)
    if argument.startswith("slow-"):
        time.sleep(0.05)
    return subprocess.CompletedProcess(
        command,
        1 if argument == "failure" else 0,
        stdout=json.dumps({"status": "pass", "passed": 1, "checkCount": 1, "failed": 0}),
        stderr="",
    )


parallel_specs = [spec(f"parallel-{index}", f"slow-{index}") for index in range(4)]
parallel_batch = server.start_package_health_parallel_smoke_batch(
    parallel_specs,
    max_workers=4,
    run_fn=fake_run,
)
parallel_receipts = []
for item in parallel_specs:
    completed, receipt = server.consume_package_health_parallel_smoke(
        parallel_batch,
        item["command"],
        cwd=item["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=item["timeout"],
        env=item["env"],
    )
    parallel_receipts.append((completed, receipt))
parallel_summary = server.finish_package_health_parallel_smoke_batch(parallel_batch)

check(
    "independent-process-smokes-overlap-with-bounded-workers",
    all(completed.returncode == 0 for completed, _receipt in parallel_receipts)
    and parallel_summary.get("workerCount") == 4
    and parallel_summary.get("registeredCount") == 4
    and parallel_summary.get("consumedCount") == 4
    and parallel_summary.get("completedCount") == 4
    and parallel_summary.get("failedCount") == 0
    and int(parallel_summary.get("elapsedMs") or 0)
    < int(parallel_summary.get("taskDurationMs") or 0),
    parallel_summary,
)
check(
    "parallel-receipts-are-original-not-derived-or-reused",
    all(
        receipt.get("derived") is False
        and receipt.get("reused") is False
        and receipt.get("isolation") == "process"
        and receipt.get("sourceSha256") == source_sha256
        and receipt.get("inputSha256") == input_sha256
        and receipt.get("invocationSha256")
        and receipt.get("contentsRecorded") is False
        for _completed, receipt in parallel_receipts
    )
    and parallel_summary.get("derivedCount") == 0
    and parallel_summary.get("reusedCount") == 0,
    parallel_summary,
)
check(
    "per-check-deadline-and-monotonic-duration-remain-truthful",
    all(
        receipt.get("deadlineMs") == 2000
        and 40 <= int(receipt.get("durationMs") or 0) < 1000
        for _completed, receipt in parallel_receipts
    )
    and 40 <= int(parallel_summary.get("elapsedMs") or 0) < 1000,
    parallel_summary,
)


identity_calls = []


def identity_run(command, **kwargs):
    identity_calls.append(
        (tuple(command), tuple(sorted((kwargs.get("env") or {}).items())))
    )
    return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")


identity_spec = spec("identity", "base")
identity_batch = server.start_package_health_parallel_smoke_batch(
    [identity_spec],
    max_workers=1,
    run_fn=identity_run,
)
server.consume_package_health_parallel_smoke(
    identity_batch,
    identity_spec["command"],
    cwd=identity_spec["cwd"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=identity_spec["timeout"],
    env=identity_spec["env"],
)
server.consume_package_health_parallel_smoke(
    identity_batch,
    [*identity_spec["command"], "different-args"],
    cwd=identity_spec["cwd"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=identity_spec["timeout"],
    env=identity_spec["env"],
)
server.consume_package_health_parallel_smoke(
    identity_batch,
    identity_spec["command"],
    cwd=identity_spec["cwd"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=identity_spec["timeout"],
    env={**identity_spec["env"], "P240_FIXTURE": "different-env"},
)
server.consume_package_health_parallel_smoke(
    identity_batch,
    identity_spec["command"],
    cwd=identity_spec["cwd"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=identity_spec["timeout"],
    env=identity_spec["env"],
)
identity_summary = server.finish_package_health_parallel_smoke_batch(identity_batch)
check(
    "differing-args-and-environment-never-coalesce",
    len(identity_calls) == 4
    and len({row[0] for row in identity_calls}) == 2
    and len({row[1] for row in identity_calls}) == 2
    and identity_summary.get("consumedCount") == 1,
    {"callCount": len(identity_calls), "summary": identity_summary},
)
check(
    "duplicate-request-executes-again-instead-of-reusing-a-receipt",
    len(identity_calls) == 4 and identity_summary.get("reusedCount") == 0,
    identity_summary,
)


for name, invalid_spec, expected_status in (
    (
        "stale-source-binding-rejected-before-execution",
        spec("stale-source", "stale-source", source_sha="0" * 64),
        "rejected",
    ),
    (
        "stale-input-artifact-rejected-before-execution",
        spec("stale-input", "stale-input", input_sha="1" * 64),
        "rejected",
    ),
    (
        "side-effectful-check-rejected-from-parallel-lane",
        spec("side-effect", "side-effect", side_effect_free=False),
        "rejected",
    ),
):
    result = server._run_package_health_parallel_smoke(invalid_spec, fake_run)
    check(
        name,
        result.get("status") == expected_status
        and result.get("returnCode") == 125
        and result.get("derived") is False
        and result.get("reused") is False,
        {key: value for key, value in result.items() if not key.startswith("_")},
    )


failure_result = server._run_package_health_parallel_smoke(
    spec("failure", "failure"),
    fake_run,
)
check(
    "failed-check-return-code-is-not-promoted",
    failure_result.get("status") == "completed"
    and failure_result.get("returnCode") == 1
    and failure_result.get("completed").returncode == 1,
    {key: value for key, value in failure_result.items() if key != "completed"},
)


timeout_result = server._run_package_health_parallel_smoke(
    spec("timeout", "timeout", timeout=1),
    fake_run,
)
check(
    "timed-out-check-remains-fail-closed",
    timeout_result.get("status") == "timed-out"
    and timeout_result.get("returnCode") == 124
    and timeout_result.get("timedOut") is True
    and isinstance(timeout_result.get("exception"), subprocess.TimeoutExpired),
    {key: value for key, value in timeout_result.items() if key != "exception"},
)


original_source_reader = server.current_verification_receipt_snapshot_source_sha256
source_reads = iter((source_sha256, "f" * 64))
try:
    server.current_verification_receipt_snapshot_source_sha256 = lambda: next(
        source_reads,
        "f" * 64,
    )
    drift_result = server._run_package_health_parallel_smoke(
        spec("source-drift", "source-drift"),
        fake_run,
    )
finally:
    server.current_verification_receipt_snapshot_source_sha256 = original_source_reader
check(
    "concurrent-source-drift-invalidates-completed-output",
    drift_result.get("status") == "source-drift"
    and drift_result.get("sourceStable") is False
    and drift_result.get("returnCode") == 0,
    {key: value for key, value in drift_result.items() if key != "completed"},
)


contract_a = spec("contract-a", "contract", output_contract="json-pass-v1")
contract_b = spec("contract-b", "contract", output_contract="json-pass-v2")
check(
    "output-contract-and-source-participate-in-invocation-provenance",
    contract_a["invocationSha256"] != contract_b["invocationSha256"]
    and contract_a["sourceSha256"] == source_sha256
    and contract_a["environmentSha256"],
    {
        "contractA": contract_a["invocationSha256"],
        "contractB": contract_b["invocationSha256"],
    },
)


registry = server.package_health_parallel_smoke_specs()
registry_names = [item.get("checkName") for item in registry]
registry_invocations = [item.get("invocationSha256") for item in registry]
exclusive_registry = server.package_health_exclusive_smoke_specs()
exclusive_names = [item.get("checkName") for item in exclusive_registry]
quiescent_registry = server.package_health_quiescent_smoke_specs()
quiescent_names = [item.get("checkName") for item in quiescent_registry]
check(
    "production-parallel-registry-is-explicit-unique-and-source-bound",
    len(registry) == 24
    and len(set(registry_names)) == len(registry)
    and len(set(registry_invocations)) == len(registry)
    and all(
        item.get("sideEffectFree") is True
        and item.get("isolation") == "process"
        and item.get("sourceSha256") == source_sha256
        and item.get("inputSha256")
        for item in registry
    )
    and "server:package-contract-reconciliation-p227" not in registry_names
    and "server:verification-snapshot-latency-p238" not in registry_names
    and registry_names.count("server:p227-package-isolation-p242") == 1
    and registry_names.count("server:user-facing-frontier-context-p243") == 1
    and registry_names.count("server:verification-telemetry-isolation-p257") == 1
    and registry_names.count("reasoning:contextual-clarification-contract-p258") == 1
    and "routing:typed-output-authority-p191" not in registry_names
    and quiescent_names == ["routing:typed-output-authority-p191"]
    and exclusive_names
    == [
        "server:package-contract-reconciliation-p227",
        "server:verification-snapshot-latency-p238",
    ]
    and not set(registry_names).intersection(exclusive_names + quiescent_names),
    {
        "parallelRegisteredCount": len(registry),
        "exclusiveRegisteredCount": len(exclusive_registry),
    },
)


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
package_start = server_source.index("def package_health_report():")
package_end = server_source.index(
    "def persist_isolated_package_health_report",
    package_start,
)
package_source = server_source[package_start:package_end]
export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "package-report-uses-monotonic-total-and-persists-batch-truth",
    "package_started = time.perf_counter()" in package_source
    and "progress_started = time.perf_counter()" in package_source
    and "parallel_smoke_batch = None" in package_source
    and "parallel_smoke_batch = start_package_health_parallel_smoke_batch()" in package_source
    and "package_smoke_timings = {}" in package_source
    and "package_exclusive_smoke_run(check_name)" in package_source
    and '"isolated-after-parallel-batch"' in package_source
    and '"durationMs": round((time.perf_counter() - package_started) * 1000)' in package_source
    and '"parallelSubprocessBatch": parallel_subprocess_batch' in package_source
    and 'or "independent-parallel-subprocess"' in package_source,
)
check(
    "p240-package-and-export-registration",
    '"server:package-runner-concurrency-p240"' in package_source
    and '"p240_package_runner_concurrency_smoke.py"' in package_source
    and '"tools/p240_package_runner_concurrency_smoke.py"' in export_source,
)


failed_checks = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed_checks else "fail",
            "suite": "p240-package-runner-concurrency",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed_checks),
            "failed": len(failed_checks),
            "failures": failed_checks,
            "timing": {
                "parallelElapsedMs": parallel_summary.get("elapsedMs"),
                "parallelTaskDurationMs": parallel_summary.get("taskDurationMs"),
                "workerCount": parallel_summary.get("workerCount"),
            },
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed_checks else 0)
