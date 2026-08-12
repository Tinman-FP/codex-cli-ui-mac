#!/usr/bin/env python3
"""Offline regression for lean local-action workers and bounded discovery."""

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
                        "condition": "synthetic bounded-discovery contract",
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


def lean_args_are_complete(args):
    return bool(
        args
        and all(
            feature in args
            for feature in server.LEAN_READ_ONLY_LOCAL_WORKER_FEATURES
        )
        and "exec_command" not in args
        and "apply_patch" not in args
    )


def bounded_prompt(prompt):
    return bool(
        "use `rg -n` for targeted source searches" in prompt
        and "`rg --files` for a bounded file inventory" in prompt
        and "Inspect likely top-level source files in the working directory first." in prompt
        and "Never use parent paths (`..`), `grep -R`, `ls -R`, or recursive `find`." in prompt
        and "hard budget of at most 4 tool calls total" in prompt
        and "stop and report the exact blocker" in prompt
    )


def main() -> int:
    read_only_route = route_with_operations(["inspect", "test"], read_only=True)
    writable_route = route_with_operations(["inspect", "edit", "test"], read_only=False)
    no_op_route = route_with_operations([], read_only=False)
    read_only_prompt = server.build_local_action_execution_worker_prompt(
        [{"role": "user", "text": "Inspect and test this local UI read-only."}],
        read_only_route,
        str(ROOT),
    )
    writable_prompt = server.build_local_action_execution_worker_prompt(
        [{"role": "user", "text": "Inspect, edit, and test this local UI."}],
        writable_route,
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

    read_only_args = server.local_action_codex_global_args(read_only_route)
    writable_args = server.local_action_codex_global_args(writable_route)
    bambu_args = server.local_action_codex_global_args(bambu_route)
    checks = [
        {
            "id": "read-only-local-action-is-lean-and-bounded",
            "ok": lean_args_are_complete(read_only_args)
            and bounded_prompt(read_only_prompt)
            and "use the actual `apply_patch` tool" not in read_only_prompt,
        },
        {
            "id": "writable-local-action-is-lean-and-bounded",
            "ok": lean_args_are_complete(writable_args)
            and bounded_prompt(writable_prompt)
            and "use the actual `apply_patch` tool" in writable_prompt,
        },
        {
            "id": "no-tool-operations-receive-no-global-args",
            "ok": server.local_action_codex_global_args(no_op_route) == [],
        },
        {
            "id": "exact-bambu-route-is-lean-and-bounded",
            "ok": bambu_frame.get("domain") == "local_product_action"
            and bambu_frame.get("actionType") == "inspect_plan_execute_verify"
            and {"inspect", "edit", "test"}.issubset(
                set((bambu_frame.get("operationPlan") or {}).get("allowedNow") or [])
            )
            and bambu_plan.get("registered") is True
            and bambu_plan.get("id") == "local-product-action"
            and lean_args_are_complete(bambu_args)
            and bounded_prompt(bambu_prompt),
            "actual": {
                "domain": bambu_frame.get("domain"),
                "action": bambu_frame.get("actionType"),
                "allowedNow": (bambu_frame.get("operationPlan") or {}).get("allowedNow"),
                "capability": bambu_plan.get("id"),
                "disabledFeatureCount": len(server.LEAN_READ_ONLY_LOCAL_WORKER_FEATURES),
            },
        },
        {
            "id": "existing-package-p126-synthetic-is-green",
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
