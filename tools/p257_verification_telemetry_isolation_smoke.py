#!/usr/bin/env python3
"""P257 adversaries for production-only autonomy supervisor telemetry."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
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


def signature(path):
    try:
        data = Path(path).read_bytes()
    except OSError:
        return {"exists": False, "size": 0, "sha256": ""}
    return {
        "exists": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


historical_before = signature(server.AUTONOMY_SUPERVISOR_LOG_PATH)

canonical = server.package_health_subprocess_environment(
    {"PATH": "/fixture/bin", "CODEX_PACKAGE_HEALTH_WORKER": "0", "KEEP": "yes"}
)
check(
    "canonical-package-child-environment-forces-worker-identity",
    canonical.get("CODEX_PACKAGE_HEALTH_WORKER") == "1"
    and canonical.get("PATH") == server.PATH_FOR_CODEX
    and canonical.get("KEEP") == "yes",
    {
        "worker": canonical.get("CODEX_PACKAGE_HEALTH_WORKER"),
        "pathMatches": canonical.get("PATH") == server.PATH_FOR_CODEX,
        "preserved": canonical.get("KEEP"),
    },
)

all_specs = (
    server.package_health_parallel_smoke_specs()
    + server.package_health_resource_smoke_specs()
    + server.package_health_quiescent_smoke_specs()
    + server.package_health_exclusive_smoke_specs()
)
check(
    "every-scheduled-package-child-is-explicitly-a-worker",
    bool(all_specs)
    and all(
        (item.get("env") or {}).get("CODEX_PACKAGE_HEALTH_WORKER") == "1"
        and (item.get("env") or {}).get("PATH") == server.PATH_FOR_CODEX
        for item in all_specs
    ),
    {"specCount": len(all_specs)},
)

source = (ROOT / "server.py").read_text(encoding="utf-8")
check(
    "isolated-synthetics-and-package-specs-share-the-canonical-boundary",
    "env=package_health_subprocess_environment()," in source
    and "environment = package_health_subprocess_environment()" in source,
)

original_path = server.AUTONOMY_SUPERVISOR_LOG_PATH
original_worker = os.environ.get("CODEX_PACKAGE_HEALTH_WORKER")
try:
    with tempfile.TemporaryDirectory(prefix="p257-autonomy-") as temp_dir:
        fixture_path = Path(temp_dir) / "autonomy.jsonl"
        server.AUTONOMY_SUPERVISOR_LOG_PATH = fixture_path
        os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)

        server.append_autonomy_supervisor_log({"action": "real-fixture"})
        real_rows = [
            json.loads(line)
            for line in fixture_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        check(
            "real-production-row-has-explicit-provenance",
            len(real_rows) == 1
            and real_rows[0].get("action") == "real-fixture"
            and real_rows[0].get("provenance") == "production",
            real_rows,
        )

        before_worker = signature(fixture_path)
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = "1"
        server.append_autonomy_supervisor_log({"action": "package-fixture"})
        after_worker = signature(fixture_path)
        check(
            "package-worker-cannot-write-autonomy-telemetry",
            before_worker == after_worker,
            {"before": before_worker, "after": after_worker},
        )

        os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)
        messages = [
            {"role": "user", "text": "Search the web for current controller prices."}
        ]
        route = {"projectId": "general", "engine": "manager"}
        before_suppressed = signature(fixture_path)
        suppressed = server.autonomy_supervisor_recover_answer(
            messages,
            route,
            "No current sources were checked.",
            web_search="off",
            record=False,
        )
        after_suppressed = signature(fixture_path)
        recorded = server.autonomy_supervisor_recover_answer(
            messages,
            route,
            "No current sources were checked.",
            web_search="off",
            record=True,
        )
        final_rows = [
            json.loads(line)
            for line in fixture_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        check(
            "synthetic-and-test-callers-can-suppress-learning-telemetry",
            suppressed.get("status", {}).get("needsHelp") is True
            and before_suppressed == after_suppressed
            and recorded.get("status", {}).get("needsHelp") is True
            and len(final_rows) == 2
            and final_rows[-1].get("action") == "needs-help"
            and final_rows[-1].get("provenance") == "production",
            {"rowCount": len(final_rows)},
        )
finally:
    server.AUTONOMY_SUPERVISOR_LOG_PATH = original_path
    if original_worker is None:
        os.environ.pop("CODEX_PACKAGE_HEALTH_WORKER", None)
    else:
        os.environ["CODEX_PACKAGE_HEALTH_WORKER"] = original_worker

check(
    "runtime-test-runs-and-package-synthetics-explicitly-disable-recording",
    'record=not bool((route or {}).get("_testRun"))' in source
    and "bad_answer,\n            web_search=\"live\",\n            record=False," in source,
)

live_feedback_source = (ROOT / "tools" / "live_feedback_smoke.py").read_text(
    encoding="utf-8"
)
generic_live_source = (
    ROOT / "tools" / "live_generic_typed_conversation_smoke.py"
).read_text(encoding="utf-8")
typed_live_source = (
    ROOT / "tools" / "live_typed_capability_conversation_smoke.py"
).read_text(encoding="utf-8")
stream_live_source = (ROOT / "tools" / "api_run_stream_contract_smoke.py").read_text(
    encoding="utf-8"
)
check(
    "live-verification-clients-identify-every-api-run-as-test-traffic",
    'request_payload["testRun"] = True' in live_feedback_source
    and live_feedback_source.count('"testRun": True') >= 1
    and generic_live_source.count('"testRun": True') == 1
    and typed_live_source.count('"testRun": True') == 1
    and stream_live_source.count('"testRun": True') == 1,
)

historical_after = signature(server.AUTONOMY_SUPERVISOR_LOG_PATH)
check(
    "historical-autonomy-evidence-remains-byte-identical",
    historical_before == historical_after,
    {"before": historical_before, "after": historical_after},
)

export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "p257-package-registration-and-public-export-are-single-owner",
    source.count('"server:verification-telemetry-isolation-p257"') == 3
    and source.count('"p257_verification_telemetry_isolation_smoke.py"') == 2
    and export_source.count('"tools/p257_verification_telemetry_isolation_smoke.py"')
    == 1,
)

failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "suite": "p257-verification-telemetry-isolation",
            "status": "pass" if not failed else "fail",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failures": failed,
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
