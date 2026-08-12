#!/usr/bin/env python3
"""Focused P182 structured-review validity, latency, and binding regressions."""

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
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


messages = [{
    "role": "user",
    "text": (
        "A 6061-T6 rail is 420 mm long and warms from 20 C to 65 C while rigidly fixed at both ends; "
        "use E = 69 GPa and alpha = 23.6e-6/C. Calculate compressive thermal stress, "
        "released-end free expansion, and the limiting assumption."
    ),
}]
route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
route["_testRun"] = True
answer = (
    "Compressive thermal stress = 73.3 MPa in compression. "
    "Released-end free expansion = 0.446 mm. "
    "The limiting assumption is perfectly rigid end restraint with uniform 6061-T6 properties over the 20 C to 65 C change. "
    "Using the supplied 420 mm length, E = 69 GPa, and alpha = 23.6e-6/C, the substitutions are sigma = E alpha delta-T and delta-L = alpha L delta-T. "
    "Sanity check: a 45 C rise gives about 0.1% strain, so both magnitudes are consistent. "
    "The ideal calculation is the fully restrained and fully released bound, not a measured in-service value."
)
plan = server.answer_obligation_review_plan(messages, route, answer)
ledger_count = len((route.get("_answerObligationLedger") or {}).get("obligations") or [])
check(
    "controller-pre-resolves-before-review",
    ledger_count >= 10
    and 0 < len(plan["preResolvedIds"]) < ledger_count
    and len(plan["unresolvedIds"]) + len(plan["preResolvedIds"]) == ledger_count,
    json.dumps({"ledger": ledger_count, "pre": len(plan["preResolvedIds"]), "unresolved": len(plan["unresolvedIds"])}),
)

schema = server.generic_reasoning_decision_schema(plan["unresolvedIds"], ["e1", "e2"])
obligation_schema = schema["properties"]["obligations"]
check(
    "native-schema-binds-exact-count-and-id-domain",
    schema.get("additionalProperties") is False
    and obligation_schema.get("minItems") == len(plan["unresolvedIds"])
    and obligation_schema.get("maxItems") == len(plan["unresolvedIds"])
    and obligation_schema["items"]["properties"]["id"].get("enum") == plan["unresolvedIds"]
    and obligation_schema["items"]["properties"]["evidence"]["items"].get("enum") == ["e1", "e2"],
)

many_budget = server.reasoning_review_output_budget(650, 16)
few_budget = server.reasoning_review_output_budget(650, 2)
check(
    "output-budget-derived-and-bounded",
    few_budget < many_budget <= 1200 and few_budget >= 320,
    json.dumps({"few": few_budget, "many": many_budget}),
)

expected = ["obl-a", "obl-b", "obl-c"]
valid_rows = [
    {"id": "obl-a", "status": "satisfied", "evidence": ["e1"]},
    {"id": "obl-b", "status": "missing", "evidence": []},
    {"id": "obl-c", "status": "uncertain", "evidence": []},
]


def payload(rows=None):
    return {"verdict": "sound", "issues": [], "notes": "", "obligations": valid_rows if rows is None else rows}


binding_cases = {
    "partial": valid_rows[:2],
    "wrong": [dict(valid_rows[0], id="obl-x"), *valid_rows[1:]],
    "duplicate": [valid_rows[0], dict(valid_rows[0]), valid_rows[2]],
    "wrong-order": [valid_rows[1], valid_rows[0], valid_rows[2]],
}
binding_results = {
    name: server.validate_reasoning_review_payload(payload(rows), expected)
    for name, rows in binding_cases.items()
}
check(
    "partial-wrong-duplicate-and-order-fail-closed",
    all(not result.get("ok") for result in binding_results.values()),
    json.dumps(binding_results, sort_keys=True),
)

spans = [{"id": "e1", "text": "First exact result."}, {"id": "e2", "text": "Second exact result."}]
forged = payload([
    {"id": "obl-a", "status": "satisfied", "evidence": ["forged"]},
    *valid_rows[1:],
])
wrong_state = payload([
    valid_rows[0],
    {"id": "obl-b", "status": "missing", "evidence": ["e2"]},
    valid_rows[2],
])
check(
    "forged-or-wrong-state-evidence-fails",
    not server.validate_reasoning_review_evidence(forged, spans).get("ok")
    and not server.validate_reasoning_review_evidence(wrong_state, spans).get("ok"),
)

original_generate = server.run_ollama_generate
calls = []


def valid_generate(_prompt, **kwargs):
    calls.append(kwargs)
    return {
        "text": json.dumps(payload()),
        "doneReason": "stop",
        "evalCount": 91,
        "promptEvalCount": 230,
    }


server.run_ollama_generate = valid_generate
try:
    reviewed = server.run_reasoning_json_review(
        "review",
        server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL,
        "",
        timeout=60,
        num_predict=650,
        num_ctx=6000,
        retry_primary=False,
        required_obligation_ids=expected,
        pre_resolved_obligation_ids=["obl-controller"],
        evidence_spans=spans,
        stage="audit",
    )
finally:
    server.run_ollama_generate = original_generate
attempt = (reviewed.get("attemptMetadata") or [{}])[0]
check(
    "one-call-valid-review-preserves-metadata-no-hidden-retry",
    len(calls) == 1
    and calls[0].get("allow_final_retry") is False
    and reviewed.get("attemptCount") == 1
    and reviewed.get("payload", {}).get("obligations", [{}])[0].get("evidenceSpans") == ["First exact result."]
    and attempt.get("doneReason") == "stop"
    and attempt.get("evalCount") == 91
    and attempt.get("promptEvalCount") == 230
    and attempt.get("bindingStatus") == "pass"
    and attempt.get("rawTextChars", 0) > 0
    and len(attempt.get("rawTextSha256") or "") == 64,
    json.dumps(attempt, sort_keys=True),
)

truncated_calls = []


def truncated_generate(_prompt, **kwargs):
    truncated_calls.append(kwargs)
    return {"text": '{"verdict":"sound"', "doneReason": "length", "evalCount": 12}


server.run_ollama_generate = truncated_generate
try:
    truncated = server.run_reasoning_json_review(
        "review",
        server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL,
        "",
        timeout=60,
        num_predict=650,
        num_ctx=6000,
        retry_primary=False,
        required_obligation_ids=expected,
        evidence_spans=spans,
    )
finally:
    server.run_ollama_generate = original_generate
truncated_meta = truncated.get("attemptMetadata") or []
check(
    "truncated-json-is-classified-without-wrapper-fanout",
    not truncated.get("payload")
    and len(truncated_calls) == 1
    and all(call.get("allow_final_retry") is False for call in truncated_calls)
    and truncated_meta[0].get("errorClass") == "truncated-json",
    json.dumps(truncated_meta, sort_keys=True),
)

prose_calls = []


def prose_generate(_prompt, **kwargs):
    prose_calls.append(kwargs)
    return {"text": "The answer looks sound.", "doneReason": "stop"}


server.run_ollama_generate = prose_generate
try:
    prose = server.run_reasoning_json_review(
        "review", server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL, "", 60, 650, 6000,
        retry_primary=False, required_obligation_ids=expected, evidence_spans=spans,
    )
finally:
    server.run_ollama_generate = original_generate
check(
    "prose-output-cannot-become-a-decision",
    not prose.get("payload")
    and len(prose_calls) == 1
    and (prose.get("attemptMetadata") or [{}])[0].get("errorClass") == "invalid-json",
)

original_cancelled = server.live_run_cancelled
cancel_calls = []
server.live_run_cancelled = lambda _run_id: True
server.run_ollama_generate = lambda *_args, **_kwargs: cancel_calls.append("unexpected") or {}
try:
    cancelled = server.run_reasoning_json_review(
        "review", server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL, "gpt-oss-20b", 60, 650, 6000,
        retry_primary=True, required_obligation_ids=expected, evidence_spans=spans,
    )
finally:
    server.live_run_cancelled = original_cancelled
    server.run_ollama_generate = original_generate
check(
    "cancellation-launches-no-review-retry-or-fallback",
    cancel_calls == [] and cancelled.get("attemptCount") == 0 and not cancelled.get("payload"),
    cancelled.get("error") or "",
)

stale_route = dict(route)
stale_route["_answerObligationLedger"] = dict(route.get("_answerObligationLedger") or {})
stale_route["_answerObligationLedger"]["requestSha256"] = "stale"
fresh_plan = server.answer_obligation_review_plan(messages, stale_route, answer)
check(
    "stale-ledger-is-rebound-before-review",
    fresh_plan.get("requestSha256") == server.text_sha256(server.latest_user_text(messages))
    and fresh_plan.get("requestSha256") != "stale",
)

audit_calls = []
repair_calls = []
verification_calls = []
audit_route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
audit_route["_testRun"] = True
audit_plan = server.answer_obligation_review_plan(messages, audit_route, answer)
answer_spans = server.reasoning_candidate_evidence_spans(answer)


def exact_excerpt_for(obligation):
    text = str(obligation.get("text") or "").lower()
    preferred = next(
        (
            item["text"]
            for item in answer_spans
            if any(token in item["text"].lower() for token in server.re_words(text) if len(token) > 4)
        ),
        answer_spans[0]["text"],
    )
    return preferred


def sound_review(_prompt, *_args, **_kwargs):
    audit_calls.append("audit")
    return {
        "payload": {
            "verdict": "sound",
            "issues": [],
            "notes": "Bounded independent decision passed.",
            "obligations": [
                {
                    "id": row["id"],
                    "status": "satisfied",
                    "evidence": exact_excerpt_for(row),
                }
                for row in audit_plan["unresolvedRows"]
            ],
        },
        "model": "synthetic-compact-review",
        "attemptedModels": ["synthetic-compact-review"],
        "attemptCount": 1,
        "durationMs": 1,
        "attemptDurationsMs": [1],
    }


audit = server.run_generic_reasoning_audit(
    messages,
    audit_route,
    answer,
    review_fn=sound_review,
    repair_generate_fn=lambda *_args, **_kwargs: repair_calls.append("repair") or {},
    verification_review_fn=lambda *_args, **_kwargs: verification_calls.append("verification") or {},
)
check(
    "sound-original-uses-one-review-zero-repair-zero-verification",
    audit_calls == ["audit"]
    and repair_calls == []
    and verification_calls == []
    and audit.get("finalAnswer") == answer
    and audit.get("repairAttemptCount") == 0
    and audit.get("verificationAttemptCount") == 0
    and (audit.get("obligationReceipt") or {}).get("status") == "pass",
    json.dumps({
        "verdict": audit.get("verdict"),
        "receipt": (audit.get("obligationReceipt") or {}).get("status"),
        "missing": (audit.get("obligationReceipt") or {}).get("missingIds"),
        "repair": audit.get("repairAttemptCount"),
        "verification": audit.get("verificationAttemptCount"),
    }),
)

registered_route = {}
server.register_generic_reasoning_audit(registered_route, audit)
registered = registered_route.get("_genericReasoningAudit") or {}
check(
    "compact-provenance-keeps-protocol-and-binding-metadata",
    registered.get("reviewProtocolVersion") == server.GENERIC_REASONING_REVIEW_PROTOCOL_VERSION
    and registered.get("reviewAttemptCount") == 1
    and isinstance(registered.get("obligationReviewPlan"), dict)
    and all("rawText" not in row for row in registered.get("reviewAttemptMetadata") or []),
)

scientific_equations = {
    "unicode-times-braced-negative-exponent": (
        r"\(\sigma = -(69 \times 10^9)(23.6 \times 10^{-6})(45) = -73.3\,\mathrm{MPa}\)"
    ),
    "unicode-superscript-negative-exponent": (
        "sigma = -(69 × 10⁹) * (23.6 × 10⁻⁶) * 45 = -73.3 MPa"
    ),
    "ascii-x": "sigma = -(69 x 10^9) * (23.6 x 10^-6) * 45 = -73.3 MPa",
    "ascii-star": "sigma = -(69 * 10^9) * (23.6 * 10^-6) * 45 = -73.3 MPa",
    "parenthesized-product": "(-69e9) * (23.6e-6) * (45) = -7.33e7 Pa",
    "ascii-e-nonbreaking-hyphen-exponent": "2.5e‑6 * 40 = 1.0e‑4",
    "ascii-e-unicode-minus-exponent": "2.5e−6 * 40 = 1.0e−4",
}
scientific_results = {
    name: server.deterministic_numeric_equation_issues(equation)
    for name, equation in scientific_equations.items()
}
check(
    "scientific-notation-is-one-token-inside-full-equation-ast",
    all(not issues for issues in scientific_results.values()),
    json.dumps(scientific_results, sort_keys=True),
)

correct_equation = scientific_equations["unicode-times-braced-negative-exponent"]
wrong_equation = r"\(\sigma = -(69 \times 10^9)(23.6 \times 10^{-6})(45) = -61.0\,\mathrm{MPa}\)"
wrong_issues = server.deterministic_numeric_equation_issues(wrong_equation)
correct_repair = server.repair_literal_numeric_equations(correct_equation)
wrong_repair = server.repair_literal_numeric_equations(wrong_equation)
check(
    "correct-equation-is-stable-and-genuinely-wrong-equation-is-rejected",
    correct_repair.get("text") == correct_equation
    and correct_repair.get("corrections") == []
    and len(wrong_issues) == 1
    and wrong_issues[0].get("kind") == "arithmetic-inconsistency"
    and len(wrong_repair.get("corrections") or []) == 1
    and "-73.3" in str(wrong_repair.get("text") or ""),
    json.dumps({"issues": wrong_issues, "repair": wrong_repair}, sort_keys=True),
)

notation_constraints = ["E = 69 GPa", "alpha = 23.6e-6/C", "delta T = 45 C"]
notation_answer = (
    "E = 69 GPa; alpha = 23.6 × 10⁻⁶/C; delta T = 45 C. "
    "Compressive thermal stress = –73.3 MPa."
)
check(
    "notation-equivalence-and-unicode-sign-preserve-obligation-binding",
    server.missing_numeric_constraints(notation_constraints, notation_answer) == []
    and server._labeled_engineering_result_present(
        notation_answer,
        r"compressive\s+thermal\s+stress",
        r"(?:pa|kpa|mpa|gpa)",
    ),
    json.dumps(server.missing_numeric_constraints(notation_constraints, notation_answer)),
)

signed_constraint_messages = [
    {
        "role": "user",
        "text": "Compare two arbitrary architectures, cycling from -20 C to +80 C.",
    }
]
signed_constraints = server.analytical_extract_constraints(signed_constraint_messages)
signed_constraint_answer = (
    "The comparison covers the complete -20 C to +80 C operating interval."
)
check(
    "signed-operating-constraints-preserve-polarity-through-extraction",
    "-20 C" in signed_constraints
    and "+80 C" in signed_constraints
    and server.missing_numeric_constraints(
        signed_constraints,
        signed_constraint_answer,
    ) == [],
    json.dumps(
        {
            "constraints": signed_constraints,
            "missing": server.missing_numeric_constraints(
                signed_constraints,
                signed_constraint_answer,
            ),
        },
        sort_keys=True,
    ),
)

unicode_signed_cases = {
    "mathematical-minus": "Cycle arbitrary architectures from −20 C to +80 C.",
    "nonbreaking-hyphen": "Cycle arbitrary architectures from ‑20 C to +80 C.",
    "en-dash": "Cycle arbitrary architectures from –20 C to +80 C.",
}
unicode_signed_results = {}
for case_name, case_query in unicode_signed_cases.items():
    case_constraints = server.analytical_extract_constraints([{"role": "user", "text": case_query}])
    unicode_signed_results[case_name] = {
        "constraints": case_constraints,
        "missing": server.missing_numeric_constraints(
            case_constraints,
            "The full interval remains −20 C to +80 C.",
        ),
    }
check(
    "unicode-minus-variants-preserve-negative-constraint-polarity",
    all(
        "-20 C" in result["constraints"]
        and "+80 C" in result["constraints"]
        and result["missing"] == []
        for result in unicode_signed_results.values()
    ),
    json.dumps(unicode_signed_results, sort_keys=True),
)

generic_result_forms = {
    "html": "<strong>Peak load</strong>: 12.4 kN",
    "markdown": "**Peak load** = 12.4 kN",
    "table-inline-unit": "| Peak load | 12.4 kN | checked |",
    "table-unit-column": "| Peak load | 12.4 | kN | checked |",
    "table-multiple-values": "| Peak load | 10.1 kN | 12.4 kN | +22.8% |",
}
check(
    "typed-output-role-binds-across-html-markdown-and-table-representations",
    all(
        server._labeled_engineering_result_present(
            candidate,
            r"peak\s+load",
            r"(?:n|kn)",
        )
        for candidate in generic_result_forms.values()
    ),
    json.dumps(
        {
            name: server._labeled_engineering_result_present(
                candidate,
                r"peak\s+load",
                r"(?:n|kn)",
            )
            for name, candidate in generic_result_forms.items()
        },
        sort_keys=True,
    ),
)

dimensionless_table = "| Normalized strain | 1.25e‑3 | checked |"
check(
    "dimensionless-labeled-table-result-does-not-require-a-fictional-unit",
    server._labeled_engineering_result_present(
        dimensionless_table,
        r"normalized\s+strain",
        None,
    ),
    dimensionless_table,
)

table_answer = (
    "| Quantity | Value | Units |\n"
    "|---|---:|---|\n"
    "| Rail length | 420 | mm |\n"
    "| Temperature rise | 65 - 20 = 45 | C |\n"
    "| Young's modulus | 69 | GPa |\n"
    "| Expansion coefficient | 23.6 × 10⁻⁶ | /C |\n"
    "Intermediate thermal strain = 1.062 × 10⁻³ (dimensionless). "
    "Compressive thermal stress = -73.3 MPa. "
    "Released-end free expansion = 0.446 mm. "
    "The limiting assumption is uniform heating with constant properties and ideal end restraint."
)
table_route = server.route_manager(
    messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
table_plan = server.answer_obligation_review_plan(messages, table_route, table_answer)
numeric_constraint_ids = {
    row["id"]
    for row in (table_route.get("_answerObligationLedger") or {}).get("obligations") or []
    if row.get("kind") == "constraint" and row.get("constraintType") == "numeric"
}
check(
    "controller-resolves-representation-independent-table-constraints",
    numeric_constraint_ids
    and numeric_constraint_ids.issubset(set(table_plan.get("preResolvedIds") or [])),
    json.dumps({"numeric": sorted(numeric_constraint_ids), "pre": table_plan.get("preResolvedIds")}),
)

table_receipt = server.answer_obligation_completion_receipt(
    messages,
    table_route,
    table_answer,
    raw_rows=[],
    review_success=False,
)
check(
    "obligation-sidecar-remains-bound-to-the-exact-final-answer-hash",
    table_receipt.get("answerSha256") == server.text_sha256(table_answer.strip())
    and not server.answer_obligation_receipt_matches_final(
        table_route.get("_answerObligationLedger") or {},
        table_receipt,
        table_answer + "\nChanged after review.",
    ),
    json.dumps(
        {
            "receipt": table_receipt.get("answerSha256"),
            "changed": server.text_sha256(table_answer + "\nChanged after review."),
        },
        sort_keys=True,
    ),
)

immutable_route = dict(audit_route)
immutable_receipt = audit.get("obligationReceipt") or {}
immutable_route["_genericReasoningFinalAnswer"] = answer.strip()
immutable_route["_genericReasoningFinalSha256"] = immutable_receipt.get("answerSha256")
immutable_answer = server.exact_stored_obligation_answer(
    immutable_route,
    immutable_route.get("_answerObligationLedger") or {},
    immutable_receipt,
)
forged_route = dict(immutable_route)
forged_route["_genericReasoningFinalSha256"] = server.text_sha256("forged")
check(
    "post-review-mutation-bounds-while-exact-stored-answer-can-publish",
    not server.answer_obligation_receipt_matches_final(
        immutable_route.get("_answerObligationLedger") or {},
        immutable_receipt,
        answer + "\nPresentation mutation.",
    )
    and immutable_answer == answer.strip()
    and server.answer_obligation_receipt_matches_final(
        immutable_route.get("_answerObligationLedger") or {},
        immutable_receipt,
        immutable_answer,
    )
    and not server.exact_stored_obligation_answer(
        forged_route,
        forged_route.get("_answerObligationLedger") or {},
        immutable_receipt,
    ),
    json.dumps(
        {
            "mutated": server.text_sha256(answer + "\nPresentation mutation."),
            "receipt": immutable_receipt.get("answerSha256"),
            "restored": server.text_sha256(immutable_answer),
        },
        sort_keys=True,
    ),
)

wrong_direction_answer = (
    "Thermal strain = 1.062e-3. Thermal stress = 73.3 MPa in tension. "
    "Released-end free expansion = 0.446 mm."
)
right_direction_answer = wrong_direction_answer.replace(
    "73.3 MPa in tension", "-73.3 MPa in compression"
)
wrong_direction_issues = server.deterministic_engineering_calculation_issues(
    messages, table_route, wrong_direction_answer
)
right_direction_issues = server.deterministic_engineering_calculation_issues(
    messages, table_route, right_direction_answer
)
check(
    "requested-result-direction-is-preserved-through-final-gate",
    any(item.get("kind") == "requested-output-direction-conflict" for item in wrong_direction_issues)
    and not any(item.get("kind") == "requested-output-direction-conflict" for item in right_direction_issues),
    json.dumps({"wrong": wrong_direction_issues, "right": right_direction_issues}),
)

numeric_followup_messages = [
    messages[0],
    {"role": "assistant", "text": table_answer},
    {
        "role": "user",
        "text": (
            "Change only the upper temperature to 80 C. Recalculate both requested outputs and the thermal strain, "
            "and briefly compare each result with your prior values."
        ),
    },
]
numeric_followup_route = server.route_manager(
    numeric_followup_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
numeric_followup_frame = numeric_followup_route.get("intentFrame") or {}
numeric_followup_profile = server.generic_reasoning_audit_profile(
    numeric_followup_route,
    numeric_followup_messages,
    table_answer,
)
numeric_followup_ledger = server.build_answer_obligation_ledger(
    numeric_followup_messages,
    numeric_followup_route,
)
numeric_followup_outputs = {
    item.get("text")
    for item in numeric_followup_ledger.get("obligations") or []
    if item.get("kind") == "requested-output"
}
check(
    "closed-numeric-update-retains-owner-and-prior-output-obligations",
    numeric_followup_frame.get("domain") == "engineering_calculation"
    and numeric_followup_frame.get("actionType") == "recompute_with_superseded_constraint"
    and (numeric_followup_route.get("capabilityPlan") or {}).get("id") == "engineering-calculation"
    and numeric_followup_profile.get("reviewModel") == server.LOCAL_STRUCTURED_CALC_REVIEW_MODEL
    and numeric_followup_profile.get("reviewTimeout") == 60
    and {"stress", "strain", "released-end free expansion"}.issubset(numeric_followup_outputs),
    json.dumps({
        "frame": numeric_followup_frame,
        "outputs": sorted(item for item in numeric_followup_outputs if item),
        "reviewModel": numeric_followup_profile.get("reviewModel"),
        "reviewTimeout": numeric_followup_profile.get("reviewTimeout"),
    }, sort_keys=True),
)

unit_calculation_messages = [
    {
        "role": "user",
        "text": (
            "A cart travels 12 m in 6 s and has a mass of 18 kg. Calculate its average speed and momentum, "
            "show the unit conversions, and label both requested results."
        ),
    },
    {"role": "assistant", "text": "Average speed is 2 m/s; momentum is 36 kg m/s."},
    {
        "role": "user",
        "text": "Change only the travel time to 4 s and recompute both requested results.",
    },
]
unit_calculation_base_route = server.route_manager(
    unit_calculation_messages[:1],
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
unit_calculation_followup_route = server.route_manager(
    unit_calculation_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
unit_calculation_followup_frame = unit_calculation_followup_route.get("intentFrame") or {}
check(
    "unit-bearing-calculation-retains-owner-without-component-taxonomy-match",
    (unit_calculation_base_route.get("intentFrame") or {}).get("domain") == "engineering_calculation"
    and (unit_calculation_base_route.get("capabilityPlan") or {}).get("id") == "engineering-calculation"
    and unit_calculation_followup_frame.get("domain") == "engineering_calculation"
    and unit_calculation_followup_frame.get("actionType") == "recompute_with_superseded_constraint"
    and (unit_calculation_followup_route.get("capabilityPlan") or {}).get("id") == "engineering-calculation"
    and (unit_calculation_followup_frame.get("typedConstraintUpdate") or {}).get("supersession")
    == "replace-only-named-input",
    json.dumps(
        {
            "base": unit_calculation_base_route.get("intentFrame"),
            "followup": unit_calculation_followup_frame,
            "capability": (unit_calculation_followup_route.get("capabilityPlan") or {}).get("id"),
        },
        sort_keys=True,
    ),
)

tolerance_messages = [
    {
        "role": "user",
        "text": (
            "A tolerance rule rejects a measurement exactly on either limit. Decide whether a value on the upper "
            "limit passes, and explain the deciding rule."
        ),
    },
    {"role": "assistant", "text": "It does not pass because both limits are exclusive."},
    {
        "role": "user",
        "text": "Change the tolerance rule to inclusive at both limits and re-evaluate the decision.",
    },
]
tolerance_prior = server.build_generic_intent_frame(tolerance_messages[:1], cwd=str(ROOT))
tolerance_followup = server.build_generic_intent_frame(tolerance_messages, cwd=str(ROOT))
check(
    "named-categorical-update-retains-prior-decision-owner",
    tolerance_followup.get("domain") == tolerance_prior.get("domain")
    and tolerance_followup.get("routeCandidates") == tolerance_prior.get("routeCandidates")
    and tolerance_followup.get("actionType") == "reevaluate_with_superseded_constraint"
    and (tolerance_followup.get("typedConstraintUpdate") or {}).get("replacementKind") == "categorical",
    json.dumps({"prior": tolerance_prior, "followup": tolerance_followup}, sort_keys=True),
)

explicit_local_action_route = server.route_manager(
    [{"role": "user", "text": "Change server.py to add the requested response field."}],
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "explicit-artifact-mutation-still-routes-local-action",
    (explicit_local_action_route.get("intentFrame") or {}).get("domain") == "local_file_work"
    and (explicit_local_action_route.get("kernelDecision") or {}).get("selectedCapability") == "local_file_work"
    and (explicit_local_action_route.get("capabilityPlan") or {}).get("id") == "local-file-work",
    json.dumps(explicit_local_action_route.get("intentFrame") or {}, sort_keys=True),
)

categorical_followup_messages = [
    {
        "role": "user",
        "text": (
            "Under this rule, residents or students qualify for general admission, while special access requires both "
            "student status and a reservation. Does Maya, a resident without a reservation, qualify for each?"
        ),
    },
    {"role": "assistant", "text": "Maya qualifies for general admission but not special access."},
    {"role": "user", "text": "Change Maya from resident to student and reevaluate both outcomes."},
]
categorical_prior = server.build_generic_intent_frame(categorical_followup_messages[:1], cwd=str(ROOT))
categorical_followup = server.build_generic_intent_frame(categorical_followup_messages, cwd=str(ROOT))
check(
    "closed-categorical-update-retains-prior-typed-owner",
    categorical_followup.get("domain") == categorical_prior.get("domain")
    and categorical_followup.get("routeCandidates") == categorical_prior.get("routeCandidates")
    and categorical_followup.get("actionType") == "reevaluate_with_superseded_constraint"
    and (categorical_followup.get("typedConstraintUpdate") or {}).get("replacementKind") == "categorical",
    json.dumps({"prior": categorical_prior, "followup": categorical_followup}, sort_keys=True),
)

ambiguous_followup_messages = [
    {"role": "user", "text": "Apply the current eligibility rule to Maya and Rowan."},
    {"role": "assistant", "text": "Maya qualifies; Rowan does not."},
    {"role": "user", "text": "Change it to the other one and rerun."},
]
ambiguous_followup = server.build_generic_intent_frame(ambiguous_followup_messages, cwd=str(ROOT))
check(
    "ambiguous-input-replacement-clarifies-before-work",
    ambiguous_followup.get("domain") == "clarification"
    and ambiguous_followup.get("actionType") == "ask_one_focused_clarification"
    and (ambiguous_followup.get("typedConstraintUpdate") or {}).get("status") == "ambiguous",
    json.dumps(ambiguous_followup, sort_keys=True),
)

failed = [item for item in checks if item["status"] != "pass"]
print(json.dumps({
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not failed else 1)
