#!/usr/bin/env python3
"""Run P4 Evidence-to-Answer Grounding acceptance checks."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def load_fixture():
    path = ROOT / "tests" / "evidence_grounding_p4_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else []
    if not isinstance(cases, list) or len(cases) < 7:
        raise ValueError("evidence-grounding fixture needs at least seven cases")
    return data, cases


def evaluate_case(case):
    messages = case.get("messages") if isinstance(case.get("messages"), list) else []
    route = case.get("route") if isinstance(case.get("route"), dict) else {}
    answer = str(case.get("answer") or "")
    expectations = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    package = server.response_package(
        messages,
        route,
        answer,
        web_search="disabled",
        evidence=case.get("evidence"),
    )
    gate = package.get("evidenceClaimGate") if isinstance(package.get("evidenceClaimGate"), dict) else {}
    has_boundary = "evidence boundary:" in str(package.get("text") or "").lower()
    failures = []
    if gate.get("status") != expectations.get("status"):
        failures.append("claim-gate status")
    if gate.get("sourceType") != expectations.get("sourceType"):
        failures.append("claim-gate source type")
    if has_boundary != bool(expectations.get("boundary")):
        failures.append("visible evidence boundary")
    if not isinstance(package.get("evidenceLedger"), list) or not package.get("evidenceLedger"):
        failures.append("evidence ledger present")
    return {
        "id": case.get("id") or "unnamed",
        "gate": gate,
        "hasBoundary": has_boundary,
        "failedChecks": failures,
        "passed": not failures,
    }


def main():
    parser = argparse.ArgumentParser(description="Run P4 evidence grounding checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fixture, cases = load_fixture()
    results = [evaluate_case(case) for case in cases]
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": fixture.get("suite") or "evidence-grounding-p4",
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
