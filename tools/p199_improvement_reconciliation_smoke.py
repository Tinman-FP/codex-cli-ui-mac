#!/usr/bin/env python3
"""Focused P199 checks for proof-bound Improvement Lab reconciliation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:1200]})


check(
    "answered-clarification-is-progress-not-failure",
    server.clarification_resolution_backlog_synthetic_check(),
)
check(
    "bambu-health-proof-is-source-consistent",
    server.bambu_h2d_health_panel_fix_synthetic_check(),
)

fixtures = [
    {
        "id": "clarification-answer",
        "type": "answer-quality",
        "status": "open",
        "title": "Repair wrong-objective: ambiguous comparison",
        "prompt": "Match Riverstone to the newer setup.",
        "evidence": (
            "I mean a local configuration file that I have not attached yet. "
            "Do you have the capability to compare it once I attach it, without modifying anything?"
        ),
    },
    {
        "id": "clarification-supervisor",
        "type": "self-healing",
        "status": "open",
        "title": "Self-repair work order: general self-repair",
        "evidence": (
            "I mean a configuration file that is not attached yet. "
            "Can you review it after I attach it without changing either file?"
        ),
    },
    {
        "id": "bambu-answer",
        "type": "answer-quality",
        "status": "open",
        "title": "Repair direct-answer-shape",
        "prompt": "Do you understand the correction?",
        "evidence": (
            "The Bambu H2D is online and printing but the Model Health panel shows it offline."
        ),
    },
    {
        "id": "bambu-supervisor",
        "type": "self-healing",
        "status": "open",
        "title": "Self-repair work order: general self-repair",
        "evidence": "Bambu H2D health panel says offline while the printer is online and printing.",
    },
]

resolutions = [server.validated_improvement_resolution(item) for item in fixtures]
check(
    "specific-current-proofs-resolve-both-feedback-surfaces",
    all(bool(item) for item in resolutions),
    resolutions,
)

unrelated = {
    "id": "unresolved",
    "type": "answer-quality",
    "status": "open",
    "title": "Unrelated unresolved issue",
    "prompt": "A novel controller answer is still incomplete.",
    "evidence": "The thermal limit is missing.",
}
check(
    "unrelated-backlog-stays-open",
    server.validated_improvement_resolution(unrelated) is None,
)

with tempfile.TemporaryDirectory(prefix="p199-improvement-lab-") as tmp_dir:
    original_path = server.IMPROVEMENT_LAB_PATH
    temp_path = Path(tmp_dir) / "improvement_lab.json"
    payload = {
        "version": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "items": [*fixtures, unrelated],
    }
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    server.IMPROVEMENT_LAB_PATH = temp_path
    try:
        first = server.auto_archive_validated_improvements()
        second = server.auto_archive_validated_improvements()
        saved = server.load_improvement_lab()
    finally:
        server.IMPROVEMENT_LAB_PATH = original_path
    archived = [item for item in saved.get("items", []) if item.get("status") == "archived"]
    open_items = [item for item in saved.get("items", []) if item.get("status") != "archived"]
    check(
        "reconciliation-is-specific-and-idempotent",
        first.get("archived") == 4
        and second.get("archived") == 0
        and len(archived) == 4
        and [item.get("id") for item in open_items] == ["unresolved"]
        and all(item.get("resolutionProof") for item in archived),
        {"first": first, "second": second, "open": open_items},
    )

for index, query in enumerate(
    [
        (
            "I mean a local configuration file that I have not attached yet. "
            "Do you have the capability to compare it once I attach it, without modifying anything?"
        ),
        (
            "Can you inspect a file after I upload it and report differences read-only?"
        ),
    ],
    start=1,
):
    messages = [{"role": "user", "text": query}]
    route = server.route_manager(
        messages,
        cwd=str(server.APP_DIR),
        requested_profile="manager",
        web_search="disabled",
    )
    route["_liveRunId"] = f"p199-read-only-capability-{index}"
    route["runtimeCapabilitySnapshot"] = server.build_runtime_capability_snapshot(
        access_level="danger-full-access",
        cwd=str(server.APP_DIR),
        web_search="disabled",
    )
    packet = server.general_direct_knowledge_answer(
        messages,
        route,
        web_search="disabled",
    ) or {}
    answer = str(packet.get("answer") or "").lower()
    receipt = server.runtime_capability_source_receipt(
        messages,
        route,
        packet.get("answer") or "",
    )
    check(
        f"narrow-read-only-capability-answer-{index}",
        (route.get("intentFrame") or {}).get("domain") == "agent_runtime_capabilities"
        and (route.get("intentFrame") or {}).get("actionType")
        == "confirm_read_only_attachment_capability"
        and (route.get("capabilityPlan") or {}).get("id") == "runtime-capability-introspection"
        and packet.get("mode") == "runtime-capability-introspection"
        and answer.startswith("yes.")
        and "compare" in answer
        and "without modifying" in answer
        and "visible commands" not in answer,
        {"packet": packet, "receipt": receipt},
    )
    check(
        f"read-only-capability-controller-receipt-{index}",
        receipt.get("runId") == route.get("_liveRunId")
        and receipt.get("sourceType") == "runtime-state"
        and receipt.get("claimDigest") == server.text_sha256(packet.get("answer") or ""),
        receipt,
    )

mutation_messages = [
    {
        "role": "user",
        "text": "Compare the two attached configurations, update the older one, and save it.",
    }
]
mutation_route = server.route_manager(
    mutation_messages,
    cwd=str(server.APP_DIR),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "writable-comparison-does-not-use-read-only-capability-owner",
    (mutation_route.get("intentFrame") or {}).get("domain")
    != "agent_runtime_capabilities",
    mutation_route.get("intentFrame"),
)

failed = [item for item in checks if not item["ok"]]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "failedCount": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
