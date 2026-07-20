#!/usr/bin/env python3
"""Run deterministic P1 response-director scenarios without model inference."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def load_cases():
    path = ROOT / "tests" / "interaction_director_p1_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else []
    if not isinstance(cases, list) or not cases:
        raise ValueError("interaction director fixture has no cases")
    return data, cases


def run_case(case):
    messages = case.get("messages") if isinstance(case.get("messages"), list) else []
    route = case.get("route") if isinstance(case.get("route"), dict) else {}
    contract = case.get("contract") if isinstance(case.get("contract"), dict) else {}
    composition = case.get("composition") if isinstance(case.get("composition"), dict) else {}
    director = server.interaction_director_policy(messages, route, contract=contract, composition=composition)
    composer = server.response_composer_policy(
        messages,
        route,
        contract=contract,
        composition=composition,
        director=director,
    )
    passed = (
        director.get("mode") == case.get("expectedInteractionMode")
        and composer.get("mode") == case.get("expectedComposerMode")
        and composer.get("interactionMode") == case.get("expectedInteractionMode")
        and composer.get("answerShape") == case.get("expectedAnswerShape")
        and bool(director.get("instruction"))
        and bool(composer.get("instruction"))
    )
    return {
        "id": case.get("id") or "unnamed",
        "interactionMode": director.get("mode"),
        "composerMode": composer.get("mode"),
        "answerShape": composer.get("answerShape"),
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Run deterministic Response Director P1 checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fixture, cases = load_cases()
    results = [run_case(case) for case in cases]
    metadata_package = server.response_package(
        [{"role": "user", "text": "Make every interaction feel like a personable expert conversation."}],
        {"matched": ["behavior-guidance"], "objectivePlan": {"responseKind": "answer-with-guidance"}},
        "Yes. Keep the answer direct, natural, and useful.",
        web_search="disabled",
    )
    metadata_passed = (
        metadata_package.get("interactionDirector", {}).get("mode") == "conversation"
        and metadata_package.get("responseComposer", {}).get("interactionMode") == "conversation"
    )
    results.append(
        {
            "id": "response-package-carries-director-metadata",
            "interactionMode": metadata_package.get("interactionDirector", {}).get("mode"),
            "composerMode": metadata_package.get("responseComposer", {}).get("mode"),
            "answerShape": metadata_package.get("responseComposer", {}).get("answerShape"),
            "passed": metadata_passed,
        }
    )
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": fixture.get("suite") or "interaction-director-p1",
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
