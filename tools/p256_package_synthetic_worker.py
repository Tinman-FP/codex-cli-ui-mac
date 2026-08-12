#!/usr/bin/env python3
"""Execute one allowlisted package synthetic in an isolated interpreter."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def main():
    function_name = str(sys.argv[1] if len(sys.argv) > 1 else "").strip()
    report = {
        "suite": "p256-package-synthetic-worker",
        "function": function_name,
        "status": "fail",
        "ok": False,
        "error": "",
        "contentsRecorded": False,
    }
    if function_name not in server.PACKAGE_HEALTH_RESOURCE_SYNTHETIC_CHECKS:
        report["error"] = "package synthetic is not allowlisted for the CPU resource lane"
        print(json.dumps(report, sort_keys=True))
        return 1
    function = getattr(server, function_name, None)
    if not callable(function):
        report["error"] = "allowlisted package synthetic is unavailable"
        print(json.dumps(report, sort_keys=True))
        return 1
    try:
        report["ok"] = bool(function())
        report["status"] = "pass" if report["ok"] else "fail"
    except Exception as exc:
        report["error"] = server.compact(exc, 240)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
