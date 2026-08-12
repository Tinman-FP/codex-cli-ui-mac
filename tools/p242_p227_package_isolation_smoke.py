#!/usr/bin/env python3
"""P242 adversaries for exclusive P227 package scheduling and receipt truth."""

from __future__ import annotations

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
base_env = {"PATH": server.PATH_FOR_CODEX, "P242_FIXTURE": "exclusive"}


def spec(name, argument, *, timeout=2):
    command = [sys.executable, str(script_path), argument]
    environment_sha256 = server.text_sha256(
        json.dumps(base_env, sort_keys=True, separators=(",", ":"))
    )
    invocation_sha256 = server.text_sha256(
        json.dumps(
            {
                "command": command,
                "cwd": str(ROOT),
                "environmentSha256": environment_sha256,
                "sourceSha256": source_sha256,
                "inputSha256": input_sha256,
                "outputContract": "json-pass-v1",
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
        "inputSha256": input_sha256,
        "environmentSha256": environment_sha256,
        "invocationSha256": invocation_sha256,
        "outputContract": "json-pass-v1",
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
                (
                    "exclusive-start",
                    argument,
                    time.perf_counter(),
                    active_parallel,
                )
            )
    if argument.startswith("parallel-"):
        time.sleep(0.04)
        with event_lock:
            active_parallel -= 1
            events.append(("parallel-end", argument, time.perf_counter()))
    if argument == "exclusive-timeout":
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)
    return subprocess.CompletedProcess(
        command,
        1 if argument == "exclusive-failure" else 0,
        stdout=json.dumps(
            {"status": "pass", "passed": 1, "checkCount": 1, "failed": 0}
        ),
        stderr="",
    )


parallel_specs = [spec(f"parallel-{index}", f"parallel-{index}") for index in range(4)]
exclusive_spec = spec("server:package-contract-reconciliation-p227", "exclusive-pass")
batch = server.start_package_health_parallel_smoke_batch(
    parallel_specs,
    max_workers=4,
    run_fn=ordered_run,
)
exclusive_completed, exclusive_receipt = (
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        batch,
        exclusive_spec,
        run_fn=ordered_run,
    )
)
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
exclusive_start = next(row for row in events if row[0] == "exclusive-start")
check(
    "p227-starts-only-after-every-parallel-future-completes",
    len(parallel_end_times) == 4
    and max(parallel_end_times) <= exclusive_start[2]
    and exclusive_start[3] == 0
    and exclusive_receipt.get("schedulingBarrier", {}).get(
        "parallelCompletedBeforeStart"
    )
    is True,
    {
        "parallelEndCount": len(parallel_end_times),
        "activeParallelAtExclusiveStart": exclusive_start[3],
        "barrier": exclusive_receipt.get("schedulingBarrier"),
    },
)
check(
    "every-original-fixture-executes-exactly-once",
    calls
    == Counter(
        {
            "parallel-0": 1,
            "parallel-1": 1,
            "parallel-2": 1,
            "parallel-3": 1,
            "exclusive-pass": 1,
        }
    )
    and summary.get("registeredCount") == 4
    and summary.get("consumedCount") == 4,
    dict(calls),
)
check(
    "exclusive-result-retains-original-identity-and-provenance",
    exclusive_completed.returncode == 0
    and exclusive_receipt.get("checkName")
    == "server:package-contract-reconciliation-p227"
    and exclusive_receipt.get("timingMode") == "isolated-after-parallel-batch"
    and exclusive_receipt.get("sourceSha256") == source_sha256
    and exclusive_receipt.get("inputSha256") == input_sha256
    and exclusive_receipt.get("invocationSha256")
    == exclusive_spec.get("invocationSha256")
    and exclusive_receipt.get("derived") is False
    and exclusive_receipt.get("reused") is False,
    {
        key: value
        for key, value in exclusive_receipt.items()
        if key not in {"completed", "_finishedMonotonic"}
    },
)
check(
    "parallel-results-remain-original-after-quiescence",
    all(
        completed.returncode == 0
        and receipt.get("derived") is False
        and receipt.get("reused") is False
        and receipt.get("sourceSha256") == source_sha256
        and receipt.get("inputSha256") == input_sha256
        for completed, receipt in parallel_receipts
    )
    and summary.get("derivedCount") == 0
    and summary.get("reusedCount") == 0,
    summary,
)
check(
    "quiescence-and-task-timing-remain-monotonic",
    summary.get("quiesced") is True
    and summary.get("quiescedBeforeChecks")
    == ["server:package-contract-reconciliation-p227"]
    and 30 <= int(summary.get("elapsedMs") or 0) < 1000
    and int(summary.get("taskDurationMs") or 0)
    >= int(summary.get("elapsedMs") or 0)
    and 0 <= int(exclusive_receipt.get("durationMs") or 0) < 1000,
    summary,
)


failure_batch = server.start_package_health_parallel_smoke_batch(
    [spec("failure-parallel", "parallel-failure-fixture")],
    max_workers=1,
    run_fn=ordered_run,
)
failure_completed, failure_receipt = (
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        failure_batch,
        spec("failure-exclusive", "exclusive-failure"),
        run_fn=ordered_run,
    )
)
server.finish_package_health_parallel_smoke_batch(failure_batch)
check(
    "exclusive-nonzero-return-code-is-not-promoted",
    failure_completed.returncode == 1
    and failure_receipt.get("returnCode") == 1
    and failure_receipt.get("status") == "completed"
    and failure_receipt.get("derived") is False
    and failure_receipt.get("reused") is False,
    {
        key: value
        for key, value in failure_receipt.items()
        if key not in {"completed", "_finishedMonotonic"}
    },
)


timeout_batch = server.start_package_health_parallel_smoke_batch(
    [spec("timeout-parallel", "parallel-timeout-fixture")],
    max_workers=1,
    run_fn=ordered_run,
)
timeout_propagated = False
try:
    server.run_package_health_exclusive_smoke_after_parallel_batch(
        timeout_batch,
        spec("timeout-exclusive", "exclusive-timeout", timeout=1),
        run_fn=ordered_run,
    )
except subprocess.TimeoutExpired:
    timeout_propagated = True
server.finish_package_health_parallel_smoke_batch(timeout_batch)
check(
    "exclusive-timeout-propagates-fail-closed",
    timeout_propagated,
    {"timeoutPropagated": timeout_propagated},
)


parallel_registry = server.package_health_parallel_smoke_specs()
exclusive_registry = server.package_health_exclusive_smoke_specs()
quiescent_registry = server.package_health_quiescent_smoke_specs()
parallel_names = [str(item.get("checkName") or "") for item in parallel_registry]
exclusive_names = [str(item.get("checkName") or "") for item in exclusive_registry]
quiescent_names = [str(item.get("checkName") or "") for item in quiescent_registry]
check(
    "production-registries-are-disjoint-and-p227-p238-are-exclusive",
    len(parallel_registry) == 24
    and len(set(parallel_names)) == 24
    and parallel_names.count("server:p227-package-isolation-p242") == 1
    and parallel_names.count("server:user-facing-frontier-context-p243") == 1
    and parallel_names.count("server:verification-telemetry-isolation-p257") == 1
    and parallel_names.count("reasoning:contextual-clarification-contract-p258") == 1
    and "server:package-contract-reconciliation-p227" not in parallel_names
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


p227_path = ROOT / "tools" / "p227_package_contract_reconciliation_smoke.py"
p227_source = p227_path.read_text(encoding="utf-8")
p227_tree = ast.parse(p227_source)
semantic_count = 0
for node in p227_tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "REQUIRED_SEMANTIC_CHECKS"
        for target in node.targets
    ):
        call = node.value
        if (
            isinstance(call, ast.Call)
            and call.args
            and isinstance(call.args[0], ast.Set)
        ):
            semantic_count = len(call.args[0].elts)
check(
    "p227-keeps-seventeen-semantics-and-fifteen-second-limit",
    semantic_count == 17
    and "PACKAGE_WORKER_RUNTIME_BUDGET_MS = 15000" in p227_source
    and '"package-worker-runtime-budget-p229"' in p227_source
    and "runtime_ms <= PACKAGE_WORKER_RUNTIME_BUDGET_MS" in p227_source,
    {"semanticCount": semantic_count, "budgetMs": 15000},
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
p227_block_start = package_source.index(
    'package_exclusive_smoke_run(\n            "server:package-contract-reconciliation-p227"'
)
p227_block_end = package_source.index(
    'add("server:package-contract-reconciliation-p227", "fail"',
    p227_block_start,
)
p227_block = package_source[p227_block_start:p227_block_end]
check(
    "package-report-uses-one-exclusive-p227-execution-and-one-p242-row",
    "package_smoke_run(" not in p227_block
    and package_source.count(
        'package_exclusive_smoke_run(\n            "server:package-contract-reconciliation-p227"'
    )
    == 1
    and package_source.count('add(\n            "server:p227-package-isolation-p242"')
    == 1
    and package_source.count(
        'add("server:p227-package-isolation-p242", "fail"'
    )
    == 1
    and export_source.count('"tools/p242_p227_package_isolation_smoke.py"')
    == 1,
    "one exclusive P227 execution, one P242 package result, and one export entry",
)


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "suite": "p242-p227-package-isolation",
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
