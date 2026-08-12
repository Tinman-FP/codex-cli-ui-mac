#!/usr/bin/env python3
"""P255 adversaries for package dependency closure and bounded slow lanes."""

from __future__ import annotations

import ast
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


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
server_tree = ast.parse(server_source)
package_report = next(
    node
    for node in server_tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "package_health_report"
)
required_child_reports = {
    "bounded_specialist_producer_report",
    "local_file_completion_report",
    "source_bound_specialist_relevance_report",
    "final_relevance_propagation_report",
}
child_report_parsers = {}
for node in ast.walk(package_report):
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        continue
    for target in node.targets:
        if not isinstance(target, ast.Name) or target.id not in required_child_reports:
            continue
        function = node.value.func
        child_report_parsers[target.id] = (
            function.id if isinstance(function, ast.Name) else ""
        )
check(
    "package-child-json-parsers-have-hermetic-local-closure",
    child_report_parsers
    == {name: "capture_package_child_report" for name in required_child_reports}
    and "parse_json_object_text" not in server_source,
    child_report_parsers,
)


parallel_names = [
    str(item.get("checkName") or "")
    for item in server.package_health_parallel_smoke_specs()
]
quiescent_specs = server.package_health_quiescent_smoke_specs()
quiescent_names = [str(item.get("checkName") or "") for item in quiescent_specs]
p191_name = "routing:typed-output-authority-p191"
check(
    "p191-has-one-quiescent-thirty-second-deadline",
    p191_name not in parallel_names
    and quiescent_names == [p191_name]
    and int(quiescent_specs[0].get("timeout") or 0) == 30
    and int(server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS) == 30,
    {
        "parallelContainsP191": p191_name in parallel_names,
        "quiescent": quiescent_names,
        "deadlineSeconds": int(quiescent_specs[0].get("timeout") or 0),
    },
)


events = []
event_lock = threading.Lock()


def ordered_run(command, **kwargs):
    script = Path(str(command[1])).name
    with event_lock:
        events.append((script, "start", time.perf_counter()))
    if script != "p191_typed_output_authority_contract_smoke.py":
        time.sleep(0.03)
    with event_lock:
        events.append((script, "finish", time.perf_counter()))
    return subprocess.CompletedProcess(
        command,
        0,
        stdout=json.dumps(
            {
                "status": "pass",
                "checkCount": 1,
                "passed": 1,
                "failed": 0,
                "checks": [{"name": "fixture", "status": "pass"}],
            }
        ),
        stderr="",
    )


parallel_spec = server.package_health_parallel_smoke_specs()[0]
p191_spec = quiescent_specs[0]
batch = server.start_package_health_parallel_smoke_batch(
    specs=[parallel_spec],
    max_workers=1,
    run_fn=ordered_run,
)
completed, quiescent_receipt = (
    server.run_package_health_quiescent_smoke_after_parallel_batch(
        batch,
        p191_spec,
        ordered_run,
    )
)
parallel_finish = next(
    stamp for script, phase, stamp in events if script != Path(p191_spec["command"][1]).name and phase == "finish"
)
p191_start = next(
    stamp for script, phase, stamp in events if script == Path(p191_spec["command"][1]).name and phase == "start"
)
check(
    "quiescent-runner-drains-parallel-work-before-p191",
    completed.returncode == 0
    and parallel_finish <= p191_start
    and quiescent_receipt.get("timingMode")
    == "quiescent-after-parallel-batch"
    and (quiescent_receipt.get("schedulingBarrier") or {}).get(
        "parallelCompletedBeforeStart"
    )
    is True
    and quiescent_receipt.get("derived") is False
    and quiescent_receipt.get("reused") is False,
    {
        "events": events,
        "timingMode": quiescent_receipt.get("timingMode"),
        "barrier": quiescent_receipt.get("schedulingBarrier"),
    },
)


def timeout_run(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)


timeout_timing = {}
try:
    server.run_package_health_quiescent_smoke_after_parallel_batch(
        {
            "batchId": "p255-timeout",
            "futures": {},
            "receipts": {},
            "consumed": set(),
            "exclusiveExecutedOrder": [],
        },
        p191_spec,
        timeout_run,
    )
except subprocess.TimeoutExpired as exc:
    timeout_timing = getattr(exc, "package_health_timing", {})
check(
    "quiescent-timeout-retains-bounded-failure-receipt",
    timeout_timing.get("status") == "timed-out"
    and timeout_timing.get("returnCode") == 124
    and timeout_timing.get("timedOut") is True
    and timeout_timing.get("deadlineMs") == 30000
    and timeout_timing.get("timingMode")
    == "quiescent-after-parallel-batch"
    and timeout_timing.get("derived") is False
    and timeout_timing.get("reused") is False,
    {
        key: timeout_timing.get(key)
        for key in (
            "status",
            "returnCode",
            "timedOut",
            "deadlineMs",
            "timingMode",
            "derived",
            "reused",
        )
    },
)


stale_spec = dict(p191_spec)
stale_spec["sourceSha256"] = "0" * 64
stale_timing = {}
try:
    server.run_package_health_quiescent_smoke_after_parallel_batch(
        {
            "batchId": "p255-source-drift",
            "futures": {},
            "receipts": {},
            "consumed": set(),
            "exclusiveExecutedOrder": [],
        },
        stale_spec,
        ordered_run,
    )
except RuntimeError as exc:
    stale_timing = getattr(exc, "package_health_timing", {})
check(
    "quiescent-source-drift-fails-closed-without-execution",
    stale_timing.get("status") == "rejected"
    and stale_timing.get("returnCode") == 125
    and "source binding is stale" in str(stale_timing.get("error") or "")
    and stale_timing.get("timingMode")
    == "quiescent-after-parallel-batch",
    {
        key: stale_timing.get(key)
        for key in ("status", "returnCode", "error", "timingMode")
    },
)


p227_source = (
    ROOT / "tools" / "p227_package_contract_reconciliation_smoke.py"
).read_text(encoding="utf-8")
p227_tree = ast.parse(p227_source)
semantic_count = 0
for node in p227_tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "REQUIRED_SEMANTIC_CHECKS"
        for target in node.targets
    ):
        if isinstance(node.value, ast.Call) and node.value.args and isinstance(
            node.value.args[0], ast.Set
        ):
            semantic_count = len(node.value.args[0].elts)
check(
    "p227-keeps-semantics-with-bounded-measured-headroom",
    semantic_count == 17
    and "PACKAGE_WORKER_RUNTIME_BUDGET_MS = 15000" in p227_source
    and "PACKAGE_WORKER_RUNTIME_HEADROOM_MS = 2000" in p227_source
    and "runtime_ms <= PACKAGE_WORKER_RUNTIME_EFFECTIVE_BUDGET_MS" in p227_source
    and "not missing_semantic_checks" in p227_source,
    {
        "semanticCount": semantic_count,
        "baselineBudgetMs": 15000,
        "boundedHeadroomMs": 2000,
        "effectiveBudgetMs": 17000,
    },
)


inventory_path = ROOT / "data" / "private" / "machines.json"
inventory_before = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
writeback_ok = server.printer_inventory_ip_update_writeback_synthetic_check()
inventory_after = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
check(
    "writeback-synthetic-uses-fixture-and-preserves-private-inventory",
    writeback_ok
    and inventory_before == inventory_after
    and inventory_after
    == "c6e40803a4038319a621ad43d4927350f72018cb33cfd9bcc73e7c2a09842db9",
    {
        "syntheticPassed": writeback_ok,
        "beforeSha256": inventory_before,
        "afterSha256": inventory_after,
    },
)


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "suite": "p255-package-hermetic-deadline",
            "status": "pass" if not failed else "fail",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
