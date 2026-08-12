#!/usr/bin/env python3
"""Offline contract for the bounded, hash-bound satisfaction decision cache."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from p177_generic_satisfaction_verifier_smoke import prepare, verdict  # noqa: E402


IMPLEMENTED = (
    "function renderDeviceRow(device, detail) {\n"
    "  const values = [];\n"
    "  values.push(device.connectionQuality);\n"
    "  values.push(device.lastSyncTime);\n"
    "  detail.textContent = values.join(' | ');\n"
    "}\n"
)


def binding_for(messages, route, root, profile="local-oss"):
    orientation = route.get("_localProductSourceOrientation") or {}
    pack = {
        "contextSnippets": server.local_product_orientation_context_snippets(
            root,
            orientation.get("contextReads") or [],
            max_snippets=1,
        )
    }
    prompt = server.build_local_action_satisfaction_prompt(messages, route, orientation_pack=pack)
    schema = server.local_action_satisfaction_output_schema(route, pack)
    return server.local_action_satisfaction_cache_binding(
        route,
        root,
        profile,
        prompt,
        schema,
        pack,
    )


def verified_runner(raw, calls):
    def run(_prompt, _schema, _timeout):
        calls.append("worker")
        return {"answer": raw, "returnCode": 0, "toolEventCount": 0}

    return run


def finalize_and_admit(messages, route, snapshot, root, result):
    receipts = list(result.get("receipts") or [])
    reconciliation = server.reconcile_local_action_candidate_sources(snapshot, receipts, root)
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
    admitted = server.admit_local_action_satisfaction_cache(route, root, result, terminal)
    return terminal, admitted


def cache_size():
    with server.LOCAL_ACTION_SATISFACTION_CACHE_LOCK:
        return len(server.LOCAL_ACTION_SATISFACTION_CACHE)


def main() -> int:
    checks = []
    server.clear_local_action_satisfaction_cache()

    with tempfile.TemporaryDirectory(prefix="codex-p179-cache-") as temp_dir:
        root = Path(temp_dir)
        messages, route, _source, snippet, snapshot = prepare(root, IMPLEMENTED)
        raw = verdict(route, snippet, snapshot, "satisfied", "implemented-behavior")
        calls = []
        cold = server.run_local_action_satisfaction_verifier(
            messages,
            route,
            root,
            runner=verified_runner(raw, calls),
        )
        before_admission = cache_size()
        terminal, admitted = finalize_and_admit(messages, route, snapshot, root, cold)
        stored_receipt = next(
            (
                item
                for item in route.get("_localCommandReceipts") or []
                if item.get("kind") == "local-action-source-satisfaction"
            ),
            {},
        )
        checks.append({
            "id": "cold-full-verifier-admits-only-after-terminal-proof",
            "ok": calls == ["worker"]
            and cold.get("completed") is True
            and before_admission == 0
            and admitted is True
            and cache_size() == 1
            and terminal.get("completed") is True
            and terminal.get("contract", {}).get("status") == "pass"
            and stored_receipt.get("cacheStatus") == "stored"
            and stored_receipt.get("workerInvoked") is True,
            "actual": {
                "calls": len(calls),
                "beforeAdmission": before_admission,
                "afterAdmission": cache_size(),
                "cacheStatus": stored_receipt.get("cacheStatus"),
            },
        })

        cached_key = cold.get("cacheKeyDigest")
        warm_messages, warm_route, _warm_source, _warm_snippet, warm_snapshot = prepare(root, IMPLEMENTED)
        warm_calls = []
        warm = server.run_local_action_satisfaction_verifier(
            warm_messages,
            warm_route,
            root,
            runner=lambda *_args: warm_calls.append("unexpected") or {},
        )
        warm_terminal, warm_admitted = finalize_and_admit(
            warm_messages,
            warm_route,
            warm_snapshot,
            root,
            warm,
        )
        serialized_cache = json.dumps(server.LOCAL_ACTION_SATISFACTION_CACHE, sort_keys=True)
        checks.append({
            "id": "warm-identical-binding-revalidates-without-worker",
            "ok": warm.get("completed") is True
            and warm.get("cacheStatus") == "hit"
            and warm.get("cacheKeyDigest") == cached_key
            and warm.get("workerInvoked") is False
            and warm_calls == []
            and warm_terminal.get("completed") is True
            and warm_admitted is False
            and IMPLEMENTED not in serialized_cache
            and "runId" not in serialized_cache
            and "answer" not in serialized_cache,
            "actual": {
                "cacheStatus": warm.get("cacheStatus"),
                "workerCalls": len(warm_calls),
                "terminal": warm_terminal.get("completed"),
            },
        })

        baseline_binding = binding_for(messages, route, root)
        request_messages, request_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        request_messages[0]["text"] = "Display battery health in the device row."
        request_route["intentFrame"]["requestedChange"] = request_messages[0]["text"]
        server.bind_local_action_request_fingerprint(request_messages, request_route)
        request_binding = binding_for(request_messages, request_route, root)

        target_messages, target_route, _source, _snippet, _snapshot = prepare(
            root,
            IMPLEMENTED,
            target_surface="device_panel.summary",
        )
        target_binding = binding_for(target_messages, target_route, root)

        authority_messages, authority_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        authority_route["capabilityPlan"]["handler_key"] = "alternate-local-controller"
        authority_binding = binding_for(authority_messages, authority_route, root)

        plan_messages, plan_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        plan_route["intentFrame"]["operationPlan"]["prohibited"] = ["network"]
        plan_binding = binding_for(plan_messages, plan_route, root)

        source_messages, source_route, _source, _snippet, _snapshot = prepare(
            root,
            IMPLEMENTED + "// source revision\n",
        )
        source_binding = binding_for(source_messages, source_route, root)

        context_messages, context_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        context_route["_localProductSourceOrientation"]["contextReads"] = [{
            "path": "ui.js",
            "start": 2,
            "end": 6,
            "hitLine": 4,
            "command": "sed -n '2,6p' ui.js",
        }]
        context_binding = binding_for(context_messages, context_route, root)

        path_messages, path_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        (root / "panel.js").write_text(IMPLEMENTED, encoding="utf-8")
        path_orientation = path_route["_localProductSourceOrientation"]
        path_orientation["candidatePaths"] = ["panel.js"]
        path_orientation["contextReads"] = [{
            "path": "panel.js",
            "start": 1,
            "end": 6,
            "hitLine": 4,
            "command": "sed -n '1,6p' panel.js",
        }]
        server.snapshot_local_action_candidate_sources(path_route, root)
        path_binding = binding_for(path_messages, path_route, root)

        with tempfile.TemporaryDirectory(prefix="codex-p179-other-root-") as other_dir:
            other_root = Path(other_dir)
            other_messages, other_route, _source, _snippet, _snapshot = prepare(other_root, IMPLEMENTED)
            root_binding = binding_for(other_messages, other_route, other_root)

        profile_binding = binding_for(messages, route, root, profile="local-review")
        original_versions = (
            server.LOCAL_ACTION_SATISFACTION_CACHE_VERSION,
            server.LOCAL_ACTION_SATISFACTION_PROMPT_VERSION,
            server.LOCAL_ACTION_SATISFACTION_SCHEMA_VERSION,
        )
        try:
            server.LOCAL_ACTION_SATISFACTION_CACHE_VERSION = "p179-test-cache-revision"
            cache_version_binding = binding_for(messages, route, root)
            server.LOCAL_ACTION_SATISFACTION_CACHE_VERSION = original_versions[0]
            server.LOCAL_ACTION_SATISFACTION_PROMPT_VERSION = "p179-test-prompt-revision"
            prompt_version_binding = binding_for(messages, route, root)
            server.LOCAL_ACTION_SATISFACTION_PROMPT_VERSION = original_versions[1]
            server.LOCAL_ACTION_SATISFACTION_SCHEMA_VERSION = "p179-test-schema-revision"
            schema_version_binding = binding_for(messages, route, root)
        finally:
            (
                server.LOCAL_ACTION_SATISFACTION_CACHE_VERSION,
                server.LOCAL_ACTION_SATISFACTION_PROMPT_VERSION,
                server.LOCAL_ACTION_SATISFACTION_SCHEMA_VERSION,
            ) = original_versions
        changed_keys = {
            request_binding.get("keyDigest"),
            root_binding.get("keyDigest"),
            profile_binding.get("keyDigest"),
            target_binding.get("keyDigest"),
            authority_binding.get("keyDigest"),
            plan_binding.get("keyDigest"),
            source_binding.get("keyDigest"),
            context_binding.get("keyDigest"),
            path_binding.get("keyDigest"),
            cache_version_binding.get("keyDigest"),
            prompt_version_binding.get("keyDigest"),
            schema_version_binding.get("keyDigest"),
        }
        checks.append({
            "id": "every-request-source-context-route-model-and-version-change-misses",
            "ok": bool(baseline_binding.get("keyDigest"))
            and "" not in changed_keys
            and None not in changed_keys
            and baseline_binding.get("keyDigest") not in changed_keys
            and len(changed_keys) == 12,
            "actual": {"distinctChangedKeys": len(changed_keys)},
        })

        stale_messages, stale_route, stale_source, stale_snippet, stale_snapshot = prepare(root, IMPLEMENTED)
        stale_raw = verdict(stale_route, stale_snippet, stale_snapshot, "satisfied", "implemented-behavior")
        stale_source.chmod(0o600)
        stale_calls = []
        stale = server.run_local_action_satisfaction_verifier(
            stale_messages,
            stale_route,
            root,
            runner=verified_runner(stale_raw, stale_calls),
        )
        checks.append({
            "id": "stale-source-mode-revalidation-never-serves-hit",
            "ok": stale_calls == ["worker"]
            and stale.get("completed") is False
            and stale.get("cacheStatus") == "miss"
            and stale.get("reasonCode") == "satisfaction-evidence-stale",
            "actual": {
                "calls": len(stale_calls),
                "cacheStatus": stale.get("cacheStatus"),
                "reasonCode": stale.get("reasonCode"),
            },
        })
        stale_source.chmod(0o644)

        cross_messages, cross_route, _source, cross_snippet, cross_snapshot = prepare(root, IMPLEMENTED)
        cross_route["intentFrame"]["domain"] = "engineering_advisory"
        cross_raw = verdict(cross_route, cross_snippet, cross_snapshot, "not-satisfied", "different-surface")
        cross_calls = []
        cross = server.run_local_action_satisfaction_verifier(
            cross_messages,
            cross_route,
            root,
            runner=verified_runner(cross_raw, cross_calls),
        )
        checks.append({
            "id": "different-domain-never-reuses-local-product-decision",
            "ok": binding_for(cross_messages, cross_route, root) == {}
            and cross_calls == ["worker"]
            and cross.get("completed") is False
            and cross.get("cacheStatus") == "miss",
            "actual": {"calls": len(cross_calls), "cacheStatus": cross.get("cacheStatus")},
        })

        invalid_start_size = cache_size()
        invalid_outcomes = []
        for label, runner in (
            (
                "timeout",
                lambda _prompt, _schema, timeout: (_ for _ in ()).throw(
                    subprocess.TimeoutExpired("satisfaction-verifier", timeout)
                ),
            ),
            ("prose", lambda *_args: {"answer": "already done", "returnCode": 0, "toolEventCount": 0}),
            ("tool", lambda *_args: {"answer": "{}", "returnCode": 0, "toolEventCount": 1}),
            ("failed", lambda *_args: {"answer": "{}", "returnCode": 2, "toolEventCount": 0}),
        ):
            with tempfile.TemporaryDirectory(prefix=f"codex-p179-{label}-") as invalid_dir:
                invalid_root = Path(invalid_dir)
                invalid_messages, invalid_route, _source, _snippet, _snapshot = prepare(
                    invalid_root,
                    IMPLEMENTED,
                )
                invalid_outcomes.append(
                    server.run_local_action_satisfaction_verifier(
                        invalid_messages,
                        invalid_route,
                        invalid_root,
                        runner=runner,
                    )
                )
        checks.append({
            "id": "timeout-prose-tool-and-failed-results-are-never-cached",
            "ok": cache_size() == invalid_start_size
            and all(item.get("completed") is False for item in invalid_outcomes)
            and {item.get("reasonCode") for item in invalid_outcomes}
            == {
                "satisfaction-timeout",
                "satisfaction-json",
                "satisfaction-tool-event",
                "satisfaction-worker-failed",
            },
            "actual": {
                "cacheDelta": cache_size() - invalid_start_size,
                "reasons": sorted(item.get("reasonCode") for item in invalid_outcomes),
            },
        })

        cancel_messages, cancel_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        cancel_run_id = "p179-cache-cancelled"
        cancel_route["_liveRunId"] = cancel_run_id
        server.register_live_run(cancel_run_id)
        server.cancel_live_run(cancel_run_id)
        cancel_calls = []
        cancelled = server.run_local_action_satisfaction_verifier(
            cancel_messages,
            cancel_route,
            root,
            runner=lambda *_args: cancel_calls.append("unexpected") or {},
        )
        server.unregister_live_run(cancel_run_id)

        steer_messages, steer_route, _source, _snippet, _snapshot = prepare(root, IMPLEMENTED)
        steer_run_id = "p179-cache-steered"
        steer_route["_liveRunId"] = steer_run_id
        server.register_live_run(steer_run_id)
        server.add_live_steering(steer_run_id, "When I say display, I mean remove those values instead.")
        steer_calls = []
        steered = server.run_local_action_satisfaction_verifier(
            steer_messages,
            steer_route,
            root,
            runner=lambda *_args: steer_calls.append("unexpected") or {},
        )
        server.unregister_live_run(steer_run_id)
        checks.append({
            "id": "cancelled-or-steered-run-cannot-serve-a-cache-hit",
            "ok": cancelled.get("completed") is False
            and cancelled.get("reasonCode") == "satisfaction-cancelled"
            and steered.get("completed") is False
            and steered.get("reasonCode") == "satisfaction-steered"
            and cancel_calls == []
            and steer_calls == [],
            "actual": {
                "cancelled": cancelled.get("reasonCode"),
                "steered": steered.get("reasonCode"),
            },
        })

        original_limit = server.LOCAL_ACTION_SATISFACTION_CACHE_MAX_ENTRIES
        original_ttl = server.LOCAL_ACTION_SATISFACTION_CACHE_TTL_SECONDS
        try:
            with server.LOCAL_ACTION_SATISFACTION_CACHE_LOCK:
                seed = copy.deepcopy(next(iter(server.LOCAL_ACTION_SATISFACTION_CACHE.values())))
                server.LOCAL_ACTION_SATISFACTION_CACHE.clear()
                server.LOCAL_ACTION_SATISFACTION_CACHE_MAX_ENTRIES = 2
                for key in ("oldest", "middle", "newest"):
                    entry = copy.deepcopy(seed)
                    entry["createdMonotonic"] = time.monotonic()
                    server.LOCAL_ACTION_SATISFACTION_CACHE[key] = entry
                server._prune_local_action_satisfaction_cache_locked()
                bounded_keys = list(server.LOCAL_ACTION_SATISFACTION_CACHE)
                server.LOCAL_ACTION_SATISFACTION_CACHE_TTL_SECONDS = 1
                server.LOCAL_ACTION_SATISFACTION_CACHE["middle"]["createdMonotonic"] = time.monotonic() - 2
                server._prune_local_action_satisfaction_cache_locked()
                ttl_keys = list(server.LOCAL_ACTION_SATISFACTION_CACHE)
        finally:
            server.LOCAL_ACTION_SATISFACTION_CACHE_MAX_ENTRIES = original_limit
            server.LOCAL_ACTION_SATISFACTION_CACHE_TTL_SECONDS = original_ttl
            server.clear_local_action_satisfaction_cache()
        checks.append({
            "id": "locked-lru-is-bounded-and-ttl-does-not-refresh",
            "ok": bounded_keys == ["middle", "newest"] and ttl_keys == ["newest"],
            "actual": {"bounded": bounded_keys, "afterTtl": ttl_keys},
        })

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
