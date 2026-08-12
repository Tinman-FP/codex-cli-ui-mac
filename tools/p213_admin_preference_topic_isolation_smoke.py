#!/usr/bin/env python3
"""Focused regression for evidence-bound learned admin-topic preferences."""

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
    checks.append(
        {"name": name, "passed": bool(passed), "detail": str(detail or "")[:1200]}
    )


fixture_state = {
    "version": 1,
    "preferences": [
        {
            "projectId": "software-projects",
            "folderId": "cad",
            "matchTerms": ["will", "retain", "constraints", "able", "opened", "fusion"],
        },
        {
            "projectId": "3d-printers",
            "folderId": "hardware",
            "matchTerms": ["lets", "search", "plus", "printer.cfg", "file", "document"],
        },
        {
            "projectId": "software-projects",
            "folderId": "cad",
            "matchTerms": ["fixture_a8bb1397.stl", "inspect", "dimensions"],
        },
    ],
}

original_loader = server.load_admin_state
server.load_admin_state = lambda: fixture_state
try:
    broad_query = "good morning! will you briefly tell me what capabilities you have to help me?"
    web_query = "is web search enabled for this run?"
    broad_boosts = server.admin_preference_boosts(broad_query)
    web_boosts = server.admin_preference_boosts(web_query)
    check(
        "single-generic-words-cannot-boost-learned-folders",
        broad_boosts == ({}, {}) and web_boosts == ({}, {}),
        {"broad": broad_boosts, "web": web_boosts},
    )

    fusion_boosts = server.admin_preference_boosts(
        "Can this be opened in Fusion?"
    )
    check(
        "single-destination-technical-trigger-retains-preference",
        fusion_boosts[0].get("software-projects") == 7
        and fusion_boosts[1].get(("software-projects", "cad")) == 9,
        fusion_boosts,
    )

    continuation_boosts = server.admin_preference_boosts(
        "Will it retain the constraints when opened?"
    )
    check(
        "two-meaningful-terms-retain-continuation-preference",
        continuation_boosts[1].get(("software-projects", "cad")) == 9,
        continuation_boosts,
    )

    identifier_boosts = server.admin_preference_boosts(
        "Inspect fixture_a8bb1397.stl."
    )
    check(
        "single-technical-identifier-retains-preference",
        identifier_boosts[1].get(("software-projects", "cad")) == 9,
        identifier_boosts,
    )

    runtime_prompts = (
        "Good morning! Will you briefly tell me what capabilities you have to help me?",
        "Is web search enabled for this run?",
    )
    runtime_topics = []
    for prompt in runtime_prompts:
        messages = [{"role": "user", "text": prompt}]
        route = server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )
        runtime_topics.append(server.route_admin_topic(messages, route))
    check(
        "runtime-self-knowledge-stays-in-software-apps",
        all(
            topic.get("topicPath") == "Software Projects / Apps"
            and "saved preference" not in (topic.get("matched") or [])
            for topic in runtime_topics
        ),
        runtime_topics,
    )

    cad_messages = [
        {"role": "user", "text": "Create a Fusion 360 script for a mounting bracket."}
    ]
    cad_route = server.route_manager(
        cad_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    cad_topic = server.route_admin_topic(cad_messages, cad_route)
    check(
        "explicit-cad-request-remains-cad",
        cad_route.get("projectId") == "cad-modeling-projects"
        and cad_topic.get("topicPath") == "Software Projects / CAD",
        {"route": cad_route.get("projectId"), "topic": cad_topic},
    )

    marketplace_messages = [
        {
            "role": "user",
            "content": (
                "Search eBay for three current listings for a new 100W JPT MOPA fiber laser. "
                "Give me the exact model or configuration and clickable links."
            ),
        }
    ]
    marketplace_route = server.route_manager(
        marketplace_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="live",
    )
    marketplace_topic = server.route_admin_topic(
        marketplace_messages,
        marketplace_route,
    )
    check(
        "typed-marketplace-domain-outranks-product-model-as-cad",
        (marketplace_route.get("intentFrame") or {}).get("domain")
        == "marketplace_listing_research"
        and marketplace_topic.get("topicPath") == "Reference / General"
        and marketplace_topic.get("matched")
        == ["typed-domain:marketplace_listing_research"],
        {"route": marketplace_route.get("projectId"), "topic": marketplace_topic},
    )

    product_model_messages = [
        {
            "role": "user",
            "text": "Compare these three motor models for efficiency and torque.",
        }
    ]
    product_model_route = server.route_manager(
        product_model_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    product_model_topic = server.route_admin_topic(
        product_model_messages,
        product_model_route,
    )
    check(
        "bare-product-model-language-cannot-open-cad-folder",
        product_model_topic.get("topicPath") != "Software Projects / CAD"
        and "model" not in (product_model_topic.get("matched") or []),
        {"route": product_model_route.get("projectId"), "topic": product_model_topic},
    )

    implicit_cad_messages = [
        {
            "role": "user",
            "text": "Create a printable 3D model of a mounting bracket with four bolt holes.",
        }
    ]
    implicit_cad_route = server.route_manager(
        implicit_cad_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    implicit_cad_topic = server.route_admin_topic(
        implicit_cad_messages,
        implicit_cad_route,
    )
    check(
        "typed-cad-artifact-domain-preserves-implicit-cad-filing",
        (implicit_cad_route.get("intentFrame") or {}).get("domain") == "cad_artifact_work"
        and implicit_cad_topic.get("topicPath") == "Software Projects / CAD",
        {"route": implicit_cad_route.get("projectId"), "topic": implicit_cad_topic},
    )
finally:
    server.load_admin_state = original_loader


failed = [item for item in checks if not item["passed"]]
report = {
    "status": "pass" if not failed else "fail",
    "passed": len(checks) - len(failed),
    "failed": len(failed),
    "checkCount": len(checks),
    "checks": checks,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if not failed else 1)
