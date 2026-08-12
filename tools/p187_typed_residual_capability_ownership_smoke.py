#!/usr/bin/env python3
"""Focused P187 typed ownership, lineage, and fail-closed dispatch regressions."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_registry
import intelligence_kernel
import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


def route(messages, cwd=ROOT):
    return server.route_manager(
        messages,
        cwd=str(cwd),
        requested_profile="manager",
        web_search="disabled",
    )


def literal_domains(path, function_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    values = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "domain"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                values.add(value.value)
    return values


declared_domains = {
    domain for spec in capability_registry.CAPABILITY_SPECS for domain in spec.domains
}
literal_domain_sets = {
    "server.build_intent_frame": literal_domains(ROOT / "server.py", "build_intent_frame"),
    "intelligence_kernel.build_generic_intent_frame": literal_domains(
        ROOT / "intelligence_kernel.py", "build_generic_intent_frame"
    ),
}
unowned = {
    owner: sorted(domains - declared_domains)
    for owner, domains in literal_domain_sets.items()
    if domains - declared_domains
}
check(
    "all-literal-intent-domains-have-typed-owner",
    not unowned,
    {"unowned": unowned, "declaredCount": len(declared_domains)},
)
health = capability_registry.registry_health()
check(
    "registry-health-includes-four-p187-owners",
    health.get("status") == "pass"
    and {
        "printer-job-eta-reasoning",
        "local-app-product-state",
        "decision-metric-design",
        "general-local-action",
    }.issubset({spec.id for spec in capability_registry.CAPABILITY_SPECS}),
    health,
)


eta_prompts = (
    "I currently have a print running on the Qidi Plus 4. Why are the slicer and machine completion times so different?",
    "Why are my slicer and Qidi device-tab completion estimates different?",
    "The slicer said 3 hours, the printer now says 4 hours remaining with 25 percent complete after 55 minutes. Why?",
    "Why did remaining time jump after pause/resume on the current print?",
    "What time will the current Qidi Plus 4 print finish?",
)
eta_routes = [route([{"role": "user", "text": prompt}]) for prompt in eta_prompts]
check(
    "eta-concept-family-is-typed-model-first-without-legacy",
    all(
        (item.get("intentFrame") or {}).get("domain") == "printer_job_eta"
        and (item.get("capabilityPlan") or {}).get("id")
        == "printer-job-eta-reasoning"
        and (item.get("capabilityPlan") or {}).get("executor") == "reasoning-worker"
        and (item.get("kernelDecision") or {}).get("mode") == "model-first"
        and (item.get("kernelDecision") or {}).get("allowLegacyDirectAnswer") is False
        and server.general_direct_knowledge_answer(
            [{"role": "user", "text": prompt}], item, web_search="disabled"
        )
        is None
        for prompt, item in zip(eta_prompts, eta_routes)
    ),
    [
        {
            "prompt": prompt,
            "frame": item.get("intentFrame"),
            "plan": item.get("capabilityPlan"),
        }
        for prompt, item in zip(eta_prompts, eta_routes)
    ],
)

eta_first = [{"role": "user", "text": eta_prompts[0]}]
eta_context = [
    *eta_first,
    {
        "role": "assistant",
        "text": "The slicer and live printer use different clocks; job-specific values would let me separate the cause.",
    },
]
eta_followups = (
    "Slicer 3h; after 55m the printer says 4h remaining at 25%.",
    "Why did it jump after I paused and resumed?",
    "What time will this print actually finish?",
)
eta_follow_routes = [
    route([*eta_context, {"role": "user", "text": prompt}])
    for prompt in eta_followups
]
eta_referential_route = route(
    [
        *eta_first,
        {"role": "assistant", "text": "What changed?"},
        {
            "role": "user",
            "text": "Why did its remaining time jump after pause and resume?",
        },
    ]
)
project_eta_route = route(
    [*eta_context, {"role": "user", "text": "When will Codex CLI UI be finished?"}]
)
check(
    "eta-value-event-and-finish-followups-retain-owner-but-project-eta-leaves",
    all(
        (item.get("intentFrame") or {}).get("domain") == "printer_job_eta"
        and (item.get("intentFrame") or {}).get("contextRelation") == "follow-up"
        and (item.get("capabilityPlan") or {}).get("id")
        == "printer-job-eta-reasoning"
        for item in eta_follow_routes
    )
    and (eta_referential_route.get("intentFrame") or {}).get("domain")
    == "printer_job_eta"
    and (eta_referential_route.get("intentFrame") or {}).get("contextRelation")
    == "follow-up"
    and (project_eta_route.get("intentFrame") or {}).get("domain")
    != "printer_job_eta",
    {
        "followups": [item.get("intentFrame") for item in eta_follow_routes],
        "referential": eta_referential_route.get("intentFrame"),
        "projectDecoy": project_eta_route.get("intentFrame"),
    },
)

bad_eta_route = eta_routes[2]
bad_eta_answer = server.guard_print_eta_discrepancy_answer(
    "The project is on track; check the repo for an exact completion date.",
    [{"role": "user", "text": eta_prompts[2]}],
    bad_eta_route,
)
good_eta_route = eta_routes[1]
good_eta_answer = (
    "The slicer estimate is a G-code/profile prediction, while the machine estimate in the device tab is a live firmware calculation from elapsed progress. "
    "Without the active values this explains the mechanism, not the exact job-specific cause."
)
check(
    "eta-wrong-family-or-author-failure-is-bounded-not-canned-success",
    "mechanism-only boundary" in bad_eta_answer
    and "3 hours" in bad_eta_answer
    and "4 hours remaining" in bad_eta_answer
    and (bad_eta_route.get("_printEtaEvidenceBoundary") or {}).get(
        "jobSpecificDiagnosis"
    )
    is False
    and bad_eta_route.get("_supervisionStatus") == "bounded"
    and bad_eta_route.get("_executionReturnCode") == 1
    and server.has_trusted_typed_bounded_execution_outcome(bad_eta_route)
    and not server.has_trusted_typed_bounded_execution_outcome(
        {
            "_supervisionStatus": "bounded",
            "_executionReturnCode": 1,
            "capabilityPlan": {
                "id": "conversation-reasoning",
                "registered": True,
            },
            "_printEtaEvidenceBoundary": bad_eta_route.get(
                "_printEtaEvidenceBoundary"
            ),
        }
    )
    and server.guard_print_eta_discrepancy_answer(
        good_eta_answer,
        [{"role": "user", "text": eta_prompts[1]}],
        good_eta_route,
    )
    == good_eta_answer
    and not good_eta_route.get("_printEtaEvidenceBoundary"),
    {
        "bounded": bad_eta_route.get("_printEtaEvidenceBoundary"),
        "answer": bad_eta_answer,
    },
)


model_health_imperative = [
    {
        "role": "user",
        "text": "In Model Health for the Bambu H2D, show progress percent and ETA for the current print.",
    }
]
imperative_route = route(model_health_imperative)
imperative_frame = imperative_route.get("intentFrame") or {}
imperative_operations = set((imperative_frame.get("operationPlan") or {}).get("allowedNow") or [])
check(
    "model-health-imperative-retains-implementation-and-test-authority",
    imperative_frame.get("domain") == "local_product_action"
    and imperative_frame.get("targetSurface") == "codex_cli_ui.model_health"
    and imperative_frame.get("actionType") == "modify_app_status_surface"
    and {"inspect", "edit", "test"}.issubset(imperative_operations)
    and not (imperative_frame.get("operationPlan") or {}).get("readOnly")
    and (imperative_route.get("capabilityPlan") or {}).get("id")
    == "local-product-action",
    imperative_frame,
)

explain_messages = [
    {
        "role": "user",
        "text": "Why does Bambu H2D show offline in Model Health even though it is printing?",
    }
]
explain_route = route(explain_messages)
explain_frame = explain_route.get("intentFrame") or {}
explain_operations = set((explain_frame.get("operationPlan") or {}).get("allowedNow") or [])
original_printer_health = server.printer_health
try:
    server.printer_health = lambda: {
        "summary": {"total": 1, "online": 0, "offline": 1, "active": 0},
        "printers": [
            {
                "name": "Bambu H2D",
                "kind": "bambu",
                "service": "Bambu status",
                "online": False,
                "state": "offline",
                "telemetry": {},
            }
        ],
    }
    explain_snapshot = server.local_product_state_evidence_snapshot(
        explain_messages, explain_route
    )
    explain_result = server.local_product_state_explanation_preflight_response(
        explain_messages, explain_route
    )
finally:
    server.printer_health = original_printer_health
check(
    "model-health-explanation-is-read-only-source-and-runtime-bound",
    explain_frame.get("domain") == "local_product_action"
    and explain_frame.get("actionType") == "inspect_explain_local_state"
    and explain_operations.issubset({"inspect", "explain"})
    and not explain_operations.intersection({"change", "edit", "fix", "write"})
    and explain_snapshot.get("kind") == "model-health-receipt"
    and explain_snapshot.get("renderContract")
    == "offline-short-circuit-otherwise-state-progress-eta"
    and len(explain_snapshot.get("sourceBindings") or []) >= 3
    and all(
        item.get("sourceSha256")
        and item.get("contextSha256")
        and item.get("contentsRecorded") is False
        for item in explain_snapshot.get("sourceBindings") or []
    )
    and explain_result.get("handled") is True
    and "Ping alone cannot prove printing progress or ETA" in explain_result.get(
        "answer", ""
    )
    and "did not change source, printer state, inventory, or the live machine"
    in explain_result.get("answer", ""),
    {"frame": explain_frame, "snapshot": explain_snapshot, "result": explain_result},
)

model_health_context = [
    *model_health_imperative,
    {
        "role": "assistant",
        "text": "I can inspect the current status source and make the requested local UI change with focused verification.",
    },
]
model_followups = {
    "proceed": "Go ahead and make the change, then test it.",
    "hold": "Use the existing MQTT telemetry, but do not change anything yet.",
    "explain": "First explain why it is shown offline.",
    "source": "The data should come from the existing Bambu status feed.",
}
model_routes = {
    name: route([*model_health_context, {"role": "user", "text": prompt}])
    for name, prompt in model_followups.items()
}
proceed_plan = (model_routes["proceed"].get("intentFrame") or {}).get("operationPlan") or {}
hold_plan = (model_routes["hold"].get("intentFrame") or {}).get("operationPlan") or {}
source_plan = (model_routes["source"].get("intentFrame") or {}).get("operationPlan") or {}
petcf_route = route(
    [
        *model_health_context,
        {
            "role": "user",
            "text": "PET-CF became brittle after annealing; what mechanisms should I check?",
        },
    ]
)
check(
    "model-health-lineage-preserves-proceed-hold-explain-and-source-semantics",
    all(
        (item.get("intentFrame") or {}).get("domain") == "local_product_action"
        and (item.get("intentFrame") or {}).get("targetSurface")
        == "codex_cli_ui.model_health"
        and (item.get("capabilityPlan") or {}).get("id") == "local-product-action"
        for item in model_routes.values()
    )
    and {"change", "test"}.issubset(set(proceed_plan.get("allowedNow") or []))
    and "change" in set(hold_plan.get("prohibited") or [])
    and hold_plan.get("readOnly") is True
    and set(
        ((model_routes["explain"].get("intentFrame") or {}).get("operationPlan") or {}).get(
            "allowedNow"
        )
        or []
    ).issubset({"inspect", "explain"})
    and {"edit", "test"}.issubset(set(source_plan.get("allowedNow") or []))
    and (petcf_route.get("intentFrame") or {}).get("targetSurface")
    != "codex_cli_ui.model_health",
    {
        "routes": {name: item.get("intentFrame") for name, item in model_routes.items()},
        "newTopic": petcf_route.get("intentFrame"),
    },
)

clarification_messages = [
    *model_health_imperative,
    {
        "role": "assistant",
        "text": "Which telemetry source should I use for the Bambu progress and ETA?",
    },
    {"role": "user", "text": "The existing Bambu status feed."},
]
clarification_route = route(clarification_messages)
clarification_frame = clarification_route.get("intentFrame") or {}
held_clarification_route = route(
    [
        *model_health_imperative,
        {
            "role": "assistant",
            "text": "Which telemetry source should I use for the Bambu progress and ETA?",
        },
        {
            "role": "user",
            "text": "Use existing MQTT telemetry, but do not change anything yet.",
        },
    ]
)
held_clarification_frame = held_clarification_route.get("intentFrame") or {}
check(
    "model-health-focused-clarification-consumes-supplied-source",
    clarification_frame.get("domain") == "local_product_action"
    and not clarification_frame.get("missingInfo")
    and any(
        "existing Bambu status feed" in str(item)
        for item in clarification_frame.get("knownConstraints") or []
    )
    and not (clarification_route.get("objectivePlan") or {}).get("missingInputs")
    and not held_clarification_frame.get("missingInfo")
    and any(
        "mqtt telemetry" in str(item).lower()
        for item in held_clarification_frame.get("knownConstraints") or []
    )
    and "change"
    in set(
        (held_clarification_frame.get("operationPlan") or {}).get("prohibited")
        or []
    )
    and (held_clarification_frame.get("operationPlan") or {}).get("readOnly") is True,
    {
        "frame": clarification_frame,
        "objective": clarification_route.get("objectivePlan"),
        "heldFrame": held_clarification_frame,
    },
)


with tempfile.TemporaryDirectory(prefix="p187-general-action-") as temp_dir:
    requested_cwd = Path(temp_dir).resolve()
    run_messages = [{"role": "user", "text": "Run the package tests and report the failures."}]
    run_route = route(run_messages, cwd=requested_cwd)
    effective_cwd = server.local_action_effective_cwd(run_route, str(requested_cwd))
install_route = route(
    [{"role": "user", "text": "Install the approved local package."}]
)
delete_route = route(
    [
        {
            "role": "user",
            "text": "Delete the generated scratch file after verifying its path.",
        }
    ]
)
live_machine_route = route(
    [{"role": "user", "text": "Update the Qidi Plus 4 firmware and restart it."}]
)
check(
    "general-action-owner-keeps-requested-cwd-and-operation-policy-without-live-machine-broadening",
    (run_route.get("intentFrame") or {}).get("domain") == "general_action"
    and (run_route.get("capabilityPlan") or {}).get("id") == "general-local-action"
    and (run_route.get("kernelDecision") or {}).get("allowLegacyDirectAnswer") is False
    and Path(effective_cwd).resolve() == requested_cwd
    and set(((run_route.get("intentFrame") or {}).get("operationPlan") or {}).get("allowedNow") or [])
    == {"run"}
    and (install_route.get("capabilityPlan") or {}).get("id") == "general-local-action"
    and set(((install_route.get("intentFrame") or {}).get("operationPlan") or {}).get("allowedNow") or [])
    == {"install"}
    and (delete_route.get("capabilityPlan") or {}).get("id") == "general-local-action"
    and set(((delete_route.get("intentFrame") or {}).get("operationPlan") or {}).get("allowedNow") or [])
    == {"delete"}
    and (live_machine_route.get("capabilityPlan") or {}).get("id")
    != "general-local-action",
    {
        "run": run_route,
        "install": install_route.get("intentFrame"),
        "delete": delete_route.get("intentFrame"),
        "liveMachineDecoy": live_machine_route,
    },
)


metric_prompt = (
    "Our failed-job count fell, but job lengths and work mix changed. "
    "Design a metric that tells us whether reliability actually improved."
)
metric_messages = [{"role": "user", "text": metric_prompt}]
metric_route = route(metric_messages)
metric_frame = metric_route.get("intentFrame") or {}
metric_policy = server.conversation_only_reasoning_policy(
    metric_messages, metric_route
)
metric_direct = server.general_direct_knowledge_answer(
    metric_messages, metric_route, web_search="disabled"
)
metric_followup_messages = [
    *metric_messages,
    {
        "role": "assistant",
        "text": "Use like-for-like attempt probability and keep exposure and consequence separate.",
    },
    {
        "role": "user",
        "text": "I also have machine-hours and kilograms printed. Which denominator should drive each decision?",
    },
]
metric_followup_route = route(metric_followup_messages)
metric_decoys = (
    "What does denominator mean?",
    "Calculate 12 failures out of 300 jobs.",
    "Is the Qidi printer online, and what percent complete is the current print?",
    "Should I accept liability for this contract without an attorney reviewing it?",
)
metric_decoy_routes = [route([{"role": "user", "text": prompt}]) for prompt in metric_decoys]
check(
    "decision-metric-is-typed-conversation-only-model-first-without-template-bypass",
    metric_frame.get("domain") == "decision_metric_design"
    and (metric_route.get("capabilityPlan") or {}).get("id")
    == "decision-metric-design"
    and (metric_route.get("kernelDecision") or {}).get("allowLegacyDirectAnswer")
    is False
    and metric_policy.get("eligible") is True
    and metric_policy.get("accessLevel") == "conversation-context"
    and metric_direct is None
    and (metric_followup_route.get("intentFrame") or {}).get("domain")
    == "decision_metric_design"
    and (metric_followup_route.get("intentFrame") or {}).get("contextRelation")
    == "follow-up"
    and all(
        (item.get("intentFrame") or {}).get("domain") != "decision_metric_design"
        for item in metric_decoy_routes
    )
    and server.decision_aligned_metric_reasoning_p116_synthetic_check(),
    {
        "frame": metric_frame,
        "plan": metric_route.get("capabilityPlan"),
        "policy": metric_policy,
        "followup": metric_followup_route.get("intentFrame"),
        "decoys": [item.get("intentFrame") for item in metric_decoy_routes],
    },
)


failures = [item for item in checks if item["status"] != "pass"]
report = {
    "suite": "p187-typed-residual-capability-ownership",
    "status": "pass" if not failures else "fail",
    "checkCount": len(checks),
    "passedCount": len(checks) - len(failures),
    "failedCount": len(failures),
    "checks": checks,
    "failures": failures,
}
print(json.dumps(report, indent=2, default=str))
raise SystemExit(0 if not failures else 1)
