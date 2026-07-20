#!/usr/bin/env python3
"""Run the P6 representativeness guard for the redacted conversation corpus."""

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
    report = server.conversation_quality_p6_coverage_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"{report['suite']}: {report['status']} ({report['caseCount']}/{report['minimumCaseCount']} cases)")
        print(f"- multi-turn continuity: {report['multiTurnCaseCount']}/{report['minimumMultiTurnCases']}")
        print(f"- traceable source boundaries: {report['sourceBoundaryCaseCount']}/{report['minimumSourceBoundaryCases']}")
        for failure in report.get("coverageFailures") or []:
            print(f"- missing coverage: {failure['tag']} ({failure['actual']}/{failure['required']})")
        for failure in report.get("failures") or []:
            print(f"- failed: {failure}")
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
