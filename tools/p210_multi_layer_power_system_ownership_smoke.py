#!/usr/bin/env python3
"""P210 regressions for complete power-chain reasoning and terminal truth."""

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


compressor_prompt = (
    "I have a 48 V 200 Ah LiFePO4 battery and want to run a 7.5 hp, "
    "230 V, three-phase induction motor that drives a loaded reciprocating air "
    "compressor. Can I do it with a VFD, what inverter/VFD architecture is "
    "required, what currents and protections should I size, and what facts must "
    "I verify before buying parts?"
)
compressor_messages = [{"role": "user", "text": compressor_prompt}]
compressor_route = server.route_manager(
    compressor_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
compressor_frame = compressor_route.get("intentFrame") or {}
compressor_plan = compressor_route.get("objectivePlan") or {}
compressor_capability = compressor_route.get("capabilityPlan") or {}

check(
    "battery-vfd-motor-load-request-is-complete-chain",
    server.source_converter_actuator_load_change(compressor_prompt),
    compressor_frame,
)
check(
    "complete-chain-does-not-collapse-to-power-conversion",
    not server.is_engineering_power_conversion_question(compressor_messages)
    and server.is_engineering_advisory_question(compressor_messages),
    {
        "powerConversion": server.is_engineering_power_conversion_question(
            compressor_messages
        ),
        "engineeringAdvisory": server.is_engineering_advisory_question(
            compressor_messages
        ),
    },
)
check(
    "complete-chain-routes-to-registered-reasoning-owner",
    compressor_frame.get("domain") == "engineering_advisory"
    and compressor_frame.get("advisoryDomain") == "power_electrical"
    and compressor_plan.get("objectiveType") == "engineering-advisory"
    and compressor_capability.get("id") == "engineering-advisory"
    and compressor_capability.get("executor") == "reasoning-worker",
    {
        "intentFrame": compressor_frame,
        "objectivePlan": compressor_plan,
        "capabilityPlan": compressor_capability,
    },
)

generic_frame = server.build_generic_intent_frame(compressor_messages, cwd=str(ROOT))
check(
    "generic-kernel-also-owns-complete-chain-as-design-judgment",
    generic_frame.get("domain") == "engineering_advisory"
    and "multi-layer-power-system-design" in (generic_frame.get("frameTags") or [])
    and "power-unit-conversion-only-answer"
    in (generic_frame.get("forbiddenRoutes") or [])
    and any(
        "complete power chain" in str(item).lower()
        for item in generic_frame.get("knownConstraints") or []
    ),
    generic_frame,
)

contract = server.task_contract(compressor_messages, compressor_route)
check(
    "complete-chain-gets-system-level-completion-contract",
    contract.get("kind") == "Multi-layer power system design"
    and "source-to-converter-to-drive-to-motor-to-load architecture"
    in (contract.get("requiredProof") or [])
    and "normal control and independent protection"
    in (contract.get("requiredProof") or [])
    and "pre-purchase evidence list" in (contract.get("requiredProof") or []),
    contract,
)

context = server.build_engineering_advisory_context(
    compressor_messages, compressor_route
)
check(
    "author-context-preserves-every-system-layer",
    all(
        phrase in context
        for phrase in (
            "source -> converter/controller -> actuator -> driven load/process -> feedback/control -> protection",
            "source-side compatibility",
            "driven-load startup",
            "process-side control or protection",
            "fault-current paths",
        )
    ),
    context,
)

author_prompt = server.engineering_reasoning_repair_prompt(
    compressor_messages,
    compressor_route,
    "Unrelated unit-conversion draft.",
    [{"kind": "wrong-system-layer"}],
)
check(
    "multi-layer-author-prompt-is-source-neutral-and-purchase-complete",
    all(
        phrase in author_prompt
        for phrase in (
            "Build the complete chain",
            "loaded startup or unloading",
            "normal process control",
            "Do not silently assume utility AC or direct battery-to-VFD compatibility",
            "battery/BMS limits when present",
            "precharge/inrush plan",
            "normal pressure control and independent relief",
        )
    )
    and "service breaker and conductors; VFD manual single-phase" not in author_prompt,
    author_prompt,
)

compressor_calculation = server.power_chain_transparent_calculation(
    compressor_prompt
)
compressor_outputs = compressor_calculation.get("outputs") or {}
check(
    "controller-provides-arithmetic-only-power-chain-ledger",
    compressor_calculation.get("family")
    == "power-unit-and-source-current-lower-bound"
    and abs(float(compressor_outputs.get("mechanicalOrLoadPowerW") or 0) - 5592.74904)
    < 0.01
    and abs(float(compressor_outputs.get("idealSourceCurrentLowerBoundA") or 0) - 116.515605)
    < 0.01
    and "ideal lower bound" in compressor_calculation.get("promptBoundary", "")
    and "not a continuous-current" in compressor_calculation.get(
        "promptBoundary", ""
    ),
    compressor_calculation,
)
check(
    "model-author-receives-checked-arithmetic-without-controller-answer",
    "Controller-verified arithmetic ledger" in author_prompt
    and "Iideal = P/V" in author_prompt
    and "not a continuous-current" in author_prompt
    and (compressor_route.get("_engineeringCalculatorReceipt") or {}).get(
        "gateStatus"
    )
    == "prompt-boundary",
    {
        "prompt": author_prompt,
        "receipt": compressor_route.get("_engineeringCalculatorReceipt"),
    },
)

revision_draft = (
    "The 48 V battery cannot directly feed an ordinary 230 V VFD. "
    "Assume 90 A for the battery source. "
    "Keep the compressor unloader and independent relief valve."
)
revision_prompt = server.engineering_reasoning_repair_prompt(
    compressor_messages,
    compressor_route,
    revision_draft,
    [
        {
            "kind": "unsupported-technical-precision",
            "claim": "90 A",
            "reason": "The draft did not derive or source this current.",
        }
    ],
    [],
)
check(
    "bounded-repair-revises-sanitized-current-draft-instead-of-restarting",
    "Usable current-turn draft:" in revision_prompt
    and "cannot directly feed an ordinary 230 V VFD" in revision_prompt
    and "compressor unloader and independent relief valve" in revision_prompt
    and "90 A" not in revision_prompt
    and "Controller-verified arithmetic ledger:" in revision_prompt
    and "unsupported-technical-precision" in revision_prompt,
    revision_prompt,
)
check(
    "multi-layer-repair-budget-fits-parent-request-deadline",
    server.MULTI_LAYER_ENGINEERING_REPAIR_TIMEOUT_SECONDS <= 75
    and server.MULTI_LAYER_ENGINEERING_REPAIR_NUM_PREDICT <= 700
    and server.MULTI_LAYER_ENGINEERING_REPAIR_NUM_CTX <= 7000,
    {
        "timeoutSeconds": server.MULTI_LAYER_ENGINEERING_REPAIR_TIMEOUT_SECONDS,
        "numPredict": server.MULTI_LAYER_ENGINEERING_REPAIR_NUM_PREDICT,
        "numCtx": server.MULTI_LAYER_ENGINEERING_REPAIR_NUM_CTX,
    },
)
author_profile = server.conversation_reasoning_generation_profile(
    compressor_messages,
    compressor_route,
)
check(
    "primary-author-preserves-focused-repair-and-terminal-reserve",
    author_profile.get("timeout") == 80
    and author_profile.get("numPredict") <= 700
    and author_profile.get("allowFinalRetry") is False,
    author_profile,
)
check(
    "shared-disposition-sends-declared-multi-layer-gap-to-focused-repair",
    server.engineering_issue_disposition(
        [{"kind": "missing-bounded-source-current-calculation"}],
        multi_layer=True,
    )
    == "focused-repair"
    and server.engineering_issue_disposition(
        [
            {"kind": "missing-bounded-source-current-calculation"},
            {"kind": "unsafe-unverified-safety-topology"},
        ],
        multi_layer=True,
    )
    == "independent-audit",
)
controller_candidate = (
    "The useful model-authored draft keeps its own wording but still needs one more system layer."
)
check(
    "controller-never-appends-technical-prose-to-multi-layer-answer",
    server.preserve_model_authored_multi_layer_candidate(
        compressor_messages,
        compressor_route,
        controller_candidate,
        {"issues": [{"kind": "incomplete-system-purchase-inputs"}]},
    )
    == controller_candidate,
)
learning_answer = "A complete engineering lesson that still names the battery, VFD, motor, and compressor."
learning_route = {
    "_supervisionStatus": "pass",
    "_answerObligationFinalBinding": {"status": "pass"},
    "_answerEnvelope": {
        "status": "complete",
        "final_text_sha256": server.text_sha256(learning_answer),
        "terminal_state": {"mayClaimComplete": True},
    },
}
bounded_learning_route = {
    **learning_route,
    "_supervisionStatus": "bounded",
    "_answerEnvelope": {
        **learning_route["_answerEnvelope"],
        "status": "bounded",
        "terminal_state": {"mayClaimComplete": False},
    },
}
verified_learning_route = {
    **learning_route,
    "_answerEnvelope": {
        **learning_route["_answerEnvelope"],
        "evidence_provenance": {
            "mayClaimVerified": True,
            "verifiedReceiptCount": 1,
            "sourceTypes": ["primary-technical-source"],
            "issues": [],
        },
    },
}
check(
    "only-exact-finalized-complete-answer-is-learning-eligible",
    server.finalized_answer_is_learning_eligible(learning_route, learning_answer)
    and not server.finalized_answer_is_learning_eligible(
        bounded_learning_route,
        learning_answer,
    )
    and not server.finalized_answer_is_learning_eligible(
        learning_route,
        learning_answer + " changed",
    ),
)
check(
    "stable-factual-learning-requires-verified-source-provenance",
    not server.stable_knowledge_learning_proof(
        learning_route,
        learning_answer,
    ).get("eligible")
    and server.stable_knowledge_learning_proof(
        verified_learning_route,
        learning_answer,
    ).get("eligible"),
)
check(
    "legacy-stable-notes-are-reuse-ineligible",
    not server.stable_knowledge_item_reuse_eligible(
        {"stability": "stable", "lesson": "legacy note"}
    )
    and not server.stable_knowledge_item_reuse_eligible(
        {
            "stability": "stable",
            "terminalStatus": "complete",
            "terminalMayClaimComplete": True,
            "answerSha256": "a" * 64,
        }
    )
    and server.stable_knowledge_item_reuse_eligible(
        {
            "stability": "stable",
            "terminalStatus": "complete",
            "terminalMayClaimComplete": True,
            "answerSha256": "a" * 64,
            "durableLearningEligible": True,
            "learningProof": "verified-source-provenance",
            "learningProofSha256": "a" * 64,
        }
    ),
)
engineering_budget, engineering_deadline_class = (
    server.request_deadline_budget_for_route(compressor_route, "balanced")
)
check(
    "complex-complete-system-answer-has-bounded-repair-budget",
    engineering_deadline_class == "multi-layer-engineering-answer"
    and engineering_budget >= 165.0
    and author_profile.get("timeout")
    + server.MULTI_LAYER_ENGINEERING_REPAIR_TIMEOUT_SECONDS
    + 5
    <= engineering_budget,
    {
        "budgetSeconds": engineering_budget,
        "routeClass": engineering_deadline_class,
    },
)

complete_battery_answer = (
    "The 48 V, 200 Ah battery cannot directly feed an ordinary 230 V VFD unless the drive maker explicitly supports that DC-bus input. "
    "Use either a documented 48 V DC-to-AC inverter feeding a compatible VFD, or an engineered DC-DC conversion stage feeding a supported DC bus. "
    "The 7.5 hp shaft requirement is about 5.59 kW, so using I=P/V gives 116.5 A as only the ideal lower bound at 48 V before losses. Size from the battery and BMS continuous current and surge current, converter input range, output voltage, continuous rating and surge rating, VFD input/DC-bus range, three-phase output and continuous duty, then the motor and load duty.\n\n"
    "A loaded reciprocating compressor still needs a working unloader and check valve; a VFD ramp does not unload trapped head pressure. "
    "Verify the compressor minimum and maximum speed, pulley ratio, lubrication, cooling and duty cycle, plus motor cooling and inverter-duty suitability. "
    "Use the pressure switch for normal pressure control and retain an independent relief valve for overpressure protection.\n\n"
    "Before buying, collect the battery and BMS continuous-discharge and peak-current limits, inverter manual, converter manual and VFD manual, including input voltage, input current, DC-bus limits, output voltage and continuous power. "
    "Record the motor nameplate, base speed and base frequency, and the compressor nameplate and compressor manual, allowed speed range, pulley ratio and operating duty. "
    "Specify the DC fuse, conductors, disconnect, contactor and precharge/inrush control from those verified limits."
)
complete_battery_issues = server.source_converter_actuator_load_issues(
    compressor_prompt,
    complete_battery_answer,
)
check(
    "complete-battery-chain-satisfies-source-specific-validator",
    not complete_battery_issues,
    complete_battery_issues,
)

natural_model_answer = (
    "Feasibility depends on verifying that the VFD accepts 48 V DC input or requires a compatible DC-DC boost stage, as standard 230 V AC-input drives will not work directly. "
    "The ideal source current lower bound is 117 A (5.59 kW / 48 V), but real continuous sizing must exceed this to account for converter inefficiencies and motor startup surges. "
    "You must separate the battery's discharge capability and BMS limits from the VFD's DC-bus input rating and the motor's inverter-duty mechanical rating. "
    "Verify that every conversion stage handles the specific voltage and current boundaries without derating.\n\n"
    "A VFD soft-start does not unload a reciprocating compressor. Retain a check valve to block receiver backflow, an unloader to vent trapped pump head pressure, "
    "a pressure switch for normal control, and an independent relief device for overpressure protection. Verify minimum operating speed, lubrication, cooling, pulley ratio, and duty cycle. "
    "The motor must be rated for inverter duty.\n\n"
    "Before purchasing, obtain the battery nameplate and BMS continuous/surge current limits; the VFD manual specifying DC-input compatibility, precharge requirements, and output ratings; "
    "the motor nameplate; and the compressor manual detailing allowed speed range, pulley ratios, lubrication rules, and duty cycle. Verify conductor sizing, disconnects, fuses, and contactors against the real currents."
)
natural_model_validation = server.engineering_single_pass_repair_validation(
    compressor_messages,
    compressor_route,
    natural_model_answer,
)
check(
    "natural-equivalent-system-answer-clears-obligations-without-keyword-template",
    natural_model_validation.get("ok") is True
    and server.battery_current_capability_evidence_present(natural_model_answer)
    and server.conversion_stage_purchase_evidence_present(natural_model_answer)
    and server.power_chain_bounded_source_current_calculation_present(
        compressor_prompt,
        natural_model_answer,
    ),
    natural_model_validation,
)
check(
    "normalized-obligation-recognition-still-rejects-incomplete-layers",
    not server.battery_current_capability_evidence_present(
        "Check the battery and BMS current limit."
    )
    and not server.conversion_stage_purchase_evidence_present(
        "Read the VFD manual and check its output rating."
    )
    and not server.power_chain_bounded_source_current_calculation_present(
        compressor_prompt,
        "The source current will be high, so use large conductors.",
    ),
)

repair_calls = []


def focused_repair_generator(prompt, **kwargs):
    repair_calls.append({"prompt": prompt, **kwargs})
    return {"text": complete_battery_answer, "error": "", "cancelled": False}


focused_repair_route = server.route_manager(
    compressor_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
focused_repair_result = server.run_engineering_reasoning_audit(
    compressor_messages,
    focused_repair_route,
    "The battery should run the motor through a VFD.",
    fast_triage_fn=lambda *args, **kwargs: {"attempted": False, "passed": False},
    generate_fn=focused_repair_generator,
)
check(
    "incomplete-primary-gets-one-focused-model-repair-not-large-audit",
    len(repair_calls) == 1
    and repair_calls[0].get("timeout")
    == server.MULTI_LAYER_ENGINEERING_REPAIR_TIMEOUT_SECONDS
    and repair_calls[0].get("num_predict")
    == server.MULTI_LAYER_ENGINEERING_REPAIR_NUM_PREDICT
    and "Controller-verified arithmetic ledger:" in repair_calls[0].get("prompt", "")
    and focused_repair_result.get("finalVerificationPassed") is True
    and focused_repair_result.get("repairAttemptCount") == 1
    and focused_repair_result.get("modelReviewSkipped") is True
    and focused_repair_result.get("finalAnswer") == complete_battery_answer,
    {
        "calls": repair_calls,
        "result": focused_repair_result,
    },
)

complete_paragraphs = complete_battery_answer.split("\n\n")
purchase_incomplete_answer = "\n\n".join(
    [
        *complete_paragraphs[:-1],
        "Before buying, check the battery and VFD manuals and retain the compressor safeguards.",
    ]
)
purchase_incomplete_kinds = {
    str(item.get("kind") or "")
    for item in server.engineering_single_pass_repair_validation(
        compressor_messages,
        compressor_route,
        purchase_incomplete_answer,
    ).get("issues")
    or []
}
purchase_repair_calls = []


def purchase_repair_generator(prompt, **kwargs):
    purchase_repair_calls.append({"prompt": prompt, **kwargs})
    return {"text": complete_paragraphs[-1], "error": "", "cancelled": False}


purchase_repair_route = server.route_manager(
    compressor_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
purchase_repair_result = server.run_engineering_reasoning_audit(
    compressor_messages,
    purchase_repair_route,
    purchase_incomplete_answer,
    fast_triage_fn=lambda *args, **kwargs: {"attempted": False, "passed": False},
    generate_fn=purchase_repair_generator,
)
check(
    "sole-purchase-gap-replaces-only-model-authored-evidence-paragraph",
    purchase_incomplete_kinds == {"incomplete-system-purchase-inputs"}
    and len(purchase_repair_calls) == 1
    and "Return only one replacement user-facing paragraph"
    in purchase_repair_calls[0].get("prompt", "")
    and purchase_repair_calls[0].get("num_predict") == 360
    and purchase_repair_result.get("targetedPurchaseEvidenceRepair") is True
    and purchase_repair_result.get("finalVerificationPassed") is True
    and purchase_repair_result.get("finalAnswer") == complete_battery_answer,
    {
        "issueKinds": sorted(purchase_incomplete_kinds),
        "calls": purchase_repair_calls,
        "result": purchase_repair_result,
    },
)
check(
    "transparent-electrical-derivations-are-not-treated-as-invented-precision",
    server.electrical_power_chain_derived_claim_is_supported(
        compressor_prompt,
        complete_battery_answer,
        "5.59 kW",
    )
    and server.electrical_power_chain_derived_claim_is_supported(
        compressor_prompt,
        complete_battery_answer,
        "116.5 A",
    )
    and not server.electrical_power_chain_derived_claim_is_supported(
        compressor_prompt,
        "Assume 90 A without showing a boundary.",
        "90 A",
    ),
)

verified_binding_route = server.route_manager(
    compressor_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
server.answer_obligation_prompt_rows(compressor_messages, verified_binding_route)
verified_binding_audit = {
    "verificationCompleted": True,
    "finalVerificationPassed": True,
    "verificationIssueCount": 0,
    "verificationVerdict": "bounded-decision-deterministic-pass",
    "repairError": "",
}
verified_binding = server.bind_verified_engineering_answer_obligations(
    compressor_messages,
    verified_binding_route,
    complete_battery_answer,
    verified_binding_audit,
)
check(
    "verified-engineering-answer-binds-shared-terminal-obligations",
    verified_binding.get("status") == "pass"
    and server.answer_obligation_receipt_matches_final(
        verified_binding_route.get("_answerObligationLedger") or {},
        verified_binding,
        complete_battery_answer,
    )
    and (verified_binding_route.get("_engineeringAnswerObligationBinding") or {}).get(
        "specialistVerificationPassed"
    )
    is True,
    verified_binding,
)
incomplete_binding_route = server.route_manager(
    compressor_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
server.answer_obligation_prompt_rows(compressor_messages, incomplete_binding_route)
incomplete_binding = server.bind_verified_engineering_answer_obligations(
    compressor_messages,
    incomplete_binding_route,
    shallow_battery_answer if "shallow_battery_answer" in globals() else "Use a VFD.",
    verified_binding_audit,
)
check(
    "specialist-binding-keeps-incomplete-answer-fail-closed",
    incomplete_binding.get("status") == "block"
    and (incomplete_binding_route.get("_engineeringAnswerObligationBinding") or {}).get(
        "specialistVerificationPassed"
    )
    is False,
    incomplete_binding,
)

shallow_battery_answer = (
    "Use a 7.5 hp VFD because 7.5 hp is about 5.6 kW. The 48 V battery should run it."
)
shallow_battery_kinds = {
    str(item.get("kind") or "")
    for item in server.source_converter_actuator_load_issues(
        compressor_prompt,
        shallow_battery_answer,
    )
}
check(
    "conversion-only-battery-answer-fails-multiple-system-layers",
    {
        "incomplete-source-converter-rating-model",
        "incomplete-driven-load-operating-envelope",
        "incomplete-process-control-protection",
        "incomplete-system-purchase-inputs",
    }.issubset(shallow_battery_kinds),
    sorted(shallow_battery_kinds),
)

complete_without_calculation = complete_battery_answer.replace(
    "The 7.5 hp shaft requirement is about 5.59 kW, so using I=P/V gives 116.5 A as only the ideal lower bound at 48 V before losses. ",
    "The source current must be checked against conversion losses. ",
)
missing_calculation_kinds = {
    str(item.get("kind") or "")
    for item in server.source_converter_actuator_load_issues(
        compressor_prompt,
        complete_without_calculation,
    )
}
check(
    "otherwise-complete-system-answer-still-cannot-omit-requested-current-math",
    "missing-bounded-source-current-calculation" in missing_calculation_kinds,
    sorted(missing_calculation_kinds),
)

alternate_prompt = (
    "A 96 V battery must run a 12 kW three-phase motor through an inverter drive for a "
    "fixed-displacement hydraulic pump. What architecture and protections do I need, and what must "
    "I verify before buying components, including source-current sizing?"
)
alternate_messages = [{"role": "user", "text": alternate_prompt}]
alternate_route = server.route_manager(
    alternate_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "different-battery-drive-load-chain-uses-same-systemic-owner",
    server.source_converter_actuator_load_change(alternate_prompt)
    and (alternate_route.get("intentFrame") or {}).get("domain")
    == "engineering_advisory"
    and (alternate_route.get("capabilityPlan") or {}).get("id")
    == "engineering-advisory"
    and (alternate_route.get("objectivePlan") or {}).get("objectiveType")
    == "engineering-advisory",
    alternate_route,
)
alternate_author_prompt = server.engineering_reasoning_repair_prompt(
    alternate_messages,
    alternate_route,
    "A generic controller answer.",
    [{"kind": "wrong-system-layer"}],
)
check(
    "battery-hydraulic-author-contract-also-remains-source-neutral",
    "do not assume utility AC or direct battery-to-VFD compatibility"
    in alternate_author_prompt
    and "battery/BMS limits when present" in alternate_author_prompt
    and "service breaker and conductors; VFD manual single-phase" not in alternate_author_prompt,
    alternate_author_prompt,
)
alternate_calculation = server.power_chain_transparent_calculation(alternate_prompt)
check(
    "arithmetic-ledger-generalizes-to-different-voltage-power-and-load",
    abs(
        float(
            (alternate_calculation.get("outputs") or {}).get(
                "idealSourceCurrentLowerBoundA"
            )
            or 0
        )
        - 125.0
    )
    < 0.001
    and "fixed-displacement" not in alternate_calculation.get(
        "promptBoundary", ""
    ),
    alternate_calculation,
)
check(
    "unrequested-current-math-does-not-create-a-calculation-receipt",
    not server.power_chain_transparent_calculation(
        "A 72 V battery runs a 10 kW motor. Explain the motor cooling options."
    ),
)

ac_prompt = (
    "I have 240 V single-phase service and a 5 hp, 230 V three-phase motor on a "
    "reciprocating compressor. Is a VFD sound, how should I size it, and what "
    "must I verify before buying?"
)
ac_answer = (
    "Keep the 5 hp motor if the compressor requires that shaft load, but use an inverter-duty motor. "
    "The VFD must be explicitly rated for single-phase input, and the VFD manual input-current and derating rule may require a larger drive rating. "
    "Verify service current, breaker, branch-circuit conductors, and the motor nameplate, base speed and base frequency. "
    "Retain the unloader and check valve for loaded starting, and verify the compressor manual, pulley ratio, minimum and maximum RPM, lubrication, cooling and duty cycle. "
    "Use a pressure switch for normal pressure control and an independent relief valve for overpressure protection."
)
ac_issue_kinds = {
    str(item.get("kind") or "")
    for item in server.source_converter_actuator_load_issues(ac_prompt, ac_answer)
}
check(
    "existing-ac-source-rating-contract-is-preserved",
    "incomplete-source-converter-rating-model" not in ac_issue_kinds,
    sorted(ac_issue_kinds),
)

battery_followup_messages = [
    {"role": "user", "text": compressor_prompt},
    {
        "role": "assistant",
        "text": (
            "Treat the battery, conversion stage, VFD, motor, compressor, controls, "
            "and protections as separate rating layers."
        ),
    },
    {
        "role": "user",
        "text": (
            "If I change the battery to 72 V but keep the same motor and compressor, "
            "which parts of that architecture change and which stay the same?"
        ),
    },
]
battery_followup_route = server.route_manager(
    battery_followup_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
battery_followup_frame = battery_followup_route.get("intentFrame") or {}
battery_followup_plan = battery_followup_route.get("objectivePlan") or {}
check(
    "multi-layer-followup-preserves-delta-action-instead-of-restarting",
    battery_followup_frame.get("actionType")
    == "reassess_engineering_conclusion_with_new_constraints"
    and battery_followup_frame.get("contextRelation") == "follow-up"
    and battery_followup_plan.get("responseKind") == "constraint-update"
    and "multi-layer-constraint-update"
    in (battery_followup_frame.get("frameTags") or []),
    {
        "intentFrame": battery_followup_frame,
        "objectivePlan": battery_followup_plan,
    },
)

narrow_prompts = (
    "What is the equivalent horsepower of an 11 kW motor?",
    (
        "I found a 72 V BLDC motor listed at 6.5 kW continuous and 18 kW peak. "
        "What is the real horsepower and what size controller would you pair with "
        "it for a lightweight kart?"
    ),
)
for index, prompt in enumerate(narrow_prompts, start=1):
    messages = [{"role": "user", "text": prompt}]
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    check(
        f"narrow-power-conversion-owner-is-preserved-{index}",
        server.is_engineering_power_conversion_question(messages)
        and not server.source_converter_actuator_load_change(prompt)
        and (route.get("intentFrame") or {}).get("domain")
        == "engineering_power_conversion"
        and (route.get("capabilityPlan") or {}).get("id")
        == "engineering-power-conversion",
        route,
    )

blocked_route = {
    "_supervisionStatus": "blocked",
    "_answerEnvelope": {"status": "blocked"},
}
check(
    "blocked-final-envelope-cannot-emit-success-return-code",
    server.completion_return_code_for_answer(
        {"error": "worker returned no answer"},
        "A useful-looking fallback.",
        "worker returned no answer",
        route=blocked_route,
    )
    == 1,
    blocked_route,
)
check(
    "complete-useful-fallback-can-still-emit-success",
    server.completion_return_code_for_answer(
        {"error": "worker returned no answer"},
        "A verified and relevant fallback answer.",
        "worker returned no answer",
        route={"_supervisionStatus": "pass", "_answerEnvelope": {"status": "complete"}},
    )
    == 0,
)

server_source = (ROOT / "server.py").read_text(encoding="utf-8")
check(
    "local-research-done-event-consumes-final-envelope-truth",
    'completion_return_code_for_answer(\n                            result,\n                            guarded_fallback,\n                            fallback_text,\n                            route=route,'
    in server_source,
)

failed = [item for item in checks if item["status"] != "pass"]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
