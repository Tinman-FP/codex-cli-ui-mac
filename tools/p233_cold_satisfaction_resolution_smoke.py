#!/usr/bin/env python3
"""P233 adversaries for cold source satisfaction, planner gating, and latency."""

from __future__ import annotations

import json
import copy
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from p177_generic_satisfaction_verifier_smoke import REQUEST, prepare, verdict  # noqa: E402


IMPLEMENTED = (
    "function renderDeviceRow(device, detail) {\n"
    "  const values = [];\n"
    "  values.push(device.connectionQuality);\n"
    "  values.push(device.lastSyncTime);\n"
    "  detail.textContent = values.join(' | ');\n"
    "}\n"
)
NOT_IMPLEMENTED = (
    "const connectionQuality = null;\n"
    "const lastSyncTime = null;\n"
    "function renderDeviceRow() { return 'idle'; }\n"
)


def scripted_runner(outcomes, calls):
    queue = list(outcomes)

    def run(prompt, schema, timeout):
        calls.append(
            {
                "timeout": float(timeout),
                "promptBound": "DECISION_INPUT=" in prompt,
                "schemaBound": schema.get("additionalProperties") is False,
            }
        )
        if not queue:
            raise AssertionError("unexpected extra satisfaction attempt")
        outcome = queue.pop(0)
        if callable(outcome):
            return outcome(prompt, schema, timeout)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, dict):
            return outcome
        return {"answer": str(outcome), "returnCode": 0, "toolEventCount": 0}

    return run


def model_result(raw, *, return_code=0, tool_events=0):
    return {
        "answer": raw,
        "returnCode": return_code,
        "toolEventCount": tool_events,
    }


def tamper(raw, path, value):
    payload = json.loads(raw)
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def finalize_and_admit(messages, route, snapshot, root, result):
    receipts = list(result.get("receipts") or [])
    reconciliation = server.reconcile_local_action_candidate_sources(
        snapshot,
        receipts,
        root,
    )
    receipts.append(reconciliation)
    route["_localCommandReceipts"] = receipts
    route["_localActionFileReconciliation"] = reconciliation
    route["_localActionControllerProposalHandled"] = True
    terminal = server.finalize_local_action_controller_answer(
        messages,
        route,
        result.get("answer") or "",
        completed=bool(result.get("completed")),
    )
    admitted = server.admit_local_action_satisfaction_cache(
        route,
        root,
        result,
        terminal,
    )
    return terminal, admitted


def main():
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    server.clear_local_action_satisfaction_cache()

    with tempfile.TemporaryDirectory(prefix="p233-cold-satisfied-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, IMPLEMENTED)
        before = source.read_bytes()
        satisfied_raw = verdict(
            route,
            snippet,
            snapshot,
            "satisfied",
            "implemented-behavior",
        )
        calls = []
        cold_started = time.perf_counter()
        cold = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner([model_result(satisfied_raw)], calls),
        )
        cold_ms = round((time.perf_counter() - cold_started) * 1000, 3)
        add(
            "cold-source-satisfied-produces-fresh-bound-verified-noop",
            cold.get("completed") is True
            and cold.get("resolutionDecision") == "verified-noop"
            and cold.get("attemptCount") == 1
            and cold.get("plannerAllowed") is False
            and len(calls) == 1
            and source.read_bytes() == before
            and any(
                item.get("kind") == "local-action-verified-noop"
                and item.get("verified") is True
                for item in cold.get("receipts") or []
            ),
            {
                "durationMs": cold_ms,
                "attempts": cold.get("attemptCount"),
                "resolution": cold.get("resolutionDecision"),
            },
        )

        terminal, admitted = finalize_and_admit(
            messages,
            route,
            snapshot,
            root,
            cold,
        )
        warm_messages, warm_route, _source, _snippet, warm_snapshot = prepare(
            root,
            IMPLEMENTED,
        )
        warm_calls = []
        warm_started = time.perf_counter()
        warm = server.run_local_action_satisfaction_resolution(
            warm_messages,
            warm_route,
            root,
            runner=scripted_runner([], warm_calls),
        )
        warm_ms = round((time.perf_counter() - warm_started) * 1000, 3)
        add(
            "positive-only-cache-revalidates-identical-warm-binding",
            terminal.get("completed") is True
            and admitted is True
            and warm.get("completed") is True
            and warm.get("cacheStatus") == "hit"
            and warm.get("attemptCount") == 1
            and warm.get("resolutionReceipt", {}).get("workerInvocationCount") == 0
            and warm_calls == []
            and warm_snapshot.get("status") == "captured",
            {
                "coldMs": cold_ms,
                "warmMs": warm_ms,
                "cacheStatus": warm.get("cacheStatus"),
            },
        )

        route["_liveRunId"] = "p233-sidecar"
        sidecar = server.local_action_receipt_sidecar(route)
        serialized_sidecar = json.dumps(sidecar, sort_keys=True)
        add(
            "resolution-sidecar-is-bounded-metadata-only",
            sidecar.get("satisfactionResolution", {}).get("decision")
            == "verified-noop"
            and sidecar.get("satisfactionResolution", {}).get("attemptCount") == 1
            and "attempts" not in sidecar.get("satisfactionResolution", {})
            and IMPLEMENTED not in serialized_sidecar
            and REQUEST not in serialized_sidecar,
            sidecar.get("satisfactionResolution"),
        )
        valid_resolution_contract = server.command_completion_contract(
            command_receipts=[copy.deepcopy(cold.get("resolutionReceipt") or {})],
            semantic_receipt={},
            latest_user_intent=REQUEST,
            access_level="workspace-write",
            operation_plan={},
            completed=False,
        )
        forged_resolution = copy.deepcopy(cold.get("resolutionReceipt") or {})
        forged_resolution["plannerAllowed"] = True
        forged_resolution_contract = server.command_completion_contract(
            command_receipts=[forged_resolution],
            semantic_receipt={},
            latest_user_intent=REQUEST,
            access_level="workspace-write",
            operation_plan={},
            completed=False,
        )
        add(
            "resolution-receipt-schema-rejects-inconsistent-controller-claims",
            valid_resolution_contract.get("status") == "pass"
            and forged_resolution_contract.get("status") == "fail"
            and "satisfaction-resolution-receipt-invalid"
            in forged_resolution_contract.get("issues", []),
            forged_resolution_contract.get("issues"),
        )

    with tempfile.TemporaryDirectory(prefix="p233-false-negative-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, IMPLEMENTED)
        before = source.read_bytes()
        negative_raw = verdict(route, snippet, snapshot, "not-satisfied", "not-implemented")
        satisfied_raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
        calls = []
        resolved = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner(
                [model_result(negative_raw), model_result(satisfied_raw)],
                calls,
            ),
        )
        add(
            "one-cold-false-negative-cannot-launch-planner-before-bound-recheck",
            resolved.get("completed") is True
            and resolved.get("resolutionDecision") == "verified-noop"
            and resolved.get("attemptCount") == 2
            and resolved.get("plannerAllowed") is False
            and len(calls) == 2
            and source.read_bytes() == before,
            resolved.get("resolutionReceipt"),
        )

    with tempfile.TemporaryDirectory(prefix="p233-edit-required-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, NOT_IMPLEMENTED)
        before = source.read_bytes()
        negative_raw = verdict(route, snippet, snapshot, "not-satisfied", "not-implemented")
        calls = []
        required = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner(
                [model_result(negative_raw), model_result(negative_raw)],
                calls,
            ),
        )
        add(
            "actual-edit-requires-two-identically-bound-negative-verdicts",
            required.get("completed") is False
            and required.get("plannerAllowed") is True
            and required.get("resolutionDecision") == "consistent-not-satisfied"
            and required.get("resolutionReceipt", {}).get("consistentNegativeBinding")
            is True
            and len(calls) == 2
            and not any(
                item.get("kind") == "local-action-verified-noop"
                for item in required.get("receipts") or []
            )
            and source.read_bytes() == before,
            required.get("resolutionReceipt"),
        )

    invalid_cases = []
    for label, path, replacement, expected_reason in (
        (
            "wrong-source-hash",
            ("evidence", "expected_source_sha256"),
            "0" * 64,
            "satisfaction-evidence-unbound",
        ),
        (
            "wrong-request-hash",
            ("request_sha256",),
            "1" * 64,
            "satisfaction-request-unbound",
        ),
        (
            "wrong-context-hash",
            ("evidence", "context_sha256"),
            "2" * 64,
            "satisfaction-evidence-unbound",
        ),
    ):
        with tempfile.TemporaryDirectory(prefix=f"p233-{label}-") as temp_dir:
            root = Path(temp_dir)
            messages, route, _source, snippet, snapshot = prepare(root, IMPLEMENTED)
            raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
            calls = []
            result = server.run_local_action_satisfaction_resolution(
                messages,
                route,
                root,
                runner=scripted_runner([model_result(tamper(raw, path, replacement))], calls),
            )
            invalid_cases.append(
                {
                    "label": label,
                    "ok": result.get("completed") is False
                    and result.get("plannerAllowed") is False
                    and result.get("attemptCount") == 1
                    and result.get("reasonCode") == expected_reason
                    and not any(
                        item.get("kind") == "local-action-verified-noop"
                        for item in result.get("receipts") or []
                    ),
                    "reason": result.get("reasonCode"),
                }
            )
    with tempfile.TemporaryDirectory(prefix="p233-wrong-surface-") as temp_dir:
        root = Path(temp_dir)
        messages, route, _source, snippet, snapshot = prepare(root, IMPLEMENTED)
        raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
        route["intentFrame"]["targetSurface"] = "device_panel.summary"
        calls = []
        result = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner([model_result(raw)], calls),
        )
        invalid_cases.append(
            {
                "label": "wrong-surface-binding",
                "ok": result.get("completed") is False
                and result.get("plannerAllowed") is False
                and result.get("attemptCount") == 1
                and result.get("reasonCode") == "satisfaction-request-unbound"
                and not any(
                    item.get("kind") == "local-action-verified-noop"
                    for item in result.get("receipts") or []
                ),
                "reason": result.get("reasonCode"),
            }
        )
    add(
        "wrong-source-request-surface-or-context-binding-never-becomes-noop-or-planner-proof",
        len(invalid_cases) == 4 and all(item.get("ok") for item in invalid_cases),
        invalid_cases,
    )

    with tempfile.TemporaryDirectory(prefix="p233-prose-") as temp_dir:
        root = Path(temp_dir)
        messages, route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        calls = []
        prose = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner(["already implemented", "still already implemented"], calls),
        )
        add(
            "prose-only-responses-never-prove-noop-or-planner-transition",
            prose.get("completed") is False
            and prose.get("plannerAllowed") is False
            and prose.get("attemptCount") == 2
            and prose.get("resolutionDecision") == "satisfaction-resolution-unproven"
            and len(calls) == 2,
            prose.get("resolutionReceipt"),
        )

    with tempfile.TemporaryDirectory(prefix="p233-worker-failure-") as temp_dir:
        root = Path(temp_dir)
        messages, route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        calls = []
        failures = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner(
                [
                    subprocess.TimeoutExpired("satisfaction-verifier", 25),
                    model_result("{}", return_code=2),
                ],
                calls,
            ),
        )
        add(
            "timeout-and-model-failure-stop-before-long-planner",
            failures.get("completed") is False
            and failures.get("plannerAllowed") is False
            and failures.get("attemptCount") == 2
            and failures.get("resolutionDurationMs")
            <= server.LOCAL_ACTION_SATISFACTION_RESOLUTION_BUDGET_SECONDS * 1000
            and [round(item.get("timeout")) for item in calls] == [25, 20],
            failures.get("resolutionReceipt"),
        )

    with tempfile.TemporaryDirectory(prefix="p233-concurrent-source-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, NOT_IMPLEMENTED)
        negative_raw = verdict(route, snippet, snapshot, "not-satisfied", "not-implemented")
        calls = []

        def change_before_second(_prompt, _schema, _timeout):
            source.write_text(NOT_IMPLEMENTED + "// concurrent revision\n", encoding="utf-8")
            return model_result(negative_raw)

        concurrent = server.run_local_action_satisfaction_resolution(
            messages,
            route,
            root,
            runner=scripted_runner(
                [model_result(negative_raw), change_before_second],
                calls,
            ),
        )
        add(
            "concurrent-source-change-invalidates-negative-consensus",
            concurrent.get("completed") is False
            and concurrent.get("plannerAllowed") is False
            and concurrent.get("attemptCount") == 2
            and concurrent.get("reasonCode") == "satisfaction-evidence-stale"
            and concurrent.get("resolutionReceipt", {}).get("consistentNegativeBinding")
            is False,
            concurrent.get("resolutionReceipt"),
        )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(encoding="utf-8")
    add(
        "production-path-uses-resolution-before-planner",
        "satisfaction_result = run_local_action_satisfaction_resolution(" in source_text
        and 'satisfaction_result.get("plannerAllowed") is False' in source_text
        and "Stopped before the mutation planner" in source_text
        and "run_local_action_satisfaction_verifier(" in source_text,
    )
    add(
        "p233-package-and-export-registration",
        "server:cold-satisfaction-resolution-p233" in source_text
        and "p233_cold_satisfaction_resolution_smoke.py" in source_text
        and "tools/p233_cold_satisfaction_resolution_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p233-cold-satisfaction-resolution",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
