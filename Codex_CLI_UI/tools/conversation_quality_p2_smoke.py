#!/usr/bin/env python3
"""Run the redacted, history-derived conversation-quality P2 acceptance suite."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def load_fixture():
    path = ROOT / "tests" / "conversation_quality_p2_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else []
    if not isinstance(cases, list) or len(cases) < 10:
        raise ValueError("conversation-quality fixture needs at least ten cases")
    return data, cases


def evaluate_case(case):
    result = server.conversation_quality_evaluation(
        case.get("messages") if isinstance(case.get("messages"), list) else [],
        case.get("route") if isinstance(case.get("route"), dict) else {},
        str(case.get("referenceAnswer") or ""),
        contract=case.get("contract") if isinstance(case.get("contract"), dict) else {},
        composition=case.get("composition") if isinstance(case.get("composition"), dict) else {},
        expectations=case.get("expectations") if isinstance(case.get("expectations"), dict) else {},
    )
    failed_checks = [check.get("name") for check in result.get("checks") or [] if not check.get("passed")]
    return {
        "id": case.get("id") or "unnamed",
        "coverage": case.get("coverage") or [],
        "interactionMode": result.get("director", {}).get("mode"),
        "composerMode": result.get("composer", {}).get("mode"),
        "score": result.get("score"),
        "firstSentence": result.get("firstSentence"),
        "failedChecks": failed_checks,
        "passed": result.get("status") == "pass",
    }


def main():
    parser = argparse.ArgumentParser(description="Run conversation-quality P2 acceptance checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fixture, cases = load_fixture()
    results = [evaluate_case(case) for case in cases]
    openings = [" ".join(str(item.get("firstSentence") or "").lower().split()) for item in results]
    unique_openings = len([item for item in openings if item]) == len(set(item for item in openings if item))
    if not unique_openings:
        results.append(
            {
                "id": "varied-answer-openings",
                "coverage": ["conversation-quality"],
                "interactionMode": "",
                "composerMode": "",
                "score": 0,
                "firstSentence": "",
                "failedChecks": ["duplicate first sentence"],
                "passed": False,
            }
        )
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": fixture.get("suite") or "conversation-quality-p2",
        "source": fixture.get("provenance", {}).get("source") if isinstance(fixture.get("provenance"), dict) else "",
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
