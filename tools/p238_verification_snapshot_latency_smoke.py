#!/usr/bin/env python3
"""P238 adversaries for request-local verification snapshot reuse."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


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

    def route_for(messages, run_id):
        route = server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )
        route["_liveRunId"] = run_id
        return route

    freshen_messages = [
        {
            "role": "user",
            "text": (
                "Which receipts are stale and how do I freshen the Codex CLI UI "
                "receipt bundle?"
            ),
        }
    ]
    freshen_route = route_for(freshen_messages, "p238-synthetic")

    fixture = {
        "summary": {
            "ok": True,
            "status": "pass",
            "passed": 6,
            "total": 6,
            "items": [
                {
                    "id": "package-health-checkpoint",
                    "label": "Package Health",
                    "status": "pass",
                    "metric": "566/566",
                    "age": "current",
                    "nextAction": "No action needed.",
                    "path": "/fixture/package.json",
                },
                {
                    "id": "live-feedback-smoke",
                    "label": "Live Smoke · Systemic Acceptance",
                    "status": "pass",
                    "metric": "130/130",
                    "age": "current",
                    "nextAction": "No action needed.",
                    "path": "/fixture/smoke.json",
                },
                {
                    "id": "live-feedback-smoke-historical-workflow",
                    "label": "Live Smoke · Historical Workflow",
                    "status": "warn",
                    "metric": "32/83",
                    "age": "historical",
                    "nextAction": "Run historical workflow.",
                    "path": "/fixture/historical.json",
                    "contributesToHealth": False,
                },
                {
                    "id": "ai-intent-500",
                    "label": "AI Intent 500",
                    "status": "pass",
                    "metric": "500/500",
                    "age": "current",
                    "nextAction": "No action needed.",
                    "path": "/fixture/replay.json",
                },
                {
                    "id": "public-export",
                    "label": "Public Export",
                    "status": "pass",
                    "metric": "178 files, 0 privacy findings, current",
                    "age": "current",
                    "nextAction": "No action needed.",
                    "path": "/fixture/export.json",
                },
                {
                    "id": "runtime-exceptions",
                    "label": "Runtime Exceptions",
                    "status": "pass",
                    "metric": "clean",
                    "age": "clean since restart",
                    "nextAction": "No action needed.",
                    "path": "/fixture/exceptions.log",
                },
                {
                    "id": "self-healing-queue",
                    "label": "Self-Healing Queue",
                    "status": "pass",
                    "metric": "0 open",
                    "age": "idle",
                    "nextAction": "No action needed.",
                    "path": "/fixture/queue.json",
                },
            ],
        },
        "artifacts": {
            "checkpointPath": "/fixture/checkpoint.md",
            "smokePath": "/fixture/smoke.json",
            "replayPath": "/fixture/replay.json",
            "smokePassed": 130,
            "smokeTotal": 130,
        },
        "inventory": {
            "defaultCount": 130,
            "receiptPassed": 130,
            "receiptTotal": 130,
        },
    }
    calls = {"summary": 0, "artifacts": 0, "inventory": 0, "observations": 0}
    source_state = {"sha": "a" * 64}
    originals = {
        "summary": server.verification_summary,
        "artifacts": server.local_improvement_status_artifacts,
        "inventory": server.local_live_feedback_smoke_inventory,
        "observations": server.trusted_local_file_source_observations,
        "source": server.current_verification_receipt_snapshot_source_sha256,
    }

    def fake_artifacts():
        calls["artifacts"] += 1
        return copy.deepcopy(fixture["artifacts"])

    def fake_inventory():
        calls["inventory"] += 1
        return copy.deepcopy(fixture["inventory"])

    def fake_summary(artifacts=None, smoke_inventory=None):
        calls["summary"] += 1
        if not isinstance(artifacts, dict) or not isinstance(smoke_inventory, dict):
            raise AssertionError("snapshot inputs were not shared with verification_summary")
        return copy.deepcopy(fixture["summary"])

    def fake_observations(paths):
        calls["observations"] += 1
        rows = []
        for index, raw_path in enumerate(paths or []):
            path = str(raw_path or "")
            if not path or any(row.get("path") == path for row in rows):
                continue
            text = f"typed fixture receipt {index}"
            rows.append(
                {
                    "kind": "source-observation",
                    "sourceType": "local-file",
                    "path": path,
                    "localPath": path,
                    "text": text,
                    "excerpt": text,
                    "contentSha256": hashlib.sha256(text.encode()).hexdigest(),
                    "observedAt": "2026-08-11T00:00:00Z",
                    "sourceId": f"fixture-{index}",
                }
            )
        return rows

    try:
        server.local_improvement_status_artifacts = fake_artifacts
        server.local_live_feedback_smoke_inventory = fake_inventory
        server.verification_summary = fake_summary
        server.trusted_local_file_source_observations = fake_observations
        server.current_verification_receipt_snapshot_source_sha256 = (
            lambda: source_state["sha"]
        )

        snapshot = server.build_verification_receipt_snapshot(
            freshen_messages,
            freshen_route,
        )
        initial_calls = dict(calls)
        packet = server.general_direct_knowledge_answer(
            freshen_messages,
            freshen_route,
            web_search="disabled",
            verification_snapshot=snapshot,
        ) or {}
        after_packet_calls = dict(calls)
        observations = server.bounded_specialist_source_observations(
            freshen_messages,
            route=freshen_route,
            verification_snapshot=snapshot,
        )
        after_observation_calls = dict(calls)
        add(
            "one-build-feeds-answer-and-evidence-without-recomputation",
            initial_calls
            == {"summary": 1, "artifacts": 1, "inventory": 1, "observations": 1}
            and after_packet_calls == initial_calls
            and after_observation_calls == initial_calls
            and packet.get("mode") == "freshen-receipts-plan"
            and observations
            and all(item.get("sourceType") == "local-file" for item in observations),
            {
                "initialCalls": initial_calls,
                "afterPacketCalls": after_packet_calls,
                "afterObservationCalls": after_observation_calls,
                "mode": packet.get("mode"),
                "sources": len(observations),
            },
        )
        direct_text = server.freshen_receipts_direct_answer(
            freshen_messages,
            route=freshen_route,
            verification_snapshot=snapshot,
        )
        add(
            "shared-snapshot-does-not-change-answer-contract",
            packet.get("answer") == direct_text
            and "I did not run any refresh commands" in direct_text
            and "130/130" in direct_text
            and "500/500" in direct_text,
            direct_text,
        )

        context_messages = [
            {"role": "assistant", "text": "An unrelated prior receipt context."},
            *freshen_messages,
        ]
        before = calls["summary"]
        context_snapshot = server.resolve_verification_receipt_snapshot(
            context_messages,
            freshen_route,
            snapshot,
        )
        add(
            "stale-context-binding-rebuilds-fail-closed",
            calls["summary"] == before + 1
            and context_snapshot.get("binding", {}).get("contextSha256")
            != snapshot.get("binding", {}).get("contextSha256"),
            context_snapshot.get("binding"),
        )

        wrong_run_route = dict(freshen_route)
        wrong_run_route["_liveRunId"] = "p238-other-run"
        before = calls["summary"]
        run_snapshot = server.resolve_verification_receipt_snapshot(
            freshen_messages,
            wrong_run_route,
            snapshot,
        )
        add(
            "wrong-run-binding-rebuilds-fail-closed",
            calls["summary"] == before + 1
            and run_snapshot.get("binding", {}).get("runId") == "p238-other-run",
            run_snapshot.get("binding"),
        )

        forged_surface = copy.deepcopy(snapshot)
        forged_surface["binding"]["targetSurface"] = "unrelated-local-status"
        before = calls["summary"]
        surface_snapshot = server.resolve_verification_receipt_snapshot(
            freshen_messages,
            freshen_route,
            forged_surface,
        )
        add(
            "wrong-surface-binding-rebuilds-fail-closed",
            calls["summary"] == before + 1
            and surface_snapshot.get("binding", {}).get("targetSurface")
            == "freshen-receipts",
            surface_snapshot.get("binding"),
        )

        source_state["sha"] = "b" * 64
        before = calls["summary"]
        drift_snapshot = server.resolve_verification_receipt_snapshot(
            freshen_messages,
            freshen_route,
            snapshot,
        )
        add(
            "source-drift-binding-rebuilds-fail-closed",
            calls["summary"] == before + 1
            and drift_snapshot.get("binding", {}).get("sourceSha256") == "b" * 64,
            drift_snapshot.get("binding"),
        )

        unrelated_messages = [
            {
                "role": "user",
                "text": "What file type from Fusion 360 preserves constraints?",
            }
        ]
        unrelated_route = route_for(unrelated_messages, "p238-unrelated")
        before_calls = dict(calls)
        unrelated_packet = server.general_direct_knowledge_answer(
            unrelated_messages,
            unrelated_route,
            web_search="disabled",
        ) or {}
        add(
            "unrelated-domain-does-not-build-or-consume-receipt-snapshot",
            server.verification_receipt_snapshot_surface(unrelated_messages) == ""
            and calls == before_calls
            and unrelated_packet.get("mode") != "verification-receipts-direct-answer"
            and "Latest verification receipts" not in str(unrelated_packet.get("answer") or ""),
            {"calls": calls, "mode": unrelated_packet.get("mode")},
        )

        fixture["summary"]["status"] = "warn"
        fixture["summary"]["passed"] = 5
        next_route = dict(freshen_route)
        next_route["_liveRunId"] = "p238-next-request"
        before = calls["summary"]
        next_snapshot = server.resolve_verification_receipt_snapshot(
            freshen_messages,
            next_route,
            None,
        )
        next_answer = server.verification_receipts_direct_result(
            freshen_messages,
            route=next_route,
            verification_snapshot=next_snapshot,
        ).get("answer", "")
        add(
            "new-request-rebuilds-instead-of-cross-request-caching",
            calls["summary"] == before + 1
            and next_snapshot.get("summary", {}).get("status") == "warn"
            and "5/6" in next_answer,
            {"calls": calls, "lead": next_answer.splitlines()[0] if next_answer else ""},
        )
    finally:
        server.verification_summary = originals["summary"]
        server.local_improvement_status_artifacts = originals["artifacts"]
        server.local_live_feedback_smoke_inventory = originals["inventory"]
        server.trusted_local_file_source_observations = originals["observations"]
        server.current_verification_receipt_snapshot_source_sha256 = originals["source"]

    real_durations = []
    real_answers = []
    real_sources = []
    for index in range(2):
        route = route_for(freshen_messages, f"p238-real-{index}")
        started = time.perf_counter()
        result = server.execute_deterministic_capability(
            freshen_messages,
            route,
            webSearch="disabled",
        )
        real_durations.append(round((time.perf_counter() - started) * 1000))
        real_answers.append(str(result.get("answer") or ""))
        real_sources.append(len(result.get("sourceObservations") or []))
    normalized_answers = [
        re.sub(r"\d{8}T\d{4}Z-freshen-receipts", "<label>", answer)
        for answer in real_answers
    ]
    add(
        "cold-and-warm-real-executor-stay-under-fifteen-seconds",
        all(duration <= 15000 for duration in real_durations)
        and all(count > 0 for count in real_sources)
        and normalized_answers[0] == normalized_answers[1]
        and all("I did not run any refresh commands" in answer for answer in real_answers),
        {"durationMs": real_durations, "sourceCounts": real_sources},
    )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "snapshot-is-not-stored-in-route-or-shared-globally",
        'route["_verificationReceiptSnapshot"]' not in source_text
        and "VERIFICATION_RECEIPT_SNAPSHOT_CACHE" not in source_text,
    )
    add(
        "p238-package-and-export-registration",
        "server:verification-snapshot-latency-p238" in source_text
        and "p238_verification_snapshot_latency_smoke.py" in source_text
        and "tools/p238_verification_snapshot_latency_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p238-verification-snapshot-latency",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "timing": {
            "budgetMs": 15000,
            "coldMs": real_durations[0] if real_durations else None,
            "warmMs": real_durations[1] if len(real_durations) > 1 else None,
        },
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
