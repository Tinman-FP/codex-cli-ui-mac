#!/usr/bin/env python3
"""P211 regressions for bounded package-health timing and progress truth."""

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


check(
    "full-suite-timeout-has-measured-runtime-headroom",
    900 <= server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS <= 1800,
    server.PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS,
)

with tempfile.TemporaryDirectory(prefix="p211-progress-") as tmp_dir:
    progress_path = Path(tmp_dir) / "progress.json"
    prior_worker = os.environ.get("CODEX_PACKAGE_HEALTH_WORKER")
    prior_progress = os.environ.get(server.PACKAGE_HEALTH_PROGRESS_PATH_ENV)
    prior_owner = os.environ.get(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV)
    prior_wall_time = server.time.time
    try:
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = "1"
        os.environ[server.PACKAGE_HEALTH_PROGRESS_PATH_ENV] = str(progress_path)
        os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = str(os.getpid())
        server.time.time = lambda: 0.0
        snapshot = server.package_health_worker_progress(
            [
                {"name": "first", "status": "pass", "detail": "ok", "durationMs": 3},
                {"name": "second", "status": "warn", "detail": "bounded", "durationMs": 4},
            ],
            server.time.perf_counter() - 0.01,
        )
    finally:
        server.time.time = prior_wall_time
        if prior_worker is None:
            os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)
        else:
            os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = prior_worker
        if prior_progress is None:
            os.environ.pop(server.PACKAGE_HEALTH_PROGRESS_PATH_ENV, None)
        else:
            os.environ[server.PACKAGE_HEALTH_PROGRESS_PATH_ENV] = prior_progress
        if prior_owner is None:
            os.environ.pop(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV, None)
        else:
            os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = prior_owner
    persisted = json.loads(progress_path.read_text(encoding="utf-8"))
    check(
        "worker-progress-is-bounded-and-machine-readable",
        snapshot.get("completedCheckCount") == 2
        and persisted.get("passed") == 1
        and persisted.get("warned") == 1
        and persisted.get("elapsedMs", 0) >= 5
        and (persisted.get("lastCompletedCheck") or {}).get("name") == "second"
        and persisted.get("contentsRecorded") is False,
        persisted,
    )

with tempfile.TemporaryDirectory(prefix="p211-nested-progress-") as tmp_dir:
    progress_path = Path(tmp_dir) / "progress.json"
    prior_worker = os.environ.get("CODEX_PACKAGE_HEALTH_WORKER")
    prior_progress = os.environ.get(server.PACKAGE_HEALTH_PROGRESS_PATH_ENV)
    prior_owner = os.environ.get(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV)
    try:
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = "1"
        os.environ[server.PACKAGE_HEALTH_PROGRESS_PATH_ENV] = str(progress_path)
        os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = str(os.getpid() + 1)
        nested_snapshot = server.package_health_worker_progress(
            [{"name": "nested", "status": "pass", "detail": "must not escape"}],
            server.time.time(),
        )
    finally:
        if prior_worker is None:
            os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)
        else:
            os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = prior_worker
        if prior_progress is None:
            os.environ.pop(server.PACKAGE_HEALTH_PROGRESS_PATH_ENV, None)
        else:
            os.environ[server.PACKAGE_HEALTH_PROGRESS_PATH_ENV] = prior_progress
        if prior_owner is None:
            os.environ.pop(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV, None)
        else:
            os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = prior_owner
    check(
        "nested-worker-cannot-overwrite-owner-progress",
        nested_snapshot == {} and not progress_path.exists(),
        nested_snapshot,
    )

prior_worker = os.environ.get("CODEX_PACKAGE_HEALTH_WORKER")
prior_owner = os.environ.get(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV)
prior_claimed = server.PACKAGE_HEALTH_PROGRESS_CLAIMED
try:
    os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = "1"
    os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = str(os.getpid())
    server.PACKAGE_HEALTH_PROGRESS_CLAIMED = False
    first_claim = server.claim_package_health_worker_progress()
    recursive_claim = server.claim_package_health_worker_progress()
finally:
    server.PACKAGE_HEALTH_PROGRESS_CLAIMED = prior_claimed
    if prior_worker is None:
        os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)
    else:
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = prior_worker
    if prior_owner is None:
        os.environ.pop(server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV, None)
    else:
        os.environ[server.PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV] = prior_owner
check(
    "recursive-report-cannot-claim-outer-progress",
    first_claim is True and recursive_claim is False,
    {"firstClaim": first_claim, "recursiveClaim": recursive_claim},
)

with tempfile.TemporaryDirectory(prefix="p211-timeout-") as tmp_dir:
    prior_latest = server.PACKAGE_HEALTH_LATEST_PATH
    prior_run = server.subprocess.run
    server.PACKAGE_HEALTH_LATEST_PATH = Path(tmp_dir) / "latest.json"

    def fake_timeout(*_args, **kwargs):
        progress_path = Path(kwargs["env"][server.PACKAGE_HEALTH_PROGRESS_PATH_ENV])
        progress_path.write_text(
            json.dumps(
                {
                    "kind": "package-health-worker-progress",
                    "completedCheckCount": 37,
                    "passed": 36,
                    "failed": 0,
                    "warned": 1,
                    "elapsedMs": 29990,
                    "lastCompletedCheck": {
                        "name": "tools:focused-smoke",
                        "status": "pass",
                        "detail": "37 checks completed",
                        "durationMs": 1200,
                    },
                    "recentChecks": [],
                    "contentsRecorded": False,
                }
            ),
            encoding="utf-8",
        )
        raise subprocess.TimeoutExpired(cmd="fixture", timeout=kwargs["timeout"])

    try:
        server.subprocess.run = fake_timeout
        timeout_report = server.isolated_package_health_report(timeout=30)
    finally:
        server.subprocess.run = prior_run
        server.PACKAGE_HEALTH_LATEST_PATH = prior_latest
    check(
        "timeout-preserves-partial-counts-and-last-check",
        timeout_report.get("status") == "fail"
        and timeout_report.get("partial") is True
        and timeout_report.get("passed") == 36
        and timeout_report.get("warned") == 1
        and timeout_report.get("total") == 38
        and timeout_report.get("receiptPersisted") is True
        and "tools:focused-smoke" in (timeout_report.get("checks") or [{}])[0].get("detail", ""),
        timeout_report,
    )

server_source = (ROOT / "server.py").read_text(encoding="utf-8")
check(
    "blocking-endpoint-uses-configurable-worker-budget",
    "def blocking_package_health_report(timeout=None):" in server_source
    and "PACKAGE_HEALTH_WORKER_TIMEOUT_SECONDS if timeout is None" in server_source
    and "CODEX_PACKAGE_HEALTH_TIMEOUT" in server_source,
)
check(
    "isolated-worker-binds-progress-to-own-pid",
    "PACKAGE_HEALTH_PROGRESS_OWNER_PID_ENV" in server_source
    and "str(os.getpid())" in server_source
    and "owner_pid != str(os.getpid())" in server_source,
)
check(
    "outer-report-claims-progress-once-per-worker",
    "publish_worker_progress = claim_package_health_worker_progress()" in server_source
    and "if publish_worker_progress:" in server_source
    and "PACKAGE_HEALTH_PROGRESS_CLAIMED" in server_source,
)
check(
    "worker-progress-uses-monotonic-clock",
    "progress_started = time.perf_counter()" in server_source
    and "package_health_worker_progress(checks, progress_started)" in server_source
    and "now_monotonic - float(started or now_monotonic)" in server_source,
)
check(
    "timeout-receipt-is-persisted-not-discarded",
    "return persist_isolated_package_health_report({" in server_source
    and "workerProgress" in server_source
    and "last completed check" in server_source,
)

failed = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
