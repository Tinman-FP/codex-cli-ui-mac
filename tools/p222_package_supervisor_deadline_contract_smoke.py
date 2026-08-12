#!/usr/bin/env python3
"""P222 regressions for package worker/supervisor deadline ordering."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


default_contract = server.package_health_deadline_contract(900, headroom=300)
check(
    "default-adds-bounded-supervisor-headroom",
    default_contract.get("workerBudgetSeconds") == 900
    and default_contract.get("supervisorHeadroomSeconds") == 300
    and default_contract.get("supervisorTimeoutSeconds") == 1200,
    default_contract,
)

low_contract = server.package_health_deadline_contract(900, headroom=-100)
high_contract = server.package_health_deadline_contract(900, headroom=9999)
check(
    "configured-headroom-is-clamped-to-safe-bounds",
    low_contract.get("supervisorHeadroomSeconds") == 60
    and high_contract.get("supervisorHeadroomSeconds") == 600,
    {"low": low_contract, "high": high_contract},
)

check(
    "worker-deadline-always-precedes-supervisor-hard-stop",
    all(
        contract["workerBudgetSeconds"]
        < contract["supervisorTimeoutSeconds"]
        for contract in (default_contract, low_contract, high_contract)
    ),
    {"default": default_contract, "low": low_contract, "high": high_contract},
)

# P221 published check 526 at 898,406 ms under a 900,000 ms hard stop. The
# remaining 1,594 ms was only 76 ms longer than its last completed check and
# could not cover the remaining package rows or final report serialization.
p221_elapsed_ms = 898_406
p221_last_check_ms = 1_518
p221_remaining_ms = 900_000 - p221_elapsed_ms
check(
    "measured-p221-runtime-proves-900-second-hard-stop-had-no-suite-headroom",
    0 < p221_remaining_ms <= p221_last_check_ms + 100
    and default_contract["supervisorTimeoutSeconds"] * 1000
    - p221_elapsed_ms
    >= 300_000,
    {
        "elapsedMsAtCheck526": p221_elapsed_ms,
        "lastCheckDurationMs": p221_last_check_ms,
        "oldHardStopRemainingMs": p221_remaining_ms,
        "newSupervisorRemainingMs": default_contract["supervisorTimeoutSeconds"]
        * 1000
        - p221_elapsed_ms,
    },
)

with tempfile.TemporaryDirectory(prefix="p222-progress-") as tmp_dir:
    progress_path = Path(tmp_dir) / "progress.json"
    prior = {
        "worker": os.environ.get("CODEX_PACKAGE_HEALTH_WORKER"),
        "progress": os.environ.get(server.PACKAGE_HEALTH_PROGRESS_PATH_ENV),
        "owner": os.environ.get(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV),
        "budget": os.environ.get(
            server.PACKAGE_HEALTH_WORKER_BUDGET_SECONDS_ENV
        ),
    }
    try:
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = "1"
        os.environ[server.PACKAGE_HEALTH_PROGRESS_PATH_ENV] = str(progress_path)
        os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = str(os.getpid())
        os.environ[server.PACKAGE_HEALTH_WORKER_BUDGET_SECONDS_ENV] = "0.001"
        progress = server.package_health_worker_progress(
            [{"name": "complete", "status": "pass", "durationMs": 1}],
            server.time.perf_counter() - 2,
        )
    finally:
        mapping = {
            "worker": "CODEX_PACKAGE_HEALTH_WORKER",
            "progress": server.PACKAGE_HEALTH_PROGRESS_PATH_ENV,
            "owner": server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV,
            "budget": server.PACKAGE_HEALTH_WORKER_BUDGET_SECONDS_ENV,
        }
        for key, env_name in mapping.items():
            if prior[key] is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = prior[key]
    persisted_progress = json.loads(progress_path.read_text(encoding="utf-8"))
check(
    "progress-preserves-counts-and-exposes-soft-budget-overrun",
    progress.get("completedCheckCount") == 1
    and persisted_progress.get("passed") == 1
    and persisted_progress.get("workerBudgetExceeded") is True
    and persisted_progress.get("workerBudgetRemainingMs") == 0
    and persisted_progress.get("contentsRecorded") is False,
    persisted_progress,
)

with tempfile.TemporaryDirectory(prefix="p222-timeout-") as tmp_dir:
    prior_latest = server.PACKAGE_HEALTH_LATEST_PATH
    prior_run = server.subprocess.run
    server.PACKAGE_HEALTH_LATEST_PATH = Path(tmp_dir) / "latest.json"

    def adversarial_timeout(*_args, **kwargs):
        progress_path = Path(
            kwargs["env"][server.PACKAGE_HEALTH_PROGRESS_PATH_ENV]
        )
        progress_path.write_text(
            json.dumps(
                {
                    "kind": "package-health-worker-progress",
                    "completedCheckCount": 526,
                    "passed": 526,
                    "failed": 0,
                    "warned": 0,
                    "lastCompletedCheck": {
                        "name": "response:tinman-etiquette",
                        "status": "pass",
                    },
                    "contentsRecorded": False,
                }
            ),
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(cmd="fixture", timeout=kwargs["timeout"])

    try:
        server.subprocess.run = adversarial_timeout
        timeout_report = server.isolated_package_health_report(timeout=30)
    finally:
        server.subprocess.run = prior_run
        server.PACKAGE_HEALTH_LATEST_PATH = prior_latest
check(
    "supervisor-timeout-preserves-trusted-progress-and-fails-closed",
    timeout_report.get("status") == "fail"
    and timeout_report.get("partial") is True
    and timeout_report.get("passed") == 526
    and timeout_report.get("failed") == 1
    and timeout_report.get("total") == 527
    and timeout_report.get("progressCountsTrusted") is True
    and timeout_report.get("workerTimeoutSeconds") == 30
    and timeout_report.get("supervisorTimeoutSeconds") == 330
    and "supervisor timed out" in timeout_report["checks"][0]["detail"],
    timeout_report,
)

untrusted = server.package_health_progress_counts(
    {"completedCheckCount": 2, "passed": 999, "failed": 0, "warned": 0}
)
check(
    "adversarial-progress-counters-cannot-create-a-false-green-partial",
    untrusted
    == {
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "warned": 0,
        "trusted": False,
    },
    untrusted,
)

source = (ROOT / "server.py").read_text(encoding="utf-8")
check(
    "p220-focused-smoke-budget-remains-independent-at-30-seconds",
    server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS == 30
    and "timeout=PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS" in source,
    server.PACKAGE_HEALTH_FOCUSED_SMOKE_TIMEOUT_SECONDS,
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
