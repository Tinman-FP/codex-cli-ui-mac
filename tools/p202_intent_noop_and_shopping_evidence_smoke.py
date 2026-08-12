#!/usr/bin/env python3
"""P202 regressions for specialist intent, no-op prose, and checked shopping evidence."""

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


interaction_messages = [
    {
        "role": "user",
        "text": "Lets proceed. Can you interact with him directly? work with him on the things that we have been struggling with?",
    }
]
interaction_route = server.route_manager(
    interaction_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
interaction_answer = server.general_direct_knowledge_answer(
    interaction_messages,
    interaction_route,
    web_search="disabled",
).get("answer", "")
check(
    "confirmed-local-agent-workflow-outranks-generic-compatibility-frame",
    interaction_route.get("projectId") == "codex-cli-ui-local-agent"
    and (interaction_route.get("intentArbitration") or {}).get("mode") == "bounded-specialist"
    and (interaction_route.get("capabilityPlan") or {}).get("id") == "bounded-specialist-capability"
    and (interaction_route.get("intentFrame") or {}).get("domain") == "bounded_specialist_capability",
    interaction_route,
)
check(
    "local-agent-workflow-answers-the-complete-request",
    all(
        phrase.lower() in interaction_answer.lower()
        for phrase in ("local Codex CLI UI", "/api/run", "routing", "response etiquette", "patch", "rerun")
    )
    and "named components" not in interaction_answer.lower(),
    interaction_answer,
)


noop_route = {
    "intentFrame": {
        "requestedChange": "Display percent complete and time remaining for the Bambu H2D in Model Health.",
        "targetSurface": "codex_cli_ui.model_health",
        "missingInfo": ["Bambu H2D progress/ETA telemetry source or manual override values"],
        "evidenceNeed": "local-code-or-state-evidence",
        "knownConstraints": [
            "This is Codex CLI UI status-panel work, not CAD geometry work.",
            "Do not infer Bambu progress or ETA from ping-only reachability.",
        ],
    },
    "objectivePlan": {
        "target": "Codex CLI UI Model Health row for Bambu H2D",
        "evidenceNeed": "live-or-configured-status-source",
        "missingInputs": ["Bambu H2D progress/ETA telemetry source or manual override values"],
    },
}
noop_answer = server.local_action_verified_noop_answer(noop_route, "app.js")
check(
    "verified-noop-is-presented-in-user-language",
    all(
        phrase.lower() in noop_answer.lower()
        for phrase in (
            "Bambu H2D",
            "Model Health",
            "percent complete",
            "time remaining",
            "status source",
            "telemetry",
            "not CAD",
        )
    )
    and "Controller-bound bounded context" not in noop_answer,
    noop_answer,
)
generic_noop = server.local_action_verified_noop_answer(
    {
        "intentFrame": {
            "requestedChange": "Show queue depth on the build monitor.",
            "targetSurface": "local_app.build_monitor",
            "missingInfo": ["queue telemetry provider"],
        },
        "objectivePlan": {
            "target": "the build monitor queue row",
            "evidenceNeed": "live-or-configured-status-source",
        },
    },
    "ui.js",
)
check(
    "verified-noop-composer-generalizes-beyond-printers",
    "build monitor queue row" in generic_noop
    and "queue depth" in generic_noop
    and "status source/telemetry" in generic_noop
    and "Bambu" not in generic_noop,
    generic_noop,
)


shopping_query = "can you find a Peopoly Magneto linear motor kit for sale for me?"
shopping_route = {
    "objectivePlan": {
        "objectiveType": "current-product-shopping",
        "target": "Peopoly Magneto linear motor kit",
    }
}
shopping_evidence = [
    {
        "id": 1,
        "title": "Magneto linear motor kit announcement",
        "url": "https://manufacturer.example/news/magneto-kit",
        "excerpt": "Peopoly Magneto Linear Motor Kit is offered for pre-order at $299.00.",
        "fetched": True,
    },
    {
        "id": 2,
        "title": "Magneto discussion",
        "url": "https://community.example/magneto",
        "excerpt": "The Peopoly Magneto linear motor kit discussion links the announced pre-order.",
        "fetched": True,
    },
    {
        "id": 3,
        "title": "Unopened seller result",
        "url": "https://seller.example/unverified-product",
        "snippet": "Peopoly Magneto kit in stock for $199.",
        "fetched": False,
    },
    {
        "id": 4,
        "title": "Unrelated motor",
        "url": "https://manufacturer.example/unrelated",
        "excerpt": "A different stepper motor is in stock.",
        "fetched": True,
    },
]
shopping_answer, checked_rows = server.checked_product_shopping_answer(
    shopping_query,
    shopping_route,
    shopping_evidence,
)
check(
    "shopping-answer-uses-only-fetched-exact-product-pages",
    len(checked_rows) == 2
    and "https://manufacturer.example/news/magneto-kit" in shopping_answer
    and "https://community.example/magneto" in shopping_answer
    and "https://seller.example/unverified-product" not in shopping_answer
    and "https://manufacturer.example/unrelated" not in shopping_answer,
    shopping_answer,
)
check(
    "shopping-answer-bounds-price-and-stock-claims",
    "$299.00" in shopping_answer
    and "source-reported" in shopping_answer
    and "Stock status" in shopping_answer
    and "pre-order" in shopping_answer
    and "$199" not in shopping_answer,
    shopping_answer,
)
empty_answer, empty_rows = server.checked_product_shopping_answer(
    shopping_query,
    shopping_route,
    [shopping_evidence[2]],
)
check(
    "search-only-result-cannot-become-a-buy-link",
    not empty_rows
    and "could not verify a current seller page" in empty_answer
    and "price and stock" in empty_answer
    and "seller.example" not in empty_answer,
    empty_answer,
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
