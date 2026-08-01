#!/usr/bin/env python3
"""Verify typed capability ownership across adversarial first and follow-up turns."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server
from tools.adversarial_understanding_replay import CASES


EXPECTED_BY_DOMAIN = {
    "engineering_power_conversion": "engineering-power-conversion",
    "engineering_advisory": "engineering-advisory",
    "klipper_config_migration": "klipper-config-migration",
}


def main() -> int:
    rows = []
    for case in CASES:
        first_messages = [{"role": "user", "text": case["first"]}]
        followup_messages = first_messages + [
            {"role": "assistant", "text": "Prior answer placeholder."},
            {"role": "user", "text": case["followup"]},
        ]
        for stage, messages in (("first", first_messages), ("followup", followup_messages)):
            route = server.route_manager(
                messages,
                requested_profile="manager",
                web_search=case.get("followupWebSearch", case.get("webSearch", "disabled")) if stage == "followup" else case.get("webSearch", "disabled"),
            )
            frame = route.get("intentFrame") or {}
            decision = route.get("kernelDecision") or {}
            plan = route.get("capabilityPlan") or {}
            expected = EXPECTED_BY_DOMAIN.get(frame.get("domain"), "")
            model_first = decision.get("mode") == "model-first"
            passed = bool(
                expected
                and plan.get("registered") is True
                and plan.get("id") == expected
                and (not model_first or decision.get("allowLegacyDirectAnswer") is False)
            )
            rows.append(
                {
                    "case": case["id"],
                    "stage": stage,
                    "domain": frame.get("domain"),
                    "mode": decision.get("mode"),
                    "allowLegacyDirectAnswer": decision.get("allowLegacyDirectAnswer"),
                    "plan": plan.get("id"),
                    "expected": expected,
                    "passed": passed,
                }
            )
    failures = [row for row in rows if not row["passed"]]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(rows) - len(failures),
        "total": len(rows),
        "registered": sum(1 for row in rows if row.get("plan") != "unregistered"),
        "failures": failures,
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
