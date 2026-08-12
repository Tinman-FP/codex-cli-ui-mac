#!/usr/bin/env python3
"""Offline regression for semantic-operation to Codex-tool mapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def route_with_operations(allowed, *, read_only):
    return {
        "intentFrame": {
            "domain": "local_product_action",
            "operationPlan": {
                "operations": [
                    {
                        "operation": operation,
                        "state": "allowed-now",
                        "condition": "synthetic prompt contract",
                    }
                    for operation in allowed
                ],
                "allowedNow": list(allowed),
                "prohibited": [],
                "discussed": [],
                "deferred": [],
                "readOnly": read_only,
                "requiresConfirmation": False,
            },
        }
    }


def no_semantic_tool_call_instruction(prompt):
    lower = prompt.lower()
    return not any(
        phrase in lower
        for phrase in (
            "call the `inspect` tool",
            "call the `edit` tool",
            "call the `test` tool",
            "call the `run` tool",
            "call the `fix` tool",
        )
    )


def main() -> int:
    writable_messages = [
        {"role": "user", "text": "Inspect the local UI, make the requested change, and test it."}
    ]
    writable_route = route_with_operations(
        ["inspect", "edit", "test"],
        read_only=False,
    )
    writable_prompt = server.build_local_action_execution_worker_prompt(
        writable_messages,
        writable_route,
        str(ROOT),
    )

    read_only_messages = [
        {"role": "user", "text": "Inspect and test the local UI without changing it."}
    ]
    read_only_route = route_with_operations(
        ["inspect", "test"],
        read_only=True,
    )
    read_only_prompt = server.build_local_action_execution_worker_prompt(
        read_only_messages,
        read_only_route,
        str(ROOT),
    )

    bambu_messages = [
        {
            "role": "user",
            "text": (
                "in the model health for the bambu h2d it is now showing printing, which is good, "
                "but i als want it to display percent complete and time remaining on the print."
            ),
        }
    ]
    bambu_route = server.route_manager(
        bambu_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    bambu_prompt = server.build_local_action_execution_worker_prompt(
        bambu_messages,
        bambu_route,
        str(ROOT),
    )
    bambu_frame = bambu_route.get("intentFrame") or {}
    bambu_plan = bambu_route.get("capabilityPlan") or {}

    checks = [
        {
            "id": "writable-policy-labels-map-to-real-tools",
            "ok": "Semantic operation labels (authorization policy, not callable tool names): inspect, edit, test." in writable_prompt
            and "use the actual `exec_command` tool" in writable_prompt
            and "use the actual `apply_patch` tool" in writable_prompt
            and "The tools named `inspect`, `edit`, `test`, `run`, `fix`, `explain`, and `research` do not exist" in writable_prompt
            and no_semantic_tool_call_instruction(writable_prompt),
        },
        {
            "id": "read-only-route-does-not-authorize-mutation",
            "ok": "Semantic operation labels (authorization policy, not callable tool names): inspect, test." in read_only_prompt
            and "use the actual `exec_command` tool" in read_only_prompt
            and "Mutation is not authorized by this operation plan." in read_only_prompt
            and "use the actual `apply_patch` tool" not in read_only_prompt
            and '"readOnly": true' in read_only_prompt
            and no_semantic_tool_call_instruction(read_only_prompt),
        },
        {
            "id": "bambu-route-reaches-corrected-worker-prompt",
            "ok": bambu_frame.get("domain") == "local_product_action"
            and bambu_frame.get("actionType") == "inspect_plan_execute_verify"
            and {"inspect", "edit", "test"}.issubset(
                set((bambu_frame.get("operationPlan") or {}).get("allowedNow") or [])
            )
            and bambu_plan.get("registered") is True
            and bambu_plan.get("id") == "local-product-action"
            and bambu_plan.get("executor") == "local-agent"
            and "Semantic operation labels (authorization policy, not callable tool names): inspect, edit, test." in bambu_prompt
            and "use the actual `exec_command` tool" in bambu_prompt
            and "use the actual `apply_patch` tool" in bambu_prompt
            and no_semantic_tool_call_instruction(bambu_prompt),
            "actual": {
                "domain": bambu_frame.get("domain"),
                "action": bambu_frame.get("actionType"),
                "allowedNow": (bambu_frame.get("operationPlan") or {}).get("allowedNow"),
                "capability": bambu_plan.get("id"),
                "executor": bambu_plan.get("executor"),
            },
        },
        {
            "id": "existing-package-synthetic-covers-tool-mapping",
            "ok": server.local_action_first_pass_execution_p126_synthetic_check() is True,
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
