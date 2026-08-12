#!/usr/bin/env python3
"""Focused P200 checks for attachment authority, routing, and receipt truth."""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server
from capability_registry import registry_health


checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:1600]})


capability_messages = [
    {
        "role": "user",
        "text": "Do you have the capability to compare a file once I attach it, without modifying anything?",
    }
]
capability_route = server.route_manager(
    capability_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
capability_frame = capability_route.get("intentFrame") or {}
capability_plan = capability_frame.get("operationPlan") or {}
capability_snapshot = server.compact_feedback_task_snapshot(
    capability_route,
    server.active_answer_relevance_task_contract(capability_messages, capability_route),
)
snapshot_operation = capability_snapshot.get("operation") or {}
capability_answer = server.runtime_capability_introspection_direct_answer(
    capability_messages,
    capability_route,
)
repaired_capability_answer, capability_boundary_repairs = (
    server.repair_missing_operation_boundary_report(
        capability_route,
        capability_answer,
    )
)
check(
    "future-capability-is-non-executing",
    capability_frame.get("actionType") == "confirm_read_only_attachment_capability"
    and (capability_route.get("capabilityPlan") or {}).get("id")
    == "runtime-capability-introspection"
    and capability_plan.get("allowedNow") == []
    and capability_plan.get("discussed") == ["inspect"]
    and capability_plan.get("prohibited") == ["change"]
    and capability_plan.get("readOnly") is True,
    capability_frame,
)
check(
    "feedback-snapshot-preserves-complete-authority",
    snapshot_operation.get("allowedNow") == []
    and snapshot_operation.get("discussed") == ["inspect"]
    and snapshot_operation.get("prohibited") == ["change"]
    and snapshot_operation.get("deferred") == []
    and snapshot_operation.get("readOnly") is True,
    snapshot_operation,
)
check(
    "natural-read-only-wording-satisfies-boundary",
    repaired_capability_answer == capability_answer and not capability_boundary_repairs,
    {"answer": capability_answer, "repairs": capability_boundary_repairs},
)

with tempfile.TemporaryDirectory(prefix="p200-attachment-smoke-") as tmp_dir:
    first = Path(tmp_dir) / "first.cfg"
    second = Path(tmp_dir) / "second.cfg"
    first.write_text("[mcu]\nserial: first\n", encoding="utf-8")
    second.write_text("[mcu]\nserial: second\n", encoding="utf-8")
    attachments = [
        {"name": first.name, "path": str(first), "size": first.stat().st_size, "type": "text/plain"},
        {"name": second.name, "path": str(second), "size": second.stat().st_size, "type": "text/plain"},
    ]

    read_messages = [
        {
            "role": "user",
            "text": "Can you compare these attached configuration files without modifying them?",
            "attachments": attachments,
        }
    ]
    read_route = server.route_manager(
        read_messages,
        cwd=tmp_dir,
        requested_profile="manager",
        web_search="disabled",
    )
    read_frame = read_route.get("intentFrame") or {}
    read_plan = read_frame.get("operationPlan") or {}
    read_capability = read_route.get("capabilityPlan") or {}
    read_answer = server.local_file_comparison_direct_answer(read_messages, cwd=tmp_dir)
    read_result = server.execute_local_tool_capability(
        read_messages,
        read_route,
        cwd=tmp_dir,
    )
    check(
        "actual-attachments-own-local-file-route",
        read_frame.get("domain") == "local_file_evidence"
        and read_frame.get("actionType") == "inspect_local_files"
        and read_capability.get("id") == "local-file-evidence"
        and read_capability.get("handler_key") == "local_file_evidence"
        and read_route.get("matched") == ["local-file-comparison"],
        {"frame": read_frame, "capability": read_capability, "matched": read_route.get("matched")},
    )
    check(
        "actual-read-only-boundary-is-typed",
        read_plan.get("allowedNow") == ["inspect"]
        and read_plan.get("prohibited") == ["edit"]
        and read_plan.get("readOnly") is True,
        read_plan,
    )
    check(
        "actual-comparison-uses-local-evidence",
        first.name in read_answer
        and second.name in read_answer
        and "hash" in read_answer.lower()
        and server.capability_dispatch_allowed(read_route, "local_file_evidence"),
        read_answer,
    )
    observations = read_result.get("sourceObservations") or []
    expected_paths = {str(first), str(second)}
    check(
        "actual-comparison-emits-trusted-source-observations",
        read_result.get("handled") is True
        and read_result.get("outcome") == "completed"
        and {item.get("localPath") for item in observations} == expected_paths
        and all(item.get("kind") == "source-observation" for item in observations)
        and all(item.get("sourceType") == "local-file" for item in observations)
        and all(
            item.get("contentSha256")
            == hashlib.sha256(Path(item.get("localPath")).read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()
            for item in observations
        ),
        {"result": read_result, "observations": observations},
    )

    write_messages = [
        {
            "role": "user",
            "text": "Compare these attached configuration files and update the second one to match the first.",
            "attachments": attachments,
        }
    ]
    write_route = server.route_manager(
        write_messages,
        cwd=tmp_dir,
        requested_profile="manager",
        web_search="disabled",
    )
    write_frame = write_route.get("intentFrame") or {}
    write_plan = write_frame.get("operationPlan") or {}
    write_capability = write_route.get("capabilityPlan") or {}
    check(
        "authorized-mutation-uses-local-agent",
        write_frame.get("domain") == "local_file_work"
        and write_capability.get("id") == "local-file-work"
        and write_capability.get("executor") == "local-agent"
        and write_plan.get("allowedNow") == ["inspect", "change"]
        and write_plan.get("readOnly") is False,
        {"frame": write_frame, "capability": write_capability},
    )
    check(
        "mutation-cannot-fall-through-read-only-comparator",
        not server.capability_dispatch_allowed(write_route, "local_file_evidence")
        and server.local_action_tool_operations(write_route) == ["change", "inspect"],
        {"capability": write_capability, "operations": server.local_action_tool_operations(write_route)},
    )

    one_messages = [
        {
            "role": "user",
            "text": "Inspect this attached configuration file without modifying it.",
            "attachments": attachments[:1],
        }
    ]
    one_route = server.route_manager(
        one_messages,
        cwd=tmp_dir,
        requested_profile="manager",
        web_search="disabled",
    )
    check(
        "single-attachment-is-still-primary-local-evidence",
        (one_route.get("intentFrame") or {}).get("domain") == "local_file_evidence"
        and (one_route.get("capabilityPlan") or {}).get("id") == "local-file-evidence"
        and (one_route.get("intentFrame") or {}).get("operationPlan", {}).get("readOnly") is True,
        one_route.get("intentFrame"),
    )

check("package-synthetic-contract", server.read_only_attachment_authority_p200_synthetic_check())
software_comparison_messages = [
    {
        "role": "user",
        "text": (
            "Compare the face-selection output in Bambu Studio, Creality Print, "
            "OrcaSlicer, and our local implementation to find the software bug."
        ),
    }
]
software_comparison_route = server.route_manager(
    software_comparison_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "named-printer-software-is-not-a-live-device",
    (software_comparison_route.get("intentFrame") or {}).get("domain")
    != "live_device_action"
    and (software_comparison_route.get("capabilityPlan") or {}).get("id")
    != "live-device-authority",
    software_comparison_route.get("intentFrame"),
)
check(
    "replacement-package-gate-does-not-inherit-prior-failure",
    server.verification_package_receipt_status("541/543", 2, worker_active=True)
    == "unknown"
    and server.verification_package_receipt_status("541/543", 2, worker_active=False)
    == "fail",
)
check("capability-registry-health", registry_health().get("status") == "pass", registry_health())

failed = [item for item in checks if not item["ok"]]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "failedCount": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
