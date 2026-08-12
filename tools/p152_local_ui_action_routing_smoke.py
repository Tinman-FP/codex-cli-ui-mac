#!/usr/bin/env python3
"""Focused offline regression for canonical local-product UI action routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capability_registry import build_capability_plan  # noqa: E402
from intelligence_kernel import (  # noqa: E402
    build_generic_intent_frame,
    decide_execution,
    select_intent_frame,
)


def evaluate(prompt: str) -> dict:
    messages = [{"role": "user", "text": prompt}]
    frame = build_generic_intent_frame(messages, cwd=str(ROOT))
    decision = decide_execution(frame, route_engine="local", web_search="disabled")
    plan = build_capability_plan(frame, decision)
    return {
        "messages": messages,
        "frame": frame,
        "decision": decision,
        "plan": plan,
    }


def canonical_local_action(result: dict) -> bool:
    frame = result["frame"]
    decision = result["decision"]
    plan = result["plan"]
    allowed_operations = set(frame.get("operationPlan", {}).get("allowedNow") or [])
    return bool(
        frame.get("domain") == "local_product_action"
        and frame.get("actionType") == "inspect_plan_execute_verify"
        and frame.get("routeCandidates") == ["local_code_agent"]
        and decision.get("mode") == "model-first"
        and decision.get("selectedCapability") == "local_code_agent"
        and plan.get("registered") is True
        and plan.get("id") == "local-product-action"
        and plan.get("executor") == "local-agent"
        and plan.get("handler_key") == "local_product_action"
        and {"inspect", "edit", "test"}.issubset(allowed_operations)
    )


def has_local_ui_workflow(result: dict) -> bool:
    allowed = set(result["frame"].get("operationPlan", {}).get("allowedNow") or [])
    return {"inspect", "edit", "test"}.issubset(allowed)


def main() -> int:
    bambu_prompt = (
        "in the model health for the bambu h2d it is now showing printing, which is good, "
        "but i als want it to display percent complete and time remaining on the print."
    )
    run_log_prompt = (
        "The Run Log panel is too tall. I want it to collapse and return that space to the chat."
    )
    bambu = evaluate(bambu_prompt)
    run_log = evaluate(run_log_prompt)
    selected = select_intent_frame(
        bambu["messages"],
        {
            "domain": "local_app_product_bug",
            "actionType": "modify_app_status_surface",
            "routeCandidates": ["codex-cli-ui-local-agent"],
            "confidence": 0.96,
        },
        bambu["frame"],
    )
    graphite = evaluate("Would a graphite panel perform well at 150 C?")
    printer_mutation = evaluate("Change the Bambu printer chamber temperature to 150 C.")
    design_question = evaluate(
        "Do you think the Model Health panel should display percent complete and time remaining?"
    )
    held_mutation = evaluate(
        "I want Model Health to display percent complete, but do not edit or fix it until I approve."
    )

    checks = [
        {
            "id": "bambu-model-health-canonical-local-action",
            "ok": canonical_local_action(bambu),
            "actual": {
                "domain": bambu["frame"].get("domain"),
                "action": bambu["frame"].get("actionType"),
                "capability": bambu["decision"].get("selectedCapability"),
                "plan": bambu["plan"].get("id"),
            },
        },
        {
            "id": "run-log-canonical-local-action",
            "ok": canonical_local_action(run_log),
            "actual": {
                "domain": run_log["frame"].get("domain"),
                "action": run_log["frame"].get("actionType"),
                "capability": run_log["decision"].get("selectedCapability"),
                "plan": run_log["plan"].get("id"),
            },
        },
        {
            "id": "legacy-local-app-conflict-selects-canonical",
            "ok": selected.get("domain") == "local_product_action"
            and (
                selected.get("actionType") == "inspect_plan_execute_verify"
                or selected.get("executionActionType") == "inspect_plan_execute_verify"
            )
            and (
                selected.get("rejectedLegacyDomain") == "local_app_product_bug"
                or selected.get("refinedLegacyDomain") == "local_app_product_bug"
            )
            and bool(
                selected.get("rejectedLegacyReason")
                or selected.get("refinedLegacyReason")
            ),
        },
        {
            "id": "graphite-panel-is-not-local-product",
            "ok": graphite["frame"].get("domain") != "local_product_action"
            and not has_local_ui_workflow(graphite),
            "actual": graphite["frame"].get("domain"),
        },
        {
            "id": "live-printer-mutation-is-not-local-product",
            "ok": printer_mutation["frame"].get("domain") != "local_product_action"
            and not has_local_ui_workflow(printer_mutation),
            "actual": printer_mutation["frame"].get("domain"),
        },
        {
            "id": "ui-design-question-is-not-execution",
            "ok": design_question["frame"].get("domain") != "local_product_action"
            and not has_local_ui_workflow(design_question),
            "actual": {
                "domain": design_question["frame"].get("domain"),
                "action": design_question["frame"].get("actionType"),
            },
        },
        {
            "id": "desired-ui-mutation-hold-is-preserved",
            "ok": held_mutation["frame"].get("domain") == "local_product_action"
            and "inspect" in (held_mutation["frame"].get("operationPlan", {}).get("allowedNow") or [])
            and "test" in (held_mutation["frame"].get("operationPlan", {}).get("allowedNow") or [])
            and not set(held_mutation["frame"].get("operationPlan", {}).get("allowedNow") or [])
            & {"create", "draft", "fix", "edit", "change", "upload", "install", "restart", "delete", "buy", "contact", "record"}
            and bool(
                set(held_mutation["frame"].get("operationPlan", {}).get("prohibited") or [])
                & {"edit", "fix"}
            ),
            "actual": held_mutation["frame"].get("operationPlan"),
        },
    ]
    failed = [item for item in checks if not item["ok"]]
    report = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
