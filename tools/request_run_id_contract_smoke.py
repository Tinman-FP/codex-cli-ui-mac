#!/usr/bin/env python3
"""Focused regression for server-bound /api/run request identities."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def main() -> int:
    explicit = "client-run_01:phase.2"
    omitted = [None, ""]
    malformed = [" ", "../escape", "bad run id", {"runId": "nested"}, 42, "x" * 97]
    generated = [server.bound_request_run_id(value) for value in omitted + malformed]
    server_source = (ROOT / "server.py").read_text(encoding="utf-8")

    checks = {
        "explicitValidRunIdPreserved": server.bound_request_run_id(explicit) == explicit,
        "omittedRunIdsReceiveServerIds": all(
            re.fullmatch(r"server-[0-9a-f]{32}", value)
            for value in generated[: len(omitted)]
        ),
        "malformedRunIdsReceiveServerIds": all(
            re.fullmatch(r"server-[0-9a-f]{32}", value)
            for value in generated[len(omitted) :]
        ),
        "generatedRunIdsAreUniqueAndSafe": bool(
            len(set(generated)) == len(generated)
            and all(server.safe_run_id(value) == value for value in generated)
        ),
        "apiRunIngressUsesBoundIdentity": (
            'run_id = bound_request_run_id(payload.get("runId"))' in server_source
        ),
        "payloadHealthIncludesIdentityBoundary": (
            server.json_persistence_payload_hardening_synthetic_check()
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "receipts": {
            "explicit": server.bound_request_run_id(explicit),
            "omitted": generated[: len(omitted)],
            "malformed": generated[len(omitted) :],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
