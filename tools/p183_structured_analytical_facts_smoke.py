#!/usr/bin/env python3
"""P183 contract checks for request-bound structured analytical facts."""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from structured_calculation import (  # noqa: E402
    STRUCTURED_ANALYTICAL_FACT_PLAN_KIND,
    STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION,
    analytical_request_sha256,
    evaluate_structured_analytical_facts,
    structured_analytical_fact_plan_schema,
    verify_structured_analytical_fact_receipt,
)


checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail or "")})


base_request = (
    "A rail is 420 mm long. It spans from −20 C to +80 C; use E = 69 GPa and "
    "alpha = 23.6e-6/C. Calculate compressive thermal stress and released-end free expansion."
)
base_sha = analytical_request_sha256(base_request)
required_outputs = [
    {"id": "obl-stress", "label": "Compressive thermal stress", "unit": "MPa"},
    {"id": "obl-expansion", "label": "Released-end free expansion", "unit": "mm"},
]


def active_provenance(binding=base_sha):
    return {"kind": "active-request", "bindingSha256": binding}


base_plan = {
    "kind": STRUCTURED_ANALYTICAL_FACT_PLAN_KIND,
    "version": STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION,
    "requestSha256": base_sha,
    "priorReceiptSha256": "",
    "changedInputs": [],
    "variables": [
        {"name": "length", "value": 0.42, "unit": "m", "provenance": active_provenance()},
        {"name": "lower", "value": -20, "unit": "degC", "provenance": active_provenance()},
        {"name": "upper", "value": +80, "unit": "degC", "provenance": active_provenance()},
        {"name": "modulus", "value": 69, "unit": "GPa", "provenance": active_provenance()},
        {"name": "alpha", "value": 23.6e-6, "unit": "1/degC", "provenance": active_provenance()},
    ],
    "calculations": [
        {
            "name": "delta_temperature", "label": "Temperature change",
            "expression": "upper - lower", "unit": "degC", "role": "intermediate", "obligationId": "",
        },
        {
            "name": "strain", "label": "Intermediate thermal strain",
            "expression": "alpha * delta_temperature", "unit": "1", "role": "intermediate", "obligationId": "",
        },
        {
            "name": "stress", "label": "Compressive thermal stress",
            "expression": "-modulus * strain", "unit": "MPa", "role": "requested-output", "obligationId": "obl-stress",
        },
        {
            "name": "expansion", "label": "Released-end free expansion",
            "expression": "strain * length", "unit": "mm", "role": "requested-output", "obligationId": "obl-expansion",
        },
    ],
    "requiredOutputs": [
        {"id": "obl-stress", "label": "Compressive thermal stress", "result": "stress", "unit": "MPa"},
        {"id": "obl-expansion", "label": "Released-end free expansion", "result": "expansion", "unit": "mm"},
    ],
}
planner_receipt = {
    "attempted": True,
    "attemptCount": 1,
    "durationMs": 17,
    "model": "fixture-schema-planner",
    "schemaVersion": STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION,
    "doneReason": "stop",
    "toolCalls": 0,
    "cancelled": False,
    "outputSha256": "a" * 64,
    "profile": "fixture-local",
    "provider": "ollama",
    "baseUrl": "http://127.0.0.1:11434",
    "networkMode": "loopback-only-model-provider; web-search-disabled",
    "freeLocalVerified": True,
}

base_receipt = evaluate_structured_analytical_facts(
    base_plan,
    base_request,
    required_outputs=required_outputs,
    active_request=base_request,
    planner_receipt=planner_receipt,
)
results = {row["name"]: row for row in base_receipt.get("results") or []}
check(
    "signed-scientific-unit-scaled-plan-passes",
    base_receipt.get("status") == "pass"
    and math.isclose(results.get("strain", {}).get("value", 0), 0.00236, rel_tol=1e-9)
    and math.isclose(results.get("stress", {}).get("value", 0), -162.84, rel_tol=1e-9)
    and math.isclose(results.get("expansion", {}).get("value", 0), 0.9912, rel_tol=1e-9),
    base_receipt.get("issues"),
)
redundant_units = copy.deepcopy(base_plan)
next(item for item in redundant_units["calculations"] if item["name"] == "expansion")["expression"] = "strain * length * mm / mm"
redundant_receipt = evaluate_structured_analytical_facts(
    redundant_units,
    base_request,
    required_outputs=required_outputs,
    active_request=base_request,
)
check(
    "redundant-multiplicative-unit-tokens-normalize-before-safe-ast",
    redundant_receipt.get("status") == "pass"
    and redundant_receipt.get("expressionNormalization", {}).get("applied") is True,
    {"issues": redundant_receipt.get("issues"), "normalization": redundant_receipt.get("expressionNormalization")},
)
check(
    "required-outputs-remain-distinct-from-intermediate",
    [row.get("id") for row in base_receipt.get("requiredOutputs") or []]
    == ["obl-stress", "obl-expansion"]
    and all(row.get("result") != "strain" for row in base_receipt.get("requiredOutputs") or []),
    base_receipt.get("requiredOutputs"),
)
check(
    "verified-receipt-is-tamper-evident",
    verify_structured_analytical_fact_receipt(base_receipt),
    base_receipt.get("receiptSha256"),
)
tampered = copy.deepcopy(base_receipt)
tampered["requiredOutputs"][0]["value"] = 0
check(
    "conversational-author-cannot-overwrite-verified-result",
    not verify_structured_analytical_fact_receipt(tampered),
)
check(
    "planner-and-evaluator-timing-are-retained",
    base_receipt.get("planner", {}).get("attemptCount") == 1
    and base_receipt.get("planner", {}).get("durationMs") == 17
    and isinstance(base_receipt.get("timing", {}).get("evaluatorDurationMs"), int),
    {"planner": base_receipt.get("planner"), "timing": base_receipt.get("timing")},
)

follow_request = "Change only upper to +100 C and recompute the same two labeled outputs."
follow_sha = analytical_request_sha256(follow_request)
follow_plan = copy.deepcopy(base_plan)
follow_plan.update(
    {
        "requestSha256": follow_sha,
        "priorReceiptSha256": base_receipt.get("receiptSha256"),
        "changedInputs": ["upper"],
    }
)
for variable in follow_plan["variables"]:
    if variable["name"] == "upper":
        variable["value"] = 100
        variable["provenance"] = active_provenance(follow_sha)
    else:
        variable["provenance"] = {
            "kind": "prior-receipt",
            "bindingSha256": base_receipt.get("receiptSha256"),
        }
follow_receipt = evaluate_structured_analytical_facts(
    follow_plan,
    base_request + " " + follow_request,
    required_outputs=required_outputs,
    expected_changed_inputs=["upper"],
    active_request=follow_request,
    prior_receipt=base_receipt,
    planner_receipt=planner_receipt,
)
follow_results = {row["name"]: row for row in follow_receipt.get("results") or []}
check(
    "changed-input-invalidates-and-recomputes-exactly",
    follow_receipt.get("status") == "pass"
    and follow_receipt.get("changedInputs") == ["upper"]
    and math.isclose(follow_results.get("stress", {}).get("value", 0), -195.408, rel_tol=1e-9)
    and math.isclose(follow_results.get("expansion", {}).get("value", 0), 1.18944, rel_tol=1e-9),
    follow_receipt.get("issues"),
)

changed_equation = copy.deepcopy(follow_plan)
next(item for item in changed_equation["calculations"] if item["name"] == "expansion")["expression"] = "strain * length * 2"
changed_equation_receipt = evaluate_structured_analytical_facts(
    changed_equation,
    base_request + " " + follow_request,
    required_outputs=required_outputs,
    expected_changed_inputs=["upper"],
    active_request=follow_request,
    prior_receipt=base_receipt,
)
check(
    "changed-input-cannot-rewrite-verified-equation-graph",
    changed_equation_receipt.get("status") == "fail"
    and any("altered the verified equation" in issue for issue in changed_equation_receipt.get("issues") or []),
    changed_equation_receipt.get("issues"),
)

stale_values = copy.deepcopy(follow_plan)
next(item for item in stale_values["variables"] if item["name"] == "upper")["value"] = 80
stale_values["changedInputs"] = []
next(item for item in stale_values["variables"] if item["name"] == "upper")["provenance"] = {
    "kind": "prior-receipt", "bindingSha256": base_receipt.get("receiptSha256")
}
stale_values_receipt = evaluate_structured_analytical_facts(
    stale_values, base_request + " " + follow_request, required_outputs=required_outputs,
    expected_changed_inputs=["upper"], active_request=follow_request, prior_receipt=base_receipt,
)
check(
    "controller-change-contract-rejects-stale-values",
    stale_values_receipt.get("status") == "fail"
    and any("controller change contract" in issue for issue in stale_values_receipt.get("issues") or []),
    stale_values_receipt.get("issues"),
)

stale = copy.deepcopy(follow_plan)
stale["requestSha256"] = base_sha
stale_receipt = evaluate_structured_analytical_facts(
    stale, base_request + " " + follow_request, required_outputs=required_outputs,
    active_request=follow_request, prior_receipt=base_receipt,
)
check("stale-request-binding-fails-closed", stale_receipt.get("status") == "fail" and any("stale" in issue for issue in stale_receipt.get("issues") or []), stale_receipt.get("issues"))

undeclared = copy.deepcopy(follow_plan)
undeclared["changedInputs"] = []
undeclared_receipt = evaluate_structured_analytical_facts(
    undeclared, base_request + " " + follow_request, required_outputs=required_outputs,
    active_request=follow_request, prior_receipt=base_receipt,
)
check("undeclared-change-fails-closed", undeclared_receipt.get("status") == "fail" and any("change set" in issue for issue in undeclared_receipt.get("issues") or []), undeclared_receipt.get("issues"))

wrong_provenance = copy.deepcopy(follow_plan)
wrong_provenance["variables"][0]["provenance"] = active_provenance(follow_sha)
wrong_provenance_receipt = evaluate_structured_analytical_facts(
    wrong_provenance, base_request + " " + follow_request, required_outputs=required_outputs,
    active_request=follow_request, prior_receipt=base_receipt,
)
check("changed-plan-provenance-is-exact", wrong_provenance_receipt.get("status") == "fail" and any("provenance" in issue for issue in wrong_provenance_receipt.get("issues") or []), wrong_provenance_receipt.get("issues"))

ungrounded = copy.deepcopy(base_plan)
next(item for item in ungrounded["variables"] if item["name"] == "modulus")["value"] = 70
ungrounded_receipt = evaluate_structured_analytical_facts(ungrounded, base_request, required_outputs=required_outputs, active_request=base_request)
check("ungrounded-input-fails-closed", ungrounded_receipt.get("status") == "fail" and any("not grounded" in issue for issue in ungrounded_receipt.get("issues") or []), ungrounded_receipt.get("issues"))

unsupported = copy.deepcopy(base_plan)
next(item for item in unsupported["calculations"] if item["name"] == "stress")["expression"] = "__import__('os').system('id')"
unsupported_receipt = evaluate_structured_analytical_facts(unsupported, base_request, required_outputs=required_outputs, active_request=base_request)
check("unsupported-equation-fails-closed", unsupported_receipt.get("status") == "fail" and any("unsupported expression" in issue for issue in unsupported_receipt.get("issues") or []), unsupported_receipt.get("issues"))

wrong_dimension = copy.deepcopy(base_plan)
wrong_dimension["requiredOutputs"][0]["result"] = "expansion"
wrong_dimension_receipt = evaluate_structured_analytical_facts(wrong_dimension, base_request, required_outputs=required_outputs, active_request=base_request)
check("wrong-output-dimension-fails-closed", wrong_dimension_receipt.get("status") == "fail" and any("dimensions" in issue for issue in wrong_dimension_receipt.get("issues") or []), wrong_dimension_receipt.get("issues"))

intermediate = copy.deepcopy(base_plan)
intermediate["requiredOutputs"][0]["result"] = "strain"
intermediate_receipt = evaluate_structured_analytical_facts(intermediate, base_request, required_outputs=required_outputs, active_request=base_request)
check("intermediate-cannot-satisfy-requested-result", intermediate_receipt.get("status") == "fail" and any("role binding" in issue or "dimensions" in issue for issue in intermediate_receipt.get("issues") or []), intermediate_receipt.get("issues"))

missing = copy.deepcopy(base_plan)
missing["requiredOutputs"] = missing["requiredOutputs"][:1]
missing_receipt = evaluate_structured_analytical_facts(missing, base_request, required_outputs=required_outputs, active_request=base_request)
check("missing-required-output-fails-closed", missing_receipt.get("status") == "fail" and any("exactly match" in issue for issue in missing_receipt.get("issues") or []), missing_receipt.get("issues"))

tool_planner = {**planner_receipt, "toolCalls": 1}
tool_receipt = evaluate_structured_analytical_facts(base_plan, base_request, required_outputs=required_outputs, active_request=base_request, planner_receipt=tool_planner)
check("planner-tool-attempt-fails-closed", tool_receipt.get("status") == "fail" and any("no-tools" in issue for issue in tool_receipt.get("issues") or []), tool_receipt.get("issues"))

cloud_planner = {
    **planner_receipt,
    "provider": "openai",
    "baseUrl": "https://api.openai.com/v1",
    "networkMode": "cloud",
    "freeLocalVerified": False,
}
cloud_receipt = evaluate_structured_analytical_facts(
    base_plan,
    base_request,
    required_outputs=required_outputs,
    active_request=base_request,
    planner_receipt=cloud_planner,
)
check(
    "paid-or-cloud-planner-provider-fails-closed",
    cloud_receipt.get("status") == "fail"
    and any("free local loopback" in issue for issue in cloud_receipt.get("issues") or []),
    cloud_receipt.get("issues"),
)

missing_digest_planner = {**planner_receipt, "outputSha256": ""}
missing_digest_receipt = evaluate_structured_analytical_facts(
    base_plan, base_request, required_outputs=required_outputs,
    active_request=base_request, planner_receipt=missing_digest_planner,
)
check(
    "planner-output-provenance-is-required",
    missing_digest_receipt.get("status") == "fail"
    and any("no-tools schema attempt" in issue for issue in missing_digest_receipt.get("issues") or []),
    missing_digest_receipt.get("issues"),
)

dilution_request = "Use 1.50 mol/L stock to make 750 mL at 0.18 mol/L. Calculate stock volume and solvent volume."
dilution_sha = analytical_request_sha256(dilution_request)
dilution_outputs = [
    {"id": "stock", "label": "Stock volume", "unit": "mL"},
    {"id": "solvent", "label": "Solvent volume", "unit": "mL"},
]
dilution_plan = {
    "kind": STRUCTURED_ANALYTICAL_FACT_PLAN_KIND, "version": 1,
    "requestSha256": dilution_sha, "priorReceiptSha256": "", "changedInputs": [],
    "variables": [
        {"name": "stock_concentration", "value": 1.5, "unit": "mol/L", "provenance": active_provenance(dilution_sha)},
        {"name": "target_concentration", "value": 0.18, "unit": "mol/L", "provenance": active_provenance(dilution_sha)},
        {"name": "final_volume", "value": 0.75, "unit": "L", "provenance": active_provenance(dilution_sha)},
    ],
    "calculations": [
        {"name": "stock_volume", "label": "Stock volume", "expression": "target_concentration * final_volume / stock_concentration", "unit": "mL", "role": "requested-output", "obligationId": "stock"},
        {"name": "solvent_volume", "label": "Solvent volume", "expression": "final_volume - stock_volume", "unit": "mL", "role": "requested-output", "obligationId": "solvent"},
    ],
    "requiredOutputs": [
        {"id": "stock", "label": "Stock volume", "result": "stock_volume", "unit": "mL"},
        {"id": "solvent", "label": "Solvent volume", "result": "solvent_volume", "unit": "mL"},
    ],
}
dilution_receipt = evaluate_structured_analytical_facts(dilution_plan, dilution_request, required_outputs=dilution_outputs, active_request=dilution_request)
dilution_results = {row["name"]: row for row in dilution_receipt.get("results") or []}
check(
    "amount-and-volume-unit-scaling-is-generic",
    dilution_receipt.get("status") == "pass"
    and math.isclose(dilution_results.get("stock_volume", {}).get("value", 0), 90, rel_tol=1e-9)
    and math.isclose(dilution_results.get("solvent_volume", {}).get("value", 0), 660, rel_tol=1e-9),
    dilution_receipt.get("issues"),
)

non_plan = evaluate_structured_analytical_facts("Compare two qualitative architectures.", "Compare two qualitative architectures.")
check(
    "nonnumeric-nonplan-control-is-not-applicable",
    non_plan.get("status") == "not-applicable" and not non_plan.get("eligible") and not non_plan.get("mayClaimVerified"),
    non_plan,
)

schema = structured_analytical_fact_plan_schema(required_outputs)
check(
    "planner-schema-is-bounded-and-obligation-aware",
    schema.get("additionalProperties") is False
    and ((schema.get("properties") or {}).get("variables") or {}).get("maxItems") == 64
    and ((schema.get("properties") or {}).get("requiredOutputs") or {}).get("items", {}).get("properties", {}).get("id", {}).get("enum") == ["obl-stress", "obl-expansion"],
)

failed = [item for item in checks if not item["passed"]]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
