#!/usr/bin/env python3
"""Generic offline contract for the source-satisfaction verifier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


REQUEST = "Display connection quality and last sync time in the device row."


def prepare(root: Path, source_text: str, *, target_surface: str = "device_panel.row"):
    source = root / "ui.js"
    source.write_text(source_text, encoding="utf-8")
    route = {
        "intentFrame": {
            "domain": "local_product_action",
            "targetSurface": target_surface,
            "requestedChange": "Display connection quality and last sync time in the device row.",
            "actionType": "modify_app_status_surface",
            "operationPlan": {
                "allowedNow": ["inspect", "edit", "test"],
                "readOnly": False,
                "prohibited": [],
                "deferred": [],
            },
        },
        "capabilityPlan": {"registered": True, "id": "local-product-action"},
    }
    messages = [{"role": "user", "text": REQUEST}]
    server.bind_local_action_request_fingerprint(messages, route)
    line_count = len(source_text.splitlines())
    context_read = {"path": "ui.js", "start": 1, "end": line_count, "hitLine": min(4, line_count)}
    snippets = server.local_product_orientation_context_snippets(root, [context_read], max_snippets=1)
    snippet = snippets[0]
    context = {
        key: snippet[key]
        for key in (
            "path", "start", "end", "hitLine", "lineCount", "renderedCharCount",
            "renderedByteCount", "sha256", "preloaded",
        )
    }
    route["_localProductSourceOrientation"] = {
        "kind": "local-product-source-orientation",
        "status": "matched",
        "candidatePaths": ["ui.js"],
        "manifestPaths": [],
        "selectedHitScores": {"ui.js": [12, 10]},
        "contextReads": [{**context_read, "command": f"sed -n '1,{line_count}p' ui.js"}],
        "preloadedContexts": [context],
        "contextPreloaded": True,
        "readOnly": True,
    }
    snapshot = server.snapshot_local_action_candidate_sources(route, root)
    return messages, route, source, snippet, snapshot


def verdict(route, snippet, snapshot, value: str, basis: str) -> str:
    typed = server.local_action_typed_request_metadata(route)
    return json.dumps(
        {
            "kind": server.LOCAL_ACTION_SATISFACTION_VERDICT_KIND,
            "version": server.LOCAL_ACTION_EDIT_PROPOSAL_VERSION,
            "verdict": value,
            "basis": basis,
            "request_sha256": route["_localActionRequestFingerprint"]["sha256"],
            "typed_request_sha256": typed["sha256"],
            "evidence": {
                "path": "ui.js",
                "expected_source_sha256": snapshot["files"][0]["sha256"],
                "context_start": snippet["start"],
                "context_end": snippet["end"],
                "context_sha256": snippet["sha256"],
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def main() -> int:
    checks = []
    implemented = (
        "function renderDeviceRow(device, detail) {\n"
        "  const values = [];\n"
        "  values.push(device.connectionQuality);\n"
        "  values.push(device.lastSyncTime);\n"
        "  detail.textContent = values.join(' | ');\n"
        "}\n"
    )

    with tempfile.TemporaryDirectory(prefix="codex-p177-satisfied-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, implemented)
        before = source.read_bytes()
        raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
        prompt = server.build_local_action_satisfaction_prompt(
            messages,
            route,
            orientation_pack={"contextSnippets": [snippet]},
        )
        constrained_schema = server.local_action_satisfaction_output_schema(
            route,
            {"contextSnippets": [snippet]},
        )
        result = server.run_local_action_satisfaction_verifier(
            messages,
            route,
            root,
            runner=lambda _prompt, _schema, _timeout: {
                "answer": raw,
                "returnCode": 0,
                "toolEventCount": 0,
            },
        )
        receipts = list(result.get("receipts") or [])
        reconciliation = server.reconcile_local_action_candidate_sources(snapshot, receipts, root)
        receipts.append(reconciliation)
        route["_localCommandReceipts"] = receipts
        route["_localActionFileReconciliation"] = reconciliation
        terminal = server.finalize_local_action_controller_answer(
            messages,
            route,
            result.get("answer") or "",
            completed=bool(result.get("completed")),
        )
        checks.append({
            "id": "arbitrary-already-satisfied-ui-change-becomes-verified-noop",
            "ok": result.get("completed") is True
            and result.get("proposalKind") == server.LOCAL_ACTION_NOOP_PROPOSAL_KIND
            and any(
                item.get("kind") == "local-action-source-satisfaction"
                and item.get("verified") is True
                for item in result.get("receipts") or []
            )
            and any(
                item.get("kind") == "local-action-verified-noop"
                and item.get("verified") is True
                for item in result.get("receipts") or []
            )
            and source.read_bytes() == before
            and terminal.get("completed") is True
            and terminal.get("contract", {}).get("status") == "pass"
            and route.get("_supervisionStatus") == "pass"
            and "field name without actual read/use/render behavior is not implementation" in prompt
            and "different surface is not satisfaction" in prompt
            and "from the one supplied context only" in prompt
            and "Silently list each value that requestedChange explicitly asks to display" in prompt
            and "Different but equivalent identifier words are allowed" in prompt
            and '"controllerSurfaceBinding":"selected-for-typed-target-surface"' in prompt
            and "Surface selection is controller-owned" in prompt
            and "Do not second-guess that binding" in prompt
            and "do not require upstream acquisition, telemetry, persistence, integration" in prompt
            and "do not require a literal object/device name or a special-case branch" in prompt
            and "request to display connection strength and last update" in prompt
            and "connectionQuality" in prompt
            and '"composed-output"' in prompt
            and '"assigned-output"' in prompt
            and constrained_schema.get("additionalProperties") is False
            and "every value explicitly requested for display"
            in constrained_schema["properties"]["verdict"].get("description", "")
            and constrained_schema["properties"]["evidence"]["oneOf"][0]["properties"]["path"].get("const") == "ui.js"
            and constrained_schema["properties"]["evidence"]["oneOf"][0]["properties"]["context_sha256"].get("const") == snippet["sha256"],
            "actual": {"verdict": result.get("verdict"), "reason": result.get("reasonCode")},
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-term-only-") as temp_dir:
        root = Path(temp_dir)
        term_only = "const connectionQuality = null;\nconst lastSyncTime = null;\nfunction renderDeviceRow() { return 'idle'; }\n"
        messages, route, source, snippet, snapshot = prepare(root, term_only)
        before = source.read_bytes()
        result = server.controller_handle_local_action_satisfaction_verdict(
            verdict(route, snippet, snapshot, "not-satisfied", "term-only"),
            route,
            root=root,
        )
        checks.append({
            "id": "requested-terms-without-use-do-not-become-noop",
            "ok": result.get("completed") is False
            and result.get("verdict") == "not-satisfied"
            and not any(item.get("kind") == "local-action-verified-noop" for item in result.get("receipts") or [])
            and source.read_bytes() == before,
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-wrong-surface-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(
            root,
            implemented,
            target_surface="device_panel.summary",
        )
        result = server.controller_handle_local_action_satisfaction_verdict(
            verdict(route, snippet, snapshot, "not-satisfied", "different-surface"),
            route,
            root=root,
        )
        checks.append({
            "id": "behavior-on-a-different-surface-does-not-become-noop",
            "ok": result.get("completed") is False
            and result.get("verdict") == "not-satisfied"
            and source.is_file(),
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-stale-") as temp_dir:
        root = Path(temp_dir)
        messages, route, source, snippet, snapshot = prepare(root, implemented)
        raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
        source.write_text(implemented + "// changed after capture\n", encoding="utf-8")
        result = server.controller_handle_local_action_satisfaction_verdict(raw, route, root=root)
        checks.append({
            "id": "stale-source-or-context-binding-fails-closed",
            "ok": result.get("completed") is False
            and result.get("reasonCode") == "satisfaction-evidence-stale"
            and not any(item.get("kind") == "local-action-verified-noop" for item in result.get("receipts") or []),
            "actual": result.get("reasonCode"),
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-invalid-") as temp_dir:
        root = Path(temp_dir)
        messages, route, _source, _snippet, _snapshot = prepare(root, implemented)
        prose = server.controller_handle_local_action_satisfaction_verdict(
            "It is already implemented.",
            route,
            root=root,
        )

        def timeout_runner(_prompt, _schema, timeout):
            raise subprocess.TimeoutExpired("satisfaction-verifier", timeout)

        timed_out = server.run_local_action_satisfaction_verifier(
            messages,
            route,
            root,
            runner=timeout_runner,
        )
        checks.append({
            "id": "prose-and-timeout-never-produce-noop",
            "ok": prose.get("completed") is False
            and prose.get("reasonCode") == "satisfaction-json"
            and timed_out.get("completed") is False
            and timed_out.get("reasonCode") == "satisfaction-timeout",
            "actual": {"prose": prose.get("reasonCode"), "timeout": timed_out.get("reasonCode")},
        })

        tool_attempt = server.run_local_action_satisfaction_verifier(
            messages,
            route,
            root,
            runner=lambda _prompt, _schema, _timeout: {
                "answer": "{}",
                "returnCode": 0,
                "toolEventCount": 1,
            },
        )
        checks.append({
            "id": "tool-attempt-never-produces-noop",
            "ok": tool_attempt.get("completed") is False
            and tool_attempt.get("reasonCode") == "satisfaction-tool-event",
            "actual": tool_attempt.get("reasonCode"),
        })

    failed = [item for item in checks if not item.get("ok")]
    payload = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
