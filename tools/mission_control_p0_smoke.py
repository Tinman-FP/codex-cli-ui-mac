#!/usr/bin/env python3
"""Run deterministic P0 Mission Control contract checks without invoking a model."""

import argparse
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CASES = APP_DIR / "tests" / "mission_control_p0_cases.json"


def load_cases(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("Mission Control case file must contain a non-empty cases list.")
    return cases


def contains_all(text, expected):
    value = str(text or "")
    return all(str(item) in value for item in expected)


def run_case(server, case):
    kind = str(case.get("kind") or "")
    messages = case.get("messages") if isinstance(case.get("messages"), list) else []
    compass = case.get("sessionCompass") if isinstance(case.get("sessionCompass"), dict) else {}
    result = {"id": str(case.get("id") or kind or "unnamed"), "kind": kind}
    if kind in {"recommend", "execute", "clarify"}:
        route = server.route_manager(messages, web_search="disabled", session_compass=compass)
        plan = route.get("objectivePlan") or {}
        answer = server.session_compass_followup_direct_answer(messages, route, plan)
        result.update(
            {
                "responseKind": plan.get("responseKind"),
                "answerPreview": str(answer).replace("\n", " ")[:260],
                "passed": plan.get("responseKind") == case.get("expectedResponseKind")
                and (kind != "recommend" or contains_all(answer, case.get("required") or [])),
            }
        )
    elif kind == "progress":
        route = server.route_manager(messages, web_search="disabled", session_compass=compass)
        progress = server.session_compass_progress_update(messages, route, case.get("answer") or "") or {}
        result.update(
            {
                "phase": progress.get("phase"),
                "nextStep": progress.get("nextStep"),
                "passed": progress.get("phase") == case.get("expectedPhase")
                and progress.get("nextStep") == case.get("expectedNextStep"),
            }
        )
    elif kind == "redaction":
        compass_state = server.normalize_session_compass(compass) or {}
        result.update(
            {
                "objective": compass_state.get("objective"),
                "passed": "MISSION_CONTROL_FIXTURE_SECRET" not in str(compass_state.get("objective") or "")
                and "[hidden]" in str(compass_state.get("objective") or ""),
            }
        )
    elif kind == "safety":
        route = server.route_manager(messages, web_search="disabled")
        contract = server.task_contract(messages, route)
        requirements = contract.get("mustDo") if isinstance(contract.get("mustDo"), list) else []
        result.update(
            {
                "contractKind": contract.get("kind"),
                "mustDo": requirements,
                "passed": contract.get("kind") == "Klipper restart safety"
                and all(item in requirements for item in case.get("required") or []),
            }
        )
    else:
        result["passed"] = False
        result["error"] = f"Unsupported case kind: {kind or 'missing'}"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(APP_DIR))
    import server  # pylint: disable=import-outside-toplevel

    cases = load_cases(args.cases)
    results = [run_case(server, case) for case in cases]
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": "mission-control-p0",
        "status": "pass" if not failed else "fail",
        "caseCount": len(results),
        "failedCount": len(failed),
        "cases": results,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"cases: {report['caseCount']}")
        for result in results:
            print(f"{'PASS' if result.get('passed') else 'FAIL'}: {result['id']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
