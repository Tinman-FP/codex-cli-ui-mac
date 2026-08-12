#!/usr/bin/env python3
"""Run P149 verification-receipt evidence handoff checks."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = server.verification_receipt_evidence_p149_synthetic_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['suite']}: {report['status']} "
            f"({report['passedCount']}/{report['checkCount']})"
        )
        for name, passed in report.get("checks", {}).items():
            print(f"- {name}: {'pass' if passed else 'fail'}")
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
