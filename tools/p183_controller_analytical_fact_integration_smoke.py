#!/usr/bin/env python3
"""Focused P183 server integration checks for controller-owned analytical facts."""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": str(detail or "")})


def route(run_id):
    return {
        "_liveRunId": run_id,
        "capabilityPlan": {"registered": True, "id": "conversation-reasoning", "review_policy": "reasoning-audit"},
        "kernelDecision": {"mode": "model-first"},
        "intentFrame": {"domain": "conversation", "actionType": "answer_or_continue_conversation"},
    }


def planner(plan, calls):
    def run(_prompt, schema):
        calls.append(schema)
        return {
            "text": json.dumps(plan),
            "model": "fixture-schema-planner",
            "doneReason": "stop",
            "promptEvalCount": 181,
            "evalCount": 224,
            "providerReceipt": {
                "verified": True,
                "profile": "fixture-local",
                "provider": "ollama",
                "baseUrl": "http://127.0.0.1:11434",
                "networkMode": "loopback-only-model-provider; web-search-disabled",
            },
        }
    return run


with server.STRUCTURED_ANALYTICAL_FACT_RECEIPTS_LOCK:
    server.STRUCTURED_ANALYTICAL_FACT_RECEIPTS.clear()

provider_receipt = server.structured_analytical_local_provider_receipt("local-fast")
check(
    "production-planner-profile-is-free-local-loopback-ollama",
    provider_receipt.get("verified") is True
    and provider_receipt.get("provider") == "ollama"
    and provider_receipt.get("ossProvider") == "ollama"
    and provider_receipt.get("model") == "gpt-oss-20b"
    and provider_receipt.get("baseUrl") == "http://127.0.0.1:11434"
    and provider_receipt.get("paidCloudEligible") is False,
    provider_receipt,
)

base_request = (
    "A hydraulic cylinder has a 42 mm bore and 180 mm stroke with 7.5 L/min inlet flow. "
    "Calculate piston area and ideal full-stroke extension time during extension. "
    "Show unit conversions and label both requested results."
)
base_messages = [{"role": "user", "text": base_request}]
base_route = route("p183-fixture-base")
base_outputs = server.structured_analytical_output_obligations(base_messages, base_route)
base_sha = server.analytical_request_sha256(base_request)
active = lambda: {"kind": "active-request", "bindingSha256": base_sha}
base_plan = {
    "kind": "structured-analytical-fact-plan",
    "version": 1,
    "requestSha256": base_sha,
    "priorReceiptSha256": "",
    "changedInputs": [],
    "variables": [
        {"name": "diameter", "value": 42, "unit": "mm", "provenance": active()},
        {"name": "stroke", "value": 180, "unit": "mm", "provenance": active()},
        {"name": "flow", "value": 7.5, "unit": "L/min", "provenance": active()},
    ],
    "calculations": [
        {"name": "radius", "label": "Piston radius", "expression": "diameter / 2", "unit": "mm", "role": "intermediate", "obligationId": ""},
        {"name": "area", "label": "piston area", "expression": "pi * radius ** 2", "unit": "mm^2", "role": "requested-output", "obligationId": base_outputs[0]["id"]},
        {"name": "volume", "label": "Swept volume", "expression": "area * stroke", "unit": "mL", "role": "intermediate", "obligationId": ""},
        {"name": "extension_time", "label": "ideal full-stroke extension time during extension", "expression": "volume / flow", "unit": "s", "role": "requested-output", "obligationId": base_outputs[1]["id"]},
    ],
    "requiredOutputs": [
        {"id": base_outputs[0]["id"], "label": base_outputs[0]["label"], "result": "area", "unit": "mm^2"},
        {"id": base_outputs[1]["id"], "label": base_outputs[1]["label"], "result": "extension_time", "unit": "s"},
    ],
}
base_calls = []
base = server.run_structured_analytical_fact_preflight(
    base_messages,
    base_route,
    planner_fn=planner(base_plan, base_calls),
)
base_receipt = base.get("receipt") or {}
base_results = {row.get("name"): row for row in base_receipt.get("results") or []}
check(
    "standalone-multi-output-plan-passes-once",
    base.get("status") == "pass"
    and len(base_calls) == 1
    and base.get("modelCalls") == 1
    and base.get("toolCalls") == 0
    and [row.get("id") for row in base_receipt.get("requiredOutputs") or []]
    == [row.get("id") for row in base_outputs]
    and math.isclose(base_results.get("area", {}).get("value", 0), 1385.44236, rel_tol=1e-7)
    and math.isclose(base_results.get("extension_time", {}).get("value", 0), 1.994, rel_tol=1e-3),
    {"status": base.get("status"), "issues": base_receipt.get("issues"), "answer": base.get("answer")},
)
check(
    "planner-stage-timing-and-token-counts-survive",
    base_receipt.get("planner", {}).get("attemptCount") == 1
    and base_receipt.get("planner", {}).get("promptEvalCount") == 181
    and base_receipt.get("planner", {}).get("evalCount") == 224
    and isinstance(base.get("primaryDurationMs"), int),
    base_receipt.get("planner"),
)
obligation_receipt = server.bind_structured_analytical_fact_obligations(
    base_messages,
    base_route,
    base.get("answer"),
    base_receipt,
)
check(
    "verified-facts-bind-to-terminal-obligation-ledger",
    obligation_receipt.get("status") == "pass"
    and obligation_receipt.get("missingIds") == [],
    obligation_receipt,
)
check(
    "exact-answer-sidecar-publishes-and-mutation-does-not",
    bool(server.structured_analytical_fact_sidecar(base_route, base.get("answer"), "p183-fixture-base"))
    and not server.structured_analytical_fact_sidecar(base_route, base.get("answer") + " changed", "p183-fixture-base"),
)

follow_request = "Change only inlet flow to 9 L/min and recompute both requested results."
follow_messages = [
    {"role": "user", "text": base_request},
    {"role": "assistant", "text": base.get("answer"), "structuredAnalyticalFacts": base_receipt},
    {"role": "user", "text": follow_request},
]
follow_route = route("p183-fixture-follow")
follow_sha = server.analytical_request_sha256(follow_request)
follow_plan = copy.deepcopy(base_plan)
follow_plan["requestSha256"] = follow_sha
follow_plan["priorReceiptSha256"] = base_receipt.get("receiptSha256")
follow_plan["changedInputs"] = ["flow"]
for variable in follow_plan["variables"]:
    if variable["name"] == "flow":
        variable["value"] = 9
        variable["provenance"] = {"kind": "active-request", "bindingSha256": follow_sha}
    else:
        variable["provenance"] = {"kind": "prior-receipt", "bindingSha256": base_receipt.get("receiptSha256")}
follow_calls = []
follow = server.run_structured_analytical_fact_preflight(
    follow_messages,
    follow_route,
    planner_fn=planner(follow_plan, follow_calls),
)
follow_receipt = follow.get("receipt") or {}
follow_results = {row.get("name"): row for row in follow_receipt.get("results") or []}
check(
    "changed-input-reuses-verified-equations-and-recomputes",
    follow.get("status") == "pass"
    and follow_receipt.get("changedInputs") == ["flow"]
    and math.isclose(follow_results.get("area", {}).get("value", 0), base_results.get("area", {}).get("value", -1), rel_tol=1e-12)
    and math.isclose(follow_results.get("extension_time", {}).get("value", 0), 1.6625, rel_tol=1e-3)
    and len(follow_calls) == 1,
    {"status": follow.get("status"), "issues": follow_receipt.get("issues"), "results": follow_receipt.get("results")},
)

forged = copy.deepcopy(base_receipt)
forged["variables"][0]["value"] = 99
forged["receiptSha256"] = server.structured_analytical_fact_receipt_sha256(forged)
forged_calls = []
forged_messages = [
    {"role": "user", "text": base_request},
    {"role": "assistant", "text": base.get("answer"), "structuredAnalyticalFacts": forged},
    {"role": "user", "text": follow_request},
]
forged_result = server.run_structured_analytical_fact_preflight(
    forged_messages,
    route("p183-fixture-forged"),
    planner_fn=lambda *_args: forged_calls.append(True),
)
check(
    "forged-prior-receipt-cannot-enter-followup-planner",
    forged_result.get("status") == "not-applicable" and forged_calls == [],
    forged_result,
)

unsupported_plan = copy.deepcopy(base_plan)
unsupported_plan["calculations"][1]["expression"] = "sqrt(radius)"
unsupported_calls = []
unsupported = server.run_structured_analytical_fact_preflight(
    base_messages,
    route("p183-fixture-unsupported"),
    planner_fn=planner(unsupported_plan, unsupported_calls),
)
check(
    "unsupported-equation-bounds-without-retry",
    unsupported.get("status") == "bounded"
    and len(unsupported_calls) == 1
    and "without guessing" in unsupported.get("answer", "").lower()
    and any("unsupported expression" in issue for issue in (unsupported.get("receipt") or {}).get("issues") or []),
    unsupported,
)

wrong_graph = copy.deepcopy(follow_plan)
wrong_graph["calculations"][-1]["expression"] = "volume / flow * 2"
wrong_graph_result = server.run_structured_analytical_fact_preflight(
    follow_messages,
    route("p183-fixture-wrong-graph"),
    planner_fn=planner(wrong_graph, []),
)
check(
    "changed-input-cannot-swap-equation-graph",
    wrong_graph_result.get("status") == "bounded"
    and any("altered the verified equation" in issue for issue in (wrong_graph_result.get("receipt") or {}).get("issues") or []),
    (wrong_graph_result.get("receipt") or {}).get("issues"),
)

nonnumeric_calls = []
nonnumeric_messages = [{"role": "user", "text": "Compare event sourcing and CRUD for an audit-heavy inventory service, then recommend a direction."}]
nonnumeric = server.run_structured_analytical_fact_preflight(
    nonnumeric_messages,
    route("p183-fixture-nonnumeric"),
    planner_fn=lambda *_args: nonnumeric_calls.append(True),
)
check(
    "nonnumerical-control-never-enters-fact-planner",
    nonnumeric.get("status") == "not-applicable" and nonnumeric.get("modelCalls") == 0 and nonnumeric_calls == [],
    nonnumeric,
)

cancel_route = route("p183-fixture-cancel")
with server.LIVE_STEERING_LOCK:
    server.LIVE_ACTIVE_RUNS["p183-fixture-cancel"] = {"cancelled": True, "updatedAt": 10**18}
cancel_calls = []
cancelled = server.run_structured_analytical_fact_preflight(
    base_messages,
    cancel_route,
    planner_fn=lambda *_args: cancel_calls.append(True),
)
check(
    "cancellation-is-checked-before-planner-call",
    cancelled.get("status") == "cancelled" and cancel_calls == [],
    cancelled,
)
with server.LIVE_STEERING_LOCK:
    server.LIVE_ACTIVE_RUNS.pop("p183-fixture-cancel", None)

failed = [item for item in checks if item["status"] != "pass"]
print(json.dumps({
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checks": checks,
}, indent=2, sort_keys=True))
raise SystemExit(1 if failed else 0)
