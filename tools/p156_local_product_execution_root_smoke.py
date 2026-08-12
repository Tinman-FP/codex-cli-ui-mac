#!/usr/bin/env python3
"""Offline regression for local-product execution roots and recovery isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def main() -> int:
    caller_cwd = str(Path.home() / "Documents" / "Codex")
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
        cwd=caller_cwd,
        requested_profile="manager",
        web_search="disabled",
    )
    primary_context = server.local_action_worker_invocation_context(
        bambu_route,
        caller_cwd,
    )
    retry_context = server.local_action_worker_invocation_context(
        bambu_route,
        caller_cwd,
    )
    bambu_prompt = server.build_local_action_execution_worker_prompt(
        bambu_messages,
        bambu_route,
        caller_cwd,
    )
    root_receipt = bambu_route.get("_localActionExecutionRoot") or {}

    unrelated_route = {
        "intentFrame": {"domain": "knowledge_question", "operationPlan": {}},
        "capabilityPlan": {"registered": False, "id": "unregistered"},
    }
    unrelated_context = server.local_action_worker_invocation_context(
        unrelated_route,
        caller_cwd,
    )
    worker_args = server.local_action_codex_global_args(bambu_route)
    expected_path_override = (
        "shell_environment_policy.set={PATH="
        + json.dumps(server.PATH_FOR_CODEX)
        + "}"
    )
    patch_compatibility = bambu_route.get("_localActionApplyPatchCompatibility") or {}

    stale_route = {
        **json.loads(json.dumps(bambu_route)),
        "project": "Printer Klipper config repair",
        "projectId": "printer-klipper-ops",
        "staleMetadata": {"path": "printer.cfg", "macro": "Klipper config"},
    }
    stale_issue = server.detect_tool_recovery_issue(
        bambu_messages,
        error_text="Load failed: local Codex returned no final response",
        cwd=caller_cwd,
        route=stale_route,
    )
    real_klipper_issue = server.detect_tool_recovery_issue(
        [{"role": "user", "text": "Find my Klipper printer.cfg path."}],
        error_text="No final response",
        cwd=caller_cwd,
        route={},
    )
    failure_route = json.loads(json.dumps(bambu_route))
    failure_route["_localCommandReceipts"] = [
        {
            "command": "python3 -m py_compile app.js",
            "status": "completed",
            "exitCode": 1,
            "outputExcerpt": "not a Python file",
            "mutationMarkers": [],
        }
    ]
    failure_answer = server.build_failure_recovery_answer(
        bambu_messages,
        route=failure_route,
        error_text="local Codex returned no valid controller edit proposal",
        cwd=caller_cwd,
        runtime_notes=["stale Klipper config metadata"],
        tool_recovery={"issue": {"kind": "klipper-config-discovery"}},
    )
    forbidden_scaffolding = (
        "Klipper config path",
        "Repair path:",
        "Routed project:",
        "Last runtime notes:",
        "Tool recovery:",
    )

    checks = [
        {
            "id": "registered-local-product-normalizes-caller-cwd",
            "ok": primary_context.get("requestedCwd") == str(Path(caller_cwd).resolve())
            and primary_context.get("effectiveCwd") == str(ROOT)
            and root_receipt.get("requestedCwd") == str(Path(caller_cwd).resolve())
            and root_receipt.get("effectiveCwd") == str(ROOT),
            "actual": root_receipt,
        },
        {
            "id": "prompt-primary-retry-share-effective-root",
            "ok": retry_context.get("effectiveCwd") == primary_context.get("effectiveCwd")
            and f"Working directory: {ROOT}" in bambu_prompt,
        },
        {
            "id": "unrelated-route-preserves-caller-cwd",
            "ok": unrelated_context.get("requestedCwd") == str(Path(caller_cwd).resolve())
            and unrelated_context.get("effectiveCwd") == str(Path(caller_cwd).resolve()),
        },
        {
            "id": "worker-shell-args-set-explicit-path",
            "ok": "shell_environment_policy.inherit=all" in worker_args
            and expected_path_override in worker_args
            and not any("model_catalog_json=" in str(item) for item in worker_args)
            and server.local_action_codex_exec_args(bambu_route) == ["--ephemeral"],
            "actual": [item for item in worker_args if "shell_environment_policy" in item],
        },
        {
            "id": "resolved-command-and-controller-proposal-guidance-is-valid",
            "ok": (
                (
                    "PRELOADED_SOURCE_EVIDENCE_BEGIN" in bambu_prompt
                    and "Source discovery with ripgrep, grep, find, or ls is prohibited" in bambu_prompt
                )
                or (
                    f"Resolved ripgrep executable: `{server.local_action_rg_executable()}`." in bambu_prompt
                    and "quote the complete path as one shell token" in bambu_prompt
                )
            )
            and "this worker is a read-only planner" in bambu_prompt
            and "Do not call `apply_patch`" in bambu_prompt
            and '"kind":"local-product-edit-proposal"' in bambu_prompt
            and '"test_command"' in bambu_prompt
            and patch_compatibility.get("status") == "controller-owned-edit-proposal"
            and patch_compatibility.get("functionProtocol") == "unsupported-by-installed-parser"
            and patch_compatibility.get("gptOssFreeform") == "broken-in-production"
            and patch_compatibility.get("qwenFreeform") == "unverified-not-promoted"
            and patch_compatibility.get("workerMutationAllowed") is False
            and patch_compatibility.get("proposalContentsRecorded") is False
            and server.operation_execution_access_level(bambu_route, "workspace-write") == "read-only",
        },
        {
            "id": "stale-route-metadata-cannot-select-klipper-recovery",
            "ok": stale_issue.get("kind") == "local-runtime-load",
            "actual": stale_issue.get("kind"),
        },
        {
            "id": "real-klipper-path-query-retains-specialized-recovery",
            "ok": real_klipper_issue.get("kind") == "klipper-config-discovery",
            "actual": real_klipper_issue.get("kind"),
        },
        {
            "id": "local-product-failure-is-concise-and-domain-safe",
            "ok": "local Codex returned no valid controller edit proposal" in failure_answer
            and "Edit receipt: not recorded. Test receipt: not recorded." in failure_answer
            and all(phrase not in failure_answer for phrase in forbidden_scaffolding),
            "actual": failure_answer,
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
