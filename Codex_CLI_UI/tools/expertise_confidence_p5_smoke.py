#!/usr/bin/env python3
"""Run P5 calibrated-expertise-confidence acceptance checks."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def load_fixture():
    path = ROOT / "tests" / "expertise_confidence_p5_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else []
    if not isinstance(cases, list) or len(cases) < 6:
        raise ValueError("expertise-confidence fixture needs at least six cases")
    return data, cases


def evaluate_case(case):
    package = server.response_package(
        case.get("messages") if isinstance(case.get("messages"), list) else [],
        case.get("route") if isinstance(case.get("route"), dict) else {},
        str(case.get("answer") or ""),
        web_search="disabled",
        evidence=case.get("evidence"),
    )
    confidence = package.get("expertiseConfidence") if isinstance(package.get("expertiseConfidence"), dict) else {}
    expected = str(case.get("expectedLevel") or "")
    failures = []
    if confidence.get("level") != expected:
        failures.append("confidence level")
    if not confidence.get("label") or not confidence.get("basis") or not confidence.get("nextMove"):
        failures.append("confidence explanation")
    return {
        "id": case.get("id") or "unnamed",
        "confidence": confidence,
        "failedChecks": failures,
        "passed": not failures,
    }


def main():
    parser = argparse.ArgumentParser(description="Run P5 expertise-confidence checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fixture, cases = load_fixture()
    results = [evaluate_case(case) for case in cases]
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": fixture.get("suite") or "expertise-confidence-p5",
        "caseCount": len(results),
        "failedCount": len(failed),
        "status": "pass" if not failed else "fail",
        "cases": results,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"{report['suite']}: {report['status']} ({report['caseCount'] - report['failedCount']}/{report['caseCount']})")
        for result in results:
            print(f"- {result['id']}: {'pass' if result['passed'] else 'fail'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
