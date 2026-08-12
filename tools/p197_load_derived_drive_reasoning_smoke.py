#!/usr/bin/env python3
"""P197 regression for load-derived drive sizing and mixed comparison turns."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import intelligence_kernel
import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "passed": bool(passed), "detail": str(detail or "")[:1800]}
    )


load_cases = {
    "utility-cart": (
        "I need to choose between a 48 V direct-drive BLDC and a 2:1 reduction drive for a "
        "900 kg utility cart that must climb a 15% grade at 25 km/h. The tire radius is "
        "0.32 m, rolling resistance coefficient is 0.02, and drivetrain efficiency is 88%. "
        "Which architecture is the better default, and what continuous motor power, wheel torque, "
        "motor torque, and controller current should I target?"
    ),
    "industrial-winch": (
        "Size a 48 V motor and compare direct drive with a 12:1 gearbox for a winch lifting a "
        "1200 kg load at 0.3 m/s on a 0.18 m drum with 82% total efficiency. Calculate drum "
        "torque, motor torque, mechanical power, and battery current."
    ),
    "factory-conveyor": (
        "Choose between direct drive and 5:1 reduction for a conveyor moving a 600 kg payload at "
        "1.2 m/s with 0.18 rolling friction, a 0.2 m drive drum, 85% efficiency, and 0.4 m/s^2 "
        "acceleration. What motor power, drum torque, motor torque, and source current at 72 V "
        "should I target?"
    ),
}

for case_id, query in load_cases.items():
    messages = [{"role": "user", "text": query}]
    frame = server.build_intent_frame(messages, cwd=str(ROOT))
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    plan = route.get("capabilityPlan") or {}
    contract = server.task_contract(messages, route)
    check(
        f"{case_id}-uses-load-derived-calculation-owner",
        intelligence_kernel.is_load_derived_drive_sizing(query)
        and not server.is_engineering_power_conversion_question(messages)
        and frame.get("domain") == "engineering_calculation"
        and frame.get("actionType") == "derive_load_and_compare_drive_architectures"
        and "load-derived-drive-sizing" in (frame.get("frameTags") or [])
        and "architecture-comparison" in (frame.get("frameTags") or [])
        and plan.get("id") == "engineering-calculation",
        {"frame": frame, "plan": plan},
    )
    check(
        f"{case_id}-requires-derivation-comparison-and-current-semantics",
        contract.get("kind")
        == "Load-derived drive sizing and architecture comparison"
        and any("load-side force" in item for item in contract.get("mustDo") or [])
        and any("all named architectures" in item for item in contract.get("mustDo") or [])
        and any("phase current" in item for item in contract.get("mustDo") or [])
        and any("existing motor kW rating" in item for item in contract.get("rejectIf") or []),
        contract,
    )

cart_query = load_cases["utility-cart"]
cart_messages = [{"role": "user", "text": cart_query}]
cart_route = server.route_manager(
    cart_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
default_prompt = server.build_intelligence_kernel_prompt(
    cart_messages,
    route=cart_route,
    cwd=str(ROOT),
)
worker_prompt = server.conversation_reasoning_primary_prompt(
    cart_messages,
    cart_route,
    default_prompt,
).lower()
generation_profile = server.conversation_reasoning_generation_profile(
    cart_messages,
    cart_route,
)
audit_profile = server.generic_reasoning_audit_profile(cart_route, cart_messages)
check(
    "worker-receives-whole-load-path-contract",
    "one bounded local calculation author" in worker_prompt
    and "derive the load-side force" in worker_prompt
    and "all named architectures" in worker_prompt
    and "phase current" in worker_prompt
    and "same efficiency boundary" in worker_prompt
    and "does not by itself change dc source current" in worker_prompt
    and "condition that would reverse it" in worker_prompt
    and "controllercalculation" in worker_prompt
    and "arithmetic source of truth" in worker_prompt
    and cart_query.lower() in worker_prompt,
    worker_prompt[-5000:],
)
reference_cases = {
    case_id: server.load_derived_drive_reference_calculation(query)
    for case_id, query in load_cases.items()
}
check(
    "controller-derives-cart-winch-and-conveyor-load-paths",
    all(item.get("complete") for item in reference_cases.values())
    and abs(reference_cases["utility-cart"].get("loadTorqueNm", 0) - 480.4) < 1.0
    and abs(reference_cases["utility-cart"].get("directMotorTorqueNm", 0) - 545.9) < 1.0
    and abs(reference_cases["utility-cart"].get("reducedMotorTorqueNm", 0) - 273.0) < 1.0
    and abs(reference_cases["industrial-winch"].get("loadTorqueNm", 0) - 2118.96) < 2.0
    and abs(reference_cases["factory-conveyor"].get("loadForceN", 0) - 1299.5) < 2.0,
    reference_cases,
)
rendered_reference_answers = {
    case_id: server.render_load_derived_drive_reference_answer(reference)
    for case_id, reference in reference_cases.items()
}
rendered_reference_gates = {
    case_id: server.load_derived_drive_candidate_gate(
        [{"role": "user", "text": load_cases[case_id]}],
        server.route_manager(
            [{"role": "user", "text": load_cases[case_id]}],
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        ),
        answer,
    )
    for case_id, answer in rendered_reference_answers.items()
}
registered_initial = server.registered_engineering_calculation_preflight(
    cart_messages,
    cart_route,
)
check(
    "controller-reference-renders-complete-human-drive-answers",
    all(gate.get("accepted") for gate in rendered_reference_gates.values()),
    {"answers": rendered_reference_answers, "gates": rendered_reference_gates},
)
check(
    "registered-preflight-owns-complete-load-derived-sizing-before-model-work",
    registered_initial.get("accepted") is True
    and (registered_initial.get("calculated") or {}).get("family")
    == "load-derived-drive-sizing"
    and (registered_initial.get("gate") or {}).get("accepted") is True
    and registered_initial.get("durationMs", 1000) < 1000,
    registered_initial,
)
check(
    "quantity-unit-tokenizer-does-not-invent-units-from-prose",
    server.normalized_quantity_unit_tokens(
        "between direct drive and 5:1 reduction for a conveyor moving a 600 kg payload at 1.2 m/s w"
    )
    == {"kg", "m"}
    and server.normalized_quantity_unit_tokens("At 72 V, use at least 30.6 A and 2.2 kW.")
    == {"v", "a", "kw"},
    {
        "prose": sorted(
            server.normalized_quantity_unit_tokens(
                "between direct drive and 5:1 reduction for a conveyor moving a 600 kg payload at 1.2 m/s w"
            )
        ),
        "quantities": sorted(
            server.normalized_quantity_unit_tokens(
                "At 72 V, use at least 30.6 A and 2.2 kW."
            )
        ),
    },
)
check(
    "load-derived-author-has-one-complete-output-budget",
    generation_profile.get("timeout") <= 90
    and generation_profile.get("numPredict") >= 2200
    and generation_profile.get("numCtx") <= 5000
    and generation_profile.get("think") is False
    and generation_profile.get("allowFinalRetry") is False,
    generation_profile,
)
check(
    "load-derived-review-uses-resident-bounded-reasoning-model",
    audit_profile.get("calculationReview") is True
    and audit_profile.get("reviewModel") == server.LOCAL_RESEARCH_MODEL
    and audit_profile.get("reviewTimeout") <= 40
    and audit_profile.get("reviewNumPredict") >= 1200
    and audit_profile.get("reviewNumCtx") <= 5000,
    audit_profile,
)
check(
    "resident-review-model-has-native-chat-schema-path",
    server.reasoning_model_supports_chat_schema(server.LOCAL_RESEARCH_MODEL)
    and not server.reasoning_model_supports_chat_schema(
        server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL
    ),
    {
        "resident": server.LOCAL_RESEARCH_MODEL,
        "structured": server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL,
    },
)
check(
    "legacy-fallback-does-not-own-load-derived-turn",
    not server.build_engineering_power_conversion_context(cart_messages, cart_route)
    and not server.guard_engineering_power_conversion_answer(
        "A checked load-side calculation belongs here.",
        cart_query,
        cart_route,
        [],
        messages=cart_messages,
    ).startswith("I can size the controller boundary"),
    cart_route,
)

cart_output_keys = [
    item[0] for item in server.engineering_calculation_requested_outputs(cart_query)
]
cart_ledger = server.build_answer_obligation_ledger(cart_messages, cart_route)
check(
    "supplied-rolling-resistance-is-not-an-ohmic-output-obligation",
    "resistance" not in cart_output_keys
    and not any(
        item.get("kind") == "requested-output"
        and item.get("text") == "resistance"
        for item in cart_ledger.get("obligations") or []
    ),
    {"outputKeys": cart_output_keys, "ledger": cart_ledger},
)
electrical_resistance_query = (
    "A 24 V load draws 18 A through a 12 m copper cable. Calculate cable resistance, "
    "voltage drop, load voltage, and cable power loss."
)
check(
    "explicit-electrical-resistance-remains-a-required-output",
    "resistance"
    in {
        item[0]
        for item in server.engineering_calculation_requested_outputs(
            electrical_resistance_query
        )
    },
    server.engineering_calculation_requested_outputs(electrical_resistance_query),
)

rounded_intermediate_equation = "Motor torque = 11.85e3 / 21.70 = 545.9 Nm."
materially_wrong_equation = "Motor torque = 11.85e3 / 21.70 = 510.0 Nm."
check(
    "displayed-intermediate-rounding-does-not-create-a-false-arithmetic-failure",
    not server.deterministic_numeric_equation_issues(rounded_intermediate_equation)
    and not server.repair_literal_numeric_equations(
        rounded_intermediate_equation
    ).get("corrections"),
    {
        "issues": server.deterministic_numeric_equation_issues(
            rounded_intermediate_equation
        ),
        "repair": server.repair_literal_numeric_equations(
            rounded_intermediate_equation
        ),
    },
)
check(
    "material-arithmetic-error-still-fails-closed",
    any(
        item.get("kind") == "arithmetic-inconsistency"
        for item in server.deterministic_numeric_equation_issues(
            materially_wrong_equation
        )
    ),
    server.deterministic_numeric_equation_issues(materially_wrong_equation),
)

complete_drive_answer = """I recommend the 2:1 reduction as the default because it preserves the required wheel output while halving motor torque.

For the 900 kg cart at 25 km/h on a 15% grade, I am assuming the stated 88% is motor-shaft-to-wheel efficiency and retaining the 48 V bus, 0.32 m tire radius, and 0.02 rolling-resistance coefficient. The load path is:
Grade force = 900 kg * 9.81 m/s^2 * 0.15 = 1324.4 N, rolling force = 900 kg * 9.81 m/s^2 * 0.02 = 176.6 N, and total force = 1501.0 N.

Wheel torque = 1501.0 N * 0.32 m = 480.3 Nm. Wheel speed = 6.944 m/s / 0.32 m = 21.70 rad/s, so wheel power = 480.3 Nm * 21.70 rad/s = 10.42 kW and motor-shaft power = 10.42 kW / 0.88 = 11.84 kW.

Direct-drive motor torque = 11.84e3 W / 21.70 rad/s = 545.6 Nm.
The 2:1 reduction motor torque = 11.84e3 W / 43.40 rad/s = 272.8 Nm. Both have the same ideal lower bound for DC source current = 11.84e3 W / 48 V = 246.7 A because gearing trades torque for speed rather than changing power. Motor phase current is different and still requires the motor torque constant Kt or a motor/controller map.

The calculated minimum is 11.84 kW at the motor shaft and a 246.7 A ideal DC lower bound. With an explicit 90% motor/controller electrical-efficiency assumption plus 20% design margin, target about 14.2 kW shaft power and 329 A continuous at the controller. Peak power is not specified because launch acceleration, traction, and climb duty are missing.

I would reverse this recommendation if a direct-drive motor map proves 546 Nm continuous at the wheel speed within the same thermal and mass limits, or if gearbox service risk dominates."""
complete_gate = server.load_derived_drive_candidate_gate(
    cart_messages,
    cart_route,
    complete_drive_answer,
)
flawed_drive_answer = complete_drive_answer.replace(
    "Direct-drive motor torque = 11.84e3 / 21.70 = 545.6 Nm.",
    "Direct-drive motor torque = 480.3 Nm.",
).replace(
    "I would reverse this recommendation if a direct-drive motor map proves 546 Nm continuous at the wheel speed within the same thermal and mass limits, or if gearbox service risk dominates.",
    "",
)
flawed_gate = server.load_derived_drive_candidate_gate(
    cart_messages,
    cart_route,
    flawed_drive_answer,
)
check(
    "complete-load-derived-answer-can-discharge-review-deterministically",
    complete_gate.get("accepted") is True,
    complete_gate,
)
check(
    "fluent-but-inconsistent-drive-answer-does-not-bypass-review",
    flawed_gate.get("accepted") is False
    and any(
        item in (flawed_gate.get("failures") or [])
        for item in ("architectureTorqueRatio", "reversal", "efficiencyBoundary")
    ),
    flawed_gate,
)
repair_calls = []


def synthetic_drive_repair(prompt, **kwargs):
    repair_calls.append({"prompt": prompt, **kwargs})
    return {"text": complete_drive_answer, "doneReason": "stop"}


repair_receipt = server.repair_load_derived_drive_candidate(
    cart_messages,
    cart_route,
    flawed_drive_answer,
    flawed_gate,
    generate_fn=synthetic_drive_repair,
)
check(
    "failed-drive-gate-gets-one-whole-answer-correction-and-revalidation",
    len(repair_calls) == 1
    and repair_receipt.get("attempted") is True
    and repair_receipt.get("accepted") is True
    and (repair_receipt.get("gate") or {}).get("accepted") is True
    and repair_calls[0].get("allow_final_retry") is False
    and "rebuild the complete answer" in repair_calls[0].get("prompt", "").lower(),
    repair_receipt,
)

rating_cases = {
    "published-rating": (
        "A 72 V BLDC motor is rated 6.5 kW continuous and 18 kW peak. What is the real horsepower "
        "and what size controller would you pair with it for a lightweight kart?"
    ),
    "underspecified-controller": "What size controller should I use for my BLDC motor?",
    "plain-conversion": "What is the equivalent horsepower of an 11 kW axial-flux motor?",
}
for case_id, query in rating_cases.items():
    messages = [{"role": "user", "text": query}]
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    check(
        f"{case_id}-keeps-rating-conversion-owner",
        not intelligence_kernel.is_load_derived_drive_sizing(query)
        and server.is_engineering_power_conversion_question(messages)
        and (route.get("intentFrame") or {}).get("domain")
        == "engineering_power_conversion"
        and (route.get("capabilityPlan") or {}).get("id")
        == "engineering-power-conversion",
        route,
    )

follow_messages = [
    {"role": "user", "text": cart_query},
    {
        "role": "assistant",
        "text": (
            "I derived the grade load, wheel torque, power, and both drive cases. The reduction "
            "drive is the provisional default, subject to the motor map and traction limit."
        ),
    },
    {
        "role": "user",
        "text": (
            "Now assume the climb is only 90 seconds every 20 minutes and maximum climb speed is "
            "12 km/h, but launch traction on gravel matters. Does the recommendation or the "
            "continuous-versus-peak rating change?"
        ),
    },
]
follow_route = server.route_manager(
    follow_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
follow_frame = follow_route.get("intentFrame") or {}
check(
    "follow-up-preserves-engineering-owner-and-prior-operating-point",
    follow_frame.get("domain") == "engineering_calculation"
    and follow_frame.get("contextRelation") == "follow-up"
    and (follow_route.get("capabilityPlan") or {}).get("id")
    == "engineering-calculation"
    and follow_frame.get("actionType")
    in {"reassess_engineering_conclusion_with_new_constraints", "recompute_with_superseded_constraint"},
    {"frame": follow_frame, "plan": follow_route.get("capabilityPlan")},
)
follow_reference = server.load_derived_drive_followup_reference(
    follow_messages,
    follow_route,
)
follow_calculation = server.solve_registered_engineering_calculation(
    follow_messages,
    follow_route,
)
follow_answer = str((follow_calculation or {}).get("answer") or "")
follow_gate = server.conditional_reassessment_candidate_gate(
    follow_messages,
    follow_route,
    follow_answer,
)
follow_preflight = server.registered_engineering_calculation_preflight(
    follow_messages,
    follow_route,
)
check(
    "follow-up-recomputes-only-explicit-drive-input-changes",
    follow_reference.get("complete") is True
    and abs(float(follow_reference.get("speedKmh") or 0) - 12.0) < 1e-9
    and abs(float(follow_reference.get("loadTorqueNm") or 0) - 480.4) < 1.0
    and abs(float(follow_reference.get("motorShaftPowerKw") or 0) - 5.686) < 0.02
    and abs(float(follow_reference.get("idealDcSourceCurrentLowerBoundA") or 0) - 118.45) < 0.5
    and abs(float(follow_reference.get("dutyCyclePct") or 0) - 7.5) < 1e-9
    and follow_reference.get("tractionConstraint") is True,
    follow_reference,
)
check(
    "follow-up-publishes-verified-duty-traction-reassessment-without-model-review",
    (follow_calculation or {}).get("family") == "load-derived-drive-reassessment"
    and follow_gate.get("accepted") is True
    and follow_preflight.get("accepted") is True
    and "conductor length" not in follow_answer.lower()
    and "does not change" in follow_answer.lower()
    and "7.5%" in follow_answer
    and "does not justify multiplying" in follow_answer.lower()
    and "tire-ground traction limit" in follow_answer.lower()
    and "phase current" in follow_answer.lower(),
    {
        "answer": follow_answer,
        "gate": follow_gate,
        "preflight": follow_preflight,
    },
)

failed = [item for item in checks if not item["passed"]]
report = {
    "status": "pass" if not failed else "fail",
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "total": len(checks),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
