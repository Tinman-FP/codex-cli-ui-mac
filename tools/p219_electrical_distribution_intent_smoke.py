#!/usr/bin/env python3
"""P219 regressions for complete electrical distribution/protection reasoning."""

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


def routed(prompt_or_messages):
    messages = (
        prompt_or_messages
        if isinstance(prompt_or_messages, list)
        else [{"role": "user", "text": prompt_or_messages}]
    )
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    return messages, route, route.get("intentFrame") or {}


baseline_prompt = (
    "I am designing a 48 V battery-backed DC power system for a workshop. "
    "It will feed a 5 kW inverter, and the main loads are a 3 kW spindle and "
    "a 2 kW air compressor. I was planning to size the battery, BMS, fuse, "
    "and cables from the sum of the nameplate power. Is that enough, or what "
    "failure modes am I missing? I care more about avoiding nuisance trips "
    "and fire risk than minimizing cost."
)
baseline_messages, baseline_route, baseline_frame = routed(baseline_prompt)
baseline_contract = server.task_contract(baseline_messages, baseline_route)

check(
    "complete-distribution-question-is-recognized-without-motor-noun",
    server.is_electrical_distribution_protection_question(baseline_messages)
    and server.is_engineering_advisory_question(baseline_messages)
    and not server.is_engineering_power_conversion_question(baseline_messages),
    {
        "electricalDistribution": server.is_electrical_distribution_protection_question(
            baseline_messages
        ),
        "engineeringAdvisory": server.is_engineering_advisory_question(
            baseline_messages
        ),
        "powerConversion": server.is_engineering_power_conversion_question(
            baseline_messages
        ),
    },
)
check(
    "complete-distribution-question-has-power-system-ownership",
    baseline_frame.get("domain") == "engineering_advisory"
    and baseline_frame.get("advisoryDomain") == "power_electrical"
    and baseline_frame.get("reasoningArchetype")
    == "electrical_distribution_protection"
    and baseline_frame.get("actionType")
    == "evaluate_electrical_distribution_protection"
    and baseline_route.get("capabilityPlan", {}).get("id")
    == "engineering-advisory"
    and baseline_route.get("capabilityPlan", {}).get("executor")
    == "reasoning-worker"
    and baseline_route.get("objectivePlan", {}).get("objectiveType")
    == "engineering-advisory",
    {
        "intentFrame": baseline_frame,
        "capabilityPlan": baseline_route.get("capabilityPlan"),
        "objectivePlan": baseline_route.get("objectivePlan"),
    },
)
check(
    "complete-distribution-contract-rejects-horsepower-and-nameplate-shortcuts",
    baseline_contract.get("kind")
    == "Electrical distribution and protection design"
    and baseline_contract.get("hardGate") is True
    and "bounded source-current calculation"
    in (baseline_contract.get("requiredProof") or [])
    and "continuous versus startup or inrush boundary"
    in (baseline_contract.get("requiredProof") or [])
    and "fuse or breaker coordination and interrupt boundary"
    in (baseline_contract.get("requiredProof") or [])
    and "answers only with horsepower or unit conversion"
    in (baseline_contract.get("rejectIf") or [])
    and "uses summed nameplate power as a complete battery, BMS, cable, or fuse rating"
    in (baseline_contract.get("rejectIf") or []),
    baseline_contract,
)

baseline_context = server.build_engineering_advisory_context(
    baseline_messages, baseline_route
)
check(
    "author-context-separates-topology-continuous-startup-and-fault-decisions",
    all(
        phrase in baseline_context
        for phrase in (
            "source -> battery/BMS -> inverter or bus -> branch/load path",
            "Summed nameplate power is only a continuous-load starting point",
            "available battery fault current",
            "ideal P/V current as a labeled lower bound",
        )
    ),
    baseline_context,
)
check(
    "component-power-parser-binds-each-rating-to-the-right-load",
    server.electrical_distribution_labeled_power_kw(baseline_prompt, ("inverter",))
    == 5.0
    and server.electrical_distribution_labeled_power_kw(
        baseline_prompt, ("spindle", "spindle motor")
    )
    == 3.0
    and server.electrical_distribution_labeled_power_kw(
        baseline_prompt, ("air compressor", "compressor")
    )
    == 2.0,
    baseline_prompt,
)

baseline_recovery = server.electrical_distribution_recovery_answer(
    baseline_messages, baseline_route
)
baseline_recovery_validation = server.engineering_single_pass_repair_validation(
    baseline_messages,
    baseline_route,
    baseline_recovery,
)
check(
    "typed-recovery-uses-only-supplied-and-transparent-derived-values",
    baseline_recovery_validation.get("ok")
    and all(
        value in baseline_recovery
        for value in ("48 V", "5 kW inverter", "3 kW spindle", "2 kW compressor", "104.2 A")
    )
    and "6 kW" not in baseline_recovery
    and "ideal input-current lower bound" in baseline_recovery,
    {
        "answer": baseline_recovery,
        "validation": baseline_recovery_validation,
    },
)


def unexpected_model_call(*_args, **_kwargs):
    raise AssertionError("typed electrical recovery must not call a review model")


baseline_audit = server.run_engineering_reasoning_audit(
    baseline_messages,
    baseline_route,
    "Adding the load names is enough; choose the battery and fuse from that total.",
    generate_fn=unexpected_model_call,
)
check(
    "weak-primary-recovers-without-slow-second-model",
    baseline_audit.get("ok")
    and baseline_audit.get("model")
    == "deterministic-electrical-distribution-recovery"
    and baseline_audit.get("modelReviewSkipped") is True
    and baseline_audit.get("finalVerificationPassed") is True
    and "104.2 A" in baseline_audit.get("finalAnswer", ""),
    baseline_audit,
)

baseline_recovery = server.electrical_distribution_recovery_answer(
    baseline_messages, baseline_route
)
baseline_recovery_validation = server.engineering_single_pass_repair_validation(
    baseline_messages, baseline_route, baseline_recovery
)
check(
    "typed-recovery-completes-the-baseline-without-a-second-model",
    baseline_recovery_validation.get("ok")
    and "5000 W / 48 V" in baseline_recovery
    and "104.2 A" in baseline_recovery
    and "available battery fault current" in baseline_recovery
    and "BMS does not replace" in baseline_recovery,
    {
        "answer": baseline_recovery,
        "validation": baseline_recovery_validation,
    },
)


def unexpected_model_call(*_args, **_kwargs):
    raise AssertionError("typed electrical-distribution recovery should skip model review")


baseline_audit = server.run_engineering_reasoning_audit(
    baseline_messages,
    baseline_route,
    "The total is 5 kW, so the system is fine.",
    generate_fn=unexpected_model_call,
)
check(
    "incomplete-baseline-recovers-without-cold-review-fanout",
    baseline_audit.get("ok")
    and baseline_audit.get("model")
    == "deterministic-electrical-distribution-recovery"
    and baseline_audit.get("modelReviewSkipped") is True
    and "104.2 A" in baseline_audit.get("finalAnswer", ""),
    baseline_audit,
)

terminal_messages, terminal_route, _ = routed(baseline_prompt)
server.answer_obligation_prompt_rows(terminal_messages, terminal_route)
server.primary_draft_provenance_receipt(
    terminal_messages,
    terminal_route,
    baseline_recovery,
    kind="controller-synthesized-recovery",
    model="deterministic-engineering-recovery",
    done_reason="length",
    error="synthetic hidden-only primary",
)
terminal_answer = server.supervise_answer_before_emit(
    terminal_messages,
    terminal_route,
    {},
    baseline_recovery,
    web_search="disabled",
)
terminal_binding = terminal_route.get("_engineeringAnswerObligationBinding") or {}
typed_terminal_receipt = terminal_route.get(
    "_typedDeterministicEngineeringRecovery"
) or {}
check(
    "validated-typed-recovery-can-complete-with-exact-provenance",
    terminal_answer == baseline_recovery
    and terminal_route.get("_supervisionStatus") == "pass"
    and terminal_binding.get("status") == "pass"
    and terminal_binding.get("specialistVerificationPassed") is True
    and typed_terminal_receipt.get("status") == "verified"
    and typed_terminal_receipt.get("domain") == "power_electrical"
    and typed_terminal_receipt.get("candidateSha256")
    == server.text_sha256(terminal_answer)
    and not server.typed_deterministic_electrical_distribution_recovery_candidate(
        terminal_messages,
        terminal_route,
        terminal_answer + " Arbitrary controller claim.",
    ),
    {
        "supervisionStatus": terminal_route.get("_supervisionStatus"),
        "binding": terminal_binding,
        "typedRecovery": typed_terminal_receipt,
    },
)

distinct_prompt = (
    "A 24 V LiFePO4 bank will supply a 2 kW inverter. The AC panel feeds a "
    "refrigeration compressor and a well pump. Can one main fuse and one pair "
    "of battery cables be sized from 2 kW, or how should I account for BMS "
    "limits, branch breakers, inrush, voltage drop, and fire risk?"
)
distinct_messages, distinct_route, distinct_frame = routed(distinct_prompt)
check(
    "distinct-source-to-load-topology-uses-the-same-systemic-owner",
    server.is_electrical_distribution_protection_question(distinct_messages)
    and distinct_frame.get("advisoryDomain") == "power_electrical"
    and distinct_frame.get("reasoningArchetype")
    == "electrical_distribution_protection"
    and server.task_contract(distinct_messages, distinct_route).get("kind")
    == "Electrical distribution and protection design",
    distinct_frame,
)

baseline_answer = (
    "No. The topology and operating cases must be established before final "
    "ratings: continuous demand, concurrent operation, conversion loss, "
    "compressor and spindle startup, BMS limits, cable ampacity and voltage "
    "drop, and fuse interrupt capability are separate constraints."
)
followup_messages = [
    *baseline_messages,
    {"role": "assistant", "text": baseline_answer},
    {
        "role": "user",
        "text": (
            "The compressor is actually on a separate utility circuit; only "
            "the spindle is behind the inverter. Reassess the battery-side "
            "current and protection plan with that topology."
        ),
    },
]
_, followup_route, followup_frame = routed(followup_messages)
check(
    "followup-topology-change-preserves-electrical-system-ownership",
    followup_frame.get("domain") == "engineering_advisory"
    and followup_frame.get("advisoryDomain") == "power_electrical"
    and followup_frame.get("reasoningArchetype")
    == "electrical_distribution_protection"
    and followup_frame.get("actionType")
    == "reassess_engineering_conclusion_with_new_constraints"
    and followup_frame.get("contextRelation") == "follow-up",
    followup_frame,
)
check(
    "followup-retains-the-new-bus-boundary-in-known-constraints",
    any(
        "compressor" in str(item).lower()
        and "separate utility" in str(item).lower()
        for item in (followup_frame.get("knownConstraints") or [])
    ),
    followup_frame.get("knownConstraints"),
)

followup_recovery = server.electrical_distribution_recovery_answer(
    followup_messages,
    followup_route,
)
followup_recovery_validation = server.engineering_single_pass_repair_validation(
    followup_messages,
    followup_route,
    followup_recovery,
)
check(
    "typed-followup-removes-utility-load-from-battery-current",
    followup_recovery_validation.get("ok")
    and "removes the 2 kW compressor" in followup_recovery
    and "only the 3 kW spindle remains" in followup_recovery
    and "62.5 A" in followup_recovery
    and "104.2 A" not in followup_recovery,
    {
        "answer": followup_recovery,
        "validation": followup_recovery_validation,
    },
)

followup_recovery = server.electrical_distribution_recovery_answer(
    followup_messages, followup_route
)
followup_recovery_validation = server.engineering_single_pass_repair_validation(
    followup_messages, followup_route, followup_recovery
)
check(
    "followup-recovery-recalculates-only-the-active-battery-path",
    followup_recovery_validation.get("ok")
    and "removes the 2 kW compressor" in followup_recovery
    and "3000 W / 48 V" in followup_recovery
    and "62.5 A" in followup_recovery
    and "separate path" in followup_recovery,
    {
        "answer": followup_recovery,
        "validation": followup_recovery_validation,
    },
)

horsepower_prompt = "What is the equivalent horsepower of an 11 kW motor?"
horsepower_messages, horsepower_route, horsepower_frame = routed(horsepower_prompt)
check(
    "narrow-horsepower-conversion-remains-narrow",
    not server.is_electrical_distribution_protection_question(horsepower_messages)
    and server.is_engineering_power_conversion_question(horsepower_messages)
    and horsepower_frame.get("domain") == "engineering_power_conversion"
    and server.task_contract(horsepower_messages, horsepower_route).get("kind")
    == "Engineering power-rating conversion",
    horsepower_frame,
)

controller_prompt = (
    "I have a 72 V BLDC motor rated 6.5 kW continuous and 18 kW peak. "
    "What battery-current and phase-current ratings should its controller have?"
)
controller_messages, controller_route, controller_frame = routed(controller_prompt)
check(
    "narrow-controller-sizing-remains-narrow",
    not server.is_electrical_distribution_protection_question(controller_messages)
    and controller_frame.get("domain") == "engineering_power_conversion"
    and server.task_contract(controller_messages, controller_route).get("kind")
    == "Engineering motor/controller sizing",
    controller_frame,
)

cnc_prompt = (
    "My CNC spindle leaves a repeatable 0.20 mm dimensional error on the X axis. "
    "What should I inspect before replacing hardware?"
)
cnc_messages, _, cnc_frame = routed(cnc_prompt)
check(
    "ordinary-cnc-spindle-diagnosis-is-not-reclassified-as-electrical-distribution",
    not server.is_electrical_distribution_protection_question(cnc_messages)
    and cnc_frame.get("advisoryDomain") != "power_electrical"
    and "electrical-distribution-protection"
    not in (cnc_frame.get("frameTags") or []),
    cnc_frame,
)


failed = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "checkCount": len(checks),
            "failed": failed,
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
