#!/usr/bin/env python3
"""Focused regression for grounded, terminal runtime introspection."""

from __future__ import annotations

import io
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
        {"name": name, "passed": bool(passed), "detail": str(detail or "")[:1000]}
    )


class CaptureHandler:
    def __init__(self, run_id):
        self.current_run_id = run_id
        self.current_source_message_id = "p196-source-message"
        self.current_web_search = "disabled"
        self.current_cwd = str(ROOT)
        self.current_friendliness_level = "warm"
        self.current_humor_level = "light"
        self.current_run_steering_applied = False
        self.wfile = io.BytesIO()

    def send_response(self, *_args):
        return None

    def send_header(self, *_args):
        return None

    def end_headers(self):
        return None


def runtime_case(prompt, *, web_search="disabled", run_id="p196-runtime"):
    messages = [{"role": "user", "text": prompt}]
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web_search,
    )
    route["_liveRunId"] = run_id
    route["runtimeAccessLevel"] = "danger-full-access"
    route["runtimeCwd"] = str(ROOT)
    route["runtimeWebSearch"] = web_search
    route["runtimeCapabilitySnapshot"] = server.build_runtime_capability_snapshot(
        access_level="danger-full-access",
        cwd=str(ROOT),
        web_search=web_search,
    )
    result = server.execute_deterministic_capability(
        messages,
        route,
        accessLevel="danger-full-access",
        webSearch=web_search,
    )
    return messages, route, result


cases = (
    (
        "cwd",
        "What is the current working directory for this run?",
        "disabled",
        f"`{ROOT}` is the active working directory for this run.",
    ),
    (
        "project-directory-synonym",
        "What local project directory are you currently working in?",
        "disabled",
        f"`{ROOT}` is the active working directory for this run.",
    ),
    (
        "model",
        "Which local model are you using for this response?",
        "disabled",
        "No local language model is generating this response.",
    ),
    (
        "web-off",
        "Is web search enabled for this run?",
        "disabled",
        "No. The Web Search switch is off for this turn.",
    ),
    (
        "web-on",
        "Is web search enabled for this run?",
        "live",
        "Yes. The Web Search switch is on for this turn",
    ),
)

for index, (case_id, prompt, web_search, expected) in enumerate(cases, 1):
    run_id = f"p196-runtime-{index}"
    messages, route, result = runtime_case(
        prompt,
        web_search=web_search,
        run_id=run_id,
    )
    frame = route.get("intentFrame") or {}
    plan = route.get("capabilityPlan") or {}
    answer = str(result.get("answer") or "")
    receipts = result.get("sourceReceipts") or []
    provenance = server.source_provenance_contract(answer, receipts, run_id=run_id)
    check(
        f"{case_id}-routes-to-registered-runtime-owner",
        frame.get("domain") == "agent_runtime_capabilities"
        and frame.get("actionType") == "summarize_verified_runtime_capabilities"
        and plan.get("id") == "runtime-capability-introspection"
        and plan.get("registered") is True
        and server.material_unresolved_referent(messages, route) == ""
        and result.get("handled") is True
        and result.get("outcome") == "completed",
        {"frame": frame, "plan": plan, "result": result},
    )
    check(
        f"{case_id}-answers-exact-controller-state",
        expected in answer and len(receipts) == 1,
        {"answer": answer, "receipts": receipts},
    )
    check(
        f"{case_id}-has-run-and-answer-bound-runtime-proof",
        provenance.get("status") == "verified"
        and provenance.get("mayClaimGrounded") is True
        and provenance.get("verifiedReceiptCount") == 1
        and not provenance.get("issues"),
        provenance,
    )

messages, route, result = runtime_case(
    "Is web search enabled for this run?",
    run_id="p196-emission",
)
handler = CaptureHandler("p196-emission")
server.emit_typed_capability_response(
    handler,
    messages,
    route,
    {"testRun": True},
    result,
    cwd=str(ROOT),
    profile="manager",
    effective_profile="manager",
    reasoning_level="medium",
    web_search="disabled",
    manager_depth=1,
    friendliness_level="warm",
    humor_level="light",
    free_only_redirect=False,
)
events = [
    json.loads(line)
    for line in handler.wfile.getvalue().decode("utf-8").splitlines()
    if line.strip()
]
status = next((item for item in events if item.get("type") == "status"), {})
assistant = next((item for item in events if item.get("type") == "assistant"), {})
done = next((item for item in events if item.get("type") == "done"), {})
envelope = assistant.get("answerEnvelope") or {}
check(
    "verified-runtime-emission-is-model-free-and-terminal-complete",
    status.get("model") == ""
    and assistant.get("text") == result.get("answer")
    and envelope.get("status") == "complete"
    and (envelope.get("terminal_state") or {}).get("mayClaimComplete") is True
    and done.get("returnCode") == 0
    and not any(item.get("type") in {"command", "file", "tool"} for item in events),
    {
        "types": [item.get("type") for item in events],
        "model": status.get("model"),
        "envelope": envelope,
        "done": done,
    },
)
check(
    "verified-runtime-emission-completes-answer-obligations",
    (route.get("_answerObligationReceipt") or {}).get("status") == "pass"
    and (route.get("_answerObligationLedger") or {}).get("obligations") is not None,
    {
        "ledger": route.get("_answerObligationLedger"),
        "receipt": route.get("_answerObligationReceipt"),
    },
)

broad_messages, broad_route, broad_result = runtime_case(
    "Good morning! Will you briefly tell me what capabilities you have to help me?",
    run_id="p196-broad-emission",
)
broad_handler = CaptureHandler("p196-broad-emission")
server.emit_typed_capability_response(
    broad_handler,
    broad_messages,
    broad_route,
    {"testRun": True},
    broad_result,
    cwd=str(ROOT),
    profile="manager",
    effective_profile="manager",
    reasoning_level="medium",
    web_search="disabled",
    manager_depth=1,
    friendliness_level="warm",
    humor_level="light",
    free_only_redirect=False,
)
broad_events = [
    json.loads(line)
    for line in broad_handler.wfile.getvalue().decode("utf-8").splitlines()
    if line.strip()
]
broad_assistant = next(
    (item for item in broad_events if item.get("type") == "assistant"), {}
)
broad_done = next((item for item in broad_events if item.get("type") == "done"), {})
broad_envelope = broad_assistant.get("answerEnvelope") or {}
broad_receipt = broad_route.get("_answerObligationReceipt") or {}
check(
    "long-grounded-runtime-answer-remains-terminal-complete",
    len(str(broad_result.get("answer") or "")) > 420
    and str(broad_assistant.get("text") or "").startswith("Good morning, Tinman.")
    and broad_receipt.get("status") == "pass"
    and broad_receipt.get("satisfiedCount") == broad_receipt.get("obligationCount")
    and broad_envelope.get("status") == "complete"
    and (broad_envelope.get("terminal_state") or {}).get("mayClaimComplete") is True
    and broad_done.get("returnCode") == 0,
    {
        "answerLength": len(str(broad_result.get("answer") or "")),
        "receipt": broad_receipt,
        "envelope": broad_envelope,
        "done": broad_done,
    },
)

bad_route = dict(broad_route)
bad_ledger = server.build_answer_obligation_ledger(broad_messages, bad_route)
bad_route["_answerObligationLedger"] = bad_ledger
bad_ids = [item.get("id") for item in bad_ledger.get("obligations") or []]
bad_receipt = server.answer_obligation_completion_receipt(
    broad_messages,
    bad_route,
    broad_result.get("answer"),
    raw_rows=[
        {
            "id": obligation_id,
            "status": "satisfied",
            "evidenceSpans": ["evidence that is absent from the final answer"],
        }
        for obligation_id in bad_ids
    ],
    review_success=True,
    controller_validated_ids=bad_ids,
)
check(
    "long-span-repair-does-not-accept-unbound-evidence",
    bad_receipt.get("status") == "block"
    and bad_receipt.get("satisfiedCount") == 0
    and set(bad_receipt.get("missingIds") or []) == set(bad_ids),
    bad_receipt,
)

for mutation, mutate in (
    ("wrong-run", lambda receipt: {**receipt, "runId": "another-run"}),
    ("wrong-answer", lambda receipt: {**receipt, "claimDigest": "0" * 64}),
):
    receipt = mutate(dict((result.get("sourceReceipts") or [{}])[0]))
    provenance = server.source_provenance_contract(
        result.get("answer"),
        [receipt],
        run_id="p196-emission",
    )
    check(
        f"forged-{mutation}-runtime-proof-fails-closed",
        provenance.get("mayClaimGrounded") is False
        and provenance.get("status") == "unverified",
        provenance,
    )

decoy_messages = [
    {"role": "user", "text": "Which local model is best for Python development?"}
]
decoy_route = server.route_manager(
    decoy_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "model-comparison-decoy-remains-expert-question",
    (decoy_route.get("intentFrame") or {}).get("domain") == "knowledge_question"
    and (decoy_route.get("capabilityPlan") or {}).get("id")
    == "conversation-reasoning",
    {
        "frame": decoy_route.get("intentFrame"),
        "plan": decoy_route.get("capabilityPlan"),
    },
)

ambiguous_messages = [{"role": "user", "text": "What is the current setup?"}]
ambiguous_route = server.route_manager(
    ambiguous_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
check(
    "generic-current-setup-does-not-inherit-runtime-exemption",
    (ambiguous_route.get("intentFrame") or {}).get("domain")
    != "agent_runtime_capabilities",
    ambiguous_route.get("intentFrame"),
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
