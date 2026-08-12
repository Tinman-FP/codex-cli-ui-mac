#!/usr/bin/env python3
"""Focused adversaries for bounded package child and predicate diagnostics."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, ok, detail=""):
    checks.append(
        {
            "name": name,
            "status": "pass" if ok else "fail",
            "detail": detail,
        }
    )


passed = server.package_health_child_diagnostics(
    {
        "status": "pass",
        "suite": "fixture-pass",
        "checkCount": 2,
        "passed": 2,
        "failed": 0,
        "checks": [
            {"name": "first", "status": "pass"},
            {"name": "second", "status": "pass"},
        ],
    },
    '{"status":"pass"}',
)
check(
    "nested-pass-keeps-summary-without-inventing-failures",
    passed.get("status") == "pass"
    and passed.get("checkCount") == 2
    and passed.get("failedChecks") == []
    and passed.get("contentsRecorded") is False,
    passed,
)


failed = server.package_health_child_diagnostics(
    {
        "status": "fail",
        "suite": "fixture-fail",
        "failed": 2,
        "failures": [
            {
                "name": "to" + "ken=" + "top-secret /Us" + "ers/alice/private-case",
                "status": "fail",
                "detail": "pass" + "word=" + "hunter2 at http://private.example/file from 192." + "168.1.7",
            },
            {"id": "named-predicate", "error": "expected stable lineage"},
        ],
    },
    '{"status":"fail"}',
)
failed_text = json.dumps(failed, sort_keys=True)
check(
    "nested-failures-retain-names-and-redact-private-detail",
    [item.get("name") for item in failed.get("failedChecks") or []]
    == ["token=[redacted] $HOME/private-case", "named-predicate"]
    and "hunter2" not in failed_text
    and "private.example" not in failed_text
    and "192." + "168.1.7" not in failed_text
    and "/Us" + "ers/alice" not in failed_text,
    failed,
)


malformed = server.package_health_child_diagnostics({}, "not-json private prose")
check(
    "malformed-child-output-is-explicit-without-copying-content",
    malformed.get("parsed") is False
    and malformed.get("malformed") is True
    and "private prose" not in json.dumps(malformed),
    malformed,
)


many_failures = [
    {"name": f"failure-{index}", "detail": "x" * 2000}
    for index in range(40)
]
bounded = server.package_health_child_diagnostics(
    {"status": "fail", "failed": 40, "failures": many_failures},
    '{"status":"fail"}',
)
bounded_bytes = len(json.dumps(bounded, sort_keys=True, separators=(",", ":")).encode())
check(
    "nested-diagnostics-are-row-and-byte-bounded",
    len(bounded.get("failedChecks") or [])
    <= server.PACKAGE_HEALTH_CHILD_DIAGNOSTIC_MAX_ROWS
    and bounded.get("omittedFailureCount", 0) > 0
    and bounded_bytes <= server.PACKAGE_HEALTH_CHILD_DIAGNOSTIC_MAX_BYTES + 64,
    {"rows": len(bounded.get("failedChecks") or []), "bytes": bounded_bytes},
)


source_sha = server.current_verification_receipt_snapshot_source_sha256()
script_path = Path(server.__file__).resolve()
spec = {
    "checkName": "fixture-source-drift",
    "command": [sys.executable, str(script_path)],
    "cwd": str(ROOT),
    "env": {},
    "timeout": 5,
    "sourceSha256": source_sha,
    "inputSha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
    "isolation": "process",
    "sideEffectFree": True,
}


def fake_completed(*_args, **_kwargs):
    return SimpleNamespace(
        returncode=1,
        stdout=json.dumps(
            {
                "status": "fail",
                "failed": 1,
                "failures": [{"name": "child-case", "detail": "predicate false"}],
            }
        ),
        stderr="",
    )


original_source_reader = server.current_verification_receipt_snapshot_source_sha256
source_reads = iter((source_sha, "f" * 64))
try:
    server.current_verification_receipt_snapshot_source_sha256 = lambda: next(
        source_reads, "f" * 64
    )
    drift = server._run_package_health_parallel_smoke(spec, fake_completed)
finally:
    server.current_verification_receipt_snapshot_source_sha256 = original_source_reader
check(
    "source-drift-retains-child-failure-but-cannot-be-completed",
    drift.get("status") == "source-drift"
    and drift.get("sourceStable") is False
    and drift.get("derived") is False
    and drift.get("reused") is False
    and (drift.get("childDiagnostics") or {}).get("failedChecks", [{}])[0].get("name")
    == "child-case",
    {key: value for key, value in drift.items() if key not in {"completed", "exception"}},
)


def fake_malformed(*_args, **_kwargs):
    return SimpleNamespace(returncode=1, stdout="not-json", stderr="ignored private text")


malformed_wrapper = server._run_package_health_parallel_smoke(spec, fake_malformed)
check(
    "wrapper-marks-malformed-json-without-stderr-content",
    malformed_wrapper.get("status") == "completed"
    and (malformed_wrapper.get("childDiagnostics") or {}).get("malformed") is True
    and "ignored private text"
    not in json.dumps(malformed_wrapper.get("childDiagnostics") or {}, default=str),
    {key: value for key, value in malformed_wrapper.items() if key != "completed"},
)


def fake_timeout(*_args, **_kwargs):
    raise subprocess.TimeoutExpired(["fixture"], 5, output='{"status":"fail"}')


timed_out = server._run_package_health_parallel_smoke(spec, fake_timeout)
timeout_diagnostics = timed_out.get("childDiagnostics") or {}
check(
    "wrapper-timeout-is-fail-closed-and-retains-deadline-metadata",
    timed_out.get("status") == "timed-out"
    and timed_out.get("timedOut") is True
    and timed_out.get("returnCode") == 124
    and timed_out.get("derived") is False
    and timed_out.get("reused") is False
    and (timeout_diagnostics.get("wrapper") or {}).get("timedOut") is True
    and (timeout_diagnostics.get("wrapper") or {}).get("deadlineMs") == 5000,
    {key: value for key, value in timed_out.items() if key != "exception"},
)


predicate_pass = server.synthetic_predicate_diagnostic_report(
    "fixture-predicates", (("one", True), ("two", True))
)
predicate_fail = server.synthetic_predicate_diagnostic_report(
    "fixture-predicates", (("one", True), ("two", False), ("three", True))
)
check(
    "named-predicate-aggregation-preserves-all-pass-boolean",
    predicate_pass.get("status") == "pass"
    and predicate_pass.get("passed") == 2
    and predicate_pass.get("failed") == 0,
    predicate_pass,
)
check(
    "named-predicate-aggregation-identifies-exact-failure",
    predicate_fail.get("status") == "fail"
    and predicate_fail.get("passed") == 2
    and predicate_fail.get("failed") == 1
    and predicate_fail.get("failures") == [{"name": "two", "status": "fail"}],
    predicate_fail,
)


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
package_start = server_source.index("def package_health_report():")
package_end = server_source.index("def persist_isolated_package_health_report", package_start)
package_source = server_source[package_start:package_end]
check(
    "package-report-captures-all-child-json-through-one-helper",
    package_source.count("capture_package_child_report(") >= 40
    and package_source.count("parse_model_json_object(") == 1
    and '"childDiagnostics": child_diagnostics' in package_source,
    {
        "captured": package_source.count("capture_package_child_report("),
        "rawParsers": package_source.count("parse_model_json_object("),
    },
)
check(
    "four-monolithic-checks-expose-diagnostic-mode-with-legacy-boolean-callers",
    all(
        f"def {name}(diagnostics=False):" in server_source
        and f'"{name}"' in server_source
        for name in (
            "engineering_project_archetype_reasoning_p93_synthetic_check",
            "grounded_conversational_judgment_p112_synthetic_check",
            "decision_linked_observability_p113_synthetic_check",
            "standalone_knowledge_primary_boundary_synthetic_check",
        )
    ),
    "four diagnostic entry points",
)


failed_checks = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed_checks else "fail",
            "suite": "p247-package-diagnostic-fidelity",
            "schemaVersion": 1,
            "checkCount": len(checks),
            "passed": len(checks) - len(failed_checks),
            "failed": len(failed_checks),
            "failures": failed_checks,
            "checks": checks,
            "contentsRecorded": False,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed_checks else 0)
