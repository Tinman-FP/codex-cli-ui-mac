#!/usr/bin/env python3
"""P250 adversaries for bound deterministic composition and terminal truth."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import answer_envelope
import server
from capability_execution import CapabilityExecutorRouter


checks = []


def check(name, passed, detail=None):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def contract_for(intent, domain):
    return {
        "kind": "deterministic-specialist-answer",
        "domains": [domain],
        "mustDo": [intent],
        "hardGate": False,
    }


def relevance_for(
    intent,
    domain,
    answer,
    *,
    run_id,
    concepts,
    owner_domain=None,
    bound=True,
    lineage=None,
):
    contract = contract_for(intent, domain)
    ownership = answer_envelope.build_template_ownership_receipt(
        receipt_id=f"template-{run_id}",
        run_id=run_id,
        template_id=f"deterministic:{domain}",
        latest_user_intent=intent,
        task_contract=contract,
        owner_domain=owner_domain or domain,
        supported_domains=[owner_domain or domain],
        concepts=concepts,
        turn_lineage_digest=(lineage or {}).get("lineageDigest") or "",
        **({"bound_output": answer} if bound else {}),
    )
    return answer_envelope.answer_relevance_contract(
        answer,
        run_id=run_id,
        latest_user_intent=intent,
        intent_domain=domain,
        task_contract=contract,
        template_ownership=ownership,
        turn_lineage=lineage or {},
        require_template_ownership=True,
    )


positive_cases = (
    (
        "thermal-design",
        "Which thermal limit should the enclosure retain?",
        "Retain the enclosure thermal limit and verify it under the expected load.",
    ),
    (
        "release-operations",
        "Which rollback signal should the release use?",
        "Use the release error-rate signal to trigger rollback.",
    ),
    (
        "inventory-policy",
        "Which inventory threshold should the policy retain?",
        "Retain the inventory threshold that preserves the stated reserve.",
    ),
)
positive_receipts = []
for index, (domain, intent, answer) in enumerate(positive_cases):
    frame = {
        "targetSurface": f"{domain}.answer",
        "requestedChange": intent,
        "knownConstraints": ["Preserve the typed decision boundary."],
    }
    concepts = server.controller_template_ownership_concepts(
        f"{domain}-owner",
        {"mode": f"{domain}-direct", "answer": answer},
        frame,
    )
    positive_receipts.append(
        relevance_for(
            intent,
            domain,
            answer,
            run_id=f"p250-positive-{index}",
            concepts=concepts,
        )
    )
check(
    "cross-domain-controller-outputs-pass-exact-template-binding",
    all(
        receipt.get("status") == "pass"
        and receipt.get("mayFinalize") is True
        and receipt.get("templateOutputBound") is True
        and receipt.get("templateOutputOverlapConcepts")
        for receipt in positive_receipts
    ),
    [
        {
            "status": receipt.get("status"),
            "issues": receipt.get("issues"),
            "bound": receipt.get("templateOutputBound"),
            "overlap": receipt.get("templateOutputOverlapConcepts"),
        }
        for receipt in positive_receipts
    ],
)

concept_probe = server.controller_template_ownership_concepts(
    "decision-owner",
    {
        "mode": "decision-direct",
        "answer": "Retain the measured thermal ceiling.",
    },
    {
        "targetSurface": "decision.answer",
        "requestedChange": "Choose the ceiling.",
        "knownConstraints": ["Use measured evidence."],
    },
)
check(
    "template-concepts-include-output-semantics-without-raw-answer",
    {"retain", "measured", "thermal", "ceiling"}.issubset(set(concept_probe))
    and "Retain the measured thermal ceiling." not in concept_probe,
    concept_probe,
)

wrong_owner = relevance_for(
    "Choose the thermal limit for the enclosure.",
    "thermal-design",
    "Use the enclosure thermal limit.",
    run_id="p250-wrong-owner",
    concepts=["enclosure", "thermal", "limit"],
    owner_domain="financial-reporting",
)
check(
    "wrong-owner-output-remains-blocked",
    wrong_owner.get("status") == "replan"
    and "template-owner-domain-not-allowed" in (wrong_owner.get("issues") or []),
    wrong_owner.get("issues"),
)

wrong_concept = relevance_for(
    "Choose the thermal limit for the enclosure.",
    "thermal-design",
    "The enclosure label should remain blue.",
    run_id="p250-wrong-concept",
    concepts=["thermal", "limit", "temperature"],
)
check(
    "wrong-concept-output-remains-blocked-despite-exact-hash",
    wrong_concept.get("status") == "replan"
    and wrong_concept.get("templateOutputBound") is True
    and "template-output-concept-mismatch" in (wrong_concept.get("issues") or []),
    wrong_concept.get("issues"),
)

tampered_binding = relevance_for(
    "Choose the thermal limit for the enclosure.",
    "thermal-design",
    "Use a different enclosure thermal limit.",
    run_id="p250-tampered-output",
    concepts=["enclosure", "thermal", "limit"],
)
tampered_ownership = dict(tampered_binding.get("templateOwnership") or {})
tampered_ownership["outputSha256"] = "0" * 64
tampered = answer_envelope.answer_relevance_contract(
    "Use a different enclosure thermal limit.",
    run_id="p250-tampered-output",
    latest_user_intent="Choose the thermal limit for the enclosure.",
    intent_domain="thermal-design",
    task_contract=contract_for(
        "Choose the thermal limit for the enclosure.", "thermal-design"
    ),
    template_ownership=tampered_ownership,
    require_template_ownership=True,
)
check(
    "tampered-output-binding-fails-closed",
    tampered.get("status") == "replan"
    and "template-output-binding-mismatch" in (tampered.get("issues") or []),
    tampered.get("issues"),
)

unbound = relevance_for(
    "Choose the thermal limit for the enclosure.",
    "thermal-design",
    "Use the enclosure thermal limit.",
    run_id="p250-unbound",
    concepts=["abstract-specialist-template"],
    bound=False,
)
check(
    "unbound-output-does-not-gain-template-ownership",
    unbound.get("status") == "replan"
    and unbound.get("templateOutputBound") is False
    and "template-output-concept-mismatch" in (unbound.get("issues") or []),
    unbound.get("issues"),
)

empty = relevance_for(
    "Choose the thermal limit for the enclosure.",
    "thermal-design",
    "",
    run_id="p250-empty",
    concepts=["thermal", "limit"],
)
check(
    "empty-output-remains-unhandled-and-nonfinal",
    empty.get("status") == "replan"
    and empty.get("mayFinalize") is False
    and empty.get("answerConcepts") == []
    and "answer-has-no-active-contract-concept" in (empty.get("issues") or []),
    {"issues": empty.get("issues"), "answerConcepts": empty.get("answerConcepts")},
)

lineage_intent = "Retain the latest release rollback signal."
lineage_contract = contract_for(lineage_intent, "release-operations")
lineage = answer_envelope.turn_lineage_contract(
    run_id="p250-lineage",
    latest_user_intent=lineage_intent,
    current_domain="release-operations",
    task_contract=lineage_contract,
    declared_relation="standalone",
)
bad_lineage = dict(lineage)
bad_lineage["lineageDigest"] = "f" * 64
lineage_failure = relevance_for(
    lineage_intent,
    "release-operations",
    "Retain the latest release rollback signal.",
    run_id="p250-lineage",
    concepts=["release", "rollback", "signal"],
    lineage=bad_lineage,
)
check(
    "wrong-lineage-output-remains-blocked",
    lineage_failure.get("status") == "replan"
    and "turn-lineage-integrity-mismatch"
    in (lineage_failure.get("issues") or []),
    lineage_failure.get("issues"),
)

source_answer = (
    "Use the verified coefficient from https://example.invalid/specification."
)
wrong_source = answer_envelope.build_source_receipt(
    receipt_id="source-p250",
    run_id="different-run",
    claim_text="different claim",
    source_type="web",
    locator="https://example.invalid/specification",
    content_sha256="a" * 64,
    observed_at="2026-08-11T00:00:00Z",
    state="checked",
)
source_provenance = answer_envelope.source_provenance_contract(
    source_answer,
    [wrong_source],
    run_id="p250-source",
)
check(
    "wrong-source-binding-cannot-support-grounded-output",
    source_provenance.get("status") == "unverified"
    and source_provenance.get("mayClaimGrounded") is False
    and {
        "source-receipt-run-mismatch",
        "source-receipt-claim-mismatch",
        "url-text-without-source-receipt",
    }.issubset(set(source_provenance.get("issues") or [])),
    source_provenance,
)


class CaptureHandler:
    def __init__(self, run_id):
        self.current_run_id = run_id
        self.current_web_search = "disabled"
        self.current_cwd = str(ROOT)
        self.path = "/synthetic/p250"
        self.wfile = io.BytesIO()

    def send_response(self, *_args):
        return None

    def send_header(self, *_args):
        return None

    def end_headers(self):
        return None


failure_messages = [
    {"role": "user", "text": "Choose the thermal limit for the enclosure."}
]
failure_route = server.route_manager(
    failure_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
failure_route["_liveRunId"] = "p250-terminal"
failure_route["intentFrame"] = {
    **dict(failure_route.get("intentFrame") or {}),
    "domain": "bounded_specialist_capability",
    "originalDomain": "thermal-design",
    "outputContract": {
        "mode": "conversation-answer",
        "binding": "advisory-or-question",
    },
    "operationPlan": {},
}
failure_route["capabilityPlan"] = {
    "id": "bounded-specialist-capability",
    "registered": True,
    "executor": "deterministic",
    "execution_binding": "router",
    "handler_key": "bounded_specialist_direct",
    "relevance_policy": "template-ownership-required",
    "access_level": "local-knowledge",
    "proof_policy": "typed deterministic result or exact blocker",
}
failure_contract = server.active_answer_relevance_task_contract(
    failure_messages, failure_route
)
rejected_answer = "The enclosure label should remain blue."
rejected_ownership = answer_envelope.build_template_ownership_receipt(
    receipt_id="template-p250-terminal",
    run_id="p250-terminal",
    template_id="deterministic:thermal-design",
    latest_user_intent=server.latest_user_text(failure_messages),
    task_contract=failure_contract,
    owner_domain="thermal-design",
    supported_domains=["thermal-design"],
    concepts=["thermal", "limit", "temperature"],
    bound_output=rejected_answer,
)


def rejected_handler(_context):
    return server.compose_controller_owned_direct_result(
        failure_messages,
        failure_route,
        {
            "mode": "deterministic-specialist-answer",
            "engine": "local-knowledge",
            "accessLevel": "local-knowledge",
            "answer": rejected_answer,
            "templateOwnership": rejected_ownership,
            "returnCode": 0,
        },
    )


original_router = server._DETERMINISTIC_CAPABILITY_ROUTER
try:
    server._DETERMINISTIC_CAPABILITY_ROUTER = CapabilityExecutorRouter(
        (("bounded_specialist_direct", rejected_handler),)
    )
    blocked_result = server.execute_deterministic_capability(
        failure_messages,
        failure_route,
        webSearch="disabled",
    )
finally:
    server._DETERMINISTIC_CAPABILITY_ROUTER = original_router

handler = CaptureHandler("p250-terminal")
server.emit_typed_capability_response(
    handler,
    failure_messages,
    failure_route,
    {"testRun": True},
    blocked_result,
    cwd=str(ROOT),
    profile="manager",
    effective_profile="manager",
    reasoning_level="medium",
    web_search="disabled",
    manager_depth=1,
    friendliness_level=3,
    humor_level=0,
    free_only_redirect=False,
)
events = [
    json.loads(line)
    for line in handler.wfile.getvalue().decode("utf-8").splitlines()
    if line.strip()
]
assistant_event = next(
    (item for item in events if item.get("type") == "assistant"), {}
)
done_event = next((item for item in events if item.get("type") == "done"), {})
failure_receipt = failure_route.get("_typedDeterministicRelevanceFailure") or {}
check(
    "blocked-output-becomes-one-typed-failure-assistant-and-terminal",
    blocked_result.get("handled") is True
    and blocked_result.get("outcome") == "failed"
    and blocked_result.get("returnCode") == 1
    and bool(assistant_event.get("text"))
    and rejected_answer not in str(assistant_event.get("text") or "")
    and (assistant_event.get("answerEnvelope") or {}).get("status") == "failed"
    and (assistant_event.get("answerEnvelope") or {}).get(
        "terminal_state", {}
    ).get("status")
    == "failed"
    and done_event.get("returnCode") == 1,
    {
        "result": {
            key: blocked_result.get(key)
            for key in ("handled", "outcome", "returnCode", "error")
        },
        "eventTypes": [item.get("type") for item in events],
        "terminal": (assistant_event.get("answerEnvelope") or {}).get(
            "terminal_state"
        ),
        "done": done_event,
    },
)
check(
    "typed-failure-receipt-is-request-answer-and-issue-bound",
    failure_receipt.get("status") == "failed"
    and failure_receipt.get("requestSha256")
    == server.text_sha256(server.latest_user_text(failure_messages))
    and failure_receipt.get("rejectedAnswerSha256")
    == server.text_sha256(rejected_answer)
    and failure_receipt.get("failureAnswerSha256")
    == server.text_sha256(blocked_result.get("answer") or "")
    and failure_receipt.get("issues")
    and failure_receipt.get("contentsRecorded") is False,
    failure_receipt,
)

check(
    "existing-agent-preference-static-synthetic-remains-green",
    server.agent_preference_direct_synthetic_check() is True,
    "existing non-live synthetic path",
)

server_source = (ROOT / "server.py").read_text(encoding="utf-8")
export_source = (ROOT / "tools" / "build_public_export.py").read_text(
    encoding="utf-8"
)
check(
    "p250-package-and-export-registration",
    '"server:controller-template-completion-p250"' in server_source
    and server_source.count("p250_controller_template_completion_smoke.py") == 1
    and export_source.count(
        '"tools/p250_controller_template_completion_smoke.py"'
    )
    == 1,
    "one package row and one public-export entry",
)


failed = [item for item in checks if item.get("status") != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "suite": "p250-controller-template-completion",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failures": failed,
            "checks": checks,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)
