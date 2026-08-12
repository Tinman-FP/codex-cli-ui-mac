#!/usr/bin/env python3
"""P217 representation comparison intent, reasoning, and audit contract."""

from __future__ import annotations

import copy
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
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


def route(prompt, attachments=None):
    message = {"role": "user", "text": prompt}
    if attachments:
        message["attachments"] = attachments
    messages = [message]
    result = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    result["_messages"] = messages
    return result


conceptual_prompts = (
    "What is the difference between a STEP CAD model and an STL mesh?",
    "How does DOCX differ from PDF for later editing?",
    "Compare SVG and PNG for editing a logo.",
    "Compare JSON and Protocol Buffers for preserving an application data model.",
    "Compare source code and compiled bytecode for later modification.",
)
conceptual_routes = [route(prompt) for prompt in conceptual_prompts]
check(
    "conceptual-representation-comparisons-own-conversation-answers",
    all(
        ((result.get("intentFrame") or {}).get("outputContract") or {}).get("mode")
        == "conversation-answer"
        and (result.get("intentFrame") or {}).get("domain") == "knowledge_comparison"
        and (result.get("capabilityPlan") or {}).get("id") == "expert-comparison"
        for result in conceptual_routes
    ),
    [result.get("intentFrame") for result in conceptual_routes],
)
check(
    "difference-and-direct-compare-grammar-retain-both-options",
    all(
        len(
            [
                item
                for item in (result.get("intentFrame") or {}).get("objectRefs") or []
                if isinstance(item, dict) and item.get("type") == "comparison-option"
            ]
        )
        == 2
        for result in conceptual_routes
    ),
    [
        (result.get("intentFrame") or {}).get("objectRefs")
        for result in conceptual_routes
    ],
)
check(
    "representation-contract-is-domain-neutral-and-typed",
    all(
        ((result.get("intentFrame") or {}).get("representationSemantics") or {}).get("kind")
        == "representation-semantics-contract"
        and "representation-semantics"
        in ((result.get("intentFrame") or {}).get("frameTags") or [])
        for result in conceptual_routes
    ),
    [
        (result.get("intentFrame") or {}).get("representationSemantics")
        for result in conceptual_routes
    ],
)
check(
    "representation-contract-owns-the-semantic-family-before-authoring",
    [
        ((result.get("intentFrame") or {}).get("representationSemantics") or {}).get(
            "semanticFamily"
        )
        for result in conceptual_routes
    ]
    == ["geometry", "document", "image", "data-serialization", "program"],
    [
        (result.get("intentFrame") or {}).get("representationSemantics")
        for result in conceptual_routes
    ],
)
serialization_contract = (
    (conceptual_routes[3].get("intentFrame") or {}).get(
        "representationSemantics"
    )
    or {}
)
check(
    "typed-family-contract-carries-positive-and-negative-authoring-boundaries",
    serialization_contract.get("version") == 2
    and "application meaning"
    in [str(item) for item in serialization_contract.get("familyVocabulary") or []]
    and any(
        "live application model and runtime state" in str(item)
        for item in serialization_contract.get("familyMethod") or []
    )
    and {
        "design intent",
        "feature history",
        "sketch constraints",
        "parametric history",
    }.issubset(
        {
            str(item)
            for item in serialization_contract.get("forbiddenFamilyVocabulary")
            or []
        }
    ),
    serialization_contract,
)

serialization_author_prompt = server.build_stable_comparison_primary_author_handoff_prompt(
    [{'role': 'user', 'text': 'What is the difference between JSON and Protocol Buffers for schema evolution?'}],
    conceptual_routes[3],
).get('prompt', '')
check(
    "serialization-author-prompt-forbids-universal-evolution-outcomes",
    "Never append 'without failure', 'without error'" in serialization_author_prompt
    and "A missing member is absent" in serialization_author_prompt
    and "does not establish whether a later serializer preserves or drops it" in serialization_author_prompt
    and "Do not claim universal ignore, preserve, discard" in serialization_author_prompt,
    serialization_author_prompt,
)
check(
    "comparison-speech-act-separates-explanation-from-decision-work",
    [
        (result.get("intentFrame") or {}).get("comparisonSpeechAct")
        for result in conceptual_routes
    ]
    == ["explanation", "explanation", "comparison", "comparison", "comparison"],
    [
        (result.get("intentFrame") or {}).get("comparisonSpeechAct")
        for result in conceptual_routes
    ],
)
decision_route = route("Which is better for 3D printing, a STEP model or an STL mesh?")
check(
    "explicit-choice-comparison-retains-decision-speech-act",
    (decision_route.get("intentFrame") or {}).get("comparisonSpeechAct")
    == "decision",
    decision_route.get("intentFrame"),
)


local_compare = route(
    "Compare these two attached files and tell me what changed without modifying them.",
    attachments=[
        {"name": "old.json", "path": "/tmp/old.json"},
        {"name": "new.json", "path": "/tmp/new.json"},
    ],
)
local_frame = local_compare.get("intentFrame") or {}
check(
    "actual-local-evidence-comparison-retains-inspection-ownership",
    local_frame.get("domain") == "local_file_evidence"
    and (local_frame.get("outputContract") or {}).get("mode") == "local-action"
    and not local_frame.get("representationSemantics"),
    local_frame,
)


material_route = route(
    "Compare aluminum and G10/FR4 for an electrically insulating mounting plate."
)
check(
    "physical-material-comparison-does-not-inherit-representation-rules",
    not (material_route.get("intentFrame") or {}).get("representationSemantics"),
    material_route.get("intentFrame"),
)


step_route = conceptual_routes[0]
step_messages = step_route["_messages"]
step_route["_answerObligationLedger"] = server.build_answer_obligation_ledger(
    step_messages, step_route
)
bad_answer = (
    "STEP files are parametric CAD models that encode material properties, feature definitions, and assembly relationships. "
    "They preserve design intent, so dimensions and constraints can be edited. STL files store a mesh representation made of triangles. "
    "The mesh is simpler and is mainly useful for printing, while STEP remains the better choice for later editing and design changes."
)
bad_gate = server.stable_expert_comparison_candidate_gate(
    step_messages, step_route, bad_answer
)
check(
    "unqualified-native-history-claims-fail-the-controller-gate",
    not bad_gate.get("accepted")
    and {
        item.get("kind") for item in bad_gate.get("epistemicIssues") or []
    }
    >= {"missing-native-source-boundary", "unqualified-cross-layer-semantics"},
    bad_gate,
)

json_route = route(
    "What is the difference between JSON and Protocol Buffers for preserving an application data model?"
)
json_messages = json_route["_messages"]
schema_evolution_route = route(
    "What is the difference between JSON and Protocol Buffers for schema evolution?"
)
check(
    "stable-versioned-serialization-explanations-stay-with-expert-reasoning",
    (schema_evolution_route.get("intentFrame") or {}).get("domain")
    == "knowledge_comparison"
    and (schema_evolution_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and ((schema_evolution_route.get("intentFrame") or {}).get("representationSemantics") or {}).get("semanticFamily")
    == "data-serialization",
    {
        "frame": schema_evolution_route.get("intentFrame"),
        "capabilityPlan": schema_evolution_route.get("capabilityPlan"),
    },
)
schema_evolution_source_route = route(
    "Using official documentation, what is the difference between JSON and Protocol Buffers for schema evolution?"
)
check(
    "explicit-documentation-request-routes-to-primary-technical-evidence",
    (schema_evolution_source_route.get("intentFrame") or {}).get("domain")
    == "technical_source_lookup"
    and (schema_evolution_source_route.get("capabilityPlan") or {}).get("id")
    == "source-backed-reasoning"
    and ((schema_evolution_source_route.get("intentFrame") or {}).get("representationSemantics") or {}).get("semanticFamily")
    == "data-serialization",
    {
        "frame": schema_evolution_source_route.get("intentFrame"),
        "capabilityPlan": schema_evolution_source_route.get("capabilityPlan"),
    },
)
representation_followup_messages = [
    {
        "role": "user",
        "text": "Using official documentation, what is the difference between JSON and Protocol Buffers for schema evolution?",
    },
    {
        "role": "assistant",
        "text": (
            "Forward compatibility means an older reader consumes a newer payload. "
            "The checked Protocol Buffers documentation defines more evolution machinery, while bare JSON leaves more behavior to the application contract."
        ),
    },
    {
        "role": "user",
        "text": (
            "So if an older service must read payloads produced by newer software, which compatibility direction is that, "
            "and which of the two gives me more built-in evolution machinery based on what you just found?"
        ),
    },
]
representation_followup_route = server.route_manager(
    representation_followup_messages,
    requested_profile="manager",
    web_search="live",
)
representation_followup_frame = representation_followup_route.get(
    "intentFrame"
) or {}
check(
    "representation-followup-inherits-options-and-semantics-instead-of-generic-compatibility",
    representation_followup_frame.get("domain") == "knowledge_comparison"
    and representation_followup_frame.get("actionType")
    == "continue_representation_comparison"
    and representation_followup_frame.get("contextRelation") == "follow-up"
    and ((representation_followup_frame.get("representationSemantics") or {}).get("semanticFamily"))
    == "data-serialization"
    and [
        item.get("name")
        for item in representation_followup_frame.get("objectRefs") or []
    ][:2]
    == ["JSON", "Protocol Buffers"]
    and "representation-follow-up"
    in (representation_followup_frame.get("frameTags") or [])
    and (representation_followup_route.get("capabilityPlan") or {}).get("id")
    == "expert-comparison"
    and representation_followup_route.get("engine") == "local",
    {
        "frame": representation_followup_frame,
        "capability": representation_followup_route.get("capabilityPlan"),
        "engine": representation_followup_route.get("engine"),
    },
)
representation_followup_policy = server.conversation_only_reasoning_policy(
    representation_followup_messages,
    representation_followup_route,
)
check(
    "representation-followup-with-prior-checked-evidence-stays-off-shell-tools",
    server.stable_offline_expert_comparison(
        representation_followup_messages,
        representation_followup_route,
    )
    and representation_followup_policy.get("eligible") is True
    and representation_followup_policy.get("comparison") is True
    and representation_followup_policy.get("mode")
    == "conversation-only-local-reasoning",
    representation_followup_policy,
)
representation_followup_continuity = (
    server.representation_followup_continuity_result(
        representation_followup_messages,
        representation_followup_route,
    )
)
check(
    "representation-followup-reuses-typed-direction-and-prior-checked-conclusion",
    representation_followup_continuity.get("accepted") is True
    and representation_followup_continuity.get("direction")
    == "forward compatibility"
    and representation_followup_continuity.get("preferredOption")
    == "Protocol Buffers"
    and "JSON" in representation_followup_continuity.get("answer", "")
    and "applicable schema changes and implementation"
    in representation_followup_continuity.get("answer", ""),
    representation_followup_continuity,
)
unbound_followup = server.representation_followup_continuity_result(
    [
        representation_followup_messages[0],
        {
            "role": "assistant",
            "text": "The prior answer did not establish which option has more evolution machinery.",
        },
        representation_followup_messages[-1],
    ],
    representation_followup_route,
)
check(
    "representation-followup-continuity-fails-closed-without-prior-conclusion",
    unbound_followup.get("accepted") is False
    and unbound_followup.get("reason")
    == "prior-comparison-conclusion-unbound",
    unbound_followup,
)
schema_queries = server.local_research_queries(
    schema_evolution_source_route["_messages"][0]["text"],
    schema_evolution_source_route,
)
check(
    "technical-representation-research-uses-official-specification-queries",
    len(schema_queries) == 9
    and all("cross reference" not in item.lower() for item in schema_queries)
    and all("datasheet" not in item.lower() for item in schema_queries)
    and any(
        '"json" official base format specification' in item.lower()
        for item in schema_queries
    )
    and any(
        '"protocol buffers" official base format specification' in item.lower()
        for item in schema_queries
    )
    and any(
        '"json" official best practices' in item.lower()
        for item in schema_queries
    )
    and any(
        '"protocol buffers" official best practices' in item.lower()
        for item in schema_queries
    )
    and any("unknown fields" in item.lower() for item in schema_queries),
    schema_queries,
)
schema_contract = server.task_contract(
    schema_evolution_source_route["_messages"],
    schema_evolution_source_route,
)
schema_director = server.interaction_director_policy(
    schema_evolution_source_route["_messages"],
    schema_evolution_source_route,
    contract=schema_contract,
)
check(
    "source-backed-explanations-use-a-distinction-not-decision-contract",
    server.analytical_core_mode(
        schema_evolution_source_route["_messages"],
        schema_evolution_source_route,
    )
    == "evidence-explanation"
    and "without forcing an unrequested recommendation"
    in str(schema_contract.get("doneMeans") or "")
    and "make a clear recommendation"
    not in [str(item) for item in schema_contract.get("mustDo") or []]
    and "traceable primary source URL"
    in [str(item) for item in schema_contract.get("requiredProof") or []]
    and schema_director.get("answerShape") == "distinction-evidence-boundary"
    and "do not manufacture a winner or recommendation"
    in str(schema_director.get("instruction") or ""),
    {
        "mode": server.analytical_core_mode(
            schema_evolution_source_route["_messages"],
            schema_evolution_source_route,
        ),
        "contract": schema_contract,
        "director": schema_director,
    },
)
official_protobuf = {
    "id": 1,
    "score": 100,
    "title": "Protocol Buffers Language Guide",
    "pageTitle": "Updating A Message Type",
    "url": "https://protobuf.dev/programming-guides/proto3/",
    "text": "Official documentation for updating message definitions and retaining unknown fields.",
    "excerpt": "Official documentation for updating message definitions and retaining unknown fields.",
    "fetched": True,
    "primaryTechnical": True,
    "sourceType": "primary-publication-or-standard",
}
official_json_standard = {
    "id": 2,
    "score": 95,
    "title": "RFC 8259 The JavaScript Object Notation Data Interchange Format",
    "pageTitle": "RFC 8259",
    "url": "https://www.rfc-editor.org/rfc/rfc8259",
    "text": "This document specifies the JSON grammar, including objects made of name/value pairs, and interoperability considerations.",
    "excerpt": "This document specifies the JSON grammar, including objects made of name/value pairs, and interoperability considerations.",
    "fetched": True,
    "primaryTechnical": True,
    "sourceType": "primary-publication-or-standard",
}
secondary_summary = {
    "id": 3,
    "score": 10,
    "title": "JSON vs Protobuf Interview Notes",
    "pageTitle": "JSON vs Protobuf Interview Notes",
    "url": "https://example.com/json-protobuf-summary",
    "text": "A short comparison assembled from other web pages.",
    "excerpt": "A short comparison assembled from other web pages.",
    "fetched": True,
    "primaryTechnical": False,
    "sourceType": "secondary-or-unclassified",
}
secondary_document_mirror = {
    "id": 4,
    "score": 20,
    "title": "Proto3 Language Guide mirror",
    "pageTitle": "Proto3 Language Guide mirror",
    "url": "https://deepwiki.com/example/proto3-language-guide",
    "text": "A third-party generated mirror of programming-guide material.",
    "excerpt": "A third-party generated mirror of programming-guide material.",
    "fetched": True,
    "primaryTechnical": False,
    "sourceType": "secondary-community",
}
official_json_evolution = {
    "id": 5,
    "score": 96,
    "title": "JSON Schema object reference",
    "pageTitle": "JSON Schema object reference",
    "url": "https://json-schema.org/understanding-json-schema/reference/object",
    "text": (
        "JSON is a data interchange syntax whose objects contain property names. "
        "Backward compatibility and forward compatibility depend on the applicable schema. "
        "Additional properties control unknown member handling, "
        "identifier reuse is governed by that schema, "
        "while application readers determine round-trip behavior."
    ),
    "excerpt": (
        "JSON is a data interchange syntax whose objects contain property names. "
        "Backward compatibility and forward compatibility depend on the applicable schema. "
        "Additional properties control unknown member handling, "
        "identifier reuse is governed by that schema, "
        "while application readers determine round-trip behavior."
    ),
    "fetched": True,
}
official_protobuf_evolution = {
    **official_protobuf,
    "text": (
        "Protocol Buffers serialization uses a message type and field numbers. "
        "Updating a message type covers backward compatibility and forward compatibility. "
        "Unknown fields can be retained for a round trip, and deleted field numbers must be reserved."
    ),
    "excerpt": (
        "Protocol Buffers serialization uses a message type and field numbers. "
        "Updating a message type covers backward compatibility and forward compatibility. "
        "Unknown fields can be retained for a round trip, and deleted field numbers must be reserved."
    ),
}
balanced_coverage = server.representation_evidence_coverage(
    schema_evolution_source_route,
    [
        official_json_standard,
        official_json_evolution,
        official_protobuf_evolution,
    ],
    allow_boundaries=True,
)
partial_coverage = server.representation_evidence_coverage(
    schema_evolution_source_route,
    [official_protobuf_evolution, secondary_summary],
)
check(
    "representation-grounding-requires-fetched-primary-coverage-for-every-option",
    balanced_coverage.get("complete")
    and not partial_coverage.get("complete")
    and any(
        item.get("option") == "JSON" and item.get("kind") == "primary-source"
        for item in partial_coverage.get("missing") or []
    ),
    {"balanced": balanced_coverage, "partial": partial_coverage},
)
missing_round_trip_json = {
    **official_json_evolution,
    "text": official_json_evolution["text"].replace(
        "while application readers determine round-trip behavior.",
        "while application readers determine deserialization behavior.",
    ),
    "excerpt": official_json_evolution["excerpt"].replace(
        "while application readers determine round-trip behavior.",
        "while application readers determine deserialization behavior.",
    ),
}
missing_round_trip_coverage = server.representation_evidence_coverage(
    schema_evolution_source_route,
    [official_json_standard, missing_round_trip_json, official_protobuf_evolution],
)
bounded_round_trip_coverage = server.representation_evidence_coverage(
    schema_evolution_source_route,
    [official_json_standard, missing_round_trip_json, official_protobuf_evolution],
    allow_boundaries=True,
)
check(
    "every-requested-evolution-dimension-needs-proof-or-an-explicit-boundary",
    not missing_round_trip_coverage.get("complete")
    and any(
        item.get("option") == "JSON"
        and item.get("kind") == "round-trip-boundary"
        for item in missing_round_trip_coverage.get("missing") or []
    )
    and bounded_round_trip_coverage.get("complete")
    and "round-trip-boundary"
    in (
        bounded_round_trip_coverage.get("optionEvidenceBoundaries", {}).get("JSON")
        or []
    ),
    {
        "unbounded": missing_round_trip_coverage,
        "bounded": bounded_round_trip_coverage,
    },
)
compiled_boundary_route = copy.deepcopy(schema_evolution_source_route)
compiled_boundary_route["_representationEvidenceCoverage"] = (
    bounded_round_trip_coverage
)
compiled_boundary_answer = server.representation_coverage_compiled_answer(
    compiled_boundary_route,
    [official_json_standard, missing_round_trip_json, official_protobuf_evolution],
)
check(
    "coverage-compiler-answers-both-options-without-inventing-missing-mechanisms",
    compiled_boundary_answer.count("\n\n") == 3
    and "JSON and Protocol Buffers are serialized payload representations"
    in compiled_boundary_answer
    and "Backward compatibility means a newer reader consumes an older payload"
    in compiled_boundary_answer
    and "For JSON, the base-format source defines the stored form"
    in compiled_boundary_answer
    and "For Protocol Buffers, the official material explicitly covers"
    in compiled_boundary_answer
    and not server.representation_source_claim_issues(
        compiled_boundary_route,
        compiled_boundary_answer,
        [
            official_json_standard,
            missing_round_trip_json,
            official_protobuf_evolution,
        ],
    )
    and not server.source_backed_explanation_candidate_issues(
        compiled_boundary_route,
        compiled_boundary_answer,
    ),
    compiled_boundary_answer,
)
balanced_rows = server.balance_representation_primary_results(
    [
        (300, secondary_summary),
        (180, official_protobuf_evolution),
        (175, official_json_standard),
        (170, official_json_evolution),
    ],
    schema_evolution_source_route,
)
check(
    "primary-source-balancing-prevents-one-option-or-secondary-pages-from-owning-fetch-budget",
    len(balanced_rows) == 4
    and official_json_standard["url"]
    in [item.get("url") for _score, item in balanced_rows[:3]]
    and all(
        any(
            server.representation_evidence_matches_option(item, option)
            and server.technical_source_classification(item).get("primaryTechnical")
            for _score, item in balanced_rows[:3]
        )
        for option in ("JSON", "Protocol Buffers")
    )
    and balanced_rows[0][1]["url"] != secondary_summary["url"],
    balanced_rows,
)
protojson_bridge = {
    **official_protobuf_evolution,
    "title": "ProtoJSON Format | Protocol Buffers Documentation",
    "pageTitle": "ProtoJSON Format | Protocol Buffers Documentation",
    "url": "https://protobuf.dev/programming-guides/json/",
    "text": (
        "ProtoJSON maps Protocol Buffers messages to JSON and discusses unknown JSON fields."
    ),
    "excerpt": (
        "ProtoJSON maps Protocol Buffers messages to JSON and discusses unknown JSON fields."
    ),
}
check(
    "bridge-document-cannot-satisfy-both-option-coverage-obligations",
    server.representation_evidence_is_bridge(
        protojson_bridge,
        schema_evolution_source_route,
    )
    and server.representation_evidence_owned_options(
        protojson_bridge,
        schema_evolution_source_route,
    )
    == ["Protocol Buffers"],
    {
        "bridge": server.representation_evidence_is_bridge(
            protojson_bridge,
            schema_evolution_source_route,
        ),
        "owners": server.representation_evidence_owned_options(
            protojson_bridge,
            schema_evolution_source_route,
        ),
    },
)
neutral_protojson_bridge = {
    **protojson_bridge,
    "title": "JSON Mapping",
    "pageTitle": "JSON Mapping",
}
check(
    "publisher-host-and-url-path-expose-neutral-title-bridge-pages",
    server.representation_evidence_is_bridge(
        neutral_protojson_bridge,
        schema_evolution_source_route,
    )
    and server.representation_evidence_owned_options(
        neutral_protojson_bridge,
        schema_evolution_source_route,
    )
    == ["Protocol Buffers"],
    {
        "bridge": server.representation_evidence_is_bridge(
            neutral_protojson_bridge,
            schema_evolution_source_route,
        ),
        "owners": server.representation_evidence_owned_options(
            neutral_protojson_bridge,
            schema_evolution_source_route,
        ),
    },
)
json_schema_profile_page = {
    **official_json_evolution,
    "title": "Moving Toward a Stable JSON Schema",
    "pageTitle": "Moving Toward a Stable JSON Schema",
    "url": "https://json-schema.org/blog/posts/stable-json-schema",
}
check(
    "more-specific-schema-publisher-cannot-own-the-base-format-by-host-substring",
    server.representation_publisher_owned_options(
        json_schema_profile_page,
        schema_evolution_source_route,
    )
    == []
    and server.representation_identity_names_more_specific_option(
        json_schema_profile_page,
        "JSON",
    )
    and "JSON"
    not in server.representation_evidence_owned_options(
        json_schema_profile_page,
        schema_evolution_source_route,
    ),
    {
        "publisherOwners": server.representation_publisher_owned_options(
            json_schema_profile_page,
            schema_evolution_source_route,
        ),
        "owners": server.representation_evidence_owned_options(
            json_schema_profile_page,
            schema_evolution_source_route,
        ),
    },
)
spoofed_official_guide = {
    "title": "Official Protocol Buffers Language Guide",
    "pageTitle": "Official Protocol Buffers Language Guide",
    "url": "https://untrusted-guides.example/protobuf/official-language-guide",
    "text": "Official documentation and language guide for schema evolution and unknown fields." * 3,
    "excerpt": "Official documentation and language guide for schema evolution and unknown fields." * 3,
    "fetched": True,
}
check(
    "official-wording-on-an-untrusted-host-does-not-prove-publisher-authority",
    server.technical_source_classification(spoofed_official_guide).get(
        "primaryTechnical"
    )
    and not server.representation_evidence_authoritative_primary(
        spoofed_official_guide,
        schema_evolution_source_route,
    ),
    {
        "classification": server.technical_source_classification(
            spoofed_official_guide
        ),
        "authoritative": server.representation_evidence_authoritative_primary(
            spoofed_official_guide,
            schema_evolution_source_route,
        ),
    },
)
check(
    "official-project-and-standards-documentation-outrank-secondary-summaries",
    server.technical_primary_evidence_requested(schema_evolution_source_route)
    and server.technical_source_classification(official_protobuf).get(
        "primaryTechnical"
    )
    and server.technical_source_classification(official_json_standard).get(
        "primaryTechnical"
    )
    and not server.technical_source_classification(secondary_summary).get(
        "primaryTechnical"
    )
    and not server.technical_source_classification(
        secondary_document_mirror
    ).get("primaryTechnical")
    and server.evidence_score(
        schema_evolution_source_route["_messages"][0]["text"],
        official_protobuf,
        route=schema_evolution_source_route,
    )
    > server.evidence_score(
        schema_evolution_source_route["_messages"][0]["text"],
        secondary_summary,
        route=schema_evolution_source_route,
    ),
    {
        "protobuf": server.technical_source_classification(official_protobuf),
        "json": server.technical_source_classification(official_json_standard),
        "secondary": server.technical_source_classification(secondary_summary),
        "secondaryMirror": server.technical_source_classification(
            secondary_document_mirror
        ),
    },
)
source_prompt = server.source_backed_local_research_prompt(
    schema_evolution_source_route["_messages"][0]["text"],
    schema_evolution_source_route,
    [official_protobuf, official_json_standard],
    messages=schema_evolution_source_route["_messages"],
)
check(
    "source-backed-author-inherits-the-explanation-and-semantic-family-contract",
    "Speech act: explanation, not selection" in source_prompt
    and "Named options that must each be explained: JSON, Protocol Buffers"
    in source_prompt
    and "Representation family: data-serialization" in source_prompt
    and "Do not choose, rank, recommend, refuse to choose" in source_prompt
    and "return one valid JSON object matching the supplied schema" in source_prompt
    and "hard fault, thermal, and EMI" not in source_prompt,
    source_prompt,
)
compact_source_prompt = server.source_backed_representation_explanation_prompt(
    schema_evolution_source_route["_messages"][0]["text"],
    schema_evolution_source_route,
    [official_protobuf, official_json_standard, secondary_document_mirror],
)
check(
    "natural-source-author-gets-a-compact-primary-only-semantic-packet",
    "Return exactly four complete natural prose paragraphs" in compact_source_prompt
    and "one JSON object matching the supplied output schema" in compact_source_prompt
    and "emit no text outside the JSON object" in compact_source_prompt
    and "Paragraph 1 names both options" in compact_source_prompt
    and "Paragraph 2 defines both compatibility directions" in compact_source_prompt
    and "Paragraph 3 names the first option" in compact_source_prompt
    and "Paragraph 4 names the second option" in compact_source_prompt
    and "Do not confuse an unknown JSON Schema keyword with an unknown member"
    in compact_source_prompt
    and "Prefer a conditional boundary over common-practice folklore"
    in compact_source_prompt
    and "backward compatibility" in compact_source_prompt.lower()
    and "unknown member" in compact_source_prompt
    and official_protobuf["url"] in compact_source_prompt
    and official_json_standard["url"] in compact_source_prompt
    and secondary_document_mirror["url"] not in compact_source_prompt
    and len(compact_source_prompt) < len(source_prompt),
    {
        "compactChars": len(compact_source_prompt),
        "fullChars": len(source_prompt),
        "prompt": compact_source_prompt,
    },
)
wrong_source_answer = (
    "I would not choose between JSON and Protocol Buffers yet. The sources do not establish a defensible winner.\n\n"
    "What could reverse the eventual choice is whether one candidate meets hard fault, thermal, and EMI limits at the operating point. "
    "Total loss and BOM cost can then decide the winner."
)
wrong_source_issues = server.source_backed_explanation_candidate_issues(
    schema_evolution_source_route,
    wrong_source_answer,
)
schema_evolution_source_route["_primaryTechnicalEvidenceUrls"] = [
    official_protobuf["url"],
    official_json_standard["url"],
]
wrong_source_gate = server.task_contract_gate(
    schema_evolution_source_route["_messages"],
    schema_evolution_source_route,
    wrong_source_answer
    + "\n\nSources checked: "
    + official_protobuf["url"],
    web_search="live",
)
check(
    "source-backed-explanation-gate-rejects-decision-template-contamination",
    {
        item.get("kind") for item in wrong_source_issues
    }
    >= {
        "cross-family-representation-language",
        "unrequested-source-backed-decision",
        "unrequested-source-backed-reversal",
    }
    and wrong_source_gate.get("status") == "block"
    and any(
        item.get("label")
        == "Explanation speech act and representation semantics"
        and not item.get("passed")
        for item in wrong_source_gate.get("checks") or []
    ),
    {
        "issues": wrong_source_issues,
        "gate": wrong_source_gate,
    },
)
engineering_decision_route = route(
    "Compare IGBTs and silicon-carbide MOSFETs for a traction inverter and recommend one based on switching loss, thermal design, EMI, and cost."
)
engineering_decision_route = copy.deepcopy(engineering_decision_route)
engineering_decision_route["intentFrame"][
    "evidenceNeed"
] = "technical-primary-evidence"
check(
    "primary-source-explanations-do-not-inherit-engineering-decision-audits",
    not server.technical_engineering_decision_audit_requested(
        schema_evolution_source_route
    )
    and server.technical_engineering_decision_audit_requested(
        engineering_decision_route
    ),
    {
        "explanation": schema_evolution_source_route.get("intentFrame"),
        "decision": engineering_decision_route.get("intentFrame"),
    },
)
schema_overclaim_answer = (
    "JSON stores text values and names, while Protocol Buffers serializes fields described by a schema. "
    "The stored payload remains separate from native application runtime state.\n\n"
    "Protocol Buffers requires synchronized schema versions for correct interpretation. "
    "Its strict contract prevents accidental data loss during round trips.\n\n"
    "Compatibility depends on producer and consumer behavior, field reuse, and unknown-field handling."
)
schema_overclaim_issues = server.stable_comparison_epistemic_overclaim_issues(
    json_messages,
    json_route,
    schema_overclaim_answer,
)
check(
    "schema-evolution-and-prevention-overclaims-fail-cross-domain",
    {
        item.get("kind") for item in schema_overclaim_issues
    }
    >= {
        "blanket-synchronized-schema-requirement",
        "source-free-absolute-assurance",
    },
    schema_overclaim_issues,
)
json_contract = server.task_contract(json_messages, json_route)
check(
    "explanatory-contract-is-domain-neutral-and-does-not-demand-a-winner",
    json_contract.get("kind") == "Expert comparison"
    and "without forcing an unrequested recommendation"
    in str(json_contract.get("doneMeans") or "")
    and "qualified conclusion"
    not in [str(item) for item in json_contract.get("requiredProof") or []]
    and "named-option distinction"
    in [str(item) for item in json_contract.get("requiredProof") or []],
    json_contract,
)
domain_neutral_boundary_answer = (
    "JSON stores names and primitive values in text, but it does not inherently encode the application's semantics. "
    "Protocol Buffers stores field values interpreted through a separate schema.\n\n"
    "The serialized payload is separate from the live application data model and its runtime invariants. "
    "Editing either representation therefore does not by itself preserve application behavior.\n\n"
    "Round-trip behavior depends on the producer, consumer, schema version, unknown-field handling, and field reuse."
)
domain_neutral_issues = server.representation_semantics_candidate_issues(
    json_route,
    domain_neutral_boundary_answer,
)
check(
    "application-semantics-language-satisfies-the-domain-neutral-source-boundary",
    not any(
        item.get("kind")
        in {
            "missing-native-source-boundary",
            "missing-explicit-native-source-separation",
        }
        for item in domain_neutral_issues
    ),
    domain_neutral_issues,
)
check(
    "schema-compliance-is-not-misread-as-legal-authority",
    not server.SOURCE_FREE_AUTHORITY_RE.search(
        "Protocol Buffers can enforce schema compliance in a particular toolchain."
    ),
    server.SOURCE_FREE_AUTHORITY_RE.pattern,
)
observed_serialization_overclaim = (
    "JSON preserves decoded values and schema-defined meaning without requiring external definitions. "
    "Protocol Buffers enforce strict typing at serialization time, ensuring that decoded values match the schema precisely.\n\n"
    "Protocol Buffers offer byte-level stability if the schema remains unchanged, but field reuse or unknown-field handling can cause data loss during evolution. "
    "Neither format preserves native authoring intent."
)
observed_serialization_issues = server.representation_semantics_candidate_issues(
    json_route,
    observed_serialization_overclaim,
)
check(
    "polished-serialization-overclaims-fail-at-the-correct-layer",
    {
        item.get("kind") for item in observed_serialization_issues
    }
    >= {
        "schema-meaning-without-schema",
        "source-free-absolute-assurance",
        "unqualified-byte-level-stability",
        "implied-interchange-native-semantics",
        "schema-evolution-boundary-incomplete",
    },
    observed_serialization_issues,
)
cross_family_serialization_answer = (
    "JSON stores names and values, while Protocol Buffers stores schema-defined fields. "
    "The serialized payload is separate from the live application model. Neither payload encodes native feature history or design intent. "
    "Producer and consumer behavior controls compatibility."
)
cross_family_serialization_issues = server.representation_semantics_candidate_issues(
    json_route,
    cross_family_serialization_answer,
)
check(
    "typed-data-family-rejects-borrowed-cad-concepts",
    any(
        item.get("kind") == "cross-family-representation-language"
        for item in cross_family_serialization_issues
    ),
    cross_family_serialization_issues,
)
readable_names_semantics_answer = (
    "JSON stores explicit field names and values, making it syntactically self-describing. "
    "This format preserves application meaning through human-readable identifiers.\n\n"
    "Protocol Buffers require producers and consumers to share a schema for correct interpretation.\n\n"
    "JSON consumers handle unknown keys for forward compatibility. Protocol Buffers cover backward and forward compatibility, field reuse, and version transitions."
)
readable_names_semantics_issues = server.representation_semantics_candidate_issues(
    json_route,
    readable_names_semantics_answer,
)
check(
    "readable-names-do-not-become-application-semantics-or-identical-schema",
    {
        item.get("kind") for item in readable_names_semantics_issues
    }
    >= {
        "source-free-interchange-native-semantics",
        "blanket-synchronized-schema-requirement",
    },
    readable_names_semantics_issues,
)
schema_difference_answer = (
    "The serialized payload is separate from the live application model and runtime state. "
    "Producer and consumer schemas may differ when their field changes follow the applicable compatibility rules. "
    "Backward compatibility, forward compatibility, unknown-field handling, and field reuse govern schema evolution."
)
schema_difference_issues = server.representation_semantics_candidate_issues(
    json_route,
    schema_difference_answer,
)
check(
    "affirmative-compatible-schema-evolution-is-not-rejected-as-synchronization",
    not any(
        item.get("kind") == "blanket-synchronized-schema-requirement"
        for item in schema_difference_issues
    ),
    schema_difference_issues,
)
identifier_reuse_answer = (
    "JSON stores names and values, while Protocol Buffers stores numeric field identifiers and encoded values. "
    "The serialized payload is separate from the live application model and runtime state.\n\n"
    "JSON backward compatibility and forward compatibility are application-defined alongside unknown keys and identifier reuse. "
    "Protocol Buffers backward compatibility and forward compatibility also depend on unknown fields and tag reuse.\n\n"
    "Producer and consumer behavior controls interpretation and round-trip results."
)
identifier_reuse_issues = server.representation_semantics_candidate_issues(
    json_route,
    identifier_reuse_answer,
)
check(
    "identifier-and-tag-reuse-satisfy-the-generic-evolution-dimension",
    not any(
        item.get("kind") == "schema-evolution-boundary-incomplete"
        for item in identifier_reuse_issues
    ),
    identifier_reuse_issues,
)
reused_identifier_answer = (
    "JSON stores names and values, while Protocol Buffers stores numeric field identifiers and encoded values. The serialized payload is separate from the live application model.\n\n"
    "JSON backward compatibility and forward compatibility depend on unknown keys and how renamed or reused identifiers are interpreted. Protocol Buffers backward compatibility and forward compatibility depend on unknown fields; reusing deleted tag numbers causes data corruption.\n\n"
    "Producer and consumer behavior controls interpretation and round-trip results."
)
reused_identifier_issues = server.representation_semantics_candidate_issues(
    json_route,
    reused_identifier_answer,
)
check(
    "reused-identifier-phrasing-counts-while-inevitable-harm-does-not",
    not any(
        item.get("kind") == "schema-evolution-boundary-incomplete"
        for item in reused_identifier_issues
    )
    and any(
        item.get("kind") == "unqualified-schema-evolution-outcome"
        for item in reused_identifier_issues
    ),
    reused_identifier_issues,
)
qualified_reuse_harm_issues = server.representation_semantics_candidate_issues(
    json_route,
    reused_identifier_answer.replace(
        "causes data corruption",
        "can cause data corruption when a consumer assigns the old tag a different meaning",
    ),
)
check(
    "conditional-reuse-harm-is-not-misread-as-inevitable",
    not any(
        item.get("kind") == "unqualified-schema-evolution-outcome"
        for item in qualified_reuse_harm_issues
    ),
    qualified_reuse_harm_issues,
)
direct_reuse_harm_issues = server.representation_semantics_candidate_issues(
    json_route,
    reused_identifier_answer.replace(
        "reusing deleted tag numbers causes data corruption",
        "reusing a deleted tag breaks interpretation",
    ),
)
check(
    "direct-tag-reuse-harm-must-remain-conditional",
    any(
        item.get("kind") == "unqualified-schema-evolution-outcome"
        for item in direct_reuse_harm_issues
    ),
    direct_reuse_harm_issues,
)
conditional_direct_reuse_harm_issues = server.representation_semantics_candidate_issues(
    json_route,
    reused_identifier_answer.replace(
        "reusing deleted tag numbers causes data corruption",
        "reusing a deleted tag can break interpretation when the consumer assigns that tag a different meaning",
    ),
)
check(
    "conditional-direct-tag-reuse-harm-remains-admissible",
    not any(
        item.get("kind") == "unqualified-schema-evolution-outcome"
        for item in conditional_direct_reuse_harm_issues
    ),
    conditional_direct_reuse_harm_issues,
)
one_sided_evolution_answer = (
    "JSON stores names and values, while Protocol Buffers stores numeric field identifiers and encoded values. "
    "The serialized payload is separate from the live application model and runtime state.\n\n"
    "Protocol Buffers backward compatibility and forward compatibility depend on unknown fields and tag reuse.\n\n"
    "Producer and consumer behavior controls interpretation and round-trip results."
)
one_sided_evolution_issues = server.representation_semantics_candidate_issues(
    json_route,
    one_sided_evolution_answer,
)
check(
    "schema-evolution-consequences-must-cover-every-named-representation",
    any(
        item.get("kind") == "per-option-schema-evolution-boundary-incomplete"
        and item.get("claim") == "JSON"
        for item in one_sided_evolution_issues
    ),
    one_sided_evolution_issues,
)
formally_green_but_human_weak_answer = (
    "JSON stores text-based key-value pairs, while Protocol Buffers store binary fields identified by tags. The stored payload is separate from the live application model.\n\n"
    "The serialized text does not establish any persistent layer beyond the exchange.\n\n"
    "Compatibility depends entirely on producers and consumers. JSON allows unknown members to pass through, supporting forward compatibility. Protocol Buffers tag reuse breaks backward compatibility."
)
formally_green_but_human_weak_issues = server.representation_semantics_candidate_issues(
    json_route,
    formally_green_but_human_weak_answer,
)
check(
    "broad-persistence-retention-and-dependency-claims-fail-human-quality-gate",
    {
        item.get("kind") for item in formally_green_but_human_weak_issues
    }
    >= {
        "unqualified-payload-persistence-boundary",
        "unqualified-representation-dependency",
        "unqualified-unknown-member-retention",
        "per-option-schema-evolution-boundary-incomplete",
    },
    formally_green_but_human_weak_issues,
)
role_paragraph_attribution_answer = (
    "JSON stores names and values, while Protocol Buffers stores numeric field identifiers and values. The serialized payload is separate from the live application model.\n\n"
    "JSON schema evolution is application-defined. Backward compatibility and forward compatibility depend on unknown-key handling. Reusing an identifier can change its interpreted meaning.\n\n"
    "Protocol Buffers schema evolution follows the applicable schema rules. Backward compatibility and forward compatibility depend on unknown-field handling. Reusing a tag can change its interpreted meaning, and round-trip behavior depends on the runtime."
)
role_paragraph_attribution_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer,
)
check(
    "single-option-role-paragraph-carries-its-following-sentences",
    not any(
        item.get("kind") == "per-option-schema-evolution-boundary-incomplete"
        for item in role_paragraph_attribution_issues
    ),
    role_paragraph_attribution_issues,
)
same_schema_rules_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer
    + " Both sides must follow the same schema version rules, even when their schema versions differ.",
)
check(
    "same-schema-version-rules-do-not-mean-identical-schema-versions",
    not any(
        item.get("kind") == "blanket-synchronized-schema-requirement"
        for item in same_schema_rules_issues
    ),
    same_schema_rules_issues,
)
unqualified_optional_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer
    + " A newer reader accepts missing optional fields while an older reader ignores added fields.",
)
check(
    "required-and-optional-labels-require-an-explicit-schema-boundary",
    any(
        item.get("kind") == "unqualified-required-optional-schema-rule"
        for item in unqualified_optional_issues
    ),
    unqualified_optional_issues,
)
qualified_optional_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer
    + " Under the applicable schema edition, a newer reader accepts missing optional fields while an older reader ignores added fields.",
)
check(
    "schema-qualified-required-and-optional-labels-remain-admissible",
    not any(
        item.get("kind") == "unqualified-required-optional-schema-rule"
        for item in qualified_optional_issues
    ),
    qualified_optional_issues,
)
unsupported_frequency_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer
    + " Identifier reuse is rare.",
)
check(
    "source-free-schema-evolution-does-not-invent-frequency",
    any(
        item.get("kind") == "unqualified-schema-frequency-claim"
        for item in unsupported_frequency_issues
    ),
    unsupported_frequency_issues,
)
undefined_direction_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer,
)
check(
    "backward-and-forward-labels-require-reader-version-direction",
    any(
        item.get("kind") == "schema-evolution-direction-undefined"
        for item in undefined_direction_issues
    ),
    undefined_direction_issues,
)
directionally_complete_answer = (
    "JSON and Protocol Buffers store serialized names or field identifiers and values, not the live application model or runtime state. Application meaning remains in the producer and consumer contract.\n\n"
    "For JSON under the applicable application schema, backward compatibility means a newer reader can consume an older payload, while forward compatibility means an older reader can consume a newer payload. Parser behavior controls unknown keys, and reusing a key can change interpretation when its assigned meaning changes.\n\n"
    "For Protocol Buffers under the applicable schema edition, backward compatibility means a newer reader can consume an older payload, while forward compatibility means an older reader can consume a newer payload. The runtime controls unknown-field handling, and reusing a numeric tag can break interpretation when a consumer applies its earlier field definition."
)
directionally_complete_issues = server.representation_semantics_candidate_issues(
    json_route,
    directionally_complete_answer,
)
check(
    "directionally-defined-schema-evolution-answer-passes-the-new-boundaries",
    not any(
        item.get("kind")
        in {
            "schema-evolution-direction-undefined",
            "unqualified-required-optional-schema-rule",
            "unqualified-schema-frequency-claim",
            "unqualified-schema-evolution-outcome",
            "per-option-schema-evolution-boundary-incomplete",
        }
        for item in directionally_complete_issues
    ),
    directionally_complete_issues,
)
four_role_serialization_answer = (
    "JSON and Protocol Buffers store serialized names, field identifiers, and values. Those payloads are distinct from the live application model and runtime state, and their stored content does not by itself establish application meaning.\n\n"
    "Backward compatibility means a newer reader consumes an older payload. Forward compatibility means an older reader consumes a newer payload.\n\n"
    "JSON backward compatibility and forward compatibility depend on the applicable consumer contract. Its parser controls unknown-key handling, and key reuse can change interpretation when an application assigns a different meaning.\n\n"
    "Protocol Buffers backward compatibility and forward compatibility depend on the applicable schema evolution rules. Its runtime controls unknown-field handling, and tag reuse can change interpretation when a consumer applies an earlier field definition. Round-trip behavior depends on the producer, consumer, schema, runtime, and toolchain."
)
four_role_serialization_gate = server.stable_expert_comparison_candidate_gate(
    json_messages,
    json_route,
    four_role_serialization_answer,
)
check(
    "data-serialization-may-render-four-typed-natural-paragraphs",
    not any(
        item.get("kind") == "explanation-paragraph-contract"
        for item in four_role_serialization_gate.get("speechActIssues") or []
    )
    and not any(
        item.get("kind") == "missing-explicit-native-source-separation"
        for item in four_role_serialization_gate.get("epistemicIssues") or []
    ),
    four_role_serialization_gate,
)
live_direction_mechanism_bad_answer = (
    "JSON and Protocol Buffers store serialized payloads separate from live application state. Stored values do not by themselves establish application meaning.\n\n"
    "Backward compatibility means a newer reader consumes older payloads without failure. Forward compatibility means an older reader consumes newer payloads without breaking execution.\n\n"
    "JSON backward compatibility relies on consumers ignoring missing fields. JSON forward compatibility requires readers to skip unknown members. Unknown-member handling varies by parser. Key reuse can create interpretation conflicts when meanings differ.\n\n"
    "Protocol Buffers backward compatibility works when new fields have default values for older readers. Protocol Buffers forward compatibility lets older readers skip unknown tags safely. Unknown-field retention depends on the runtime. Tag reuse is dangerous because reusing a number changes meaning entirely."
)
live_direction_mechanism_issue_kinds = {
    item.get("kind")
    for item in server.representation_semantics_candidate_issues(
        json_route,
        live_direction_mechanism_bad_answer,
    )
}
check(
    "live-reader-direction-and-mechanism-errors-fail-closed",
    live_direction_mechanism_issue_kinds
    >= {
        "schema-evolution-direction-overpromised",
        "schema-evolution-mechanism-conflict",
        "schema-evolution-reader-role-conflict",
        "unqualified-schema-evolution-outcome",
    },
    sorted(live_direction_mechanism_issue_kinds),
)
qualified_direction_promises = server.qualify_schema_evolution_direction_promises(
    "Backward compatibility lets a newer reader consume an older payload without error. "
    "Forward compatibility lets an older reader consume a newer payload without breaking execution. "
    "A separate sentence without error should remain unchanged."
)
check(
    "schema-evolution-normalizer-removes-error-free-promises-only-from-compatibility-sentences",
    "without error" not in qualified_direction_promises.split("Forward compatibility", 1)[0]
    and "without breaking" not in qualified_direction_promises
    and "rules execution" not in qualified_direction_promises
    and qualified_direction_promises.count(
        "under the applicable schema and runtime rules"
    )
    == 2
    and "A separate sentence without error should remain unchanged."
    in qualified_direction_promises,
    qualified_direction_promises,
)
source_boundary_route = copy.deepcopy(json_route)
source_boundary_route["_representationEvidenceCoverage"] = {
    "kind": "representation-evidence-coverage",
    "version": 1,
    "complete": True,
    "options": ["JSON", "Protocol Buffers"],
    "optionEvidenceBoundaries": {
        "JSON": ["identifier-lifecycle", "round-trip-boundary"],
        "Protocol Buffers": [],
    },
}
unsupported_identifier_consequence = (
    "JSON backward compatibility and forward compatibility depend on the applicable application schema. "
    "Unknown members are controlled by that schema and parser, but identifier reuse overwrites the previous value.\n\n"
    "Protocol Buffers backward compatibility and forward compatibility depend on its schema evolution rules. "
    "Unknown fields and tag reuse follow the documented runtime and reservation rules."
)
unsupported_identifier_source_issues = server.representation_source_claim_issues(
    source_boundary_route,
    unsupported_identifier_consequence,
    [official_json_standard, official_protobuf_evolution],
)
check(
    "identifier-consequences-cannot-cross-an-explicit-primary-evidence-boundary",
    any(
        item.get("kind") == "representation-claim-beyond-evidence"
        and str(item.get("reason") or "").startswith("JSON:")
        for item in unsupported_identifier_source_issues
    ),
    unsupported_identifier_source_issues,
)
unknown_retention_issues = server.representation_semantics_candidate_issues(
    json_route,
    role_paragraph_attribution_answer.replace(
        "Backward compatibility and forward compatibility depend on unknown-key handling.",
        "Backward compatibility and forward compatibility depend on unknown keys being skipped, preserving existing data.",
        1,
    ),
)
check(
    "skipping-unknown-members-does-not-prove-an-operational-outcome",
    any(
        item.get("kind") == "unqualified-unknown-member-outcome"
        for item in unknown_retention_issues
    ),
    unknown_retention_issues,
)

hedged_bad_answer = (
    "A STEP file acts as an interchange format that retains parametric intent to varying degrees depending on the exporter. "
    "STEP files support later editing because they maintain the logical structure of the model, while STL stores triangles. "
    "The receiving application controls how much editing is available after import."
)
hedged_bad_issues = server.representation_semantics_candidate_issues(
    step_route, hedged_bad_answer
)
check(
    "hedged-interchange-native-semantics-still-fail-source-free",
    any(
        item.get("kind") == "source-free-interchange-native-semantics"
        for item in hedged_bad_issues
    ),
    hedged_bad_issues,
)

live_style_bad_answer = (
    "A STEP file stores precise boundary-representation geometry and serves as an interchange format. "
    "It retains the geometric intent needed for later modification. An STL stores a triangulated surface.\n\n"
    "The reverse conversion is impossible because the original design intent is absent. "
    "I recommend STEP for later engineering changes. I would reverse this recommendation for slicing only. "
    "My first test would import both files and edit a hole."
)
live_style_gate = server.stable_expert_comparison_candidate_gate(
    step_messages, step_route, live_style_bad_answer
)
check(
    "live-style-overclaim-and-unrequested-work-fail-closed",
    not live_style_gate.get("accepted")
    and {
        item.get("kind")
        for item in live_style_gate.get("epistemicIssues") or []
    }
    >= {
        "source-free-interchange-native-semantics",
        "absolute-representation-conversion-claim",
    }
    and {
        item.get("kind")
        for item in live_style_gate.get("speechActIssues") or []
    }
    >= {
        "unrequested-recommendation",
        "unrequested-reversal-condition",
        "unrequested-validation-test",
    },
    live_style_gate,
)

serialization_route = conceptual_routes[3]
serialization_bad_answer = (
    "JSON is self-describing and its round trip is lossless regarding text content. "
    "Protocol Buffers require synchronized schema versions between every producer and consumer."
)
serialization_issues = server.representation_semantics_candidate_issues(
    serialization_route, serialization_bad_answer
)
check(
    "serialization-layer-absolutes-fail-across-a-second-domain",
    {
        item.get("kind") for item in serialization_issues
    }
    >= {
        "unqualified-self-describing-layer",
        "undefined-lossless-identity",
        "blanket-synchronized-schema-requirement",
    },
    serialization_issues,
)
qualified_self_description = (
    "The serialized payload is separate from native runtime state. JSON is syntactically self-describing at the token and value-structure layer, not at the application-semantics layer. "
    "Its decoded values still need application rules, while round-trip behavior depends on the parser and serializer toolchain."
)
check(
    "adverbial-syntactic-qualification-is-not-falsely-rejected",
    not any(
        item.get("kind") == "unqualified-self-describing-layer"
        for item in server.representation_semantics_candidate_issues(
            serialization_route,
            qualified_self_description,
        )
    ),
    server.representation_semantics_candidate_issues(
        serialization_route,
        qualified_self_description,
    ),
)
lexical_self_description = (
    "JSON stores a self-describing lexical structure. The serialized payload is separate from the live application model, and round-trip behavior depends on the parser and serializer."
)
check(
    "lexical-self-description-names-a-valid-syntax-layer",
    not any(
        item.get("kind") == "unqualified-self-describing-layer"
        for item in server.representation_semantics_candidate_issues(
            serialization_route,
            lexical_self_description,
        )
    ),
    server.representation_semantics_candidate_issues(
        serialization_route,
        lexical_self_description,
    ),
)
backward_contract_answer = (
    "JSON stores names and values, while Protocol Buffers stores numeric field identifiers and encoded values. The serialized payload is separate from the live application model.\n\n"
    "JSON lacks strict backward contracts but can support forward compatibility through unknown-key handling and identifier reuse. Protocol Buffers backward rules and forward compatibility depend on unknown fields and tag reuse.\n\n"
    "Producer and consumer behavior controls interpretation and round-trip results."
)
check(
    "backward-contract-and-rule-language-satisfies-the-evolution-dimension",
    not any(
        item.get("kind") == "schema-evolution-boundary-incomplete"
        for item in server.representation_semantics_candidate_issues(
            json_route,
            backward_contract_answer,
        )
    ),
    server.representation_semantics_candidate_issues(
        json_route,
        backward_contract_answer,
    ),
)

accepted_live_repair_bad_answer = (
    "STEP stores boundary-representation geometry, while STL stores triangle facets and normals. "
    "STL discards native-source history.\n\n"
    "Downstream CAD tools can interpret STEP curves for dimensioning. Converting STEP to STL is lossy, "
    "while converting STL back to STEP is generally impossible without manual reconstruction due to the irretrievable loss of parametric intent."
)
accepted_live_repair_bad_issues = server.representation_semantics_candidate_issues(
    step_route,
    accepted_live_repair_bad_answer,
)
check(
    "keyword-scattering-cannot-satisfy-native-and-conversion-boundaries",
    {
        item.get("kind") for item in accepted_live_repair_bad_issues
    }
    >= {
        "missing-explicit-native-source-separation",
        "absolute-representation-conversion-claim",
        "implied-interchange-native-semantics",
    },
    accepted_live_repair_bad_issues,
)
observed_failed_repair = (
    "The stored payload is separate from native authoring state. STL discards parametric history. "
    "Reversing this conversion is impossible because constraints are not present. "
    "The mesh offers no mechanism for verifying geometric accuracy beyond visual inspection."
)
observed_failed_repair_issues = server.representation_semantics_candidate_issues(
    step_route,
    observed_failed_repair,
)
check(
    "conversion-and-validation-absolutes-fail-at-the-correct-layer",
    {
        item.get("kind") for item in observed_failed_repair_issues
    }
    >= {
        "absolute-representation-conversion-claim",
        "implied-interchange-native-semantics",
        "embedded-versus-external-validation-confusion",
    },
    observed_failed_repair_issues,
)
correct_separation_answer = (
    "The exported payload is separate from native authoring state and does not carry the source application's parametric history or constraints. "
    "It stores schema-defined geometry, and the importer controls the round-trip boundary."
)
correct_separation_issues = server.representation_semantics_candidate_issues(
    step_route,
    correct_separation_answer,
)
check(
    "explicit-noncarriage-of-native-state-is-not-misread-as-conversion-loss",
    not any(
        item.get("kind") == "implied-interchange-native-semantics"
        for item in correct_separation_issues
    ),
    correct_separation_issues,
)
stale_serialization_lesson = {
    "stability": "stable",
    "terminalStatus": "complete",
    "terminalMayClaimComplete": True,
    "answerSha256": "a" * 64,
    "lesson": (
        "JSON is self-describing and Protocol Buffers requires synchronized schema versions. "
        "Serialization discards native application semantics and prevents accidental data loss."
    ),
}
verified_stale_serialization_lesson = {
    **stale_serialization_lesson,
    "durableLearningEligible": True,
    "learningProof": "verified-source-provenance",
    "learningProofSha256": "a" * 64,
}
check(
    "legacy-knowledge-is-ineligible-and-verified-history-is-revalidated",
    not server.stable_knowledge_item_reuse_eligible(stale_serialization_lesson)
    and server.stable_knowledge_item_reuse_eligible(verified_stale_serialization_lesson)
    and not server.stable_knowledge_item_reuse_eligible(
        verified_stale_serialization_lesson,
        messages=json_messages,
        route=json_route,
    ),
    server.deterministic_generic_reasoning_issues(
        stale_serialization_lesson["lesson"],
        messages=json_messages,
        route=json_route,
    ),
)
geometric_intent_and_no_path_answer = (
    "The exported STEP file preserves geometric intent. The payload is separate from native authoring state, and the importer controls round-trip behavior. "
    "An STL mesh offers no path back to editable engineering data."
)
geometric_intent_and_no_path_issues = server.representation_semantics_candidate_issues(
    step_route,
    geometric_intent_and_no_path_answer,
)
check(
    "geometric-intent-and-no-path-absolutes-fail-source-free",
    {
        item.get("kind") for item in geometric_intent_and_no_path_issues
    }
    >= {
        "source-free-interchange-native-semantics",
        "absolute-representation-conversion-claim",
    },
    geometric_intent_and_no_path_issues,
)
negated_native_semantics_answer = (
    "The exported representation is separate from native authoring state. It may preserve topology but rarely restores the original feature tree or sketch constraints. "
    "Round-trip behavior depends on the importer and exporter."
)
negated_native_semantics_issues = server.representation_semantics_candidate_issues(
    step_route,
    negated_native_semantics_answer,
)
check(
    "negated-native-semantics-span-is-not-treated-as-preservation",
    not any(
        item.get("kind") == "source-free-interchange-native-semantics"
        for item in negated_native_semantics_issues
    ),
    negated_native_semantics_issues,
)
scoped_negation_answer = (
    "The serialized payload is separate from runtime behavior. Protocol Buffers store schema-defined field values without claiming to retain unproven native semantics. "
    "Round-trip behavior depends on the producer and consumer implementations."
)
scoped_negation_issues = server.representation_semantics_candidate_issues(
    json_route,
    scoped_negation_answer,
)
check(
    "without-claiming-negation-is-not-read-as-positive-retention",
    not any(
        item.get("kind") == "source-free-interchange-native-semantics"
        for item in scoped_negation_issues
    ),
    scoped_negation_issues,
)
adverbial_native_negation_answer = (
    "JSON stores lexical syntax in a serialized payload that is separate from the live application model, meaning readable identifiers do not inherently preserve application invariants. "
    "Protocol Buffers stores schema-bound values, and round-trip behavior depends on producer and consumer implementations."
)
adverbial_native_negation_issues = server.representation_semantics_candidate_issues(
    json_route,
    adverbial_native_negation_answer,
)
check(
    "adverbial-negation-is-not-read-as-positive-semantic-preservation",
    not any(
        item.get("kind") == "source-free-interchange-native-semantics"
        for item in adverbial_native_negation_issues
    ),
    adverbial_native_negation_issues,
)
step_contract = server.task_contract(step_messages, step_route)
check(
    "neutral-difference-question-does-not-acquire-recommendation-work",
    "force an unrequested recommendation"
    in str(step_contract.get("doneMeans") or "")
    and "direct format recommendation"
    not in [str(item) for item in step_contract.get("requiredProof") or []]
    and any(
        "representation-layer" in str(item)
        for item in step_contract.get("requiredProof") or []
    ),
    step_contract,
)
bad_boundary = server.generic_reasoning_boundary_answer(
    {
        "verdict": "revise",
        "issues": [
            {
                "kind": "reasoning-audit-unavailable",
                "reason": "The independent reviewer did not complete.",
            }
        ],
    },
    bad_answer,
    step_route,
)
check(
    "rejected-representation-draft-is-not-presented-as-usable-partial",
    "parametric CAD models" not in bad_boundary
    and bad_boundary.startswith("I could not close the requested result reliably."),
    bad_boundary,
)


good_answer = (
    "The practical difference is that a STEP export usually stores precise boundary-representation geometry and may carry assembly or product metadata, depending on the application protocol and exporter. "
    "It is an interchange payload, not proof that the native authoring file's sketches, feature timeline, parameters, or constraints survived.\n\n"
    "An STL is a derived triangle mesh, so it loses exact analytic geometry and higher-level model semantics. For later design changes, keep the native source, use STEP to exchange editable geometry, and use STL mainly as a delivery mesh. "
    "What can be reimported or edited depends on the receiving application; neither format provides a lossless round trip by itself."
)
technical_unless_answer = good_answer + (
    " Native source semantics remain separate unless a specific toolchain proves otherwise."
)
technical_unless_gate = server.stable_expert_comparison_candidate_gate(
    step_messages,
    step_route,
    technical_unless_answer,
)
check(
    "technical-unless-clause-is-not-a-decision-reversal",
    not any(
        item.get("kind") == "unrequested-reversal-condition"
        for item in technical_unless_gate.get("speechActIssues") or []
    ),
    technical_unless_gate,
)
good_gate = server.stable_expert_comparison_candidate_gate(
    step_messages, step_route, good_answer
)
check(
    "layered-qualified-answer-clears-representation-epistemic-gate",
    not good_gate.get("epistemicIssues"),
    good_gate,
)
check(
    "explanatory-comparison-does-not-require-an-unrequested-decision",
    not any(
        item.get("kind") == "no-decision"
        for item in good_gate.get("analyticalGaps") or []
    ),
    good_gate,
)
final_task_gate = server.task_contract_gate(
    step_messages,
    step_route,
    good_answer,
    web_search="disabled",
)
final_task_labels = {
    item.get("label") for item in final_task_gate.get("checks") or []
}
check(
    "final-emission-gate-honors-explanatory-representation-speech-act",
    final_task_gate.get("status") == "pass"
    and "Representation distinction present" in final_task_labels
    and "Representation reasoning and boundary" in final_task_labels
    and "Format recommendation present" not in final_task_labels
    and "Decision reasoning and boundary" not in final_task_labels,
    final_task_gate,
)
clean_but_unverified_boundary = server.generic_reasoning_boundary_answer(
    {
        "verdict": "revise",
        "issues": [
            {
                "kind": "final-contract-not-proven",
                "reason": "The final representation gate did not pass.",
            }
        ],
    },
    good_answer,
    step_route,
)
check(
    "representation-recovery-never-mixes-a-draft-with-machine-boilerplate",
    clean_but_unverified_boundary.startswith(
        "I could not close the requested result reliably."
    )
    and good_answer not in clean_but_unverified_boundary,
    clean_but_unverified_boundary,
)
boundary_route = dict(step_route)
boundary_route["intentFrame"] = dict(step_route.get("intentFrame") or {})
boundary_route["capabilityPlan"] = dict(step_route.get("capabilityPlan") or {})
boundary_route["kernelDecision"] = dict(step_route.get("kernelDecision") or {})
bounded_answer = server.apply_generic_reasoning_final_gate(
    step_messages,
    boundary_route,
    bad_answer,
    audit_fn=lambda *_args, **_kwargs: {
        "ok": False,
        "verdict": "revise",
        "issues": [
            {
                "kind": "implied-interchange-native-semantics",
                "reason": "The candidate treats unproven native intent as payload loss.",
            }
        ],
        "finalAnswer": "",
        "repairApplied": False,
    },
)
check(
    "reasoning-failure-registers-a-truthful-bounded-terminal-owner",
    bounded_answer.startswith("I could not close the requested result reliably.")
    and (boundary_route.get("_genericReasoningBoundary") or {}).get("status")
    == "bounded"
    and "implied-interchange-native-semantics"
    in (boundary_route.get("_genericReasoningBoundary") or {}).get(
        "issueKinds", []
    ),
    {
        "answer": bounded_answer,
        "receipt": boundary_route.get("_genericReasoningBoundary"),
    },
)
verbose_answer = good_answer.replace(". ", ".\n\n", 4)
verbose_gate = server.stable_expert_comparison_candidate_gate(
    step_messages, step_route, verbose_answer
)
check(
    "explanatory-comparison-enforces-compact-human-shape",
    not verbose_gate.get("accepted")
    and any(
        item.get("kind") == "explanation-paragraph-contract"
        for item in verbose_gate.get("speechActIssues") or []
    )
    and any(
        item.get("kind") == "explanation-paragraph-contract"
        for item in server.stable_comparison_gate_issue_rows(verbose_gate)
    ),
    verbose_gate,
)
check(
    "response-form-failure-is-not-dropped-before-repair",
    any(
        item.get("kind") == "comparison-response-form"
        for item in server.stable_comparison_gate_issue_rows(
            {"etiquetteStatus": "review", "wordCount": 120}
        )
    ),
    server.stable_comparison_gate_issue_rows(
        {"etiquetteStatus": "review", "wordCount": 120}
    ),
)

engineering_messages = [
    {
        "role": "user",
        "text": "A 24 V load draws 18 A through 12 m of cable. Calculate voltage drop and power loss.",
    }
]
engineering_route = server.route_manager(
    engineering_messages,
    cwd=str(ROOT),
    web_search="disabled",
)
engineering_answer = (
    "Using the stated cable resistance of 0.0996 ohm, the voltage drop is 18 A * 0.0996 ohm = 1.7928 V. "
    "The cable loss is 18^2 * 0.0996 = 32.27 W, leaving 22.2072 V at the load."
)
engineering_comparison_gate = (
    server.stable_expert_comparison_candidate_gate(
        engineering_messages,
        engineering_route,
        engineering_answer,
    )
    if server.stable_offline_expert_comparison(
        engineering_messages,
        engineering_route,
    )
    else {}
)
engineering_comparison_issues = (
    []
    if not engineering_comparison_gate
    or engineering_comparison_gate.get("accepted")
    else server.stable_comparison_gate_issue_rows(engineering_comparison_gate)
)
check(
    "absent-comparison-gate-does-not-leak-into-engineering-reasoning",
    not engineering_comparison_gate and not engineering_comparison_issues,
    {
        "routeDomain": (engineering_route.get("intentFrame") or {}).get("domain"),
        "gate": engineering_comparison_gate,
        "issues": engineering_comparison_issues,
    },
)


review_calls = []
structured_good_answer = good_answer.replace(
    " For later design changes,",
    "\n\nFor later design changes,",
)


def unexpected_review(*_args, **_kwargs):
    review_calls.append(True)
    raise AssertionError("controller-proven representation defects must bypass semantic review")


final_gate_audit = server.run_generic_reasoning_audit(
    step_messages,
    step_route,
    verbose_answer,
    triage_fn=lambda *_args, **_kwargs: {"attempted": False, "passed": False},
    review_fn=unexpected_review,
    repair_generate_fn=lambda *_args, **_kwargs: {
        "text": structured_good_answer,
        "doneReason": "stop",
    },
)
check(
    "sound-review-cannot-bypass-final-comparison-controller-gate",
    final_gate_audit.get("repairApplied") is True
    and final_gate_audit.get("finalAnswer") == structured_good_answer
    and final_gate_audit.get("deterministicPreflight") is True
    and final_gate_audit.get("reviewAttemptCount") == 0
    and not review_calls
    and final_gate_audit.get("verificationCompleted") is True
    and final_gate_audit.get("verificationUnavailableAccepted") is False
    and (final_gate_audit.get("obligationReceipt") or {}).get("status") == "pass",
    final_gate_audit,
)


packet = server.build_stable_comparison_primary_author_handoff_prompt(
    step_messages, step_route
)
prompt_text = str(packet.get("prompt") or "")
check(
    "primary-author-receives-request-bound-representation-obligations",
    packet.get("requestSha256")
    and packet.get("ledgerSha256")
    and "representation-semantics explanation" in prompt_text
    and "native authoring or runtime state" in prompt_text
    and "conversion, round-trip, or later-use boundary" in prompt_text
    and "If you use exact, lossless, or self-describing" in prompt_text
    and '"forbiddenFamilyVocabulary"' not in prompt_text,
    packet,
)
representation_repair_prompt = server.generic_reasoning_repair_prompt(
    step_messages,
    step_route,
    bad_answer,
    bad_gate.get("epistemicIssues") or [],
)
check(
    "repair-author-receives-explicit-cross-layer-output-contract",
    "Representation repair output contract:" in representation_repair_prompt
    and "payload is separate from native authoring or runtime state" in representation_repair_prompt
    and "exactly three compact natural paragraphs" in representation_repair_prompt
    and "180 to 220 words total" in representation_repair_prompt
    and "under 450 characters" in representation_repair_prompt
    and "Stay in the user's domain" in representation_repair_prompt
    and "typed semantic family is geometry" in representation_repair_prompt
    and "Separate exact or faceted stored geometry" in representation_repair_prompt
    and "does not establish that layer" in representation_repair_prompt
    and "Return final prose only" in representation_repair_prompt
    and "do not emit JSON" in representation_repair_prompt
    and "rejected draft is intentionally omitted" in representation_repair_prompt
    and bad_answer not in representation_repair_prompt,
    representation_repair_prompt,
)
json_route["_answerObligationLedger"] = server.build_answer_obligation_ledger(
    json_messages,
    json_route,
)
json_packet = server.build_stable_comparison_primary_author_handoff_prompt(
    json_messages,
    json_route,
)
json_prompt_text = str(json_packet.get("prompt") or "")
json_grounding_queries = server.local_research_queries(
    json_messages[0]["text"],
    json_route,
)
check(
    "stable-representation-intent-can-use-bounded-primary-grounding",
    server.source_backed_representation_explanation(json_route)
    and (json_route.get("intentFrame") or {}).get("domain") == "knowledge_comparison"
    and (json_route.get("capabilityPlan") or {}).get("id") == "expert-comparison"
    and any("official best practices" in item for item in json_grounding_queries)
    and any("unknown fields" in item for item in json_grounding_queries),
    {"route": json_route, "queries": json_grounding_queries},
)
grounded_answer_without_sources = server.representation_grounded_answer_text(
    "Direct expert answer.\n\nSources checked\nhttps://example.test/spec"
)
check(
    "grounded-expert-answer-keeps-source-bookkeeping-out-of-prose",
    grounded_answer_without_sources == "Direct expert answer.",
    grounded_answer_without_sources,
)
linked_grounded_answer = server.ensure_source_links(
    compiled_boundary_answer,
    [official_json_standard, official_protobuf_evolution],
)
check(
    "source-links-form-a-separate-readable-paragraph",
    "\n\nSources checked\n" in linked_grounded_answer
    and server.tinman_etiquette_metrics(
        schema_evolution_source_route["_messages"],
        compiled_boundary_route,
        linked_grounded_answer,
    ).get("status")
    == "pass",
    {
        "answer": linked_grounded_answer,
        "etiquette": server.tinman_etiquette_metrics(
            schema_evolution_source_route["_messages"],
            compiled_boundary_route,
            linked_grounded_answer,
        ),
    },
)
grounded_route = copy.deepcopy(json_route)
grounded_route["_representationGroundingReceipt"] = {
    "status": "complete",
    "coverageComplete": True,
    "evidenceCount": 2,
}
grounded_route["_sourceFidelityAudit"] = {
    "ok": True,
    "verdict": "sound",
}
unverified_grounded_route = copy.deepcopy(grounded_route)
unverified_grounded_route["_sourceFidelityAudit"] = {
    "ok": False,
    "verdict": "unavailable",
}
check(
    "source-free-relaxation-requires-verified-grounding",
    server.verified_representation_grounding(grounded_route)
    and not server.verified_representation_grounding(unverified_grounded_route),
    {
        "verified": server.verified_representation_grounding(grounded_route),
        "unverified": server.verified_representation_grounding(
            unverified_grounded_route
        ),
    },
)
json_missing_boundary_answer = (
    "JSON stores lexical names and primitive values, while Protocol Buffers stores numeric field identifiers and encoded values. "
    "Producer and consumer behavior controls interpretation. Backward compatibility, forward compatibility, unknown-field handling, and field reuse govern schema evolution."
)
json_missing_boundary_issues = server.representation_semantics_candidate_issues(
    json_route,
    json_missing_boundary_answer,
)
json_repair_prompt = server.generic_reasoning_repair_prompt(
    json_messages,
    json_route,
    json_missing_boundary_answer,
    json_missing_boundary_issues,
)
check(
    "author-packets-separate-positive-family-guidance-from-verifier-negatives",
    "The typed semantic family is data-serialization" in json_prompt_text
    and "stored payload is separate from native authoring or runtime state"
    in json_prompt_text
    and "Return four paragraphs"
    in json_prompt_text
    and "four separate sentences for backward compatibility, forward compatibility, unknown-member handling, and identifier reuse"
    in json_prompt_text
    and "Keep parse acceptance separate from unknown-member retention on reserialization"
    in json_prompt_text
    and "For backward compatibility, the older payload may lack members known to the newer reader"
    in json_prompt_text
    and "typed semantic family is data-serialization" in json_repair_prompt
    and "stored payload is separate from native authoring or runtime state"
    in json_repair_prompt
    and "Paragraph two must define backward compatibility"
    in json_repair_prompt
    and "Paragraph four must name Protocol Buffers"
    in json_repair_prompt
    and "Keep parse acceptance separate from unknown-member retention on reserialization"
    in json_repair_prompt
    and '"forbiddenFamilyVocabulary"' not in json_prompt_text
    and "design intent" not in json_prompt_text.lower()
    and "feature history" not in json_prompt_text.lower()
    and "design intent" not in json_repair_prompt.lower()
    and "feature history" not in json_repair_prompt.lower(),
    {
        "primary": json_prompt_text,
        "repair": json_repair_prompt,
    },
)
check(
    "primary-author-is-explicitly-bound-to-explanation-speech-act",
    '"comparisonSpeechAct":"explanation"' in prompt_text
    and "The active request asks for an explanation, not a decision." in prompt_text
    and "Use exactly three compact natural paragraphs totaling 180 to 220 words" in prompt_text
    and "under 450 characters" in prompt_text
    and "Return final prose only. Do not emit JSON" in prompt_text
    and "Return the final prose now" in prompt_text,
    packet,
)
malformed_payload = json.dumps(
    {
        "paragraphs": [
            "A STEP payload can carry schema-defined geometry through a supported exchange profile. This stored payload remains separate from the native authoring state. dangling讀",
            "continued fragment. An STL payload stores a triangulated surface rather than the source application's native feature history. Its editability therefore depends on reconstruction in the receiving toolchain.",
            "Round-trip behavior depends on the exact exporter and importer. Conversion can create another editable representation without automatically recovering the original native structures.",
        ]
    }
)
parsed_malformed_payload = server.parse_representation_paragraph_payload(
    malformed_payload
)
check(
    "schema-bound-paragraph-parser-removes-an-incomplete-tail",
    "dangling" not in parsed_malformed_payload
    and "讀" not in parsed_malformed_payload
    and "continued fragment" not in parsed_malformed_payload
    and parsed_malformed_payload.count("\n\n") == 2,
    parsed_malformed_payload,
)
role_bound_payload = json.dumps(
    {
        "storageBoundary": (
            "JSON and Protocol Buffers store different serialized structures. Both stored payloads remain separate from the live application model and runtime state, so application meaning depends on the producer and consumer contract."
        ),
        "compatibilityDirections": (
            "Backward compatibility means a newer reader consumes an older payload, while forward compatibility means an older reader consumes a newer payload."
        ),
        "firstOptionEvolution": [
            "JSON backward behavior depends on the applicable consumer contract.",
            "JSON forward behavior depends on the applicable consumer contract.",
            "JSON parser behavior determines how unknown keys are handled.",
            "JSON key reuse can change interpretation when assigned meaning changes.",
        ],
        "secondOptionEvolution": [
            "Protocol Buffers backward behavior follows the applicable schema rules.",
            "Protocol Buffers forward behavior follows the applicable schema rules.",
            "Protocol Buffers runtime behavior controls unknown-field handling.",
            "Protocol Buffers tag reuse can change interpretation across schema versions.",
        ],
        "roundTripBoundary": "Round-trip behavior still depends on the producer, consumer, runtime, and toolchain.",
    }
)
parsed_role_bound_payload = server.parse_representation_paragraph_payload(
    role_bound_payload
)
check(
    "legacy-named-semantic-output-roles-render-in-controller-order",
    parsed_role_bound_payload.startswith("JSON and Protocol Buffers")
    and "\n\nBackward compatibility means a newer reader" in parsed_role_bound_payload
    and "\n\nJSON backward behavior" in parsed_role_bound_payload
    and "\n\nProtocol Buffers backward behavior" in parsed_role_bound_payload
    and server.representation_paragraph_schema(json_route).get("required")
    == [
        "storageBoundary",
        "compatibilityDirections",
        "firstOptionEvolution",
        "secondOptionEvolution",
    ],
    parsed_role_bound_payload,
)
check(
    "data-serialization-schema-bounds-four-natural-paragraphs",
    set(server.representation_paragraph_schema(json_route).get("required") or [])
    == {
        "storageBoundary",
        "compatibilityDirections",
        "firstOptionEvolution",
        "secondOptionEvolution",
    }
    and all(
        str(item.get("description") or "").strip()
        for item in (
            server.representation_paragraph_schema(json_route).get("properties")
            or {}
        ).values()
    ),
    server.representation_paragraph_schema(json_route),
)
atomic_schema_route = copy.deepcopy(json_route)
atomic_schema_route["_representationEvidenceCoverage"] = {
    "optionDimensions": {
        "JSON": ["stored-representation", "identifier-definition"],
        "Protocol Buffers": [
            "stored-representation",
            "unknown-handling",
            "identifier-lifecycle",
            "round-trip-boundary",
        ],
    },
    "optionEvidenceBoundaries": {
        "JSON": [
            "compatibility-direction",
            "unknown-handling",
            "identifier-lifecycle",
            "round-trip-boundary",
        ],
        "Protocol Buffers": ["compatibility-direction"],
    },
}
atomic_schema = server.representation_paragraph_schema(atomic_schema_route)
first_atomic = atomic_schema["properties"]["firstOptionEvolution"]
second_atomic = atomic_schema["properties"]["secondOptionEvolution"]
check(
    "serialization-schema-binds-each-option-and-evolution-dimension-atomically",
    first_atomic.get("type") == "object"
    and first_atomic["properties"]["optionName"].get("enum") == ["JSON"]
    and second_atomic["properties"]["optionName"].get("enum")
    == ["Protocol Buffers"]
    and first_atomic["properties"]["unknownMembers"]["properties"]
    ["evidenceStatus"].get("enum")
    == ["boundary"]
    and second_atomic["properties"]["unknownMembers"]["properties"]
    ["evidenceStatus"].get("enum")
    == ["checked"]
    and second_atomic["properties"]["backwardCompatibility"]["properties"]
    ["evidenceStatus"].get("enum")
    == ["boundary"],
    atomic_schema,
)
atomic_payload = {
    "storageBoundary": (
        "JSON stores a textual serialized data representation, while Protocol Buffers stores a schema-defined tagged payload. "
        "Both payloads remain separate from live application objects and runtime state."
    ),
    "compatibilityDirections": (
        "Backward compatibility means a newer reader consumes an older payload, while forward compatibility means an older reader consumes a newer payload; each outcome remains scoped to its schema and implementation."
    ),
    "firstOptionEvolution": {
        "optionName": "JSON",
        "backwardCompatibility": {
            "evidenceStatus": "boundary",
            "statement": "Backward compatibility is controlled by the applicable application schema and consumer contract.",
        },
        "forwardCompatibility": {
            "evidenceStatus": "boundary",
            "statement": "Forward compatibility is controlled by the applicable application schema and consumer contract.",
        },
        "unknownMembers": {
            "evidenceStatus": "boundary",
            "statement": "Unknown members are governed by the selected parser and application contract.",
        },
        "identifierReuse": {
            "evidenceStatus": "boundary",
            "statement": "Identifier reuse is governed by the meaning assigned in the application schema or profile.",
        },
        "roundTripBoundary": {
            "evidenceStatus": "boundary",
            "statement": "Round-trip behavior depends on the selected parser, serializer, and application toolchain.",
        },
    },
    "secondOptionEvolution": {
        "optionName": "Protocol Buffers",
        "backwardCompatibility": {
            "evidenceStatus": "boundary",
            "statement": "Backward compatibility depends on the applicable message schema and runtime rules.",
        },
        "forwardCompatibility": {
            "evidenceStatus": "boundary",
            "statement": "Forward compatibility depends on the applicable message schema and runtime rules.",
        },
        "unknownMembers": {
            "evidenceStatus": "checked",
            "statement": "Unknown fields follow the behavior documented for the selected language runtime.",
        },
        "identifierReuse": {
            "evidenceStatus": "checked",
            "statement": "Tag reuse follows the checked field-number reservation rules for the schema.",
        },
        "roundTripBoundary": {
            "evidenceStatus": "checked",
            "statement": "Round-trip behavior remains scoped to the checked runtime and serialization path.",
        },
    },
}
parsed_atomic_payload = server.parse_representation_paragraph_payload(
    json.dumps(atomic_payload),
    route=atomic_schema_route,
)
check(
    "atomic-representation-receipt-renders-only-after-option-and-status-validation",
    parsed_atomic_payload.count("\n\n") == 3
    and "For JSON, backward compatibility" in parsed_atomic_payload
    and "For Protocol Buffers, backward compatibility" in parsed_atomic_payload,
    parsed_atomic_payload,
)
swapped_atomic_payload = copy.deepcopy(atomic_payload)
swapped_atomic_payload["firstOptionEvolution"]["optionName"] = "Protocol Buffers"
swapped_atomic_payload["secondOptionEvolution"]["optionName"] = "JSON"
wrong_status_atomic_payload = copy.deepcopy(atomic_payload)
wrong_status_atomic_payload["firstOptionEvolution"]["unknownMembers"][
    "evidenceStatus"
] = "checked"
check(
    "swapped-options-and-inflated-evidence-status-fail-before-prose-rendering",
    not server.parse_representation_paragraph_payload(
        json.dumps(swapped_atomic_payload),
        route=atomic_schema_route,
    )
    and not server.parse_representation_paragraph_payload(
        json.dumps(wrong_status_atomic_payload),
        route=atomic_schema_route,
    ),
    {
        "swapped": swapped_atomic_payload,
        "wrongStatus": wrong_status_atomic_payload,
    },
)
check(
    "semantic-families-do-not-share-an-incompatible-output-shape",
    server.representation_paragraph_schema(step_route).get("required")
    == ["storageBoundary", "firstOptionBoundary", "secondOptionBoundary"]
    and "compatibilityDirections"
    not in (server.representation_paragraph_schema(step_route).get("properties") or {})
    and "compatibilityDirections"
    in (server.representation_paragraph_schema(json_route).get("properties") or {}),
    {
        "geometry": server.representation_paragraph_schema(step_route),
        "dataSerialization": server.representation_paragraph_schema(json_route),
    },
)
check(
    "missing-semantic-output-role-fails-closed",
    not server.parse_representation_paragraph_payload(
        json.dumps(
            {
                "paragraphs": [
                    "This incomplete payload has only two otherwise substantial paragraphs. It must fail closed rather than changing the requested response shape.",
                    "Backward compatibility and forward compatibility still need their own complete direction definitions in the final response.",
                ]
            }
        )
    ),
    server.representation_paragraph_schema(json_route),
)
check(
    "representation-contract-selects-strong-local-author",
    server.conversation_reasoning_primary_model(
        step_messages, step_route, "local-oss"
    )
    == server.LOCAL_RESEARCH_MODEL,
    server.conversation_reasoning_primary_model(
        step_messages, step_route, "local-oss"
    ),
)
representation_generation_profile = server.conversation_reasoning_generation_profile(
    step_messages,
    step_route,
)
check(
    "representation-author-budget-enforces-the-compact-answer-contract",
    representation_generation_profile.get("timeout") == 90
    and representation_generation_profile.get("numPredict") == 2200
    and representation_generation_profile.get("numCtx") == 8000
    and representation_generation_profile.get("think") == "low"
    and representation_generation_profile.get("allowFinalRetry") is False,
    representation_generation_profile,
)
representation_request_budget = server.request_deadline_budget_for_route(
    json_route,
    "balanced",
)
check(
    "representation-request-retains-primary-repair-and-terminal-reserve",
    representation_request_budget
    == (server.REQUEST_REPRESENTATION_BUDGET_SECONDS, "representation-semantics-answer")
    and representation_request_budget[0] >= 180,
    representation_request_budget,
)
representation_audit_profile = server.generic_reasoning_audit_profile(
    step_route,
    messages=step_messages,
    draft=bad_answer,
)
check(
    "representation-repair-budget-fits-the-bounded-local-model",
    representation_audit_profile.get("repairModel") == server.LOCAL_RESEARCH_MODEL
    and representation_audit_profile.get("repairTimeout") >= 90
    and representation_audit_profile.get("repairAttempts") == 2
    and representation_audit_profile.get("repairNumPredict") == 2000
    and representation_audit_profile.get("repairNumCtx") == 8000
    and representation_audit_profile.get("repairThink") == "low",
    representation_audit_profile,
)
ordinary_comparison_route = copy.deepcopy(step_route)
ordinary_comparison_route["intentFrame"].pop("representationSemantics", None)
ordinary_comparison_route["intentFrame"].pop("representationFamily", None)
ordinary_comparison_profile = server.generic_reasoning_audit_profile(
    ordinary_comparison_route,
    messages=step_messages,
    draft=bad_answer,
)
check(
    "ordinary-stable-comparison-keeps-one-repair-pass",
    ordinary_comparison_profile.get("stableComparisonReview") is True
    and ordinary_comparison_profile.get("repairAttempts") == 1,
    ordinary_comparison_profile,
)


negative_assurance_answer = good_answer + (
    " Neither format guarantees preservation of native feature history."
)
negative_issues = server.stable_comparison_epistemic_overclaim_issues(
    step_messages, step_route, negative_assurance_answer
)
check(
    "negative-assurance-language-is-not-misread-as-an-overclaim",
    not any(
        item.get("kind")
        in {"source-free-absolute-assurance", "source-free-absolute-outcome"}
        for item in negative_issues
    ),
    negative_issues,
)
nor_negative_assurance_issues = server.stable_comparison_epistemic_overclaim_issues(
    json_messages,
    json_route,
    (
        "JSON stores readable names and values, while Protocol Buffers stores tagged values. The serialized payload is separate from runtime state. "
        "A readable name does not preserve application meaning, nor does a numeric identifier guarantee semantic equivalence across schema versions."
    ),
)
check(
    "nor-does-negative-assurance-is-not-read-as-a-positive-guarantee",
    not any(
        item.get("kind") == "source-free-absolute-assurance"
        for item in nor_negative_assurance_issues
    ),
    nor_negative_assurance_issues,
)
negative_exact_sync_answer = (
    "JSON and Protocol Buffers store serialized values separately from the live application model. "
    "Neither guarantees exact reconstruction of application meaning without a synchronized schema definition."
)
negative_exact_sync_issues = server.stable_comparison_epistemic_overclaim_issues(
    json_messages,
    json_route,
    negative_exact_sync_answer,
)
check(
    "negative-exact-claim-is-safe-while-synchronized-schema-overclaim-still-fails",
    not any(
        item.get("kind") == "source-free-absolute-outcome"
        for item in negative_exact_sync_issues
    )
    and any(
        item.get("kind") == "blanket-synchronized-schema-requirement"
        for item in negative_exact_sync_issues
    ),
    negative_exact_sync_issues,
)
comparative_guarantee_noun_issues = server.stable_comparison_epistemic_overclaim_issues(
    json_messages,
    json_route,
    (
        "JSON stores readable names and values, while Protocol Buffers stores schema-bound identifiers and values. "
        "The serialized payload is separate from the live application model. JSON offers weaker structural guarantees, and round-trip behavior depends on producer and consumer implementations."
    ),
)
check(
    "comparative-guarantee-noun-is-not-read-as-an-absolute-verb",
    not any(
        item.get("kind") == "source-free-absolute-assurance"
        for item in comparative_guarantee_noun_issues
    ),
    comparative_guarantee_noun_issues,
)
lacks_guarantee_noun_issues = server.stable_comparison_epistemic_overclaim_issues(
    json_messages,
    json_route,
    (
        "JSON stores readable names and values, while Protocol Buffers stores schema-bound identifiers and values. "
        "The serialized payload is separate from the live application model. JSON lacks strict backward guarantees, and round-trip behavior depends on producer and consumer implementations."
    ),
)
check(
    "lacks-guarantee-noun-is-not-read-as-an-absolute-verb",
    not any(
        item.get("kind") == "source-free-absolute-assurance"
        for item in lacks_guarantee_noun_issues
    ),
    lacks_guarantee_noun_issues,
)


check(
    "source-backed-representation-explanations-own-a-distinct-author-path",
    server.source_backed_representation_explanation(
        schema_evolution_source_route
    )
    and not server.source_backed_representation_explanation(
        engineering_decision_route
    ),
    {
        "explanation": schema_evolution_source_route.get("intentFrame"),
        "decision": engineering_decision_route.get("intentFrame"),
    },
)

explanation_boundary = server.safe_technical_primary_evidence_boundary_answer(
    schema_evolution_source_route["_messages"][0]["text"],
    schema_evolution_source_route,
    [official_protobuf, official_json_standard],
    reason="The local author did not return a typed explanation.",
)
check(
    "source-backed-explanation-fallback-does-not-become-a-decision-template",
    "JSON and Protocol Buffers" in explanation_boundary
    and "Sources checked" in explanation_boundary
    and "recommendation" not in explanation_boundary.lower()
    and "operating point" not in explanation_boundary.lower()
    and "winner" not in explanation_boundary.lower()
    and "what could reverse" not in explanation_boundary.lower(),
    explanation_boundary,
)

preservation_route = copy.deepcopy(schema_evolution_source_route)
preservation_route.setdefault("capabilityPlan", {})[
    "review_policy"
] = "source-fidelity-audit"
preserved_text, preservation_issues = server.preserve_source_audited_answer(
    preservation_route,
    [official_protobuf, official_json_standard],
    wrong_source_answer,
)
check(
    "final-source-preservation-rejects-speech-act-and-family-contamination",
    preservation_issues
    and preserved_text != wrong_source_answer
    and "hard fault" not in preserved_text.lower()
    and "winner" not in preserved_text.lower(),
    {
        "issues": preservation_issues,
        "preserved": preserved_text,
    },
)

auditor_calls = []
original_generate = server.run_ollama_generate


def capture_source_auditor(*args, **kwargs):
    auditor_calls.append(kwargs)
    return {
        "text": json.dumps(
            {
                "verdict": "supported",
                "issues": [],
                "finalAnswer": explanation_boundary,
                "notes": "",
            }
        )
    }


try:
    server.run_ollama_generate = capture_source_auditor
    server.run_source_fidelity_audit(
        schema_evolution_source_route["_messages"][0]["text"],
        [official_protobuf, official_json_standard],
        explanation_boundary,
        route=schema_evolution_source_route,
    )
finally:
    server.run_ollama_generate = original_generate

check(
    "source-backed-explanation-audit-reuses-the-capable-natural-author-model",
    bool(auditor_calls)
    and all(call.get("model") == server.LOCAL_RESEARCH_MODEL for call in auditor_calls)
    and all(call.get("timeout") == 120 for call in auditor_calls)
    and all(call.get("num_predict") == 1100 for call in auditor_calls)
    and all(call.get("num_ctx") == 8000 for call in auditor_calls)
    and all(call.get("response_format") is None for call in auditor_calls)
    and all(call.get("think") == "low" for call in auditor_calls)
    and all(call.get("allow_final_retry") is False for call in auditor_calls),
    auditor_calls,
)

critique_repair_calls = []


def capture_critique_then_repair(prompt, **kwargs):
    captured_kwargs = dict(kwargs)
    if callable(captured_kwargs.get("api_call_fn")):
        captured_kwargs["api_call_fn"] = captured_kwargs["api_call_fn"].__name__
    critique_repair_calls.append({"prompt": prompt, **captured_kwargs})
    if len(critique_repair_calls) == 1:
        return {
            "text": json.dumps(
                {
                    "verdict": "revise",
                    "issues": [
                        {
                            "claim": "JSON unknown-member handling",
                            "kind": "unsupported simplification",
                            "reason": "Keep data-object members separate from unknown schema keywords.",
                        }
                    ],
                    "finalAnswer": "The draft contains an unsupported simplification and should be revised.",
                    "notes": "The finalAnswer is an audit critique, not a user-facing explanation.",
                }
            )
        }
    return {
        "text": json.dumps(
            {
                "storageBoundary": (
                    "JSON and Protocol Buffers store serialized names, field identifiers, and values. "
                    "Those payloads are distinct from the live application model and runtime state, "
                    "and their stored content does not by itself establish application meaning."
                ),
                "compatibilityDirections": (
                    "Backward compatibility means a newer reader consumes an older payload. "
                    "Forward compatibility means an older reader consumes a newer payload."
                ),
                "firstOptionEvolution": {
                    "optionName": "JSON",
                    "backwardCompatibility": {
                        "evidenceStatus": "boundary",
                        "statement": "Backward compatibility for JSON is controlled by the applicable consumer contract and application schema.",
                    },
                    "forwardCompatibility": {
                        "evidenceStatus": "boundary",
                        "statement": "Forward compatibility for JSON is controlled by the applicable consumer contract and application schema.",
                    },
                    "unknownMembers": {
                        "evidenceStatus": "boundary",
                        "statement": "Unknown members in JSON are handled according to the selected parser and application contract.",
                    },
                    "identifierReuse": {
                        "evidenceStatus": "boundary",
                        "statement": "Identifier reuse in JSON is governed by the meaning assigned in the application schema or profile.",
                    },
                    "roundTripBoundary": {
                        "evidenceStatus": "boundary",
                        "statement": "Round-trip behavior for JSON depends on the selected parser, serializer, and application toolchain.",
                    },
                },
                "secondOptionEvolution": {
                    "optionName": "Protocol Buffers",
                    "backwardCompatibility": {
                        "evidenceStatus": "boundary",
                        "statement": "Backward compatibility for Protocol Buffers depends on the applicable schema and runtime rules.",
                    },
                    "forwardCompatibility": {
                        "evidenceStatus": "boundary",
                        "statement": "Forward compatibility for Protocol Buffers depends on the applicable schema and runtime rules.",
                    },
                    "unknownMembers": {
                        "evidenceStatus": "boundary",
                        "statement": "Unknown fields in Protocol Buffers are governed by the selected language runtime and schema edition.",
                    },
                    "identifierReuse": {
                        "evidenceStatus": "boundary",
                        "statement": "Tag reuse in Protocol Buffers is governed by the applicable schema-evolution rules.",
                    },
                    "roundTripBoundary": {
                        "evidenceStatus": "boundary",
                        "statement": "Round-trip behavior for Protocol Buffers depends on the producer, runtime, schema, and consumer toolchain.",
                    },
                },
            }
        )
    }


try:
    server.run_ollama_generate = capture_critique_then_repair
    critique_repair_result = server.run_source_fidelity_audit(
        schema_evolution_source_route["_messages"][0]["text"],
        [official_protobuf, official_json_standard],
        four_role_serialization_answer,
        route=schema_evolution_source_route,
    )
finally:
    server.run_ollama_generate = original_generate

check(
    "auditor-critique-is-repair-evidence-not-the-next-answer-candidate",
    len(critique_repair_calls) == 2
    and "typed representation contract below supplies controller-validated definitions"
    in critique_repair_calls[0]["prompt"]
    and "Rejected answer:\n" + server.compact(four_role_serialization_answer, 7000)
    in critique_repair_calls[1]["prompt"]
    and "Return exactly four complete natural prose paragraphs"
    in critique_repair_calls[1]["prompt"]
    and "An explicit evidence boundary is sufficient for that dimension"
    in critique_repair_calls[1]["prompt"]
    and "do not invent defaulting, ignore/reject behavior, preservation"
    in critique_repair_calls[1]["prompt"]
    and critique_repair_calls[1].get("api_call_fn")
    == "ollama_structured_chat_api_call"
    and critique_repair_calls[1].get("response_format")
    == server.representation_paragraph_schema(schema_evolution_source_route)
    and "unsupported simplification" in critique_repair_calls[1]["prompt"]
    and critique_repair_result.get("verdict") == "revise"
    and critique_repair_result.get("finalAnswer", "").startswith(
        "JSON and Protocol Buffers store serialized names"
    )
    and "For JSON, backward compatibility" in critique_repair_result.get(
        "finalAnswer", ""
    )
    and "For Protocol Buffers, backward compatibility"
    in critique_repair_result.get("finalAnswer", ""),
    {
        "calls": critique_repair_calls,
        "result": critique_repair_result,
    },
)


failed = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "checkCount": len(checks),
            "failed": failed,
            "checks": checks,
        },
        indent=2,
    )
)
raise SystemExit(1 if failed else 0)
