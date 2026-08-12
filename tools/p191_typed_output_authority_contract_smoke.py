#!/usr/bin/env python3
"""Focused P191 typed answer/action/artifact output-authority contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


def route(prompt):
    messages = [{"role": "user", "text": prompt}]
    return route_messages(messages)


def route_messages(messages):
    result = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    result["_messages"] = messages
    result["_contract"] = server.task_contract(messages, result)
    return result


def frame(result):
    return result.get("intentFrame") or {}


def output(result):
    return frame(result).get("outputContract") or {}


def capability(result):
    return result.get("capabilityPlan") or {}


def contract(result):
    return result.get("_contract") or {}


def allowed(result):
    return set((frame(result).get("operationPlan") or {}).get("allowedNow") or [])


def discussed(result):
    return set((frame(result).get("operationPlan") or {}).get("discussed") or [])


def deferred(result):
    return {
        str(item.get("operation") or "") if isinstance(item, dict) else str(item)
        for item in ((frame(result).get("operationPlan") or {}).get("deferred") or [])
    }


answer_prompts = (
    "What wall thickness should I use for a 3D-printed CPAP cooling duct? Give the recommendation, reason, and practical limits.",
    "What thickness should a CNC spoilboard use? Give the recommendation, reason, and practical limits.",
    "Which alloy should I use for a motor mount? Give the recommendation, reason, and practical limits.",
    "Do not create a CAD file; tell me what wall thickness the duct should use.",
    "Draft an explanation of why bearing preload matters.",
    "Build a recommendation for CNC spoilboard thickness.",
    "What would it take to create a bearing cartridge drawing?",
    "Can you explain how to export a STEP file?",
    "Should I export this as STEP or STL?",
    "Give me a report-style answer comparing these options, not a PDF.",
    "Create a mental model for PID tuning.",
    "Build my understanding of bearing preload.",
    "What is the difference between a STEP CAD model and an STL mesh?",
    "Is a STEP CAD model better than an STL mesh for later editing?",
    "Does a solid CAD model preserve more design intent than an STL mesh?",
    "I have a STEP CAD model and an STL mesh. Compare them in plain language.",
)
answer_routes = [route(prompt) for prompt in answer_prompts]
check(
    "answer-shape-and-advisory-turns-remain-model-first-conversation",
    all(
        output(result).get("mode") == "conversation-answer"
        and capability(result).get("executor") == "reasoning-worker"
        and capability(result).get("id") in {"conversation-reasoning", "expert-comparison"}
        and contract(result).get("hardGate") is False
        and not server.route_owns_cad_artifact_contract(result["_messages"], result)
        for result in answer_routes
    ),
    [
        {
            "prompt": prompt,
            "frame": frame(result),
            "capability": capability(result),
            "contract": contract(result),
        }
        for prompt, result in zip(answer_prompts, answer_routes)
    ],
)


direct_cad_model_prompts = (
    "Model this bracket in CAD and export a STEP file.",
    "Please model this bracket in CAD and export a STEP file.",
    "Can you model this bracket in CAD and export a STEP file?",
    "I want you to model this bracket in CAD and export a STEP file.",
)
direct_cad_model_routes = [route(prompt) for prompt in direct_cad_model_prompts]
check(
    "direct-model-verb-requests-retain-cad-artifact-authority",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("artifactClass") == "cad"
        and output(result).get("requestedFormat") == "step"
        and frame(result).get("domain") == "cad_artifact_work"
        and capability(result).get("id") == "local-cad-artifact"
        and contract(result).get("hardGate") is True
        for result in direct_cad_model_routes
    ),
    [
        {"prompt": prompt, "frame": frame(result), "capability": capability(result)}
        for prompt, result in zip(direct_cad_model_prompts, direct_cad_model_routes)
    ],
)


material_comparison = route(
    "Compare aluminum and G10/FR4 for an electrically insulating mounting plate. Which is the better default?"
)
material_wrong_gate = server.task_contract_gate(
    material_comparison["_messages"],
    material_comparison,
    "Use a 72 V controller for a kart and size battery current from motor power.",
    web_search="disabled",
)
material_valid_gate = server.task_contract_gate(
    material_comparison["_messages"],
    material_comparison,
    (
        "G10/FR4 is the better default for an electrically insulating mounting plate because it avoids "
        "a conductive mounting path. Choose aluminum instead when stiffness or heat spreading controls "
        "the design and a separately verified isolation barrier is available."
    ),
    web_search="disabled",
)
ordinary_advisory = route(
    "Would a cast aluminum tooling plate remain flat enough to use as a 180 C heated bed?"
)
ordinary_advisory_gate = server.task_contract_gate(
    ordinary_advisory["_messages"],
    ordinary_advisory,
    (
        "It can be suitable conditionally, but alloy condition, thickness, support spacing, and the hot "
        "temperature gradient control flatness. Verify the exact plate with a thermal-cycle flatness test "
        "before treating room-temperature flatness as proof."
    ),
    web_search="disabled",
)
check(
    "typed-comparison-owners-enforce-named-options-across-semantic-contracts",
    frame(material_comparison).get("actionType") == "compare_material_properties"
    and {
        str(item.get("name") or "")
        for item in frame(material_comparison).get("objectRefs") or []
        if isinstance(item, dict)
    }
    >= {"aluminum", "G10/FR4"}
    and material_wrong_gate.get("status") == "block"
    and material_valid_gate.get("status") != "block"
    and ordinary_advisory_gate.get("status") != "block",
    {
        "comparisonFrame": frame(material_comparison),
        "wrongGate": material_wrong_gate,
        "validGate": material_valid_gate,
        "ordinaryAdvisoryGate": ordinary_advisory_gate,
    },
)


engineering_comparison_prompts = (
    "Compare a belt drive and ballscrew for a vertical Z axis. Which is the better default?",
    "Compare a Jetson Orin Nano and an RTX mini PC for local inference across 10 printers. Which is the better default?",
)
engineering_comparisons = [route(prompt) for prompt in engineering_comparison_prompts]
wrong_domain_draft = "Use a 72 V controller for a kart and size battery current from motor power."
engineering_wrong_gates = [
    server.task_contract_gate(
        result["_messages"],
        result,
        wrong_domain_draft,
        web_search="disabled",
    )
    for result in engineering_comparisons
]
single_object_advisory = route(
    "Would a ballscrew Z axis remain reliable in a dusty enclosure, and what should I validate?"
)
single_object_gate = server.task_contract_gate(
    single_object_advisory["_messages"],
    single_object_advisory,
    (
        "It can be reliable conditionally, but dust exclusion, lubrication compatibility, alignment, and duty cycle "
        "control the result. Validate contamination ingress, running torque, backlash, and temperature under the "
        "representative cycle before treating the architecture as proven."
    ),
    web_search="disabled",
)
check(
    "comparison-option-receipts-outrank-generic-engineering-judgment-labels",
    all(
        len(
            [
                item
                for item in frame(result).get("objectRefs") or []
                if isinstance(item, dict) and item.get("type") == "comparison-option"
            ]
        )
        >= 2
        for result in engineering_comparisons
    )
    and all(gate.get("status") == "block" for gate in engineering_wrong_gates)
    and single_object_gate.get("status") != "block",
    {
        "comparisons": [frame(result) for result in engineering_comparisons],
        "wrongGates": engineering_wrong_gates,
        "singleObjectGate": single_object_gate,
    },
)


reversal_comparison = route(
    "Compare a belt drive and ballscrew for a vertical Z axis. Which is the better default, and what could reverse the choice?"
)
reversal_variants = (
    "A belt drive can be preferable instead when travel speed, long stroke, and low moving mass outweigh holding stiffness.",
    "A belt drive becomes the better choice when travel speed and low moving mass outweigh holding stiffness.",
    "A belt drive is the better choice when travel speed and low moving mass outweigh holding stiffness.",
    "A belt drive is better when travel speed and low moving mass outweigh holding stiffness.",
    "A belt drive wins if travel speed and low moving mass outweigh holding stiffness.",
    "The choice flips to a belt drive when travel speed and low moving mass outweigh holding stiffness.",
    "Use the belt drive when travel speed and low moving mass outweigh holding stiffness.",
    "Use the ballscrew unless long travel speed controls the design, in which case use the belt drive.",
)
reversal_gates = [
    server.task_contract_gate(
        reversal_comparison["_messages"],
        reversal_comparison,
        (
            "Use the ballscrew as the default vertical Z-axis drive because its holding stiffness and positioning "
            "repeatability suit the load. "
            + variant
        ),
        web_search="disabled",
    )
    for variant in reversal_variants
]
missing_reversal_gate = server.task_contract_gate(
    reversal_comparison["_messages"],
    reversal_comparison,
    (
        "Use the ballscrew as the default vertical Z-axis drive because its holding stiffness and positioning "
        "repeatability suit the load. A belt drive is the better choice."
    ),
    web_search="disabled",
)
check(
    "natural-reversal-language-carries-a-decision-changing-condition",
    all(gate.get("status") != "block" for gate in reversal_gates)
    and missing_reversal_gate.get("status") == "block"
    and "Reversal conditions"
    in {item.get("label") for item in missing_reversal_gate.get("failed") or []},
    {
        "valid": reversal_gates,
        "missing": missing_reversal_gate,
    },
)


cad_prompts = (
    "Create a CNC spoilboard drilling template and save the DXF.",
    "Draft a bearing cartridge drawing with dimensions.",
    "Design a CPAP cooling duct and export a STEP file.",
    "Model a motor mount in CAD and export a STEP file.",
)
cad_routes = [route(prompt) for prompt in cad_prompts]
check(
    "explicit-cad-action-object-pairs-own-cad-artifact-execution",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("artifactClass") == "cad"
        and output(result).get("operation") in {"create", "draft", "record"}
        and frame(result).get("domain") == "cad_artifact_work"
        and capability(result).get("id") == "local-cad-artifact"
        and capability(result).get("executor") == "local-tool"
        and contract(result).get("kind") == "CAD/design deliverable"
        and contract(result).get("hardGate") is True
        and server.route_owns_cad_artifact_contract(result["_messages"], result)
        for result in cad_routes
    ),
    [frame(result) for result in cad_routes],
)


revision_artifact_prompts = (
    "Can you regenerate this .f3z file so it retains the constraints?",
    "Can you rebuild this STEP file and save it as .f3z?",
)
revision_artifact_routes = [route(prompt) for prompt in revision_artifact_prompts]
revision_advice = route("Can you explain how to regenerate a constrained .f3z file?")
revision_prohibited = route("Do not regenerate this .f3z file yet; explain the blocker.")


def fusion_native_boundary(result):
    current_frame = frame(result)
    return bool(
        current_frame.get("domain") == "bounded_specialist_capability"
        and current_frame.get("originalDomain") == "cad_artifact_work"
        and current_frame.get("specialistOwner") == "fusion-reference-boundary"
        and capability(result).get("id") == "bounded-specialist-capability"
        and capability(result).get("executor") == "deterministic"
        and contract(result).get("kind") == "CAD/design deliverable"
        and contract(result).get("hardGate") is True
    )


check(
    "regenerate-and-rebuild-bind-artifacts-without-promoting-advice-or-holds",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("artifactClass") == "cad"
        and output(result).get("operation") == "create"
        and (
            (
                frame(result).get("domain") == "cad_artifact_work"
                and capability(result).get("id") == "local-cad-artifact"
            )
            or fusion_native_boundary(result)
        )
        for result in revision_artifact_routes
    )
    and output(revision_advice).get("mode") == "conversation-answer"
    and "create" not in allowed(revision_advice)
    and "create" in discussed(revision_advice)
    and output(revision_prohibited).get("mode") == "conversation-answer"
    and "create" not in allowed(revision_prohibited)
    and "create" in set(
        (frame(revision_prohibited).get("operationPlan") or {}).get("prohibited") or []
    ),
    {
        "actions": [frame(result) for result in revision_artifact_routes],
        "advice": frame(revision_advice),
        "prohibited": frame(revision_prohibited),
    },
)


generic_artifact_prompts = (
    "Create a CSV file with the supplied rows and save it as results.csv.",
    "Generate a workbook and save it as XLSX.",
    "Write a Markdown file with the checklist.",
    "Create a PDF report and save it locally.",
    "Make a PNG image and save it locally.",
    "Build a Python script in /tmp.",
    "Prepare the test plan as a DOCX document.",
    "Draft a recommendation report and save it as PDF.",
    "Write a report-style answer to a Markdown file.",
    "Analyze the design. The output should be a Markdown report.",
)
generic_artifact_routes = [route(prompt) for prompt in generic_artifact_prompts]
check(
    "generic-saved-artifacts-use-proof-bearing-local-agent-not-read-handler",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("artifactClass") == "document"
        and output(result).get("operation") in {"create", "draft", "record"}
        and frame(result).get("domain") == "general_action"
        and capability(result).get("id") == "general-local-action"
        and capability(result).get("executor") == "local-agent"
        and contract(result).get("kind") == "Typed local artifact"
        and contract(result).get("hardGate") is True
        and bool(allowed(result) & {"create", "draft", "record"})
        for result in generic_artifact_routes
    ),
    [
        {"frame": frame(result), "capability": capability(result), "contract": contract(result)}
        for result in generic_artifact_routes
    ],
)


diagram_prompts = (
    "Draft a wiring diagram and save it as SVG.",
    "Design a block diagram and save it as SVG.",
)
diagram_routes = [route(prompt) for prompt in diagram_prompts]
check(
    "diagram-verb-synonyms-preserve-engineering-diagram-owner",
    all(
        output(result).get("artifactClass") == "diagram"
        and frame(result).get("domain") == "engineering_diagram_work"
        and capability(result).get("id") == "local-engineering-diagram-artifact"
        and contract(result).get("kind") == "Engineering diagram"
        and contract(result).get("hardGate") is True
        and "clickable diagram/report files" in (contract(result).get("requiredProof") or [])
        and not server.route_owns_cad_artifact_contract(result["_messages"], result)
        for result in diagram_routes
    ),
    [frame(result) for result in diagram_routes],
)


inline_prompts = (
    "Create a CSV table here in the answer; do not save a file.",
    "Create a JSON example in your response.",
    "Generate an SVG snippet inline in chat.",
    "Write the report here, not as a file.",
    "Create the CSV content in the answer, do not save it.",
)
inline_routes = [route(prompt) for prompt in inline_prompts]
check(
    "explicit-conversation-destination-suppresses-file-execution-authority",
    all(
        output(result).get("mode") == "conversation-answer"
        and output(result).get("binding") == "explicit-conversation-destination"
        and frame(result).get("domain") in {"conversation", "knowledge_question"}
        and capability(result).get("executor") == "reasoning-worker"
        and not (allowed(result) & {"create", "draft", "record"})
        and contract(result).get("hardGate") is False
        for result in inline_routes
    ),
    [frame(result) for result in inline_routes],
)


mixed_route = route(
    "Create a CSV file locally and also show a preview in the answer."
)
check(
    "saved-artifact-plus-inline-preview-retains-local-artifact-owner",
    output(mixed_route).get("mode") == "local-artifact"
    and output(mixed_route).get("requestedFormat") == "csv"
    and capability(mixed_route).get("id") == "general-local-action"
    and {"create", "record"}.issubset(allowed(mixed_route)),
    frame(mixed_route),
)


desired_prompts = (
    "I need a CSV file with the inventory totals.",
    "I want a PDF report.",
    "The deliverable should be a STEP file.",
    "Please give me a downloadable spreadsheet.",
    "Can I get a Markdown checklist saved locally?",
    "I would like an SVG wiring diagram.",
    "My expected output is a JSON file and a short README.",
    "Return the answer as a CSV file.",
)
desired_routes = [route(prompt) for prompt in desired_prompts]
check(
    "natural-desired-result-grammar-binds-explicit-file-output",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("operation") in {"create", "draft", "record"}
        and contract(result).get("hardGate") is True
        for result in desired_routes
    ),
    [frame(result) for result in desired_routes],
)


bare_result_prompts = (
    "I want a report.",
    "I want a recommendation.",
    "Describe what a wiring diagram should show.",
)
bare_result_routes = [route(prompt) for prompt in bare_result_prompts]
check(
    "bare-answer-nouns-do-not-imply-saved-artifact",
    all(
        output(result).get("mode") == "conversation-answer"
        and capability(result).get("executor") == "reasoning-worker"
        and contract(result).get("hardGate") is False
        for result in bare_result_routes
    ),
    [frame(result) for result in bare_result_routes],
)


clarified_artifact_messages = (
    [
        {"role": "user", "text": "Create an inventory report with these totals."},
        {"role": "assistant", "text": "Which format should I save it in?"},
        {"role": "user", "text": "CSV please."},
    ],
    [
        {"role": "user", "text": "I need a report comparing options."},
        {"role": "assistant", "text": "Do you want it in chat or as a saved file?"},
        {"role": "user", "text": "A PDF file."},
    ],
)
clarified_artifact_routes = [
    route_messages(messages) for messages in clarified_artifact_messages
]
check(
    "focused-format-clarifications-retain-artifact-ownership",
    all(
        output(result).get("mode") == "local-artifact"
        and output(result).get("requestedFormat") in {"csv", "pdf"}
        and output(result).get("operation") in {"create", "draft", "record"}
        and frame(result).get("contextRelation") == "follow-up"
        and capability(result).get("executor") in {"local-agent", "local-tool"}
        and contract(result).get("hardGate") is True
        for result in clarified_artifact_routes
    ),
    [frame(result) for result in clarified_artifact_routes],
)


held_draft = route_messages(
    [
        {"role": "user", "text": "Create an inventory report and save it as CSV."},
        {"role": "assistant", "text": "I can create that."},
        {"role": "user", "text": "Do not save it yet; show me the draft here first."},
    ]
)
check(
    "conversation-preview-hold-removes-current-write-authority",
    output(held_draft).get("mode") == "conversation-answer"
    and output(held_draft).get("binding") == "explicit-conversation-destination"
    and capability(held_draft).get("executor") == "reasoning-worker"
    and not (allowed(held_draft) & {"create", "draft", "record"})
    and "record" in set(
        (frame(held_draft).get("operationPlan") or {}).get("prohibited") or []
    )
    and contract(held_draft).get("hardGate") is False,
    frame(held_draft),
)


advisory_operation_prompts = (
    "Compare event sourcing and CRUD, state when you would reverse it, and name the first test you would run.",
    "Tell me which benchmark I should run first.",
    "What command should I run to check disk space?",
    "What package should I install for PDF parsing?",
    "Which test would you run first?",
    "Explain how to restart the local service safely.",
    "Tell me what cache file I should delete.",
    "A production line sends every part through two independent vision inspectors. What combined detection rate do they produce, and what assumption could make it optimistic?",
)
advisory_operation_routes = [route(prompt) for prompt in advisory_operation_prompts]
direct_operation_routes = [
    route("Run the focused unit test now."),
    route("Please test the parser."),
    route("Install numpy in the project environment now."),
    route("Run the disk-space check and report the output."),
]
check(
    "advisory-operation-references-never-grant-execution-authority",
    all(
        output(result).get("mode") == "conversation-answer"
        and not (
            allowed(result)
            & {"create", "draft", "record", "edit", "change", "fix", "install", "restart", "delete", "run", "test"}
        )
        and (
            {"run", "test", "inspect", "install", "restart", "delete", "create"}.intersection(
            set((frame(result).get("operationPlan") or {}).get("discussed") or [])
            )
            or not (frame(result).get("operationPlan") or {}).get("operations")
        )
        and (frame(result).get("operationPlan") or {}).get("readOnly", True) is True
        for result in advisory_operation_routes
    )
    and all(
        output(result).get("mode") == "local-action"
        and bool(allowed(result) & {"run", "test", "install", "inspect"})
        and capability(result).get("id") == "general-local-action"
        and capability(result).get("executor") == "local-agent"
        and contract(result).get("kind") == "Typed local action"
        and contract(result).get("hardGate") is True
        for result in direct_operation_routes
    ),
    {
        "advisory": [frame(result) for result in advisory_operation_routes],
        "direct": [frame(result) for result in direct_operation_routes],
    },
)


printer_advice_routes = [
    route("Should I cancel the current print?"),
    route("Explain how to cancel the print safely."),
]
direct_print_cancel = route("Cancel the current print now.")
latency_false_positives = (
    "What steering geometry should I use on a kart?",
    "How do I steer a boat safely?",
    "How do I cancel an eBay order?",
    "How do I cancel a subscription?",
    "How do I cancel a download?",
    "What speed for slow-tool steel machining?",
)
latency_positive_controls = (
    "How should cancellation work in the Codex UI during a slow run?",
    "Show live progress for the active Codex task.",
)
check(
    "printer-advice-retains-typed-read-only-authority-without-latency-theft",
    all(
        output(result).get("mode") == "conversation-answer"
        and "cancel" in discussed(result)
        and "cancel" not in allowed(result)
        and (frame(result).get("operationPlan") or {}).get("readOnly") is True
        and capability(result).get("executor") == "reasoning-worker"
        and capability(result).get("id") != "bounded-specialist-capability"
        and contract(result).get("kind") != "Research"
        and "latency-progress" not in (result.get("matched") or [])
        and not server.material_unresolved_referent(result["_messages"], result)
        for result in printer_advice_routes
    )
    and frame(direct_print_cancel).get("domain") == "live_device_action"
    and capability(direct_print_cancel).get("id") == "live-device-authority"
    and "cancel" in deferred(direct_print_cancel)
    and all(
        not server.is_latency_progress_question([{"role": "user", "text": prompt}])
        for prompt in latency_false_positives
    )
    and all(
        server.is_latency_progress_question([{"role": "user", "text": prompt}])
        for prompt in latency_positive_controls
    ),
    {
        "advice": [
            {
                "frame": frame(result),
                "capability": capability(result),
                "contract": contract(result),
                "matched": result.get("matched"),
            }
            for result in printer_advice_routes
        ],
        "direct": {
            "frame": frame(direct_print_cancel),
            "capability": capability(direct_print_cancel),
        },
    },
)


check(
    "completion-claims-require-a-bound-first-person-verb-phrase",
    not server.answer_operation_completion_claim(
        "I read the local verification summary from the app's saved receipts.",
        "create",
    )
    and bool(server.answer_operation_completion_claim("I saved the report.", "create"))
    and bool(server.answer_operation_completion_claim("I've successfully created it.", "create"))
    and bool(
        server.answer_operation_completion_claim(
            "I researched the listings, purchased one, and contacted the seller.",
            "buy",
        )
    )
    and not server.answer_operation_completion_claim("I have not saved the report.", "create")
    and not server.answer_operation_completion_claim("I will save the report later.", "create"),
)


payload = {
    "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
    "checkCount": len(checks),
    "passed": sum(item["status"] == "pass" for item in checks),
    "failed": sum(item["status"] == "fail" for item in checks),
    "checks": checks,
}
print(json.dumps(payload, indent=2, sort_keys=True))
raise SystemExit(0 if payload["status"] == "pass" else 1)
