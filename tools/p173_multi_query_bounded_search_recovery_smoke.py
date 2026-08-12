#!/usr/bin/env python3
"""Offline regression for finite multi-query bounded search recovery."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def run_json_tool(name: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / name)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {}
    return {
        "returnCode": result.returncode,
        "status": report.get("status"),
        "passed": report.get("passed"),
        "failed": report.get("failed"),
        "total": report.get("total"),
        "stderr": result.stderr[-500:],
    }


def main() -> int:
    messages = [
        {
            "role": "user",
            "text": (
                "in the model health for the bambu h2d it is now showing printing, which is good, "
                "but i als want it to display percent complete and time remaining on the print."
            ),
        }
    ]
    route = server.route_manager(
        messages,
        cwd=str(Path.home() / "Documents" / "Codex"),
        requested_profile="manager",
        web_search="disabled",
    )
    prompt = server.build_local_action_execution_worker_prompt(
        messages,
        route,
        str(Path.home() / "Documents" / "Codex"),
    )
    commands = (
        "/bin/bash -lc 'grep -n \"function formatPrinterRemaining\" -R . | head'",
        "/bin/bash -lc 'grep -n \"printerDetail\" -R .'",
        "/bin/bash -lc 'grep -n \"timeRemainingSeconds\" -R . | head'",
    )
    recoveries = []
    results = []
    active_prompt = prompt
    budget_used = 0
    prompt_after_two = ""
    for index, command in enumerate(commands, start=1):
        result = server.local_product_bounded_search_recovery_attempt(
            command,
            route,
            recoveries,
            8,
            budget_used,
        )
        results.append(result)
        if result.get("allowed"):
            recoveries = result.get("recoveries") or []
            budget_used = int(result.get("commandBudgetUsed") or budget_used)
            active_prompt = server.local_product_bounded_search_continuation_prompt(
                active_prompt,
                command,
                result,
            )
        if index == 2:
            prompt_after_two = active_prompt

    duplicate = server.local_product_bounded_search_recovery_attempt(
        commands[1],
        route,
        recoveries,
        8,
        budget_used,
    )
    fourth = server.local_product_bounded_search_recovery_attempt(
        "/bin/bash -lc 'grep -n generic_printer_health -R . | head'",
        route,
        recoveries,
        8,
        budget_used,
    )
    punctuation = server.local_product_bounded_search_recovery_attempt(
        "/bin/bash -lc 'grep -n \"printerDetail(\" -R . | head'",
        json.loads(json.dumps(route)),
        [],
        8,
        0,
    )
    series = route.get("_localProductBoundedSearchRecoverySeries") or {}
    compatibility = route.get("_localActionApplyPatchCompatibility") or {}
    handler_source = Path(server.__file__).read_text(encoding="utf-8")
    p172 = run_json_tool("p172_apply_patch_payload_compatibility_smoke.py")
    p156 = run_json_tool("p156_local_product_execution_root_smoke.py")

    digests = [item.get("receipt", {}).get("queryDigest", "") for item in results]
    checks = [
        {
            "id": "two-distinct-recoveries-chain-with-prior-evidence-once",
            "ok": all(item.get("allowed") is True for item in results[:2])
            and prompt_after_two.count("CONTROLLER_BOUNDED_SEARCH_RECOVERY_BEGIN") == 2
            and all(prompt_after_two.count(digest) == 1 for digest in digests[:2]),
        },
        {
            "id": "three-distinct-recoveries-fit-controller-limit",
            "ok": all(item.get("allowed") is True for item in results)
            and len(recoveries) == 3
            and active_prompt.count("CONTROLLER_BOUNDED_SEARCH_RECOVERY_BEGIN") == 3
            and active_prompt.count("PRELOADED_SOURCE_EVIDENCE_BEGIN") == 1
            and all(active_prompt.count(digest) == 1 for digest in digests),
        },
        {
            "id": "every-recovery-is-controller-only-and-never-recursive-execution",
            "ok": all(
                item.get("receipt", {}).get("recursiveWalk") is False
                and item.get("commandReceipt", {}).get("recursiveExecuted") is False
                and item.get("commandReceipt", {}).get("controllerRecovered") is True
                for item in results
            ),
        },
        {
            "id": "duplicate-query-digest-fails-closed",
            "ok": duplicate.get("allowed") is False
            and "repeated query digest" in duplicate.get("reason", "")
            and duplicate.get("seriesReceipt", {}).get("reasonCode") == "duplicate-query-digest",
            "actual": duplicate.get("reason"),
        },
        {
            "id": "fourth-distinct-query-fails-with-exact-recovery-budget",
            "ok": fourth.get("allowed") is False
            and "recovery budget exhausted: 3/3" in fourth.get("reason", "")
            and fourth.get("seriesReceipt", {}).get("reasonCode") == "recovery-budget-exhausted",
            "actual": fourth.get("reason"),
        },
        {
            "id": "recoveries-consume-existing-command-budget-slots",
            "ok": budget_used == 3
            and [item.get("receipt", {}).get("commandBudgetSlot") for item in results] == [1, 2, 3]
            and series.get("commandBudgetAllowed") == 8
            and series.get("commandBudgetUsed") == 3,
            "actual": {"used": budget_used, "series": series},
        },
        {
            "id": "series-receipt-is-digest-count-and-bound-only",
            "ok": series.get("count") == 3
            and series.get("limit") == 3
            and len(series.get("queryDigests") or []) == 3
            and all(len(item) == 64 for item in series.get("queryDigests") or [])
            and all(fragment not in json.dumps(series) for fragment in (
                "formatPrinterRemaining",
                "printerDetail",
                "timeRemainingSeconds",
                "*** Begin Patch",
                str(ROOT),
            )),
            "actual": series,
        },
        {
            "id": "p171-quoted-punctuation-recovery-remains-supported",
            "ok": punctuation.get("allowed") is True
            and punctuation.get("receipt", {}).get("fixedString") is True
            and punctuation.get("commandReceipt", {}).get("recursiveExecuted") is False,
        },
        {
            "id": "controller-owned-proposal-boundary-remains-reachable",
            "ok": compatibility.get("status") == "controller-owned-edit-proposal"
            and compatibility.get("installedApplyPatchToolType") == "freeform"
            and compatibility.get("functionProtocol") == "unsupported-by-installed-parser"
            and compatibility.get("gptOssFreeform") == "broken-in-production"
            and compatibility.get("qwenFreeform") == "unverified-not-promoted"
            and compatibility.get("workerMutationAllowed") is False
            and compatibility.get("proposalContentsRecorded") is False,
            "actual": compatibility,
        },
        {
            "id": "primary-handler-uses-finite-ledger-and-cumulative-active-prompt",
            "ok": "bounded_search_recoveries = []" in handler_source
            and "local_product_bounded_search_recovery_attempt(" in handler_source
            and "active_worker_prompt = continuation_prompt" in handler_source
            and "bounded_search_recovery_used" not in handler_source
            and handler_source.index("local_product_bounded_search_recovery_attempt(")
            < handler_source.rindex("local_action_forbidden_discovery_reason(command, route=route)"),
        },
        {
            "id": "p172-focused-contract-remains-green-12-of-12",
            "ok": p172 == {
                "returnCode": 0,
                "status": "pass",
                "passed": 12,
                "failed": 0,
                "total": 12,
                "stderr": "",
            },
            "actual": p172,
        },
        {
            "id": "p156-focused-contract-remains-green-9-of-9",
            "ok": p156 == {
                "returnCode": 0,
                "status": "pass",
                "passed": 9,
                "failed": 0,
                "total": 9,
                "stderr": "",
            },
            "actual": p156,
        },
        {
            "id": "package-owned-p126-synthetic-remains-green",
            "ok": server.local_action_first_pass_execution_p126_synthetic_check() is True,
        },
    ]
    failed = [item for item in checks if not item.get("ok")]
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
