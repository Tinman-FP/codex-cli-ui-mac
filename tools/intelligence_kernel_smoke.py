#!/usr/bin/env python3
"""Focused regression for the generic intelligence front door."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from intelligence_kernel import synthetic_kernel_check  # noqa: E402


def evaluate_messages(case_id: str, messages: list[dict], web_search: str = "live") -> dict:
    route = server.route_manager(messages, cwd=str(ROOT), web_search=web_search)
    decision = route.get("kernelDecision") or {}
    allow_legacy = bool(decision.get("allowLegacyDirectAnswer", True))
    direct = server.general_direct_knowledge_answer(
        messages,
        route=route,
        web_search=web_search,
        allow_legacy=allow_legacy,
    )
    prompt = (
        server.build_intelligence_kernel_prompt(messages, route=route, cwd=str(ROOT))
        if decision.get("useCompactPrompt")
        else ""
    )
    composition = server.adaptive_answer_composition_profile(messages, route)
    interaction = server.interaction_director_policy(
        messages,
        route,
        contract=server.task_contract(messages, route),
        composition=composition,
    )
    return {
        "id": case_id,
        "projectId": route.get("projectId"),
        "domain": (route.get("intentFrame") or {}).get("domain"),
        "actionType": (route.get("intentFrame") or {}).get("actionType"),
        "specialistOwner": (route.get("intentFrame") or {}).get("specialistOwner"),
        "rejectedLegacyDomain": (route.get("intentFrame") or {}).get("rejectedLegacyDomain"),
        "engine": route.get("engine"),
        "mode": decision.get("mode"),
        "allowLegacyDirectAnswer": allow_legacy,
        "capability": (route.get("capabilityPlan") or {}).get("id"),
        "capabilityHandler": (route.get("capabilityPlan") or {}).get("handler_key"),
        "reviewPolicy": (route.get("capabilityPlan") or {}).get("review_policy"),
        "directMode": direct.get("mode") if isinstance(direct, dict) else None,
        "promptChars": len(prompt),
        "forceLabeledSections": composition.get("forceLabeledSections"),
        "contractKind": server.task_contract(messages, route).get("kind"),
        "analyticalMode": server.analytical_core_mode(messages, route),
        "objectiveType": (route.get("objectivePlan") or {}).get("objectiveType"),
        "responseKind": (route.get("objectivePlan") or {}).get("responseKind"),
        "interactionMode": interaction.get("mode"),
        "objectTypes": [
            item.get("type")
            for item in ((route.get("intentFrame") or {}).get("objectRefs") or [])
            if isinstance(item, dict)
        ],
    }


def evaluate_case(case_id: str, question: str, web_search: str = "live") -> dict:
    return evaluate_messages(case_id, [{"role": "user", "text": question}], web_search)


def main() -> int:
    report = synthetic_kernel_check()
    cases = [
        evaluate_case(
            "runtime-capabilities-compound",
            "What can you do in this session, and what access do you have?",
        ),
        evaluate_case("local-installation", "Do you have Hunyuan3D-2.1 installed?"),
        evaluate_case("clarification", "Can you fix it?"),
        evaluate_case("selection-clarification", "Let's do 1, 4 & 5."),
        evaluate_case("technical-comparison", "What is stronger PET-CF or PCTG-CF?"),
        evaluate_case(
            "technical-comparison-wrong-owner-negative",
            "Compare SQLite and PostgreSQL for a multi-user maintenance database.",
            web_search="disabled",
        ),
        evaluate_case(
            "mathematical-proof",
            "Prove that the square of every even integer is even.",
            web_search="disabled",
        ),
        evaluate_case(
            "explicit-scientific-evidence",
            "Is there scientific evidence or measured data showing that annealing this composite improves tensile strength?",
        ),
        evaluate_case(
            "current-market",
            "What are the top 10 4 x 8 CNC machines under $20,000 right now?",
        ),
        evaluate_case(
            "current-market-announcement-window",
            (
                "What tool-changing 3D printers have officially announced availability, "
                "preorder, or shipping windows in the next few months? Give exact models "
                "and distinguish confirmed products from rumors."
            ),
        ),
        evaluate_case(
            "current-market-announcement-wrong-owner-negative",
            (
                "What tool-changing CNC machines have officially announced availability, "
                "preorder, or shipping windows in the next few months? Give exact models "
                "and distinguish confirmed products from rumors."
            ),
        ),
        evaluate_case(
            "ebay-marketplace",
            "Find the best current deal on eBay for a 100W JPT MOPA fiber laser and check the complete listings.",
            web_search="disabled",
        ),
        evaluate_case(
            "ebay-marketplace-single-turn-detailed",
            (
                "Find me the best deal on eBay for a complete 100W JPT MOPA fiber laser. "
                "Check the live listings completely for source, lens, software, rotary, enclosure, "
                "warranty, seller reputation, shipping, and delivered price."
            ),
            web_search="live",
        ),
        evaluate_case(
            "local-action",
            "Fix the status panel in Codex CLI UI and verify the change.",
        ),
        evaluate_case(
            "local-reference-implementation-diagnostic",
            (
                "The reference application produces the correct contact geometry, but our local output does not. "
                "Inspect both working applications on this Mac, compare them with our implementation, find the root "
                "cause that is preventing the desired output, and verify the correction."
            ),
            web_search="disabled",
        ),
        evaluate_case(
            "source-file-comparison-keyword-conflict",
            (
                "Compare /tmp/capability_execution.py and /tmp/capability_registry.py "
                "and tell me whether they are similar."
            ),
            web_search="disabled",
        ),
        evaluate_case(
            "engineering-calculation",
            "What size axial flux motor would produce 250 horsepower at 3500 RPM?",
        ),
        evaluate_case(
            "general-engineering-calculation",
            (
                "A 6061-T6 aluminum cantilever is 200 mm long with a 40 mm by 10 mm section and a 1 kN tip load. "
                "Compare both orientations, estimate maximum bending stress and tip deflection, and determine "
                "whether either passes a factor of safety of 2 against yielding."
            ),
            web_search="disabled",
        ),
        evaluate_messages(
            "engineering-calculation-follow-up",
            [
                {
                    "role": "user",
                    "text": (
                        "A 6061-T6 aluminum cantilever is 200 mm long with a 40 mm by 10 mm section and a 1 kN tip load. "
                        "Compare both orientations, estimate stress and deflection, and check a factor of safety of 2."
                    ),
                },
                {
                    "role": "assistant",
                    "text": "The 40 mm vertical orientation passes; the 10 mm vertical orientation fails.",
                },
                {
                    "role": "user",
                    "text": (
                        "Now add a 6 mm diameter hole 20 mm from the fixed end and assume continuous operation at 120 C. "
                        "Does the conclusion still hold?"
                    ),
                },
            ],
            web_search="disabled",
        ),
        evaluate_case(
            "engineering-suitability",
            "Would a graphite bed in a 3D printer perform well with chamber temperatures of 150C?",
        ),
        evaluate_case(
            "engineering-state-preservation",
            "Would a steel frame remain aligned under a sustained 5 kN side load?",
            web_search="disabled",
        ),
        evaluate_case(
            "keyword-conflict-veto",
            "Compare 6061-T6 aluminum and G10/FR4 for an electrically insulating motor-controller mounting plate in a hot, vibrating enclosure.",
        ),
    ]
    by_id = {item["id"]: item for item in cases}
    failures = []
    if report.get("status") != "pass":
        failures.append("generic intent cases failed")
    runtime = by_id["runtime-capabilities-compound"]
    if (
        runtime["domain"] != "agent_runtime_capabilities"
        or runtime["capability"] != "runtime-capability-introspection"
        or runtime["mode"] != "deterministic-capability"
    ):
        failures.append("compound runtime capability question lost self-knowledge intent")
    if by_id["local-installation"]["directMode"] != "local-installation-status":
        failures.append("bounded local installation capability did not run")
    if by_id["clarification"]["directMode"] != "objective-plan-clarification":
        failures.append("missing-referent clarification did not run")
    if by_id["selection-clarification"]["mode"] != "deterministic-capability":
        failures.append("context-free numbered selection did not request clarification")
    for case_id in (
        "technical-comparison-wrong-owner-negative",
        "mathematical-proof",
        "explicit-scientific-evidence",
        "current-market",
        "current-market-announcement-wrong-owner-negative",
        "ebay-marketplace",
        "ebay-marketplace-single-turn-detailed",
        "local-action",
        "local-reference-implementation-diagnostic",
        "engineering-calculation",
        "general-engineering-calculation",
        "engineering-calculation-follow-up",
        "engineering-suitability",
        "engineering-state-preservation",
        "keyword-conflict-veto",
    ):
        case = by_id[case_id]
        if case["mode"] != "model-first" or case["allowLegacyDirectAnswer"]:
            failures.append(f"{case_id} did not use model-first execution")
        if case["directMode"] is not None:
            failures.append(f"{case_id} leaked into a legacy direct answer")
        if not 0 < case["promptChars"] < 8000:
            failures.append(f"{case_id} compact prompt size is outside the regression bound")
        if case["forceLabeledSections"] is not False:
            failures.append(f"{case_id} still forces canned response labels")
    technical_comparison = by_id["technical-comparison"]
    if (
        technical_comparison["projectId"] != "tinmanx-slicer-research"
        or technical_comparison["engine"] != "local"
        or technical_comparison["domain"] != "bounded_specialist_capability"
        or technical_comparison["actionType"] != "answer_from_confirmed_specialist_capability"
        or technical_comparison["specialistOwner"] != "materials-comparison"
        or technical_comparison["mode"] != "deterministic-capability"
        or technical_comparison["allowLegacyDirectAnswer"] is not True
        or technical_comparison["capability"] != "bounded-specialist-capability"
        or technical_comparison["capabilityHandler"] != "bounded_specialist_direct"
        or technical_comparison["reviewPolicy"] != "deterministic"
        or technical_comparison["directMode"] != "tinmanx-ui-direct-answer"
        or technical_comparison["promptChars"] != 0
        or technical_comparison["contractKind"] != "Bounded specialist response"
        or technical_comparison["objectiveType"] != "materials-comparison"
        or technical_comparison["responseKind"] != "direct-materials-comparison"
        or technical_comparison["interactionMode"] != "expert-direct"
    ):
        failures.append("PET-CF/PCTG-CF comparison lost exact deterministic materials-specialist ownership")
    technical_wrong_owner = by_id["technical-comparison-wrong-owner-negative"]
    if (
        technical_wrong_owner["projectId"] != "codex-cli-ui-local-agent"
        or technical_wrong_owner["engine"] != "local"
        or technical_wrong_owner["specialistOwner"] is not None
        or technical_wrong_owner["domain"] != "knowledge_comparison"
        or technical_wrong_owner["actionType"] != "compare_decision_factors"
        or technical_wrong_owner["mode"] != "model-first"
        or technical_wrong_owner["allowLegacyDirectAnswer"]
        or technical_wrong_owner["capability"] != "expert-comparison"
        or technical_wrong_owner["capabilityHandler"] != "expert_comparison"
        or technical_wrong_owner["reviewPolicy"] != "reasoning-audit"
        or technical_wrong_owner["directMode"] is not None
        or not 0 < technical_wrong_owner["promptChars"] < 8000
        or technical_wrong_owner["contractKind"] != "Expert comparison"
        or technical_wrong_owner["objectiveType"] != "direct-help"
        or technical_wrong_owner["responseKind"] != "answer-or-act"
        or technical_wrong_owner["interactionMode"] != "conversation"
    ):
        failures.append("unrelated technical comparison was captured by the materials specialist")
    if by_id["current-market"]["engine"] != "local-research":
        failures.append("current market request did not select local research")
    local_reference_diagnostic = by_id["local-reference-implementation-diagnostic"]
    if (
        local_reference_diagnostic["domain"] != "local_product_action"
        or local_reference_diagnostic["actionType"] != "inspect_compare_diagnose_verify"
        or local_reference_diagnostic["capability"] != "local-product-action"
        or local_reference_diagnostic["contractKind"] != "Local reference implementation diagnostic"
        or local_reference_diagnostic["objectiveType"] != "local-reference-diagnostic"
        or local_reference_diagnostic["objectTypes"]
        != ["reference-implementation", "diagnostic-target"]
    ):
        failures.append("known-good local reference comparison did not enter the root-cause diagnostic workflow")
    mathematical_proof = by_id["mathematical-proof"]
    if (
        mathematical_proof["engine"] != "local"
        or mathematical_proof["domain"] not in {"conversation", "knowledge_question"}
        or mathematical_proof["capability"] != "conversation-reasoning"
        or mathematical_proof["reviewPolicy"] != "reasoning-audit"
    ):
        failures.append("mathematical proof was confused with empirical evidence research")
    scientific_evidence = by_id["explicit-scientific-evidence"]
    if (
        scientific_evidence["engine"] != "local-research"
        or scientific_evidence["domain"] != "scientific_evidence_review"
        or scientific_evidence["capability"] != "current-web-research"
    ):
        failures.append("explicit scientific-evidence request lost evidence-review routing")
    market_window = by_id["current-market-announcement-window"]
    if (
        market_window["projectId"] != "research-parts-reference"
        or market_window["engine"] != "local-research"
        or market_window["domain"] != "current_market_research"
        or market_window["actionType"] != "research_current_options"
        or market_window["specialistOwner"] is not None
        or market_window["mode"] != "model-first"
        or market_window["allowLegacyDirectAnswer"]
        or market_window["capability"] != "current-web-research"
        or market_window["capabilityHandler"] != "local_research"
        or market_window["reviewPolicy"] != "contract-gated"
        or market_window["directMode"] is not None
        or not 0 < market_window["promptChars"] < 8000
        or market_window["contractKind"] != "Current market landscape"
        or market_window["objectiveType"] != "current-market-landscape"
        or market_window["responseKind"] != "source-backed-market-landscape"
        or market_window["interactionMode"] != "verification"
    ):
        failures.append("announcement/availability market request lost current-web capability ownership")
    market_wrong_owner = by_id["current-market-announcement-wrong-owner-negative"]
    if (
        market_wrong_owner["projectId"] != "research-parts-reference"
        or market_wrong_owner["engine"] != "local-research"
        or market_wrong_owner["domain"] != "current_market_research"
        or market_wrong_owner["actionType"] != "research_current_options"
        or market_wrong_owner["specialistOwner"] is not None
        or market_wrong_owner["mode"] != "model-first"
        or market_wrong_owner["allowLegacyDirectAnswer"]
        or market_wrong_owner["capability"] != "current-web-research"
        or market_wrong_owner["capabilityHandler"] != "local_research"
        or market_wrong_owner["reviewPolicy"] != "contract-gated"
        or market_wrong_owner["directMode"] is not None
        or not 0 < market_wrong_owner["promptChars"] < 8000
        or market_wrong_owner["contractKind"] != "Current market landscape"
        or market_wrong_owner["objectiveType"] != "current-market-landscape"
        or market_wrong_owner["responseKind"] != "source-backed-market-landscape"
        or market_wrong_owner["interactionMode"] != "verification"
    ):
        failures.append("non-printer market announcement was captured by a bounded specialist")
    fleet_control_messages = [
        {
            "role": "user",
            "text": "Ping all my printers and tell me which ones are online.",
        }
    ]
    fleet_control_route = server.route_manager(
        fleet_control_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    fleet_control_frame = fleet_control_route.get("intentFrame") or {}
    fleet_control_capability = fleet_control_route.get("capabilityPlan") or {}
    if (
        fleet_control_route.get("projectId") != "printer-klipper-ops"
        or fleet_control_route.get("engine") != "local"
        or fleet_control_frame.get("domain") != "bounded_specialist_capability"
        or fleet_control_frame.get("specialistOwner") != "printer-fleet-reachability"
        or fleet_control_capability.get("id") != "bounded-specialist-capability"
        or fleet_control_capability.get("handler_key") != "bounded_specialist_direct"
        or fleet_control_capability.get("executor") != "deterministic"
    ):
        failures.append("true printer-fleet ping lost its exact deterministic reachability owner")
    if (
        by_id["ebay-marketplace"]["engine"] != "local-research"
        or by_id["ebay-marketplace"]["domain"] != "marketplace_listing_research"
    ):
        failures.append("eBay marketplace request did not select typed listing research")
    detailed_ebay = by_id["ebay-marketplace-single-turn-detailed"]
    if (
        detailed_ebay["engine"] != "local-research"
        or detailed_ebay["domain"] != "marketplace_listing_research"
    ):
        failures.append("detailed single-turn eBay request lost named-source intent")
    if by_id["engineering-calculation"]["engine"] != "local":
        failures.append("stable engineering calculation was incorrectly promoted to local research")
    general_calculation = by_id["general-engineering-calculation"]
    if (
        general_calculation["projectId"] != "general"
        or general_calculation["domain"] != "engineering_calculation"
        or general_calculation["capability"] != "engineering-calculation"
        or general_calculation["reviewPolicy"] != "calculation-contract"
        or general_calculation["contractKind"] != "Engineering calculation"
        or general_calculation["analyticalMode"] != "calculation"
        or general_calculation["objectiveType"] != "engineering-calculation"
        or "comparison-option" in general_calculation["objectTypes"]
    ):
        failures.append("general numerical engineering problem did not receive the calculation contract")
    calculation_followup = by_id["engineering-calculation-follow-up"]
    if (
        calculation_followup["projectId"] != "general"
        or calculation_followup["domain"] != "engineering_calculation"
        or calculation_followup["capability"] != "engineering-calculation"
        or calculation_followup["reviewPolicy"] != "calculation-contract"
        or calculation_followup["contractKind"] != "Conditional engineering reassessment"
        or calculation_followup["objectiveType"] != "engineering-calculation"
        or calculation_followup["responseKind"] != "conditional-engineering-reassessment"
        or calculation_followup["interactionMode"] != "expert-direct"
    ):
        failures.append("engineering calculation follow-up lost typed capability continuity")
    calculation_followup_messages = [
        {
            "role": "user",
            "text": (
                "A 6061-T6 aluminum cantilever is 200 mm long with a 40 mm by 10 mm section and a 1 kN tip load. "
                "Compare both orientations, estimate stress and deflection, and check a factor of safety of 2."
            ),
        },
        {
            "role": "assistant",
            "text": (
                "The 40 mm vertical orientation passes at 75 MPa with 0.73 mm tip deflection; "
                "the 10 mm vertical orientation fails at 300 MPa with 11.6 mm tip deflection."
            ),
        },
        {
            "role": "user",
            "text": (
                "Now add a 6 mm diameter hole 20 mm from the fixed end, centered through the 40 mm width, "
                "and assume continuous operation at 120 C. Does the conclusion still hold?"
            ),
        },
    ]
    calculation_followup_route = server.route_manager(
        calculation_followup_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    show_work_followup_messages = [
        {
            "role": "user",
            "text": (
                "A 6061-T6 aluminum cantilever bracket is 200 mm long with a rectangular 40 mm by 10 mm "
                "cross-section and a 1 kN tip load. Compare the two possible section orientations, estimate "
                "maximum bending stress and tip deflection for each, and determine which is safe with a factor "
                "of safety of 2. Show your work and state your assumptions."
            ),
        },
        {
            "role": "assistant",
            "text": "The 40 mm vertical orientation passes at 75 MPa; the 10 mm vertical orientation fails at 300 MPa.",
        },
        {
            "role": "user",
            "text": (
                "Now add a 6 mm diameter hole 20 mm from the fixed end, centered through the 40 mm width, "
                "and assume continuous operation at 120 C. Does the conclusion still hold?"
            ),
        },
    ]
    show_work_followup_frame = server.build_generic_intent_frame(
        show_work_followup_messages,
        cwd=str(ROOT),
    )
    show_work_followup_route = server.route_manager(
        show_work_followup_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    cross_domain_followups = {
        "electrical": [
            {
                "role": "user",
                "text": (
                    "A 24 V DC supply feeds a load through 8 m total round-trip cable with 8.3 milliohms per meter "
                    "resistance. At 15 A, calculate voltage drop, cable loss, load voltage, and check a 5 percent limit."
                ),
            },
            {
                "role": "assistant",
                "text": "The drop is 0.996 V and 4.15 percent, so it passes the 5 percent limit.",
            },
            {
                "role": "user",
                "text": "Now use 12 m total round-trip length and 18 A. Does the conclusion still hold?",
            },
        ],
        "thermal": [
            {
                "role": "user",
                "text": "At 80 W through a 0.60 C/W path to 25 C ambient, calculate temperature rise and check a 90 C limit.",
            },
            {
                "role": "assistant",
                "text": "The rise is 48 C and component temperature is 73 C, so it passes the 90 C limit.",
            },
            {
                "role": "user",
                "text": "Now add 0.15 C/W interface resistance and raise ambient to 40 C. Does the conclusion still hold?",
            },
        ],
        "fluid": [
            {
                "role": "user",
                "text": "A loop drops 18 kPa at 20 L/min while its pump provides 30 kPa. Check the pressure margin.",
            },
            {
                "role": "assistant",
                "text": "The pressure margin is 12 kPa, so the pump clears the stated demand.",
            },
            {
                "role": "user",
                "text": (
                    "Now increase flow to 25 L/min, use the square-law relationship, and add a 4 kPa filter drop. "
                    "Does the conclusion still hold?"
                ),
            },
        ],
    }
    cross_domain_routes = {
        name: server.route_manager(messages, cwd=str(ROOT), web_search="disabled")
        for name, messages in cross_domain_followups.items()
    }
    registered_calculator_audit_calls = {"count": 0}

    def unexpected_registered_calculator_audit(*_args, **_kwargs):
        registered_calculator_audit_calls["count"] += 1
        return {"ok": False, "verdict": "unsafe", "issues": [], "finalAnswer": ""}

    registered_calculator_answers = {
        name: server.apply_generic_reasoning_final_gate(
            messages,
            cross_domain_routes[name],
            "An intentionally incomplete model draft.",
            audit_fn=unexpected_registered_calculator_audit,
        )
        for name, messages in cross_domain_followups.items()
    }
    incomplete_followup = (
        "The prior conclusion needs another check because the hole and temperature change the bracket."
    )
    complete_followup = (
        "The prior conclusion is no longer proven as stated. The new 6 mm diameter hole is 20 mm from the fixed end "
        "and is centered through the 40 mm width; continuous operation at 120 C can reduce the material's allowable strength.\n\n"
        "The established baseline is 75 MPa maximum stress with 0.73 mm tip deflection for the 40 mm vertical orientation, "
        "and 300 MPa maximum stress with 11.6 mm tip deflection for the 10 mm vertical orientation. "
        "The 40 mm vertical orientation remains the only plausible candidate, but an exact revised factor "
        "of safety requires the hole direction and local stress concentration plus a verified 6061-T6 yield value at "
        "120 C.\n\nUntil those are checked, I cannot confirm that the earlier factor-of-safety conclusion still holds."
    )
    incomplete_followup_issues = server.deterministic_engineering_calculation_issues(
        calculation_followup_messages,
        calculation_followup_route,
        incomplete_followup,
    )
    complete_followup_issues = server.deterministic_engineering_calculation_issues(
        calculation_followup_messages,
        calculation_followup_route,
        complete_followup,
    )
    invented_followup = (
        "The prior conclusion still passes with a revised factor of safety of 1.4 because the 120 C yield allowable "
        "is 200 MPa and Kt = 3. The 6 mm hole remains 20 mm from the fixed end through the 40 mm width."
    )
    invented_followup_issues = server.deterministic_engineering_calculation_issues(
        calculation_followup_messages,
        calculation_followup_route,
        invented_followup,
    )
    followup_repair_prompt = server.generic_reasoning_repair_prompt(
        calculation_followup_messages,
        calculation_followup_route,
        incomplete_followup,
        incomplete_followup_issues,
    )
    followup_audit_prompt = server.generic_reasoning_audit_prompt(
        calculation_followup_messages,
        calculation_followup_route,
        incomplete_followup,
    )
    followup_verification_prompt = server.generic_reasoning_verification_prompt(
        calculation_followup_messages,
        calculation_followup_route,
        complete_followup,
    )
    followup_worker_prompt = server.build_intelligence_kernel_prompt(
        calculation_followup_messages,
        route=calculation_followup_route,
        cwd=str(ROOT),
    )
    conditional_boundary = server.conditional_engineering_reassessment_boundary_answer(
        calculation_followup_messages,
        calculation_followup_route,
    )
    long_prior_followup_messages = [
        {
            "role": "user",
            "text": "Compare two support layouts under the stated load and report stress, deflection, and margin.",
        },
        {
            "role": "assistant",
            "text": (
                "Background: " + ("This derivation establishes the governing equations and assumptions. " * 12) + "\n\n"
                "Case Alpha: maximum stress = 82 MPa and deflection = 1.4 mm, so it passes the stated limit.\n"
                "Case Beta: maximum stress = 164 MPa and deflection = 5.8 mm, so it fails the stated limit.\n"
                "Recommendation: choose Case Alpha because it is the only passing layout."
            ),
        },
        {
            "role": "user",
            "text": "Now increase the slot width to 8 mm and operate cyclically at 90 C. Does that conclusion still hold?",
        },
    ]
    long_prior_summary = server.conditional_reassessment_baseline_summary(
        long_prior_followup_messages,
    )
    long_prior_boundary = server.conditional_engineering_reassessment_boundary_answer(
        long_prior_followup_messages,
        calculation_followup_route,
    )
    followup_generation_profile = server.conversation_reasoning_generation_profile(
        calculation_followup_messages,
        calculation_followup_route,
    )
    followup_audit_profile = server.generic_reasoning_audit_profile(
        calculation_followup_route
    )
    electrical_boundary = server.conditional_engineering_reassessment_boundary_answer(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
    )
    exact_electrical_update = (
        "No. With 12 m at the same resistance per meter, cable resistance is 0.0996 ohm. "
        "At 18 A, voltage drop is 1.7928 V, cable loss is 32.27 W, load voltage is 22.2072 V, "
        "and the drop is 7.47 percent. The earlier pass becomes a fail because that exceeds the same 5 percent limit."
    )
    electrical_requested_output_keys = [
        item[0]
        for item in server.engineering_calculation_requested_outputs(
            cross_domain_followups["electrical"][0]["text"]
        )
    ]
    exact_electrical_gate = server.conditional_reassessment_candidate_gate(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
        exact_electrical_update,
    )
    wrong_electrical_arithmetic = server.deterministic_engineering_calculation_issues(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
        exact_electrical_update.replace("32.27 W", "32.23 W").replace(
            "cable loss is 32.23 W",
            "cable loss is 18^2 * 0.0996 = 32.23 W",
        ),
    )
    corrected_electrical_arithmetic = server.repair_literal_numeric_equations(
        exact_electrical_update.replace("32.27 W", "32.23 W").replace(
            "cable loss is 32.23 W",
            "cable loss is 18^2 * 0.0996 = 32.23 W",
        )
    )
    corrected_electrical_gate = server.conditional_reassessment_candidate_gate(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
        corrected_electrical_arithmetic.get("text") or "",
    )
    arithmetic_review_calls = {"review": 0, "repair": 0}

    def sound_corrected_arithmetic_review(prompt, *_args, **_kwargs):
        arithmetic_review_calls["review"] += 1
        if "18^2 * 0.0996 = 32.27 W" not in prompt:
            raise AssertionError("independent review did not receive the corrected complete draft")
        return {
            "payload": {"verdict": "sound", "issues": [], "notes": "Arithmetic and conclusion are consistent."},
            "model": "synthetic-sound-reviewer",
            "attemptedModels": ["synthetic-sound-reviewer"],
            "fallbackApplied": False,
            "retryApplied": False,
            "error": "",
            "durationMs": 1,
            "attemptDurationsMs": [1],
        }

    def unexpected_arithmetic_rewrite(*_args, **_kwargs):
        arithmetic_review_calls["repair"] += 1
        return {"text": "This rewrite should never run."}

    arithmetic_preserving_audit = server.run_generic_reasoning_audit(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
        exact_electrical_update.replace("32.27 W", "32.23 W").replace(
            "cable loss is 32.23 W",
            "cable loss is 18^2 * 0.0996 = 32.23 W",
        ),
        review_fn=sound_corrected_arithmetic_review,
        repair_generate_fn=unexpected_arithmetic_rewrite,
    )
    missing_electrical_outputs = server.deterministic_engineering_calculation_issues(
        cross_domain_followups["electrical"],
        cross_domain_routes["electrical"],
        "The 12 m cable has 0.0996 ohm resistance and 1.7928 V voltage drop at 18 A. "
        "The earlier pass becomes a fail because the drop is 7.47 percent, above the same 5 percent limit.",
    )
    invalid_reviewer_arithmetic = server.reasoning_review_payload_arithmetic_issues(
        {
            "verdict": "revise",
            "issues": [
                {
                    "claim": "The updated cable still passes.",
                    "kind": "calculation-error",
                    "reason": "The new ratio is (12 * 0.0083) * 18 / 24 = 0.936, so it remains below 5 percent.",
                }
            ],
            "notes": "",
        }
    )
    unit_exponent_not_literal_equation = server.deterministic_numeric_equation_issues(
        "Cable loss = 18 A^2 * 0.0996 ohm = 32.27 W."
    )
    latex_fraction_arithmetic = server.deterministic_numeric_equation_issues(
        r"Voltage drop = \frac{1.7928}{24} \times 100 = 7.47 percent."
    )
    outage_review_calls = {"count": 0}

    def unavailable_calculation_review(*_args, **_kwargs):
        outage_review_calls["count"] += 1
        return {
            "payload": {},
            "model": "synthetic-unavailable-reviewer",
            "attemptedModels": ["synthetic-unavailable-reviewer"],
            "fallbackApplied": False,
            "retryApplied": False,
            "error": "synthetic reviewer unavailable",
            "durationMs": 1,
            "attemptDurationsMs": [1],
        }

    safe_repair_calls = {"count": 0}

    def safe_outage_repair(*_args, **_kwargs):
        safe_repair_calls["count"] += 1
        return {"text": complete_followup}

    safe_outage_audit = server.run_generic_reasoning_audit(
        calculation_followup_messages,
        calculation_followup_route,
        incomplete_followup,
        review_fn=unavailable_calculation_review,
        repair_generate_fn=safe_outage_repair,
    )
    unsafe_repair_calls = {"count": 0}

    def unsafe_outage_repair(*_args, **_kwargs):
        unsafe_repair_calls["count"] += 1
        return {"text": invented_followup}

    unsafe_outage_audit = server.run_generic_reasoning_audit(
        calculation_followup_messages,
        calculation_followup_route,
        incomplete_followup,
        review_fn=unavailable_calculation_review,
        repair_generate_fn=unsafe_outage_repair,
    )
    if (
        not server.conditional_engineering_reassessment(calculation_followup_route)
        or show_work_followup_frame.get("domain") != "engineering_calculation"
        or show_work_followup_frame.get("actionType") != "reassess_engineering_conclusion_with_new_constraints"
        or (show_work_followup_route.get("capabilityPlan") or {}).get("id") != "engineering-calculation"
        or any(
            (candidate.get("intentFrame") or {}).get("domain") != "engineering_calculation"
            or (candidate.get("intentFrame") or {}).get("actionType") != "reassess_engineering_conclusion_with_new_constraints"
            or (candidate.get("capabilityPlan") or {}).get("id") != "engineering-calculation"
            for candidate in cross_domain_routes.values()
        )
        or registered_calculator_audit_calls["count"] != 0
        or not all(
            (cross_domain_routes[name].get("_engineeringCalculatorReceipt") or {}).get("gateStatus") == "pass"
            for name in cross_domain_followups
        )
        or not all(
            token in registered_calculator_answers["electrical"]
            for token in ("0.0996 ohm", "1.7928 V", "32.2704 W", "22.2072 V", "7.47 percent")
        )
        or not all(
            token in registered_calculator_answers["thermal"]
            for token in ("0.75 C/W", "60 C", "100 C", "updated result is a fail")
        )
        or not all(
            token in registered_calculator_answers["fluid"]
            for token in ("28.125 kPa", "32.125 kPa", "-2.125 kPa", "updated result is a fail")
        )
        or not server.calculation_contract_owns_semantic_correction(calculation_followup_route)
        or not incomplete_followup_issues
        or complete_followup_issues
        or not any(
            item.get("kind") == "conditional-reassessment-unsupported-precision"
            for item in invented_followup_issues
        )
        or "repairing one engineering follow-up" not in followup_repair_prompt
        or "Do not invent or estimate a material property" not in followup_repair_prompt
        or "Give one explicit result row or paragraph for every requested case" in followup_repair_prompt
        or "75 MPa" not in followup_audit_prompt
        or "75 MPa" not in followup_verification_prompt
        or "prior assistant result" not in followup_audit_prompt
        or "prior assistant result" not in followup_verification_prompt
        or "Do not invent or estimate a material property" not in followup_worker_prompt
        or "report every requested numerical result" in followup_worker_prompt
        or followup_generation_profile.get("think") != "low"
        or followup_generation_profile.get("numCtx", 0) > 5000
        or followup_audit_profile.get("reviewModel") != server.LOCAL_DEEP_REVIEW_MODEL
        or followup_audit_profile.get("reviewTimeout") != 90
        or followup_audit_profile.get("repairThink") != "low"
        or followup_audit_profile.get("repairNumCtx", 0) > 5000
        or followup_audit_profile.get("repairAttempts") != 2
        or safe_outage_audit.get("finalAnswer") != complete_followup
        or safe_outage_audit.get("auditUnavailableAccepted") is not True
        or safe_outage_audit.get("outageRepairApplied") is not True
        or safe_outage_audit.get("repairApplied") is not True
        or safe_repair_calls["count"] != 1
        or unsafe_outage_audit.get("finalAnswer")
        or unsafe_outage_audit.get("auditUnavailableAccepted") is True
        or unsafe_repair_calls["count"] != 2
        or outage_review_calls["count"] != 2
        or not all(value in conditional_boundary for value in ("6 mm", "20 mm", "40 mm", "120 C"))
        or not all(value in conditional_boundary for value in ("75 MPa", "300 MPa"))
        or "..." in conditional_boundary
        or "repair draft" in conditional_boundary.lower()
        or not all(value in long_prior_summary for value in ("Case Alpha", "82 MPa", "Case Beta", "164 MPa"))
        or "governing equations and assumptions" in long_prior_summary.lower()
        or not all(value in long_prior_boundary for value in ("8 mm", "90 C", "remaining load-bearing section", "operating temperature", "cycle-dependent"))
        or "..." in long_prior_boundary
        or exact_electrical_gate.get("accepted") is not True
        or electrical_requested_output_keys != ["voltage drop", "load voltage", "power loss"]
        or not any(item.get("kind") == "arithmetic-inconsistency" for item in wrong_electrical_arithmetic)
        or "18^2 * 0.0996 = 32.27 W" not in (corrected_electrical_arithmetic.get("text") or "")
        or len(corrected_electrical_arithmetic.get("corrections") or []) != 1
        or corrected_electrical_gate.get("accepted") is not True
        or "18^2 * 0.0996 = 32.27 W" not in (arithmetic_preserving_audit.get("finalAnswer") or "")
        or not (arithmetic_preserving_audit.get("literalArithmeticRepair") or {}).get("applied")
        or arithmetic_review_calls != {"review": 1, "repair": 0}
        or not any(item.get("kind") == "conditional-reassessment-output-omission" for item in missing_electrical_outputs)
        or not invalid_reviewer_arithmetic
        or unit_exponent_not_literal_equation
        or latex_fraction_arithmetic
        or "voltage-drop, loss, and load-voltage" not in electrical_boundary
        or "load-bearing section" in electrical_boundary
        or "earlier conclusion is no longer proven" not in conditional_boundary.lower()
        or "unresolved issue is" in conditional_boundary.lower()
    ):
        failures.append("conditional calculation follow-up lost its bounded reassessment contract")
    correction_calls = {"coach": 0, "audit": 0}

    def unexpected_quality_coach(*_args, **_kwargs):
        correction_calls["coach"] += 1
        return {"text": "The general Quality Coach should not own calculation correction."}

    def synthetic_calculation_audit(_messages, _route, _candidate, emit=None):
        correction_calls["audit"] += 1
        return {
            "ok": True,
            "verdict": "revise",
            "issues": [
                {
                    "claim": "The draft omitted the conditional decision boundary.",
                    "kind": "conditional-reassessment-no-conclusion",
                    "reason": "The prior conclusion must be reassessed under the new constraints.",
                }
            ],
            "finalAnswer": complete_followup,
            "notes": "Synthetic calculation ownership fixture.",
            "model": "synthetic-calculation-audit",
        }

    supervised_followup = server.supervise_answer_before_emit(
        calculation_followup_messages,
        calculation_followup_route,
        server.route_admin_topic(calculation_followup_messages, calculation_followup_route),
        "The hole changes things.",
        cwd=str(ROOT),
        web_search="disabled",
        quality_coach_fn=unexpected_quality_coach,
        reasoning_audit_fn=synthetic_calculation_audit,
    )
    if (
        correction_calls != {"coach": 0, "audit": 1}
        or supervised_followup != complete_followup
        or not calculation_followup_route.get("_calculationDeferredAnalyticalGaps")
    ):
        failures.append("calculation follow-up did not keep one semantic correction owner")
    calculation_messages = [
        {
            "role": "user",
            "text": (
                "A 6061-T6 aluminum cantilever is 200 mm long with a 40 mm by 10 mm section and a 1 kN tip load. "
                "Estimate maximum bending stress and tip deflection, then determine the factor of safety."
            ),
        }
    ]
    calculation_route = server.route_manager(
        calculation_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    calculation_tool_policy = server.conversation_only_reasoning_policy(
        calculation_messages,
        calculation_route,
    )
    calculation_audit_profile = server.generic_reasoning_audit_profile(calculation_route)
    incomplete_calculation_issues = server.deterministic_engineering_calculation_issues(
        calculation_messages,
        calculation_route,
        "Use sigma = Mc/I and delta = PL^3/(3EI); the stronger orientation is better.",
    )
    complete_calculation_issues = server.deterministic_engineering_calculation_issues(
        calculation_messages,
        calculation_route,
        (
            "**Maximum bending stress**\n\n"
            "\\[\\sigma_{\\max}=75\\;\\text{MPa}\\]\n\n"
            "- Max stress ≈ 75 MPa.\n\n"
            "**Tip deflection**\n\n"
            "\\[\\delta=0.72\\;\\text{mm}\\]\n\n"
            "Deflection ≈ 0.72 mm and FS ≈ 3.7, so this orientation passes the assumed yield criterion."
        ),
    )
    if (
        not any(item.get("kind") == "incomplete-engineering-calculation" for item in incomplete_calculation_issues)
        or complete_calculation_issues
    ):
        failures.append("engineering calculation completeness guard did not distinguish formulas from finished results")
    if (
        calculation_tool_policy.get("eligible") is not True
        or calculation_tool_policy.get("mode") != "conversation-only-local-reasoning"
    ):
        failures.append("self-contained engineering calculation did not stay on the local reasoning worker")
    if (
        calculation_audit_profile.get("reviewModel") != server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL
        or calculation_audit_profile.get("reviewTimeout") != 60
        or calculation_audit_profile.get("retryPrimary") is not False
        or calculation_audit_profile.get("repairAttempts") != 2
        or not server.reasoning_model_supports_strict_schema(server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL)
    ):
        failures.append("engineering calculation review lost its bounded schema-constrained reviewer profile")
    source_file_comparison = by_id["source-file-comparison-keyword-conflict"]
    if (
        source_file_comparison["domain"] != "local_file_evidence"
        or source_file_comparison["capability"] != "local-file-evidence"
        or source_file_comparison["mode"] != "capability-first"
        or source_file_comparison["rejectedLegacyDomain"] != "engineering_advisory"
        or source_file_comparison["contractKind"] != "Local file evidence"
    ):
        failures.append("explicit source-file comparison lost to filename keyword routing")
    suitability = by_id["engineering-suitability"]
    if (
        suitability["domain"] != "material_process_behavior"
        or suitability["capability"] != "engineering-advisory"
        or suitability["reviewPolicy"] != "engineering-contract"
        or suitability["contractKind"] != "Engineering advisory"
    ):
        failures.append("constrained material suitability question did not receive the engineering contract")
    state_preservation = by_id["engineering-state-preservation"]
    if (
        state_preservation["domain"] != "material_process_behavior"
        or state_preservation["capability"] != "engineering-advisory"
        or state_preservation["reviewPolicy"] != "engineering-contract"
        or state_preservation["contractKind"] != "Engineering advisory"
    ):
        failures.append("required-state-under-load question did not receive the engineering suitability contract")
    conflict = by_id["keyword-conflict-veto"]
    if (
        conflict["projectId"] != "general"
        or conflict["domain"] != "knowledge_comparison"
        or conflict["rejectedLegacyDomain"] != "engineering_power_conversion"
        or conflict["contractKind"] != "Expert comparison"
        or conflict["analyticalMode"] != "decision"
    ):
        failures.append("full-request conflict veto did not reject a keyword-only power-conversion route")

    new_topic_messages = [
        {"role": "user", "content": "Search eBay for a 100W JPT MOPA fiber laser."},
        {"role": "assistant", "content": "I checked current eBay listings."},
        {"role": "user", "content": "Would a graphite bed in a 3D printer perform well with chamber temperatures of 150C?"},
    ]
    new_topic_route = server.route_manager(new_topic_messages, cwd=str(ROOT), web_search="live")
    new_topic_prompt = server.build_intelligence_kernel_prompt(
        new_topic_messages,
        route=new_topic_route,
        cwd=str(ROOT),
    )
    scoped_new_topic = server.scope_messages_for_intent(
        new_topic_messages,
        new_topic_route.get("intentFrame"),
    )
    superseded_domain_switch_messages = [
        {
            "role": "user",
            "content": "Find the current manufacturer rating and official source for the fictional Acme QZ-991 motor.",
        },
        {
            "role": "assistant",
            "content": "I cannot verify that rating without a checked manufacturer source.",
        },
        {
            "role": "user",
            "content": "Never mind the rating or source. What controller voltage headroom should I use for a 72 V lightweight kart?",
        },
    ]
    superseded_domain_switch_route = server.route_manager(
        superseded_domain_switch_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    scoped_superseded_domain_switch = server.scope_messages_for_intent(
        superseded_domain_switch_messages,
        superseded_domain_switch_route.get("intentFrame"),
    )
    same_domain_replacement_messages = [
        {
            "role": "user",
            "content": (
                "Choose between a 48 V direct-drive BLDC and a 2:1 reduction drive for a 900 kg "
                "utility cart climbing a 15% grade at 25 km/h. The tire radius is 0.32 m, rolling "
                "resistance coefficient is 0.02, and drivetrain efficiency is 88%. Calculate the "
                "required power, wheel torque, motor torque, and controller current."
            ),
        },
        {
            "role": "assistant",
            "content": "The grade, speed, tire radius, and duty cycle control the drive sizing.",
        },
        {
            "role": "user",
            "content": "Ignore the prior 25 km/h speed and use 12 km/h for the same cart sizing.",
        },
    ]
    same_domain_replacement_route = server.route_manager(
        same_domain_replacement_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    scoped_same_domain_replacement = server.scope_messages_for_intent(
        same_domain_replacement_messages,
        same_domain_replacement_route.get("intentFrame"),
    )
    assumed_subtype_issues = server.deterministic_engineering_scope_issues(
        scoped_new_topic,
        new_topic_route,
        (
            "No, a standard graphite-coated aluminum bed will fail because the coating has a "
            "23 um/m-K expansion mismatch and only a consumer-grade composite is relevant."
        ),
    )
    original_generate = server.run_ollama_generate
    proportionate_calls = []

    def fake_suitability_review(_prompt, **kwargs):
        proportionate_calls.append(kwargs.get("model"))
        return {
            "text": json.dumps(
                {
                    "verdict": "revise",
                    "issues": [],
                    "missingConstraints": ["exact graphite grade and bed construction"],
                    "notes": "The material and the complete bed assembly need separate judgments.",
                    "finalAnswer": (
                        "Graphite itself is not the likely temperature limit at the stated 150 C, "
                        "but the complete bed still depends on its grade, heater, supports, electrical isolation, "
                        "surface durability, and mounting. Verify the exact construction through repeated thermal "
                        "cycles while measuring flatness before treating it as production-ready. "
                        "A 170 C ceiling is recommended."
                    ),
                }
            )
        }

    try:
        server.run_ollama_generate = fake_suitability_review
        proportionate_review = server.run_engineering_reasoning_audit(
            scoped_new_topic,
            new_topic_route,
            "No, a standard graphite-coated aluminum bed will fail at 150 C.",
        )
    finally:
        server.run_ollama_generate = original_generate
    followup_messages = [
        {"role": "user", "content": "Would a graphite bed work in a 150C printer chamber?"},
        {"role": "assistant", "content": "The graphite grade and support design control the answer."},
        {"role": "user", "content": "Would it still work if the chamber reached 170C?"},
    ]
    followup_route = server.route_manager(followup_messages, cwd=str(ROOT), web_search="live")
    scoped_followup = server.scope_messages_for_intent(
        followup_messages,
        followup_route.get("intentFrame"),
    )
    bounded_followup_messages = [
        {"role": "user", "content": "Search eBay for a 100W JPT MOPA fiber laser."},
        {"role": "assistant", "content": "I checked current marketplace candidates."},
        *followup_messages,
    ]
    bounded_followup_route = server.route_manager(
        bounded_followup_messages,
        cwd=str(ROOT),
        web_search="live",
    )
    scoped_bounded_followup = server.scope_messages_for_intent(
        bounded_followup_messages,
        bounded_followup_route.get("intentFrame"),
    )
    supplied_detail_followup = [
        {"role": "user", "content": "Would a cast aluminum tooling plate remain flat enough to use as a 180C heated bed?"},
        {"role": "assistant", "content": "The exact grade, geometry, heater, and mounting determine the answer."},
        {"role": "user", "content": "It is MIC-6, 500 x 500 x 8 mm, with a silicone heater bonded underneath and kinematic three-point mounts. Does that change your answer?"},
    ]
    supplied_detail_route = server.route_manager(
        supplied_detail_followup,
        cwd=str(ROOT),
        web_search="disabled",
    )
    supplied_detail_recovery = server.conditional_suitability_recovery_answer(
        supplied_detail_followup,
        supplied_detail_route,
    )
    supplied_detail_scope_issues = server.deterministic_engineering_scope_issues(
        supplied_detail_followup,
        supplied_detail_route,
        supplied_detail_recovery,
    )
    supplied_detail_safe_recovery = server.safe_engineering_advisory_recovery_answer(
        supplied_detail_followup,
        supplied_detail_route,
    )
    compact_temperature_question = new_topic_messages[-1]["content"]
    supplied_temperature_issues = server.unsupported_precision_claims_not_in_prompt(
        compact_temperature_question,
        "The bed assembly must be validated for sustained operation at 150C.",
    )
    invented_temperature_issues = server.unsupported_precision_claims_not_in_prompt(
        compact_temperature_question,
        "The bed assembly must be validated for sustained operation at 170C.",
    )
    invented_cycle_issues = server.unsupported_precision_claims_not_in_prompt(
        compact_temperature_question,
        "Run 5-10 thermal cycles before use.",
    )
    invented_duration_issues = server.unsupported_precision_claims_not_in_prompt(
        compact_temperature_question,
        "Hold the sample for two hours before measuring flatness.",
    )
    recovery_answer = server.safe_engineering_advisory_recovery_answer(
        scoped_new_topic,
        new_topic_route,
    )
    intrinsic_scope_messages = [
        *new_topic_messages[:2],
        {
            "role": "user",
            "content": (
                "Would a graphite bed in a 3D printer perform well with sustained chamber temperatures of 150 C? "
                "I mean the build-plate substrate itself, not a graphite coating."
            ),
        },
    ]
    intrinsic_scope_route = server.route_manager(
        intrinsic_scope_messages,
        cwd=str(ROOT),
        web_search="disabled",
    )
    scoped_intrinsic = server.scope_messages_for_intent(
        intrinsic_scope_messages,
        intrinsic_scope_route.get("intentFrame"),
    )
    intrinsic_takeover = (
        "Graphite may be suitable at 150 C, but that is not enough to approve the complete assembly.\n\n"
        "The controlling limit is the assembled stack, including its heater, adhesive, backing, and mounts.\n\n"
        "Thermal-cycle the complete assembly and measure flatness.\n\n"
        "What is the exact layer stack and backing?"
    )
    intrinsic_scope_issues = server.deterministic_engineering_scope_issues(
        scoped_intrinsic,
        intrinsic_scope_route,
        intrinsic_takeover,
    )
    intrinsic_review = server.run_engineering_reasoning_audit(
        scoped_intrinsic,
        intrinsic_scope_route,
        intrinsic_takeover,
    )
    intrinsic_recovery = str(intrinsic_review.get("finalAnswer") or "")
    intrinsic_prompt = server.build_intelligence_kernel_prompt(
        scoped_intrinsic,
        route=intrinsic_scope_route,
        cwd=str(ROOT),
    )
    categorical_intrinsic_drift = (
        "No, a bare graphite substrate is generally unsuitable for sustained operation at 150 C.\n\n"
        "In a typical printer it remains hot for hours or days, so long-term use will fail.\n\n"
        "Inspect it after use."
    )
    categorical_intrinsic_issues = server.deterministic_engineering_scope_issues(
        scoped_intrinsic,
        intrinsic_scope_route,
        categorical_intrinsic_drift,
    )
    categorical_intrinsic_review = server.run_engineering_reasoning_audit(
        scoped_intrinsic,
        intrinsic_scope_route,
        categorical_intrinsic_drift,
    )
    categorical_intrinsic_recovery = str(categorical_intrinsic_review.get("finalAnswer") or "")
    cross_domain_suitability = []
    for query in (
        "Would a ceramic fixture work under a sustained 300 C thermal cycle? Judge the complete assembly.",
        "Would a polymer bracket work under a sustained 5 kN load? Judge the complete assembly.",
        "Would this controller assembly work at 48 VDC and 30 A? Judge the complete assembly.",
    ):
        case_messages = [{"role": "user", "content": query}]
        case_route = server.route_manager(case_messages, cwd=str(ROOT), web_search="disabled")
        case_review = server.run_engineering_reasoning_audit(
            case_messages,
            case_route,
            "The named item may tolerate the stated condition.",
        )
        cross_domain_suitability.append(
            bool(
                (case_route.get("intentFrame") or {}).get("actionType") == "evaluate_operating_suitability"
                and case_review.get("modelReviewSkipped") is True
                and case_review.get("model") == "deterministic-conditional-suitability-recovery"
                and server.low_risk_suitability_answer_complete(
                    case_messages,
                    case_route,
                    case_review.get("finalAnswer") or "",
                )
            )
        )
    naturalized_suitability = server.naturalize_simple_suitability_format(
        "Engineering Judgment:\n\nGraphite may be suitable.\n\nPotential Issues & Mitigations:\n- Verify the assembly.\n\nClarification Needed:\nWhat exact grade is it?"
    )
    evidence_decision_completeness = (
        server.engineering_decision_evidence_completeness_p50_synthetic_check()
    )
    current_market_primary_evidence = (
        server.current_market_primary_product_evidence_p51_synthetic_check()
    )
    context_boundary = {
        "newTopicRelation": (new_topic_route.get("intentFrame") or {}).get("contextRelation"),
        "newTopicScope": (new_topic_route.get("intentFrame") or {}).get("contextScope"),
        "newTopicWorkerMessages": len(scoped_new_topic),
        "supersededDomainSwitchWorkerMessages": len(scoped_superseded_domain_switch),
        "supersededDomainSwitchLatestRetained": bool(
            len(scoped_superseded_domain_switch) == 1
            and "controller voltage headroom"
            in str(
                scoped_superseded_domain_switch[0].get("content")
                or scoped_superseded_domain_switch[0].get("text")
                or ""
            ).lower()
        ),
        "sameDomainReplacementHistoryRetained": bool(
            len(scoped_same_domain_replacement) == len(same_domain_replacement_messages)
            and "900 kg utility cart"
            in "\n".join(
                str(message.get("content") or message.get("text") or "").lower()
                for message in scoped_same_domain_replacement
            )
        ),
        "oldTopicAbsentFromPrompt": all(
            term not in new_topic_prompt.lower()
            for term in ("ebay", "jpt", "mopa", "fiber laser")
        ),
        "latestTopicPresentInPrompt": "graphite bed" in new_topic_prompt.lower(),
        "objectIdentityConstraintPresent": "preserve the construction and identity" in new_topic_prompt.lower(),
        "assumedSubtypeIssueKinds": sorted(
            {str(item.get("kind") or "") for item in assumed_subtype_issues}
        ),
        "proportionateReviewCalls": len(proportionate_calls),
        "proportionateReviewPassed": bool(
            proportionate_review.get("proportionateReview")
            and proportionate_review.get("finalVerificationPassed")
            and proportionate_review.get("modelReviewSkipped") is True
            and proportionate_review.get("model") == "deterministic-conditional-suitability-recovery"
            and "graphite" in str(proportionate_review.get("finalAnswer") or "").lower()
            and "150" in str(proportionate_review.get("finalAnswer") or "")
            and "170" not in str(proportionate_review.get("finalAnswer") or "")
        ),
        "legacyPrinterStatusBlocked": not bool(
            server.gated_printer_status_direct_answer(scoped_new_topic, new_topic_route)
        ),
        "compactTemperatureRetained": "150" in recovery_answer,
        "suppliedTemperatureAllowed": not supplied_temperature_issues,
        "inventedTemperatureRejected": any(
            "170" in str(item) for item in invented_temperature_issues
        ),
        "inventedCycleCountRejected": any(
            "cycle" in str(item).lower() for item in invented_cycle_issues
        ),
        "inventedWordDurationRejected": any(
            "two hours" in str(item).lower() for item in invented_duration_issues
        ),
        "reportHeadingsRemoved": bool(
            "Graphite may be suitable." in naturalized_suitability
            and "Verify the assembly." in naturalized_suitability
            and "What exact grade is it?" in naturalized_suitability
            and "Engineering Judgment" not in naturalized_suitability
            and "Potential Issues" not in naturalized_suitability
            and "Clarification Needed" not in naturalized_suitability
        ),
        "crossDomainSuitabilityRecovery": all(cross_domain_suitability),
        "evidenceDecisionCompleteness": evidence_decision_completeness,
        "currentMarketPrimaryEvidence": current_market_primary_evidence,
        "followupRelation": (followup_route.get("intentFrame") or {}).get("contextRelation"),
        "followupDomain": (followup_route.get("intentFrame") or {}).get("domain"),
        "followupAction": (followup_route.get("intentFrame") or {}).get("actionType"),
        "followupCapability": (followup_route.get("capabilityPlan") or {}).get("id"),
        "followupWorkerMessages": len(scoped_followup),
        "boundedFollowupWorkerMessages": len(scoped_bounded_followup),
        "boundedFollowupOldTopicAbsent": all(
            term not in "\n".join(
                str(message.get("content") or message.get("text") or "").lower()
                for message in scoped_bounded_followup
            )
            for term in ("ebay", "jpt", "mopa", "fiber laser")
        ),
        "suppliedDetailRecoveryPreserved": bool(
            "MIC-6" in supplied_detail_recovery
            and "500 x 500 x 8 mm" in supplied_detail_recovery
            and "180C" in supplied_detail_recovery
            and "three-point" in supplied_detail_recovery
            and "flatness tolerance" in supplied_detail_recovery
            and "What is the exact layer stack" not in supplied_detail_recovery
            and "500 x, 8 mm" not in supplied_detail_recovery
        ),
        "suppliedDetailScopeIssues": supplied_detail_scope_issues,
        "suppliedDetailSafeRecoveryMatches": supplied_detail_safe_recovery == supplied_detail_recovery,
        "intrinsicScopePreserved": bool(
            server.engineering_suitability_scope(scoped_intrinsic, intrinsic_scope_route) == "intrinsic"
            and len(scoped_intrinsic) == 1
            and any(
                item.get("kind") == "intrinsic-scope-overridden-by-assembly"
                for item in intrinsic_scope_issues
            )
            and intrinsic_review.get("model") == "deterministic-conditional-suitability-recovery"
            and intrinsic_review.get("modelReviewSkipped") is True
            and "150 C" in intrinsic_recovery
            and "answer is a qualified yes" in intrinsic_recovery
            and "what is the exact layer stack" not in intrinsic_recovery.lower()
            and "tinman explicitly narrowed" in intrinsic_prompt.lower()
            and "ebay" not in intrinsic_prompt.lower()
            and any(
                item.get("kind") == "unbounded-intrinsic-suitability-verdict"
                for item in categorical_intrinsic_issues
            )
            and any(
                item.get("kind") == "unsupported-service-duration-envelope"
                for item in categorical_intrinsic_issues
            )
            and categorical_intrinsic_review.get("model") == "deterministic-conditional-suitability-recovery"
            and "generally unsuitable" not in categorical_intrinsic_recovery.lower()
            and "hours or days" not in categorical_intrinsic_recovery.lower()
        ),
    }
    if not all(
        (
            context_boundary["newTopicRelation"] == "new-topic",
            context_boundary["newTopicScope"] == "latest-turn",
            context_boundary["newTopicWorkerMessages"] == 1,
            context_boundary["supersededDomainSwitchWorkerMessages"] == 1,
            context_boundary["supersededDomainSwitchLatestRetained"],
            context_boundary["sameDomainReplacementHistoryRetained"],
            context_boundary["oldTopicAbsentFromPrompt"],
            context_boundary["latestTopicPresentInPrompt"],
            context_boundary["objectIdentityConstraintPresent"],
            "assumed-object-subtype" in context_boundary["assumedSubtypeIssueKinds"],
            "unsupported-material-precision" in context_boundary["assumedSubtypeIssueKinds"],
            context_boundary["proportionateReviewCalls"] == 0,
            context_boundary["proportionateReviewPassed"],
            context_boundary["legacyPrinterStatusBlocked"],
            context_boundary["compactTemperatureRetained"],
            context_boundary["suppliedTemperatureAllowed"],
            context_boundary["inventedTemperatureRejected"],
            context_boundary["inventedCycleCountRejected"],
            context_boundary["inventedWordDurationRejected"],
            context_boundary["reportHeadingsRemoved"],
            context_boundary["crossDomainSuitabilityRecovery"],
            context_boundary["evidenceDecisionCompleteness"],
            context_boundary["currentMarketPrimaryEvidence"],
            context_boundary["followupRelation"] == "follow-up",
            context_boundary["followupDomain"] == "material_process_behavior",
            context_boundary["followupAction"] == "evaluate_operating_suitability",
            context_boundary["followupCapability"] == "engineering-advisory",
            context_boundary["followupWorkerMessages"] == len(followup_messages),
            context_boundary["boundedFollowupWorkerMessages"] == len(followup_messages),
            context_boundary["boundedFollowupOldTopicAbsent"],
            context_boundary["suppliedDetailRecoveryPreserved"],
            not context_boundary["suppliedDetailScopeIssues"],
            context_boundary["suppliedDetailSafeRecoveryMatches"],
            context_boundary["intrinsicScopePreserved"],
        )
    ):
        failures.append("turn context boundary did not isolate a new topic while preserving a true follow-up")

    output = {
        "status": "pass" if not failures else "fail",
        "kernel": report,
        "cases": cases,
        "contextBoundary": context_boundary,
        "failures": failures,
    }
    print(json.dumps(output, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
