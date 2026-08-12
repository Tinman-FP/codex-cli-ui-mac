#!/usr/bin/env python3
"""P203 regressions for bounded specialist ownership and artifact authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:1800]})


def route(text: str) -> dict:
    return server.route_manager(
        [{"role": "user", "text": text}],
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )


receipt_route = route("What evidence file should I create for AI UI human QA Q500?")
receipt_frame = receipt_route.get("intentFrame") or {}
receipt_plan = receipt_frame.get("operationPlan") or {}
check(
    "registered-evidence-template-has-bounded-artifact-authority",
    receipt_frame.get("domain") == "bounded_specialist_capability"
    and (receipt_route.get("capabilityPlan") or {}).get("id") == "bounded-specialist-capability"
    and (receipt_frame.get("outputContract") or {}).get("mode") == "local-artifact"
    and (receipt_frame.get("outputContract") or {}).get("binding") == "registered-bounded-specialist-workflow"
    and receipt_plan.get("allowedNow") == ["create"]
    and receipt_plan.get("readOnly") is False,
    receipt_route,
)


for name, prompt in (
    (
        "qa-evidence-summary-keeps-deterministic-owner",
        "Summarize the latest Production human QA Q500 evidence receipt and compare it to the rehearsal row.",
    ),
    (
        "qa-record-guard-keeps-deterministic-owner",
        "What command should I use to record AI UI human QA Q321 after I complete the evidence template?",
    ),
    (
        "localization-keeps-deterministic-owner",
        "Can it detect the user's language accurately and respond in the requested language?",
    ),
):
    selected = route(prompt)
    check(
        name,
        (selected.get("intentArbitration") or {}).get("mode") == "bounded-specialist"
        and (selected.get("capabilityPlan") or {}).get("id") == "bounded-specialist-capability"
        and (selected.get("capabilityPlan") or {}).get("handler_key") == "bounded_specialist_direct"
        and (
            name != "qa-evidence-summary-keeps-deterministic-owner"
            or (selected.get("intentFrame") or {}).get("outputContract", {}).get("mode")
            == "conversation-answer"
        ),
        selected,
    )


localization_messages = [
    {"role": "user", "text": "Can it detect the user's language accurately and respond in the requested language?"}
]
localization_route = route(localization_messages[0]["text"])
localization_answer = server.general_direct_knowledge_answer(
    localization_messages,
    localization_route,
    web_search="disabled",
).get("answer", "")
check(
    "localization-owner-produces-the-stable-direct-answer",
    "requested language" in localization_answer.lower()
    and "silently guessing" in localization_answer.lower(),
    localization_answer,
)


shortlist_prompt = (
    "Research current listings and build a shortlist, but do not buy anything "
    "or contact sellers."
)
shortlist_route = route(shortlist_prompt)
check(
    "embedded-rtl-letters-do-not-steal-current-market-routing",
    not server.is_localization_baseline_question(
        [{"role": "user", "text": shortlist_prompt}]
    )
    and (shortlist_route.get("intentFrame") or {}).get("domain")
    == "current_market_research"
    and (shortlist_route.get("capabilityPlan") or {}).get("id")
    == "current-web-research",
    shortlist_route,
)


ordinary = route("What file should I create for a new workshop idea?")
ordinary_frame = ordinary.get("intentFrame") or {}
check(
    "ordinary-advisory-file-question-remains-non-writing",
    (ordinary_frame.get("outputContract") or {}).get("mode") == "conversation-answer"
    and "create" not in ((ordinary_frame.get("operationPlan") or {}).get("allowedNow") or [])
    and "registered-bounded-specialist-artifact" not in (ordinary_frame.get("frameTags") or []),
    ordinary,
)


negative = route("Do not create an AI UI human QA Q500 evidence receipt; explain what it would contain.")
negative_frame = negative.get("intentFrame") or {}
check(
    "explicit-negative-scope-cannot-create-specialist-artifact",
    "create" not in ((negative_frame.get("operationPlan") or {}).get("allowedNow") or [])
    and (negative_frame.get("outputContract") or {}).get("mode") != "local-artifact",
    negative,
)


status_messages = [
    {"role": "user", "text": "What is the current status of the 500 question AI intent audit?"}
]
status_route = route(status_messages[0]["text"])
check(
    "named-current-status-is-self-contained",
    not server.material_unresolved_referent(status_messages, status_route),
    status_route,
)
status_contract = server.task_contract(status_messages, status_route)
check(
    "bounded-specialist-does-not-inherit-generic-web-research-contract",
    status_contract.get("kind") == "Bounded specialist response"
    and "source URL" not in (status_contract.get("requiredProof") or []),
    status_contract,
)
status_execution = server.execute_deterministic_capability(
    status_messages,
    status_route,
    webSearch="disabled",
)
status_observations = status_execution.get("sourceObservations") or []
check(
    "audit-status-carries-controller-owned-local-evidence",
    status_execution.get("eligible") is True
    and any(
        str(item.get("localPath") or "").endswith(
            "/tests/ai_ui_intent_500_audit.json"
        )
        and item.get("contentSha256")
        for item in status_observations
        if isinstance(item, dict)
    ),
    status_execution,
)


failed = [item for item in checks if not item["ok"]]
report = {
    "status": "pass" if not failed else "fail",
    "checkCount": len(checks),
    "failedCount": len(failed),
    "checks": checks,
}
print(json.dumps(report, indent=2))
raise SystemExit(0 if not failed else 1)
