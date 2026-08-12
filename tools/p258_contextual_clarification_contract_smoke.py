#!/usr/bin/env python3
"""Cross-domain contract for contextual referents and truthful needs-input turns."""

import inspect
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import intelligence_kernel
import server


checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


comparison_messages = [
    {
        "role": "user",
        "text": "I am choosing between a compact edge appliance and a desktop accelerator for several simultaneous camera streams.",
    },
    {
        "role": "assistant",
        "text": "The desktop accelerator has more throughput, while the edge appliance uses less power and space.",
    },
    {"role": "user", "text": "What would make the smaller one the better choice anyway?"},
]
relationship = server.turn_context_relationship(comparison_messages)
comparison_route = server.route_manager(
    comparison_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
comparison_frame = comparison_route.get("intentFrame") or {}
comparison_names = [
    str(item.get("name") or "")
    for item in (comparison_frame.get("objectRefs") or [])
    if isinstance(item, dict)
]
check(
    "comparative-referent-retains-prior-turn",
    relationship.get("contextRelation") == "follow-up"
    and relationship.get("contextScope") == "recent-thread",
    relationship,
)
check(
    "comparative-referent-retains-both-options",
    any("edge appliance" in value.lower() for value in comparison_names)
    and any("desktop accelerator" in value.lower() for value in comparison_names),
    comparison_names,
)
comparison_packet = server.build_stable_comparison_primary_author_handoff_prompt(
    comparison_messages,
    comparison_route,
)
comparison_prompt = str(comparison_packet.get("prompt") or "")
check(
    "comparative-author-receives-bound-prior-context",
    (
        "linkedPriorRequest" in comparison_prompt
        and "linkedPriorAnswer" in comparison_prompt
        and "comparativeReferentFollowup" in comparison_prompt
        and "compact edge appliance" in comparison_prompt
        and "uses less power and space" in comparison_prompt
        and "Do not substitute an unrelated workload" in comparison_prompt
        and "Do not describe this as reversing your recommendation" in comparison_prompt
        and "Do not add a validation test that the user did not request" in comparison_prompt
    ),
    {
        "options": comparison_packet.get("options"),
        "promptSha256": server.text_sha256(comparison_prompt),
    },
)

unrelated_messages = [
    {"role": "user", "text": "Compare a pump and a compressor for the test stand."},
    {"role": "assistant", "text": "The two machines serve different pressure and flow regimes."},
    {"role": "user", "text": "Explain smaller semiconductor feature sizes in a new topic."},
]
unrelated = server.turn_context_relationship(unrelated_messages)
check(
    "explicit-new-subject-remains-isolated",
    unrelated.get("contextRelation") == "new-topic",
    unrelated,
)

missing_file_messages = [
    {
        "role": "user",
        "text": "Compare the two configuration files and update the older one, but do not deploy it.",
    }
]
missing_file_route = server.route_manager(
    missing_file_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
missing_file_frame = missing_file_route.get("intentFrame") or {}
missing_file_result = server.execute_deterministic_capability(
    missing_file_messages,
    missing_file_route,
    fullMessages=missing_file_messages,
    cwd=str(ROOT),
    accessLevel="danger-full-access",
    webSearch="disabled",
)
check(
    "absent-local-files-route-to-clarification",
    missing_file_frame.get("domain") == "clarification"
    and (missing_file_route.get("capabilityPlan") or {}).get("id") == "focused-clarification",
    {"frame": missing_file_frame, "plan": missing_file_route.get("capabilityPlan")},
)
check(
    "absent-local-files-ask-for-path-or-attachment",
    missing_file_result.get("outcome") == "needs-input"
    and "path" in str(missing_file_result.get("answer") or "").lower()
    and "attach" in str(missing_file_result.get("answer") or "").lower(),
    missing_file_result,
)

artifact_word_collision_messages = [
    {
        "role": "user",
        "text": (
            "Compare the red application's face-selection output with our black output. "
            "The red output shows flat faces and contours above the model; inspect the "
            "locally installed applications and find what prevents the desired result."
        ),
    }
]
artifact_word_collision_route = server.route_manager(
    artifact_word_collision_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "artifact-words-do-not-imply-missing-files",
    (artifact_word_collision_route.get("intentFrame") or {}).get("domain") != "clarification"
    and (artifact_word_collision_route.get("capabilityPlan") or {}).get("id")
    != "focused-clarification",
    artifact_word_collision_route,
)

open_result_messages = [
    {
        "role": "user",
        "text": "No change: 6.67 grams in all configurations. Should I keep it open so you can inspect the result?",
    }
]
open_result_route = server.route_manager(
    open_result_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "open-result-inspection-is-not-a-file-path-clarification",
    (open_result_route.get("intentFrame") or {}).get("domain") != "clarification"
    and (open_result_route.get("capabilityPlan") or {}).get("id")
    != "focused-clarification",
    open_result_route,
)
check(
    "focused-needs-input-is-successful-conversation",
    server.successful_conversational_clarification(missing_file_route),
    missing_file_route.get("_capabilityExecution"),
)
missing_file_contract = server.task_contract(missing_file_messages, missing_file_route)
check(
    "focused-clarification-owns-its-task-contract",
    missing_file_contract.get("kind") == "Focused clarification"
    and "source artifact" in " ".join(missing_file_contract.get("requiredProof") or []).lower()
    and "source URL" not in (missing_file_contract.get("requiredProof") or []),
    missing_file_contract,
)
missing_file_policy = server.evidence_ledger_policy(
    missing_file_messages,
    missing_file_route,
    contract=missing_file_contract,
)
check(
    "successful-clarification-needs-no-external-proof",
    missing_file_policy.get("sourceType") == "not-needed"
    and missing_file_policy.get("terminalRequirement") == "none",
    missing_file_policy,
)

resolved_file_messages = [
    {
        "role": "user",
        "text": "Compare /tmp/first.ini and /tmp/second.ini and update /tmp/first.ini, but do not deploy it.",
    }
]
resolved_file_route = server.route_manager(
    resolved_file_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "explicit-file-paths-do-not-trigger-input-clarification",
    (resolved_file_route.get("intentFrame") or {}).get("domain") != "clarification",
    resolved_file_route.get("intentFrame"),
)
parsed_paths = server.local_text_file_names_from_text(
    "Compare /tmp/alpha/first.ini and /tmp/beta/second.ini before making a recommendation."
)
check(
    "multiple-absolute-paths-tokenize-independently",
    "/tmp/alpha/first.ini" in parsed_paths
    and "/tmp/beta/second.ini" in parsed_paths
    and not any("first.ini and /tmp" in value for value in parsed_paths),
    parsed_paths,
)
with tempfile.TemporaryDirectory(prefix="p258-file-pair-") as temp_dir:
    left_path = Path(temp_dir) / "left.ini"
    right_path = Path(temp_dir) / "right.ini"
    left_path.write_text("[device]\nmode = stable\n", encoding="utf-8")
    right_path.write_text("[device]\nmode = revised\n", encoding="utf-8")
    pair_messages = [
        {
            "role": "user",
            "text": f"Compare {left_path} and {right_path} and tell me whether they differ.",
        }
    ]
    pair_route = server.route_manager(
        pair_messages,
        cwd=temp_dir,
        requested_profile="manager",
        web_search="disabled",
    )
    pair_result = server.execute_local_tool_capability(
        pair_messages,
        pair_route,
        cwd=temp_dir,
        webSearch="disabled",
    )
check(
    "two-explicit-local-files-reach-comparison-owner",
    pair_result.get("handled") is True
    and pair_result.get("outcome") == "completed"
    and "left.ini" in str(pair_result.get("answer") or "")
    and "right.ini" in str(pair_result.get("answer") or ""),
    pair_result,
)

typed_missing_route = {
    "intentFrame": {
        "domain": "bounded_artifact_work",
        "missingInfo": ["source artifact", "hardware revision"],
    },
    "capabilityPlan": {
        "id": "bounded-artifact-owner",
        "registered": True,
    },
}
typed_missing_messages = [
    {"role": "user", "text": "Update the current configuration after reading its source files."}
]
check(
    "typed-missing-input-owner-bypasses-generic-referent-guard",
    server.unresolved_referent_preflight_response(typed_missing_messages, typed_missing_route) == {},
    server.material_unresolved_referent(typed_missing_messages, typed_missing_route),
)

migration_messages = [
    {
        "role": "user",
        "text": "Draft a Klipper migration from the existing mainboard to BTT Kraken and BTT EBB42 Gen2, map every pin, and do not install or flash anything. I have not supplied the active config or exact board revisions.",
    }
]
migration_route = server.route_manager(
    migration_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
migration_result = server.execute_local_tool_capability(
    migration_messages,
    migration_route,
    fullMessages=migration_messages,
    cwd=str(ROOT),
    accessLevel="danger-full-access",
    webSearch="disabled",
    snapshot={"ok": False, "url": "read-only://active-config", "error": "source unavailable"},
)
check(
    "typed-artifact-blocker-is-needs-input",
    migration_result.get("handled") is True
    and migration_result.get("outcome") == "needs-input"
    and migration_result.get("returnCode") == 0,
    migration_result,
)
check(
    "typed-needs-input-is-successful-conversation",
    server.successful_conversational_clarification(migration_route),
    migration_route.get("_capabilityExecution"),
)
explicit_missing_result = server.klipper_migration_executor(
    {
        "messages": migration_messages,
        "fullMessages": migration_messages,
        "snapshot": {"ok": True, "files": [{"path": "wrong-printer.cfg"}]},
    }
)
check(
    "explicitly-absent-migration-source-stops-before-discovery",
    explicit_missing_result.get("outcome") == "needs-input"
    and "unknown mainboard" in str(explicit_missing_result.get("answer") or "").lower()
    and "wrong-printer.cfg" not in str(explicit_missing_result),
    explicit_missing_result,
)
check(
    "explicit-missing-migration-answer-survives-last-mile-contract",
    not server.klipper_board_migration_answer_violates_contract(
        explicit_missing_result.get("answer") or "",
        migration_messages,
    ),
    explicit_missing_result.get("answer"),
)

bounded_route = {
    "capabilityPlan": {"id": "bounded-owner", "registered": True},
    "_capabilityExecution": {
        "handled": True,
        "outcome": "bounded",
        "handlerKey": "bounded_owner",
        "error": "",
    },
}
check(
    "bounded-work-is-not-promoted-to-clarification-success",
    not server.successful_conversational_clarification(bounded_route),
    bounded_route,
)

kernel_source = inspect.getsource(intelligence_kernel)
server_source = inspect.getsource(server)
check(
    "repair-is-shared-and-domain-neutral",
    "_CONTEXT_COMPARATIVE_REFERENT_RE" in kernel_source
    and "_missing_local_artifact_inputs" in kernel_source
    and "capability_plan.get(\"registered\") is True" in server_source,
    "shared relationship, missing-input, and typed-owner boundaries are present",
)

failed = [item for item in checks if item["status"] != "pass"]
report = {
    "suite": "p258-contextual-clarification-contract",
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "failures": failed,
    "checks": checks,
    "contentsRecorded": False,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
