#!/usr/bin/env python3
"""Offline regression for local-worker shell inheritance and ephemeral execs."""

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
                        "condition": "synthetic environment contract",
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


def lean_environment_contract(route):
    args = server.local_action_codex_global_args(route)
    return bool(
        args
        and "shell_environment_policy.inherit=all" in args
        and all(
            feature in args
            for feature in server.LEAN_READ_ONLY_LOCAL_WORKER_FEATURES
        )
        and "exec_command" not in args
        and "apply_patch" not in args
        and server.local_action_codex_exec_args(route) == ["--ephemeral"]
    )


def resolved_rg_prompt_contract(prompt, rg_path):
    return bool(
        rg_path
        and f"Resolved ripgrep executable: `{rg_path}`." in prompt
        and f"`{rg_path} -n`" in prompt
        and f"`{rg_path} --files`" in prompt
        and "never use parent paths" in prompt.lower()
        and "hard budget of at most 4 tool calls total" in prompt
    )


def main() -> int:
    rg_path = server.local_action_rg_executable()
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

    checks = [
        {
            "id": "rg-resolves-from-path-for-codex",
            "ok": bool(rg_path)
            and Path(rg_path).name == "rg"
            and str(Path(rg_path).parent) in server.PATH_FOR_CODEX.split(":"),
            "actual": rg_path,
        },
        {
            "id": "read-only-worker-inherits-shell-and-is-ephemeral",
            "ok": lean_environment_contract(read_only_route)
            and resolved_rg_prompt_contract(read_only_prompt, rg_path)
            and "use the actual `apply_patch` tool" not in read_only_prompt,
        },
        {
            "id": "writable-worker-inherits-shell-and-is-ephemeral",
            "ok": lean_environment_contract(writable_route)
            and resolved_rg_prompt_contract(writable_prompt, rg_path)
            and "use the actual `apply_patch` tool" in writable_prompt,
        },
        {
            "id": "no-operation-route-has-no-worker-overrides",
            "ok": server.local_action_codex_global_args(no_op_route) == []
            and server.local_action_codex_exec_args(no_op_route) == [],
        },
        {
            "id": "exact-bambu-route-uses-same-worker-contract",
            "ok": bambu_frame.get("domain") == "local_product_action"
            and bambu_frame.get("actionType") == "inspect_plan_execute_verify"
            and {"inspect", "edit", "test"}.issubset(
                set((bambu_frame.get("operationPlan") or {}).get("allowedNow") or [])
            )
            and bambu_plan.get("registered") is True
            and bambu_plan.get("id") == "local-product-action"
            and lean_environment_contract(bambu_route)
            and resolved_rg_prompt_contract(bambu_prompt, rg_path),
            "actual": {
                "domain": bambu_frame.get("domain"),
                "action": bambu_frame.get("actionType"),
                "allowedNow": (bambu_frame.get("operationPlan") or {}).get("allowedNow"),
                "capability": bambu_plan.get("id"),
                "rg": rg_path,
                "execArgs": server.local_action_codex_exec_args(bambu_route),
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
