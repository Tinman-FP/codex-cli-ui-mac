#!/usr/bin/env python3
"""Offline regression for semantic live-smoke required phrases."""

import json
from pathlib import Path

import live_feedback_smoke as smoke


APP_DIR = Path(__file__).resolve().parents[1]


def run_with_answer(answer, required):
    case = {
        "id": "p150-offline-semantic-requirements",
        "messages": [{"role": "user", "text": "Give me the semantic result naturally."}],
        "required": required,
        "conversationQuality": {"noFormalLabels": True},
    }
    events = (
        {"type": "status", "route": {}},
        {"type": "assistant", "text": answer, "adminTopic": {}},
        {"type": "done", "returnCode": 0},
    )
    original = smoke.post_json_stream
    smoke.post_json_stream = lambda *_args, **_kwargs: iter(events)
    try:
        return smoke.run_case(
            "http://offline.invalid",
            case,
            timeout=1,
            cwd=str(APP_DIR),
        )
    finally:
        smoke.post_json_stream = original


def main():
    required = [
        "semantic-one",
        "This is why:",
        "semantic-two",
        "You should also consider:",
    ]
    filtered = smoke.semantic_required_phrases({"required": required})
    exact_only = smoke.semantic_required_phrases(
        {
            "required": [
                "This is why",
                "this is why:",
                "You should also consider",
                "you should also consider:",
            ]
        }
    )
    natural = run_with_answer(
        "Semantic-one is satisfied, and semantic-two is also present.",
        required,
    )
    missing_semantic = run_with_answer(
        "Semantic-one is satisfied.",
        required,
    )
    canned = run_with_answer(
        "Semantic-one and semantic-two are present.\n\nThis is why: canned.\n\nYou should also consider: canned.",
        required,
    )

    checks = [
        {
            "id": "legacy-presentation-tokens-immutable",
            "ok": smoke.LEGACY_PRESENTATION_ONLY_REQUIRED_PHRASES
            == ("This is why:", "You should also consider:"),
        },
        {
            "id": "legacy-presentation-tokens-filtered",
            "ok": filtered == ["semantic-one", "semantic-two"],
        },
        {
            "id": "filter-is-exact-only",
            "ok": exact_only
            == [
                "This is why",
                "this is why:",
                "You should also consider",
                "you should also consider:",
            ],
        },
        {
            "id": "natural-semantic-answer-passes",
            "ok": natural.get("ok") is True
            and natural.get("missing") == []
            and natural.get("conversationQuality", {}).get("status") == "pass",
        },
        {
            "id": "missing-semantic-content-fails",
            "ok": missing_semantic.get("ok") is False
            and missing_semantic.get("missing") == ["semantic-two"],
        },
        {
            "id": "no-formal-labels-still-rejects-canned-shape",
            "ok": canned.get("ok") is False
            and canned.get("missing") == []
            and canned.get("conversationQuality", {}).get("status") == "fail"
            and [
                item.get("label")
                for item in canned.get("conversationQuality", {}).get("failed", [])
            ]
            == ["natural-conversational-shape"],
        },
    ]
    failed = [item for item in checks if not item["ok"]]
    receipt = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
