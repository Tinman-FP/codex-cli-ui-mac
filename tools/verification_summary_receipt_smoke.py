#!/usr/bin/env python3
"""Focused synthetic coverage for Verification Summary live-smoke receipts."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server.py"


def main():
    spec = importlib.util.spec_from_file_location("codex_verification_summary_receipt_smoke", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    report = server.verification_summary_live_smoke_synthetic_check()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
