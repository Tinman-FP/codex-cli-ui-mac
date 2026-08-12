#!/usr/bin/env python3
"""P205 regression: typed clarification owns wording and specialist context."""

from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from intelligence_kernel import build_clarification_question, build_generic_intent_frame
import server


def check(name, condition, detail, rows):
    rows.append({"name": name, "ok": bool(condition), "detail": detail})


def main():
    rows = []
    strength = [{"role": "user", "text": "Can you make it stronger?"}]
    printer = [{"role": "user", "text": "do the same for the other printer"}]
    profile = [{"role": "user", "text": "put those settings on the other profile"}]

    strength_frame = build_generic_intent_frame(strength)
    strength_answer = build_clarification_question(strength, strength_frame)
    check(
        "strength request becomes typed clarification",
        strength_frame.get("domain") == "clarification"
        and "strength-requirements-clarification" in strength_frame.get("frameTags", []),
        str(strength_frame.get("frameTags")),
        rows,
    )
    check(
        "strength question names decision dimensions",
        all(term in strength_answer.lower() for term in ("which part", "load and direction", "failure mode", "bending stiffness", "impact", "fatigue"))
        and strength_answer.count("?") == 1,
        strength_answer,
        rows,
    )

    for name, messages, expected_project, expected_phrase in (
        ("printer", printer, "printer-klipper-ops", "target printer"),
        ("profile", profile, "orcaslicer-codex", "destination profile"),
    ):
        route = server.route_manager(messages, web_search="disabled")
        answer = build_clarification_question(messages, route.get("intentFrame") or {})
        check(
            f"{name} clarification preserves specialist project",
            route.get("projectId") == expected_project
            and (route.get("capabilityPlan") or {}).get("id") == "focused-clarification",
            f"project={route.get('projectId')} plan={(route.get('capabilityPlan') or {}).get('id')}",
            rows,
        )
        check(
            f"{name} clarification asks for actionable context",
            "previous action" in answer.lower()
            and expected_phrase in answer.lower()
            and answer.count("?") == 1,
            answer,
            rows,
        )
        check(
            f"{name} typed owner is not preempted",
            server.unresolved_referent_preflight_response(messages, route) == {},
            str(route.get("intentFrame", {}).get("targetSurface")),
            rows,
        )
        result = server.execute_deterministic_capability(messages, route)
        check(
            f"{name} clarification is a successful conversation turn",
            result.get("handled") is True
            and result.get("outcome") == "needs-input"
            and server.successful_conversational_clarification(route),
            str(route.get("_capabilityExecution")),
            rows,
        )

    prior_context = [
        {"role": "user", "text": "This bracket fails at the upper bolt under a downward 800 N load."},
        {"role": "assistant", "text": "I see the failure location and load direction."},
        {"role": "user", "text": "Can you make it stronger?"},
    ]
    named_target = [{"role": "user", "text": "Can you make this motor mount stronger?"}]
    check(
        "visible prior context prevents clarification reset",
        build_generic_intent_frame(prior_context).get("domain") != "clarification",
        str(build_generic_intent_frame(prior_context).get("domain")),
        rows,
    )
    check(
        "self-contained strength request proceeds",
        build_generic_intent_frame(named_target).get("domain") != "clarification",
        str(build_generic_intent_frame(named_target).get("domain")),
        rows,
    )

    passed = sum(1 for row in rows if row["ok"])
    for row in rows:
        print(("PASS" if row["ok"] else "FAIL"), row["name"], "-", row["detail"])
    print(f"P205 typed clarification ownership: {passed}/{len(rows)} checks passed")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
