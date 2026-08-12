#!/usr/bin/env python3
"""Focused regression for final answer and supervision-state agreement."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail or "")})


def envelope(status="complete", *, terminal_status="complete", may_complete=True):
    return {
        "status": status,
        "terminal_state": {
            "status": terminal_status,
            "mayClaimComplete": may_complete,
        },
    }


complete_route = {
    "_supervisionStatus": "reviewing",
    "_answerEnvelope": envelope(),
}
resolved = server.reconcile_terminal_supervision_status(complete_route)
check(
    "typed-complete-resolves-provisional-review",
    resolved == "pass" and complete_route.get("_supervisionStatus") == "pass",
    complete_route,
)
check(
    "resolved-complete-return-code-is-success",
    server.supervision_completion_code(complete_route, 1) == 0,
    server.supervision_completion_code(complete_route, 1),
)
timing = server.model_path_timing_receipt(120, 10, 80, route=complete_route)
check(
    "timing-receipt-reports-final-pass",
    timing.get("supervisionStatus") == "pass",
    timing.get("supervisionStatus"),
)

unreconciled = {
    "_supervisionStatus": "reviewing",
    "_answerEnvelope": envelope(),
}
check(
    "provisional-review-cannot-masquerade-as-success",
    server.supervision_completion_code(unreconciled, 0) == 1,
    server.supervision_completion_code(unreconciled, 0),
)

for state in ("bounded", "blocked", "failed", "cancelled"):
    route = {
        "_supervisionStatus": "reviewing",
        "_answerEnvelope": envelope(
            state,
            terminal_status=state,
            may_complete=False,
        ),
    }
    server.reconcile_terminal_supervision_status(route)
    check(
        f"terminal-{state}-is-preserved",
        route.get("_supervisionStatus") == state,
        route,
    )

incomplete_terminal = {
    "_supervisionStatus": "reviewing",
    "_answerEnvelope": envelope(terminal_status="bounded", may_complete=False),
}
server.reconcile_terminal_supervision_status(incomplete_terminal)
check(
    "incomplete-terminal-proof-does-not-promote",
    incomplete_terminal.get("_supervisionStatus") == "reviewing",
    incomplete_terminal,
)

source = (ROOT / "server.py").read_text(encoding="utf-8")
assignment = 'route["_answerEnvelope"] = package["answerEnvelope"]'
reconciliation = "reconcile_terminal_supervision_status(route)"
check(
    "emission-reconciles-before-assistant-event",
    assignment in source
    and reconciliation in source[source.index(assignment) : source.index("assistant_event =", source.index(assignment))],
)

failed = [item for item in checks if not item["passed"]]
report = {
    "status": "pass" if not failed else "fail",
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "total": len(checks),
    "checks": checks,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
