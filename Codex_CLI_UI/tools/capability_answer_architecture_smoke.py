#!/usr/bin/env python3
"""Focused smoke for capability selection and immutable final answers."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from answer_envelope import synthetic_envelope_check
from capability_registry import build_capability_plan, synthetic_registry_check
import server


def main() -> int:
    cases = [
        {
            "id": "runtime-capabilities",
            "frame": {"domain": "agent_runtime_capabilities"},
            "decision": {"mode": "deterministic-capability", "selectedCapability": "runtime_capability_introspection"},
            "expected": "runtime-capability-introspection",
        },
        {
            "id": "installation",
            "frame": {"domain": "local_installation_status"},
            "decision": {"mode": "deterministic-capability", "selectedCapability": "codex-cli-ui-local-agent"},
            "expected": "local-installation-status",
        },
        {
            "id": "bounded-specialist",
            "frame": {"domain": "bounded_specialist_capability"},
            "decision": {"mode": "deterministic-capability", "selectedCapability": "bounded_specialist_direct"},
            "expected": "bounded-specialist-capability",
        },
        {
            "id": "local-file",
            "frame": {"domain": "local_file_evidence"},
            "decision": {"mode": "capability-first", "selectedCapability": "local_file_retrieval"},
            "expected": "local-file-evidence",
        },
        {
            "id": "market",
            "frame": {"domain": "current_market_research"},
            "decision": {"mode": "model-first", "selectedCapability": "research-parts-reference"},
            "expected": "current-web-research",
        },
        {
            "id": "comparison",
            "frame": {"domain": "knowledge_comparison"},
            "decision": {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
            "expected": "expert-comparison",
        },
        {
            "id": "power-conversion",
            "frame": {"domain": "engineering_power_conversion"},
            "decision": {"mode": "model-first", "selectedCapability": "energy-power-research"},
            "expected": "engineering-power-conversion",
        },
        {
            "id": "engineering-advisory",
            "frame": {"domain": "engineering_advisory"},
            "decision": {"mode": "model-first", "selectedCapability": "printer-klipper-ops"},
            "expected": "engineering-advisory",
        },
        {
            "id": "klipper",
            "frame": {"domain": "klipper_config_migration"},
            "decision": {"mode": "capability-first", "selectedCapability": "printer-klipper-ops"},
            "expected": "klipper-config-migration",
        },
        {
            "id": "conversation",
            "frame": {"domain": "conversation"},
            "decision": {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
            "expected": "conversation-reasoning",
        },
        {
            "id": "knowledge-question",
            "frame": {"domain": "knowledge_question"},
            "decision": {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
            "expected": "conversation-reasoning",
        },
        {
            "id": "source-backed",
            "frame": {"domain": "source_resolution"},
            "decision": {"mode": "model-first", "selectedCapability": "source_backed_reasoning"},
            "expected": "source-backed-reasoning",
        },
        {
            "id": "technical-compatibility",
            "frame": {"domain": "technical_compatibility"},
            "decision": {"mode": "model-first", "selectedCapability": "source_backed_reasoning"},
            "expected": "source-backed-reasoning",
        },
        {
            "id": "local-product-action",
            "frame": {"domain": "local_product_action"},
            "decision": {"mode": "model-first", "selectedCapability": "local_code_agent"},
            "expected": "local-product-action",
        },
        {
            "id": "clarification",
            "frame": {"domain": "clarification"},
            "decision": {"mode": "deterministic-capability", "selectedCapability": "clarification"},
            "expected": "focused-clarification",
        },
    ]
    registry = synthetic_registry_check(cases)
    envelope = synthetic_envelope_check()
    conversation_plan = build_capability_plan(
        {"domain": "knowledge_question"},
        {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
    )
    power_plan = build_capability_plan(
        {"domain": "engineering_power_conversion"},
        {"mode": "model-first", "selectedCapability": "energy-power-research"},
    )
    source_plan = build_capability_plan(
        {"domain": "source_resolution"},
        {"mode": "model-first", "selectedCapability": "source_backed_reasoning"},
    )
    comparison_plan = build_capability_plan(
        {"domain": "knowledge_comparison"},
        {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
    )
    advisory_plan = build_capability_plan(
        {"domain": "engineering_advisory"},
        {"mode": "model-first", "selectedCapability": "conversation_reasoning"},
    )
    review_policy_ok = bool(
        conversation_plan.get("review_policy") == "reasoning-audit"
        and comparison_plan.get("review_policy") == "reasoning-audit"
        and power_plan.get("review_policy") == "calculation-contract"
        and advisory_plan.get("review_policy") == "engineering-contract"
        and source_plan.get("review_policy") == "source-fidelity-audit"
    )
    power_audit_calls = []
    power_candidate = "At 72 V, a 150 A battery-current ceiling is 10.8 kW of electrical input."

    def unexpected_power_audit(*_args, **_kwargs):
        power_audit_calls.append(True)
        return {"ok": False, "verdict": "unsafe", "issues": [], "finalAnswer": ""}

    power_final = server.apply_generic_reasoning_final_gate(
        [{"role": "user", "text": "What does a 150 A battery-current limit mean at 72 V?"}],
        {
            "capabilityPlan": power_plan,
            "kernelDecision": {"mode": "model-first"},
        },
        power_candidate,
        audit_fn=unexpected_power_audit,
    )
    calculation_review_boundary_ok = bool(
        power_final == power_candidate and not power_audit_calls
    )
    advisory_messages = [
        {
            "role": "user",
            "text": (
                "I want one local box to watch 10 printer cameras for spaghetti/failure "
                "detection and drive an HDMI command center. Would you build around Jetson "
                "Orin, an N100 mini PC, or a small RTX desktop?"
            ),
        }
    ]
    advisory_route = server.route_manager(
        advisory_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    advisory_comparison_names = [
        str(ref.get("name") or "").strip()
        for ref in advisory_route.get("intentFrame", {}).get("objectRefs", [])
        if isinstance(ref, dict) and ref.get("type") == "comparison-option"
    ]
    omitted_option_candidate = (
        "For ten cameras, choose Jetson Orin when power is the priority and a small RTX "
        "desktop when inference headroom is the priority. Validate both with recorded clips."
    )
    named_option_preservation_ok = bool(
        advisory_comparison_names == ["Jetson Orin", "N100 mini PC", "small RTX desktop"]
        and server.missing_intent_object_names(advisory_route, omitted_option_candidate)
        == ["N100 mini PC"]
        and not server.missing_intent_object_names(
            advisory_route,
            "Jetson Orin, an N100 mini PC, and a small RTX desktop each fit a different workload.",
        )
        and any(
            gap.get("kind") == "objective-object-mismatch"
            for gap in server.analytical_answer_gaps(
                advisory_messages,
                advisory_route,
                omitted_option_candidate,
                web_search="disabled",
            )
        )
    )
    advisory_coach_calls = []

    def unexpected_advisory_coach(*_args, **_kwargs):
        advisory_coach_calls.append(True)
        return {"text": "A second model rewrote the primary answer."}

    def synthetic_sound_engineering_audit(_messages, _route, draft, emit=None):
        return {
            "ok": True,
            "verdict": "sound",
            "issues": [],
            "missingConstraints": [],
            "notes": "Deterministic architecture-smoke approval.",
            "model": "synthetic-engineering-audit",
            "finalAnswer": draft,
            "repairApplied": False,
            "verificationCompleted": True,
            "durationMs": 0,
        }

    advisory_candidate = (
        "I would choose an RTX 4060 desktop when reliable inference across all ten cameras "
        "is the priority. The Jetson Orin is the low-power alternative, while the N100 is better "
        "used as the dashboard host. The RTX desktop uses lower power than Jetson Orin. "
        "It will always draw exactly 500 W. Validate with recorded "
        "clips and measure decode load, inference latency, dropped frames, thermals, and power."
    )
    advisory_final = server.supervise_answer_before_emit(
        advisory_messages,
        advisory_route,
        server.route_admin_topic(advisory_messages, advisory_route),
        advisory_candidate,
        web_search="disabled",
        quality_coach_fn=unexpected_advisory_coach,
        engineering_audit_fn=synthetic_sound_engineering_audit,
    )
    engineering_review_ownership_ok = bool(
        advisory_route.get("capabilityPlan", {}).get("review_policy") == "engineering-contract"
        and not advisory_coach_calls
        and "small RTX desktop" in advisory_final
        and "Jetson Orin" in advisory_final
        and "N100" in advisory_final
        and "RTX 4060" not in advisory_final
        and "500 W" not in advisory_final
        and "lower power than Jetson" not in advisory_final
        and "more power" in advisory_final
        and "second model" not in advisory_final.lower()
        and advisory_route.get("_supervisionStatus") == "pass"
    )
    metric_table = (
        "| Platform | Throughput |\n"
        "|---|---|\n"
        "| Edge system | 40‑50 TFLOPs |\n"
        "| Desktop system | 7.5‑12.6 TFLOPs |"
    )
    metric_table_claims = server.unsupported_precision_claims_not_in_prompt(
        advisory_messages[0]["text"],
        metric_table,
        [],
    )
    metric_table_review = {
        "gaps": [
            {
                "kind": "unsupported-technical-precision",
                "severity": "high",
            }
        ]
    }
    metric_table_guard_ok = bool(
        metric_table_claims
        and "TFLOPs" not in server.strip_unsupported_precision_claims(
            metric_table,
            metric_table_review,
            query_text=advisory_messages[0]["text"],
            evidence_claims=[],
        )
    )
    prefixed_precision = server.unsupported_precision_claims_not_in_prompt(
        advisory_messages[0]["text"],
        "Reduce FPS to 15‑20, use 720p, enable FP16, and expect a processor near 2 GHz.",
        [],
    )
    coherence_candidate = (
        "It gives you ample headroom.\n\n"
        "Tradeoffs\n\n"
        "1. 2. 3. 4. Use a measured prototype workload.\n\n"
        "Bottom line: Use the component class that meets the measured workload.\n\n3."
    )
    coherence_repaired = server.repair_sanitized_answer_coherence(coherence_candidate)
    sanitization_integrity_gaps = server.sanitized_answer_integrity_gaps(
        " ".join(["A complete engineering explanation with measured validation details."] * 20),
        "Use-case recap.\n\n3. Validation steps\n\nDocument each metric.",
    )
    coherence_guard_ok = bool(
        len(prefixed_precision) >= 4
        and coherence_repaired.startswith("Use the component class")
        and "It gives you" not in coherence_repaired
        and "1. 2. 3." not in coherence_repaired
        and not coherence_repaired.endswith("3.")
        and coherence_repaired.count("Use the component class") == 1
        and {gap.get("kind") for gap in sanitization_integrity_gaps}
        == {"sanitization-broken-enumeration", "sanitization-excessive-information-loss"}
    )
    clarification_route = server.route_manager(
        advisory_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    focused_clarification = (
        "Before I recommend one, could you tell me whether the ten cameras are USB webcams "
        "or IP cameras? The capture interface can change which host is the practical choice."
    )
    clarification_final = server.supervise_answer_before_emit(
        advisory_messages,
        clarification_route,
        server.route_admin_topic(advisory_messages, clarification_route),
        focused_clarification,
        web_search="disabled",
        quality_coach_fn=unexpected_advisory_coach,
        engineering_audit_fn=synthetic_sound_engineering_audit,
    )
    focused_clarification_ok = bool(
        server.answer_is_focused_clarification(focused_clarification)
        and clarification_final == focused_clarification
        and clarification_route.get("_focusedClarification") is True
        and clarification_route.get("_supervisionStatus") == "pass"
        and not advisory_coach_calls
    )
    safety_control_messages = [
        {
            "role": "user",
            "text": (
                "A local PLC controls pumps and heaters while a Linux supervisor can fail. "
                "How should control authority be divided so one failure cannot flood or overheat the process?"
            ),
        }
    ]
    safety_control_route = server.route_manager(
        safety_control_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    unsafe_safety_candidate = (
        "The PLC owns safety. Wire the emergency stop so it shorts the safety relay coils. "
        "Use normally-closed relays because they always cut power safely on power loss. "
        "This guarantees a single failure cannot flood or overheat the process."
    )
    safety_audit_calls = []

    def synthetic_safety_audit(_messages, _route, _draft, emit=None):
        safety_audit_calls.append(True)
        return {
            "ok": True,
            "verdict": "sound",
            "issues": [],
            "missingConstraints": [],
            "notes": "Synthetic model audit intentionally missed the deterministic violations.",
            "model": "synthetic-safety-audit",
        }

    safety_control_final = server.supervise_answer_before_emit(
        safety_control_messages,
        safety_control_route,
        server.route_admin_topic(safety_control_messages, safety_control_route),
        unsafe_safety_candidate,
        web_search="disabled",
        engineering_audit_fn=synthetic_safety_audit,
    )
    safety_followup_messages = [
        *safety_control_messages,
        {"role": "assistant", "text": safety_control_final},
        {
            "role": "user",
            "text": "What changes if the controller stores only 24 hours of schedules and forecasts arrive through Linux?",
        },
    ]
    safety_followup_recovery = server.safe_engineering_advisory_recovery_answer(
        safety_followup_messages,
        safety_control_route,
        reason="synthetic-followup",
    )
    followup_constraints = server.analytical_extract_constraints(safety_followup_messages)
    safety_issue_kinds = {
        item.get("kind")
        for item in server.deterministic_safety_control_issues(
            safety_control_messages,
            unsafe_safety_candidate,
        )
    }
    safety_control_contract_ok = bool(
        server.engineering_safety_control_request(safety_control_messages)
        and safety_control_route.get("capabilityPlan", {}).get("id") == "engineering-advisory"
        and safety_control_route.get("capabilityPlan", {}).get("review_policy") == "engineering-contract"
        and safety_control_route.get("intentFrame", {}).get("objectRefs")
        == [
            {"type": "control-actor", "name": "PLC"},
            {"type": "supervisory-actor", "name": "Linux"},
        ]
        and safety_audit_calls == [True]
        and {
            "unsafe-unverified-safety-topology",
            "undefined-energized-safe-state",
            "unsupported-single-fault-guarantee",
        }.issubset(safety_issue_kinds)
        and "PLC" in safety_control_final
        and "Linux" in safety_control_final
        and "FMEA" in safety_control_final
        and "fault injection" in safety_control_final
        and "shorts the safety relay" not in safety_control_final
        and server.safety_control_external_input_followup(safety_followup_messages)
        and "24 hours" in safety_followup_recovery
        and "PLC" in safety_followup_recovery
        and "Linux" in safety_followup_recovery
        and "valid-through" in safety_followup_recovery
        and "stale" in safety_followup_recovery
        and "degraded" in safety_followup_recovery
        and safety_followup_recovery != safety_control_final
        and any("24 hours" in item for item in followup_constraints)
        and not server.missing_numeric_constraints(followup_constraints, safety_followup_recovery)
        and safety_control_route.get("_supervisionStatus") == "bounded"
    )
    engineering_repair_messages = [
        {
            "role": "user",
            "text": "For a production CNC axis, compare closed-loop steppers and AC servos.",
        },
        {
            "role": "assistant",
            "text": "The decision depends on moving mass, torque at speed, and duty cycle.",
        },
        {
            "role": "user",
            "text": "What changes if it cuts only foam and plywood but runs 8 hours a day?",
        },
    ]
    engineering_repair_route = server.route_manager(
        engineering_repair_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    engineering_repair_outputs = iter(
        [
            {
                "text": json.dumps(
                    {
                        "verdict": "revise",
                        "issues": [
                            {
                                "claim": "Low cutting force makes commanded stepper current low.",
                                "kind": "unstated-control-mode",
                                "reason": "Drive current is controlled independently of instantaneous cutting load.",
                            }
                        ],
                        "missingConstraints": [],
                        "notes": "The mechanism is wrong.",
                    }
                )
            },
            {
                "text": (
                    "Use AC servos because they will always hold positioning error below 5 microns for the full 8-hour foam and plywood cycle."
                )
            },
            {
                "text": json.dumps(
                    {
                        "verdict": "revise",
                        "issues": [
                            {
                                "claim": "AC servos will always hold positioning error below 5 microns.",
                                "kind": "invented-threshold",
                                "reason": "The user supplied neither a required tolerance nor evidence for a universal servo result.",
                            }
                        ],
                        "missingConstraints": ["required positioning tolerance"],
                        "notes": "The first repair still forces an unsupported winner.",
                    }
                )
            },
            {
                "text": (
                    "The lighter foam and plywood cutting load helps the force budget, but running for 8 hours still makes thermal margin and torque at operating speed decisive. "
                    "Compare closed-loop steppers and AC servos from the required axis force, moving mass, reduction, torque-speed curves, enclosure temperature, and recovery from overload; do not infer commanded current from the material alone. "
                    "Calculate the worst-axis operating point, then run a representative cycle for 8 hours while logging following error, motor and drive temperatures, and any position loss against the required positioning tolerance."
                )
            },
            {
                "text": json.dumps(
                    {
                        "verdict": "sound",
                        "issues": [],
                        "missingConstraints": [],
                        "notes": "The answer preserves the operating constraints and corrects the control mechanism.",
                    }
                )
            },
        ]
    )
    engineering_repair_models = []
    original_engineering_generate = server.run_ollama_generate

    def fake_engineering_generate(_prompt, **kwargs):
        engineering_repair_models.append(kwargs.get("model"))
        return next(engineering_repair_outputs)

    try:
        server.run_ollama_generate = fake_engineering_generate
        engineering_repair_audit = server.run_engineering_reasoning_audit(
            engineering_repair_messages,
            engineering_repair_route,
            (
                "Foam and plywood need little torque, so the stepper current stays low. "
                "Keep acceleration below the motor current rating."
            ),
        )
    finally:
        server.run_ollama_generate = original_engineering_generate
    engineering_repair_answer = str(engineering_repair_audit.get("finalAnswer") or "")
    engineering_current_context_repair_ok = bool(
        server.engineering_advisory_model_first_contract_synthetic_check()
        and engineering_repair_route.get("capabilityPlan", {}).get("review_policy") == "engineering-contract"
        and engineering_repair_audit.get("repairApplied") is True
        and engineering_repair_audit.get("verificationCompleted") is True
        and engineering_repair_audit.get("repairAttemptCount") == 2
        and engineering_repair_audit.get("verificationAttemptCount") == 2
        and "8 hours" in engineering_repair_answer
        and "closed-loop steppers" in engineering_repair_answer
        and "AC servos" in engineering_repair_answer
        and "commanded current" in engineering_repair_answer
        and len(engineering_repair_models) == 5
        and not server.engineering_advisory_fast_direct_answer(
            engineering_repair_messages,
            engineering_repair_route,
        )
    )
    relationship_issues = server.deterministic_generic_reasoning_issues(
        "Education -> Interview Score\n"
        "Work Experience -> Interview Score\n"
        "Opened path: Education <- Interview Score -> Work Experience -> Salary"
    )
    relationship_gate_ok = bool(
        any(item.get("kind") == "relationship-direction-conflict" for item in relationship_issues)
    )
    servo_domain = server.engineering_advisory_domain(
        [
            {
                "role": "user",
                "text": "Why can increasing closed-loop bandwidth make a servo system less stable when transport delay is present?",
            }
        ]
    )
    servo_domain_ok = servo_domain == "engineering_systems"
    failure_detection_messages = [
        {
            "role": "user",
            "text": (
                "I want one local box to watch 10 printer cameras for spaghetti/failure "
                "detection and drive an HDMI command center."
            ),
        }
    ]
    actual_correction_messages = [
        {
            "role": "user",
            "text": "Your answer was wrong and missed the point. Please try again.",
        }
    ]
    failure_detection_route = server.route_manager(
        failure_detection_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    failure_detection_depth = server.manager_auto_deep_review_decision(
        failure_detection_messages,
        failure_detection_route,
        "fast",
        "manager",
    )
    correction_speech_act_ok = bool(
        not server.deep_review_trigger_terms(failure_detection_messages)
        and failure_detection_depth.get("effectiveDepth") == "fast"
        and failure_detection_depth.get("escalated") is False
        and server.deep_review_trigger_terms(actual_correction_messages)
        == ["Tinman is correcting a weak or failed answer"]
    )
    production_probability_messages = [
        {
            "role": "user",
            "text": (
                "A production line sends every part through two independent vision inspectors. "
                "What combined detection rate do they produce, and what assumption could make it optimistic?"
            ),
        }
    ]
    production_probability_route = server.route_manager(
        production_probability_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    production_probability_contract = server.task_contract(
        production_probability_messages,
        production_probability_route,
    )
    typed_contract_authority_ok = bool(
        production_probability_route.get("capabilityPlan", {}).get("id")
        == "conversation-reasoning"
        and production_probability_contract.get("kind") == "Model-first expert answer"
        and not server.is_cad_design_request(production_probability_messages)
        and server.is_direct_factual_question_without_artifact_action(
            production_probability_messages[0]["text"]
        )
        and server.is_cad_design_request(
            [
                {
                    "role": "user",
                    "text": "Can you design a CAD duct model and export a STEP file?",
                }
            ]
        )
    )
    source_messages = [
        {
            "role": "user",
            "text": "According to https://docs.python.org/3/library/asyncio-task.html, what does TaskGroup do when one child task fails?",
        }
    ]
    source_route = server.route_manager(
        source_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="live",
    )
    source_prompt = server.local_research_prompt(
        source_messages[0]["text"],
        source_route,
        [
            {
                "id": 1,
                "title": "Coroutines and Tasks",
                "url": "https://docs.python.org/3/library/asyncio-task.html",
                "score": 100,
                "fetched": True,
                "excerpt": "If a task fails, remaining tasks are cancelled and exceptions are grouped after completion.",
            }
        ],
        messages=source_messages,
    )
    source_prompt_ok = bool(
        "supplied URL as a document to inspect" in source_prompt
        and "Answer the exact question" in source_prompt
        and "shopping comparisons" not in source_prompt
        and "buy order" not in source_prompt
        and len(source_prompt) < 8000
    )
    escaped_audit = server.parse_model_json_object(
        r'{"verdict":"revise","issues":[],"finalAnswer":"\(X\rightarrow Y\)","notes":""}'
    )
    audit_parser_ok = bool(
        escaped_audit.get("verdict") == "revise"
        and "\\rightarrow" in str(escaped_audit.get("finalAnswer") or "")
        and server.GENERIC_REASONING_AUDIT_MODEL == server.LOCAL_DEEP_REVIEW_MODEL
        and server.GENERIC_REASONING_REPAIR_MODEL == server.LOCAL_DEEP_REVIEW_MODEL
        and server.reasoning_model_supports_strict_schema(server.GENERIC_REASONING_AUDIT_MODEL)
        and not server.reasoning_model_supports_strict_schema(server.GENERIC_REASONING_AUDIT_FALLBACK_MODEL)
    )
    audit_decision_prompt = server.generic_reasoning_audit_prompt(
        source_messages,
        source_route,
        "TaskGroup cancels the remaining child tasks after a child fails.",
    )
    audit_decision_only_ok = bool(
        "Do not rewrite the answer" in audit_decision_prompt
        and "Required keys: verdict, issues, notes" in audit_decision_prompt
        and "finalAnswer" not in audit_decision_prompt
    )
    verification_prompt = server.generic_reasoning_verification_prompt(
        source_messages,
        source_route,
        "A collider path is X -> C <- Y.",
    )
    reasoning_verification_ok = bool(
        "final cross-domain reasoning verifier" in verification_prompt
        and "arrowheads point into the collider" in verification_prompt
        and "Do not rewrite the answer" in verification_prompt
    )
    causal_rules = server.formal_reasoning_rules(
        [
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ]
    )
    formal_reasoning_rules_ok = bool(
        "X -> C <- U -> Y" in causal_rules
        and "Predictive strength is not proof" in causal_rules
        and "never reverses arrows" in causal_rules
    )
    formal_direction_issues = server.deterministic_generic_reasoning_issues(
        "The opened path is X <- C -> Y.",
        messages=[
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ],
    )
    formal_role_issues = server.deterministic_generic_reasoning_issues(
        "The causal diagram is X -> C <- Y.",
        messages=[
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ],
    )
    formal_path_issues = server.deterministic_generic_reasoning_issues(
        "Conditioning creates a backdoor-like directed path X -> C <- U -> Y, where U is an unmeasured confounder and the association is mediated by the opened collider.",
        messages=[
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ],
    )
    hiring_messages = [
        {
            "role": "user",
            "text": "Why does conditioning on a collider bias a causal estimate? Give me a hiring example.",
        }
    ]
    hiring_role_issues = server.deterministic_generic_reasoning_issues(
        "The hiring decision is a collider of interview score and job performance: InterviewScore -> Hire <- JobPerformance.",
        messages=hiring_messages,
    )
    latent_role_issues = server.deterministic_generic_reasoning_issues(
        "The graph is X -> U -> Y and X -> C <- U, so conditioning on C creates the bias.",
        messages=[
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ],
    )
    hiring_repair_prompt = server.generic_reasoning_repair_prompt(
        hiring_messages,
        {"intentFrame": {"domain": "knowledge_question"}},
        "InterviewScore -> Hire <- JobPerformance.",
        hiring_role_issues,
    )
    correct_contrast_issues = server.deterministic_generic_reasoning_issues(
        (
            "The opened graph path is X -> C <- U -> Y. It is not a backdoor path and not a directed causal path. "
            "U is not a confounder of X and Y because U does not cause X; the association is not mediated by C. "
            "The collider has arrows pointing into C, not X <- C -> Y."
        ),
        messages=[
            {
                "role": "user",
                "text": "Why does conditioning on a collider bias a causal estimate?",
            }
        ],
    )
    formal_reasoning_gate_ok = bool(
        any(item.get("kind") == "formal-direction-violation" for item in formal_direction_issues)
        and any(item.get("kind") == "formal-role-violation" for item in formal_role_issues)
        and any(item.get("kind") == "formal-path-classification" for item in formal_path_issues)
        and any(item.get("kind") == "formal-role-classification" for item in formal_path_issues)
        and any(item.get("kind") == "formal-mechanism-classification" for item in formal_path_issues)
        and any(item.get("kind") == "formal-path-directionality" for item in formal_path_issues)
        and any(item.get("kind") == "formal-natural-role-violation" for item in hiring_role_issues)
        and any(item.get("kind") == "formal-latent-role-violation" for item in latent_role_issues)
        and "InterviewScore -> Hire <- Qualification -> JobPerformance" in hiring_repair_prompt
        and "full directed path" not in hiring_repair_prompt
        and "opened non-causal collider path" in hiring_repair_prompt
        and not correct_contrast_issues
    )
    probability_messages = [
        {
            "role": "user",
            "text": (
                "Two independent inspectors each detect 90% of defects and falsely flag 5% of good parts. "
                "A part is rejected if either flags it. What are the detection and false-reject rates?"
            ),
        }
    ]
    probability_rules = server.formal_reasoning_rules(probability_messages)
    probability_issues = server.deterministic_generic_reasoning_issues(
        "Detection is 99% and false reject is 9.75%. Correlated errors make both rates less optimistic.",
        messages=probability_messages,
    )
    probability_missing_value_issues = server.deterministic_generic_reasoning_issues(
        "Detection is 95% and false reject is 5%.",
        messages=probability_messages,
    )
    formal_probability_gate_ok = bool(
        "99% detection" in probability_rules
        and "9.75% false reject" in probability_rules
        and any(item.get("kind") == "formal-dependence-direction" for item in probability_issues)
        and len(
            [
                item
                for item in probability_missing_value_issues
                if item.get("kind") == "formal-probability-calculation"
            ]
        )
        == 2
    )
    original_generate = server.run_ollama_generate
    audit_calls = []
    audit_outputs = iter(
        [
            {
                "text": json.dumps(
                    {
                        "verdict": "revise",
                        "issues": [
                            {
                                "claim": "X <- C -> Y",
                                "kind": "directionality",
                                "reason": "A collider has arrowheads pointing into C.",
                            }
                        ],
                        "finalAnswer": "Conditioning opens X <- C -> Y.",
                        "notes": "The graph is reversed.",
                    }
                )
            },
            {"text": "Conditioning on C opens association along X -> C <- U -> Y without reversing any arrow."},
            {"text": json.dumps({"verdict": "sound", "issues": [], "notes": ""})},
        ]
    )

    def fake_generate(_prompt, **kwargs):
        audit_calls.append(kwargs.get("model"))
        return next(audit_outputs)

    try:
        server.run_ollama_generate = fake_generate
        repaired_audit = server.run_generic_reasoning_audit(
            [
                {
                    "role": "user",
                    "text": "Why can controlling for a collider bias a causal estimate?",
                }
            ],
            {"intentFrame": {"domain": "knowledge_question"}},
            "Conditioning opens X <- C -> Y.",
        )
    finally:
        server.run_ollama_generate = original_generate
    generic_repair_contract_ok = bool(
        repaired_audit.get("repairApplied") is True
        and repaired_audit.get("verificationCompleted") is True
        and "X -> C <- U -> Y" in str(repaired_audit.get("finalAnswer") or "")
        and audit_calls == [
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_REPAIR_MODEL,
            server.GENERIC_REASONING_AUDIT_MODEL,
        ]
    )
    audit_timing_telemetry_ok = bool(
        isinstance(repaired_audit.get("durationMs"), int)
        and isinstance(repaired_audit.get("auditDurationMs"), int)
        and isinstance(repaired_audit.get("repairDurationMs"), int)
        and isinstance(repaired_audit.get("verificationDurationMs"), int)
        and len(repaired_audit.get("auditAttemptDurationsMs") or []) == 1
        and len(repaired_audit.get("repairAttemptDurationsMs") or []) == 1
        and len(repaired_audit.get("verificationAttemptDurationsMs") or []) == 1
    )
    iterative_calls = []
    iterative_outputs = iter(
        [
            {
                "text": json.dumps(
                    {
                        "verdict": "revise",
                        "issues": [
                            {
                                "claim": "Some A can be C.",
                                "kind": "set-logic",
                                "reason": "The premises exclude that overlap.",
                            }
                        ],
                        "finalAnswer": "Yes, some A can be C.",
                        "notes": "The conclusion contradicts the premises.",
                    }
                )
            },
            {"text": "Yes, some A can still be C."},
            {
                "text": json.dumps(
                    {
                        "verdict": "revise",
                        "issues": [
                            {
                                "claim": "Some A can be C.",
                                "kind": "set-logic",
                                "reason": "All A are B and no B are C.",
                            }
                        ],
                        "notes": "One contradiction remains.",
                    }
                )
            },
            {"text": "No. Every A is a B, and no B is a C, so no A can be a C."},
            {"text": json.dumps({"verdict": "sound", "issues": [], "notes": ""})},
        ]
    )

    def fake_iterative_generate(_prompt, **kwargs):
        iterative_calls.append(kwargs.get("model"))
        return next(iterative_outputs)

    try:
        server.run_ollama_generate = fake_iterative_generate
        iterative_audit = server.run_generic_reasoning_audit(
            [
                {
                    "role": "user",
                    "text": "If all A are B and no B are C, can any A be C?",
                }
            ],
            {"intentFrame": {"domain": "knowledge_question"}},
            "Yes, some A can be C.",
        )
    finally:
        server.run_ollama_generate = original_generate
    iterative_repair_contract_ok = bool(
        iterative_audit.get("repairApplied") is True
        and iterative_audit.get("repairAttemptCount") == 2
        and iterative_audit.get("verificationAttemptCount") == 2
        and str(iterative_audit.get("finalAnswer") or "").startswith("No.")
        and iterative_calls
        == [
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_REPAIR_MODEL,
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_REPAIR_MODEL,
            server.GENERIC_REASONING_AUDIT_MODEL,
        ]
    )
    fallback_calls = []
    fallback_outputs = iter(
        [
            {"text": "not valid JSON"},
            {"text": "still not valid JSON"},
            {"text": json.dumps({"verdict": "sound", "issues": [], "notes": "fallback worked"})},
        ]
    )

    def fake_fallback_generate(_prompt, **kwargs):
        fallback_calls.append(kwargs.get("model"))
        return next(fallback_outputs)

    try:
        server.run_ollama_generate = fake_fallback_generate
        fallback_review = server.run_reasoning_json_review(
            "Return JSON.",
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_FALLBACK_MODEL,
            timeout=30,
            num_predict=200,
            num_ctx=1000,
        )
    finally:
        server.run_ollama_generate = original_generate
    reasoning_fallback_ok = bool(
        fallback_review.get("payload", {}).get("verdict") == "sound"
        and fallback_review.get("fallbackApplied") is True
        and fallback_calls
        == [
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_FALLBACK_MODEL,
        ]
    )
    retry_calls = []
    retry_outputs = iter(
        [
            {"text": "not valid JSON"},
            {"text": json.dumps({"verdict": "sound", "issues": [], "notes": "retry worked"})},
        ]
    )

    def fake_retry_generate(_prompt, **kwargs):
        retry_calls.append(kwargs.get("model"))
        return next(retry_outputs)

    try:
        server.run_ollama_generate = fake_retry_generate
        retry_review = server.run_reasoning_json_review(
            "Return JSON.",
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_FALLBACK_MODEL,
            timeout=30,
            num_predict=200,
            num_ctx=1000,
        )
    finally:
        server.run_ollama_generate = original_generate
    reasoning_retry_ok = bool(
        retry_review.get("payload", {}).get("verdict") == "sound"
        and retry_review.get("retryApplied") is True
        and retry_review.get("fallbackApplied") is False
        and retry_calls
        == [server.GENERIC_REASONING_AUDIT_MODEL, server.GENERIC_REASONING_AUDIT_MODEL]
    )
    unavailable_calls = []

    def fake_unavailable_generate(_prompt, **kwargs):
        unavailable_calls.append(kwargs.get("model"))
        return {"text": "still not valid JSON"}

    try:
        server.run_ollama_generate = fake_unavailable_generate
        unavailable_audit = server.run_generic_reasoning_audit(
            [{"role": "user", "text": "Explain this difficult mechanism."}],
            {"intentFrame": {"domain": "knowledge_question"}},
            "An unverified draft.",
        )
    finally:
        server.run_ollama_generate = original_generate
    reasoning_fail_closed_ok = bool(
        unavailable_audit.get("ok") is False
        and unavailable_audit.get("verdict") == "revise"
        and not unavailable_audit.get("finalAnswer")
        and any(
            item.get("kind") == "reasoning-audit-unavailable"
            for item in unavailable_audit.get("issues") or []
        )
        and unavailable_calls
        == [
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_MODEL,
            server.GENERIC_REASONING_AUDIT_FALLBACK_MODEL,
        ]
    )
    final_owner_messages = [
        {
            "role": "user",
            "text": "Why is the square of every even integer also even?",
        }
    ]
    final_owner_route = server.route_manager(
        final_owner_messages,
        requested_profile="manager",
        web_search="disabled",
    )
    final_owner_seen = []

    def fake_final_owner_audit(_messages, _route, candidate, emit=None):
        final_owner_seen.append(candidate)
        return {
            "ok": True,
            "verdict": "sound",
            "issues": [],
            "finalAnswer": candidate,
            "notes": "",
            "model": "synthetic-final-owner",
        }

    final_owner_answer = server.supervise_answer_before_emit(
        final_owner_messages,
        final_owner_route,
        server.route_admin_topic(final_owner_messages, final_owner_route),
        "Write the even integer as n = 2k. Then n^2 = 4k^2 = 2(2k^2), so n^2 is even.",
        web_search="disabled",
        reasoning_audit_fn=fake_final_owner_audit,
    )
    reasoning_final_ownership_ok = bool(
        len(final_owner_seen) == 1
        and final_owner_seen[0] == final_owner_answer
        and server.reasoning_audit_owns_answer(final_owner_route, final_owner_answer)
        and final_owner_route.get("_genericReasoningFinalAnswer") == final_owner_answer
    )
    trimmed_text, trim_applied = server.safe_pre_send_trim(
        "One two three four five. Six seven eight nine ten. Eleven twelve thirteen.",
        10,
    )
    audited_word_budget = server.response_review_word_budget(
        [{"role": "user", "text": "Explain this difficult mechanism."}],
        {"kind": "General help"},
        {"mode": "conversation"},
        [],
        route={"capabilityPlan": {"review_policy": "reasoning-audit"}},
    )
    sentence_safe_polish_ok = bool(
        trim_applied
        and trimmed_text.endswith(".")
        and not trimmed_text.endswith("...")
        and audited_word_budget == 0
    )
    source_audit_prompt = server.source_fidelity_audit_prompt(
        source_messages[0]["text"],
        [
            {
                "id": 1,
                "title": "Coroutines and Tasks",
                "url": "https://docs.python.org/3/library/asyncio-task.html",
                "score": 100,
                "fetched": True,
                "excerpt": "Remaining tasks are cancelled and failures are combined in an ExceptionGroup after all tasks finish.",
            }
        ],
        "The first exception is propagated immediately.",
    )
    source_audit_prompt_ok = bool(
        "strict source-fidelity auditor" in source_audit_prompt
        and "aggregation behavior" in source_audit_prompt
        and "Use only the checked evidence" in source_audit_prompt
        and len(source_audit_prompt) < 9000
        and server.SOURCE_FIDELITY_AUDIT_MODEL == server.LOCAL_DEEP_REVIEW_MODEL
    )
    focused_excerpt = server.query_focused_excerpt(
        ("Navigation and unrelated introduction. " * 180)
        + "TaskGroup child failure behavior: remaining tasks are cancelled; after all tasks finish, exceptions are combined in an ExceptionGroup.",
        "What does TaskGroup do when one child task fails?",
        max_chars=700,
    )
    focused_excerpt_ok = bool(
        "remaining tasks are cancelled" in focused_excerpt
        and "ExceptionGroup" in focused_excerpt
        and len(focused_excerpt) <= 700
    )
    original_http_get_text = server.http_get_text
    try:
        server.http_get_text = lambda *_args, **_kwargs: {
            "text": (
                "<html><title>Task documentation</title><body>"
                + ("Navigation and unrelated introduction. " * 220)
                + "TaskGroup child failure behavior: remaining tasks are cancelled; "
                + "after all tasks finish, exceptions are combined in an ExceptionGroup."
                + "</body></html>"
            ),
            "contentType": "text/html",
        }
        extracted_page = server.extract_page_evidence(
            {
                "title": "Task documentation",
                "url": "https://docs.example.test/tasks",
                "snippet": "Direct source",
            },
            query="What does TaskGroup do when one child task fails?",
        )
    finally:
        server.http_get_text = original_http_get_text
    html_extraction_ok = bool(
        "remaining tasks are cancelled" in str(extracted_page.get("text") or "")
        and "ExceptionGroup" in str(extracted_page.get("text") or "")
        and len(str(extracted_page.get("text") or "")) <= 5000
    )
    unsupported_boundary = server.source_fidelity_boundary_answer(
        [{"title": "Task documentation", "url": "https://docs.example.test/tasks"}],
        {
            "verdict": "unsupported",
            "issues": [{"reason": "The checked excerpt does not establish exception behavior."}],
        },
    )
    unsupported_boundary_ok = bool(
        "couldn't verify" in unsupported_boundary
        and "does not establish exception behavior" in unsupported_boundary
        and "https://docs.example.test/tasks" in unsupported_boundary
    )
    aggregation_issues = server.deterministic_source_fidelity_issues(
        [
            {
                "excerpt": (
                    "After processing completes, failures are combined in an ExceptionGroup "
                    "and raised together."
                )
            }
        ],
        "Only the first failure is propagated.",
    )
    singular_aggregation_issues = server.deterministic_source_fidelity_issues(
        [{"excerpt": "Failures are combined in an ExceptionGroup and raised together."}],
        "The group re-raises that exception after every task has finished.",
    )
    aggregation_gate_ok = bool(
        any(item.get("kind") == "cardinality-aggregation-conflict" for item in aggregation_issues)
        and any(
            item.get("kind") == "cardinality-aggregation-conflict"
            for item in singular_aggregation_issues
        )
    )
    preserved_answer, preservation_issues = server.preserve_source_audited_answer(
        {
            "capabilityPlan": {"review_policy": "source-fidelity-audit"},
            "_sourceFidelityFinalAnswer": "Failures are combined and raised together.",
        },
        [{"excerpt": "Failures are combined and raised together."}],
        "Only the first failure is propagated.",
    )
    source_final_ownership_ok = bool(
        preserved_answer == "Failures are combined and raised together."
        and preservation_issues
    )
    passed = bool(
        registry.get("status") == "pass"
        and envelope.get("status") == "pass"
        and review_policy_ok
        and calculation_review_boundary_ok
        and engineering_review_ownership_ok
        and named_option_preservation_ok
        and focused_clarification_ok
        and safety_control_contract_ok
        and engineering_current_context_repair_ok
        and metric_table_guard_ok
        and coherence_guard_ok
        and relationship_gate_ok
        and servo_domain_ok
        and correction_speech_act_ok
        and typed_contract_authority_ok
        and source_prompt_ok
        and audit_parser_ok
        and audit_decision_only_ok
        and reasoning_verification_ok
        and generic_repair_contract_ok
        and audit_timing_telemetry_ok
        and iterative_repair_contract_ok
        and formal_reasoning_rules_ok
        and formal_reasoning_gate_ok
        and formal_probability_gate_ok
        and reasoning_fallback_ok
        and reasoning_retry_ok
        and reasoning_fail_closed_ok
        and reasoning_final_ownership_ok
        and sentence_safe_polish_ok
        and source_audit_prompt_ok
        and focused_excerpt_ok
        and html_extraction_ok
        and unsupported_boundary_ok
        and aggregation_gate_ok
        and source_final_ownership_ok
    )
    report = {
        "status": "pass" if passed else "fail",
        "registry": registry,
        "envelope": envelope,
        "reviewPolicies": {
            "passed": review_policy_ok,
            "conversation": conversation_plan.get("review_policy"),
            "comparison": comparison_plan.get("review_policy"),
            "engineeringPower": power_plan.get("review_policy"),
            "engineeringAdvisory": advisory_plan.get("review_policy"),
            "sourceBacked": source_plan.get("review_policy"),
            "calculationBoundaryPassed": calculation_review_boundary_ok,
            "engineeringReviewOwnershipPassed": engineering_review_ownership_ok,
            "namedOptionPreservationPassed": named_option_preservation_ok,
            "namedOptions": advisory_comparison_names,
            "focusedClarificationPassed": focused_clarification_ok,
            "safetyControlContractPassed": safety_control_contract_ok,
            "safetyControlIssueKinds": sorted(safety_issue_kinds),
            "engineeringCurrentContextRepairPassed": engineering_current_context_repair_ok,
            "engineeringRepairModels": engineering_repair_models,
            "metricTableEvidenceBoundaryPassed": metric_table_guard_ok,
            "sanitizedCoherencePassed": coherence_guard_ok,
        },
        "relationshipConsistencyGate": {
            "passed": relationship_gate_ok,
            "issues": relationship_issues,
        },
        "servoDomainBoundary": {
            "passed": servo_domain_ok,
            "domain": servo_domain,
        },
        "correctionSpeechActBoundary": {
            "passed": correction_speech_act_ok,
            "technicalFailureTerms": server.deep_review_trigger_terms(
                failure_detection_messages
            ),
            "actualCorrectionTerms": server.deep_review_trigger_terms(
                actual_correction_messages
            ),
        },
        "typedContractAuthority": {
            "passed": typed_contract_authority_ok,
            "contractKind": production_probability_contract.get("kind"),
            "capability": production_probability_route.get("capabilityPlan", {}).get("id"),
        },
        "sourcePromptBoundary": {
            "passed": source_prompt_ok,
            "promptChars": len(source_prompt),
        },
        "genericAuditBoundary": {
            "passed": audit_parser_ok,
            "model": server.GENERIC_REASONING_AUDIT_MODEL,
            "repairModel": server.GENERIC_REASONING_REPAIR_MODEL,
            "verificationPromptPassed": reasoning_verification_ok,
            "decisionOnlyPassed": audit_decision_only_ok,
            "repairContractPassed": generic_repair_contract_ok,
            "timingTelemetryPassed": audit_timing_telemetry_ok,
            "iterativeRepairContractPassed": iterative_repair_contract_ok,
            "formalRulesPassed": formal_reasoning_rules_ok,
            "formalGatePassed": formal_reasoning_gate_ok,
            "formalProbabilityGatePassed": formal_probability_gate_ok,
            "fallbackPassed": reasoning_fallback_ok,
            "retryPassed": reasoning_retry_ok,
            "failClosedPassed": reasoning_fail_closed_ok,
            "finalOwnershipPassed": reasoning_final_ownership_ok,
            "sentenceSafePolishPassed": sentence_safe_polish_ok,
            "escapedJsonParsed": bool(escaped_audit),
        },
        "sourceFidelityAuditBoundary": {
            "passed": source_audit_prompt_ok,
            "promptChars": len(source_audit_prompt),
            "model": server.SOURCE_FIDELITY_AUDIT_MODEL,
        },
        "queryFocusedEvidence": {
            "passed": focused_excerpt_ok,
            "excerptChars": len(focused_excerpt),
        },
        "queryFocusedHtmlExtraction": {
            "passed": html_extraction_ok,
            "excerptChars": len(str(extracted_page.get("text") or "")),
        },
        "unsupportedSourceBoundary": {
            "passed": unsupported_boundary_ok,
        },
        "sourceAggregationGate": {
            "passed": aggregation_gate_ok,
            "issues": aggregation_issues + singular_aggregation_issues,
        },
        "sourceFinalOwnership": {
            "passed": source_final_ownership_ok,
            "restored": preserved_answer,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
