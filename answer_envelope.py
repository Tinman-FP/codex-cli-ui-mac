"""Structured answer state for the Codex CLI UI response pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


ENVELOPE_VERSION = 1
FINAL_STATES = {"complete", "bounded", "blocked", "failed"}
TERMINAL_STATE_PRIORITY = {
    "complete": 0,
    "bounded": 1,
    "blocked": 2,
    "failed": 3,
}
EVIDENCE_REQUIREMENTS = {
    "none": "",
    "grounded": "mayClaimGrounded",
    "cited": "mayClaimCited",
    "verified": "mayClaimVerified",
}

SOURCE_RECEIPT_KIND = "source-receipt"
TEMPLATE_OWNERSHIP_KIND = "template-ownership"
TURN_LINEAGE_KIND = "turn-lineage-receipt"
CONTEXT_EVIDENCE_KIND = "context-evidence-receipt"
SEMANTIC_EXCLUSION_KIND = "semantic-exclusion-receipt"
SOURCE_TYPES = frozenset({"web", "local-file", "source-vault", "runtime-state"})
SOURCE_METHODS = {
    "web": "web-fetch",
    "local-file": "local-file-read",
    "source-vault": "source-vault-read",
    "runtime-state": "controller-runtime-snapshot",
}
VERIFIED_SOURCE_STATES = frozenset({"checked", "verified"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", flags=re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>\]\[()]+", flags=re.IGNORECASE)
_CONCEPT_RE = re.compile(r"[a-z0-9]+", flags=re.IGNORECASE)
_CONCEPT_STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "after",
        "all",
        "also",
        "am",
        "an",
        "and",
        "answer",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "each",
        "for",
        "from",
        "had",
        "has",
        "have",
        "help",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "latest",
        "me",
        "must",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "please",
        "should",
        "so",
        "some",
        "than",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "use",
        "used",
        "using",
        "was",
        "we",
        "were",
        "what",
        "when",
        "which",
        "while",
        "with",
        "would",
        "you",
        "your",
    }
)
_CONCEPT_EQUIVALENTS = {
    "owned": "own",
    "owner": "own",
    "owners": "own",
    "ownership": "own",
    "owns": "own",
    "supported": "support",
    "supporting": "support",
    "supports": "support",
    "users": "user",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def text_sha256(value: Any) -> str:
    return hashlib.sha256(_text(value).encode("utf-8")).hexdigest()


def _items(value: Any) -> list[str]:
    if value is None:
        candidates = []
    elif isinstance(value, (str, bytes)):
        candidates = [value]
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = value
    else:
        candidates = []
    return list(dict.fromkeys(_text(item) for item in candidates if _text(item)))


def _canonical_sha256(value: Any) -> str:
    try:
        serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        serialized = _text(value)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _nested_text(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            item
            for nested in value.values()
            for item in _nested_text(nested)
        ]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for nested in value for item in _nested_text(nested)]
    normalized = _text(value)
    return [normalized] if normalized else []


def _concept_tokens(*values: Any) -> list[str]:
    return sorted(
        {
            _CONCEPT_EQUIVALENTS.get(token, token)
            for value in values
            for text in _nested_text(value)
            for token in _CONCEPT_RE.findall(text.lower())
            if token not in _CONCEPT_STOP_WORDS
            and (len(token) > 2 or token.isdigit())
        }
    )


def _domain_items(value: Any) -> list[str]:
    return list(
        dict.fromkeys(
            re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-")
            for item in _items(value)
            if re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-")
        )
    )


def _task_contract_domains(task_contract: Any) -> list[str]:
    if not isinstance(task_contract, dict):
        return []
    values: list[Any] = []
    for key in ("domain", "domains", "allowedDomain", "allowedDomains", "allowed_domains"):
        if key in task_contract:
            values.extend(_items(task_contract.get(key)))
    return _domain_items(values)


def _semantic_answer_segments(value: Any) -> list[str]:
    """Split answer prose at polarity-changing boundaries."""

    return [
        segment.strip()
        for segment in re.split(
            r"(?:[,:;.!?\n]+|\b(?:and|but|however|instead|rather)\b)",
            _text(value),
            flags=re.IGNORECASE,
        )
        if segment.strip()
    ]


def _semantic_nonreliance_mention(segment: str, concept: str) -> bool:
    """Recognize a brief rejection/disclaimer around one excluded concept."""

    pattern = re.compile(rf"\b{re.escape(concept)}\b", flags=re.IGNORECASE)
    for match in pattern.finditer(segment):
        prefix = segment[max(0, match.start() - 120) : match.start()].lower()
        suffix = segment[match.end() : min(len(segment), match.end() + 100)].lower()
        if re.search(
            r"(?:\b(?:do|does|did|will|would|should|must|can|could|am|is|are|was|were)\s+)?"
            r"\b(?:not|never)\s+(?:be\s+|being\s+)?"
            r"(?:use|using|used|rely|relying|relied|base|basing|cite|citing|include|including|"
            r"consider|considering|retain|retaining|carry|carrying)\b[^.;!?]{0,90}$",
            prefix,
        ):
            continue
        if re.search(
            r"\b(?:without|exclude|excluding|excluded|ignore|ignoring|ignored|avoid|avoiding|"
            r"discard|discarding|disregard|disregarding|retire|retiring|retired|drop|dropping|"
            r"omit|omitting|abandon|abandoning|supersede|superseding|superseded|never\s+mind)\b"
            r"[^.;!?]{0,90}$",
            prefix,
        ):
            continue
        if re.search(
            r"^\s*(?:is|are|was|were|will\s+be|should\s+be)?\s*"
            r"(?:not|never)\s+(?:being\s+)?(?:used|relied\s+on|cited|included|considered|retained)\b|"
            r"^\s*(?:is|are|was|were|will\s+be|should\s+be)\s+"
            r"(?:excluded|ignored|avoided|discarded|retired|dropped|omitted|abandoned|superseded)\b",
            suffix,
        ):
            continue
        return False
    return True


def _semantic_substantive_mentions(
    answer_text: Any,
    concept: str,
    *,
    disposition: str,
) -> list[str]:
    """Return answer segments that rely on an excluded subject."""

    concept_pattern = re.compile(rf"\b{re.escape(concept)}\b", flags=re.IGNORECASE)
    reliance_pattern = re.compile(
        r"\b(?:use|using|used|rely|relying|relied|base|basing|based|basis|cite|citing|cited|"
        r"according|recommend|recommended|choose|chosen|select|selected|retain|retaining|"
        r"continue|continuing|assume|assuming|treat|include|including|derive|derived|"
        r"says|states|shows|supports|proves|confirms|reports|indicates)\b",
        flags=re.IGNORECASE,
    )
    violations = []
    for segment in _semantic_answer_segments(answer_text):
        if not concept_pattern.search(segment):
            continue
        if _semantic_nonreliance_mention(segment, concept):
            continue
        if disposition == "superseded" or concept.isdigit() or reliance_pattern.search(segment):
            violations.append(segment[:240])
    return violations


def _semantic_distinct_active_qualification(
    segment: str,
    concept: str,
    *,
    active_concepts: Iterable[str],
    excluded_group_concepts: Iterable[str],
) -> bool:
    """Allow a homonym only when an active qualifier owns that exact phrase."""

    if concept.isdigit():
        return False
    segment_tokens = set(_concept_tokens(segment))
    sibling_exclusions = set(excluded_group_concepts) - {concept}
    if segment_tokens & sibling_exclusions:
        return False
    active = set(active_concepts) - set(excluded_group_concepts)
    if not active:
        return False
    pattern = re.compile(rf"\b{re.escape(concept)}\b", flags=re.IGNORECASE)
    for match in pattern.finditer(segment):
        prefix_tokens = _concept_tokens(segment[max(0, match.start() - 48) : match.start()])
        suffix_tokens = _concept_tokens(segment[match.end() : min(len(segment), match.end() + 48)])
        if set(prefix_tokens[-3:]) & active or set(suffix_tokens[:3]) & active:
            return True
    return False


def build_context_evidence_receipt(
    *,
    receipt_id: Any,
    run_id: Any,
    intent_text: Any,
    domain: Any,
    concepts: Any,
    source_receipt_ids: Any = (),
    state: str = "checked",
    answer_text: Any = None,
    binding_scope: Any = "",
    task_contract: Any = None,
) -> Dict[str, Any]:
    """Describe evidence concepts for relevance without upgrading source proof."""

    normalized = {
        "kind": CONTEXT_EVIDENCE_KIND,
        "receiptId": _text(receipt_id),
        "runId": _text(run_id),
        "intentDigest": text_sha256(intent_text),
        "domains": _domain_items(domain),
        "concepts": _items(concepts),
        "sourceReceiptIds": _items(source_receipt_ids),
        "state": _text(state).lower(),
        "answerDigest": (
            text_sha256(answer_text) if answer_text is not None else ""
        ),
        "bindingScope": _text(binding_scope),
        "taskContractDigest": (
            _canonical_sha256(task_contract)
            if isinstance(task_contract, dict)
            else ""
        ),
    }
    return {
        **normalized,
        "receiptDigest": _canonical_sha256(normalized),
    }


def turn_lineage_contract(
    *,
    run_id: Any,
    latest_user_intent: Any,
    current_domain: Any,
    task_contract: Any,
    declared_relation: Any,
    prior_user_intent: Any = "",
    prior_domain: Any = (),
    explicit_cross_domain: bool = False,
    bridge_concepts: Any = (),
) -> Dict[str, Any]:
    """Classify typed turn continuity and declare which prior context may survive."""

    latest_intent = _text(latest_user_intent)
    prior_intent = _text(prior_user_intent)
    current_domains = _domain_items(current_domain)
    prior_domains = _domain_items(prior_domain)
    contract = task_contract if isinstance(task_contract, dict) else {}
    task_domains = _task_contract_domains(contract)
    relation = re.sub(
        r"[^a-z0-9]+",
        "-",
        _text(declared_relation).lower(),
    ).strip("-")
    latest_concepts = _concept_tokens(latest_intent)
    prior_concepts = _concept_tokens(prior_intent)
    bridges = _concept_tokens(bridge_concepts)
    domain_union = set(current_domains) | set(prior_domains)
    same_domain = bool(set(current_domains) & set(prior_domains))
    different_domain = bool(current_domains and prior_domains and not same_domain)
    bridge_valid = bool(
        explicit_cross_domain
        and different_domain
        and len(domain_union) >= 2
        and domain_union.issubset(set(task_domains))
        and bridges
        and set(bridges) & set(latest_concepts)
        and set(bridges) & set(prior_concepts)
    )
    issues: list[str] = []

    if not _text(run_id):
        issues.append("missing-turn-lineage-run-id")
    if not latest_intent:
        issues.append("missing-latest-user-intent")
    if not current_domains:
        issues.append("missing-current-turn-domain")
    if not contract:
        issues.append("missing-current-task-contract")
    elif not task_domains:
        issues.append("missing-current-task-contract-domain")

    ambiguous_relations = {"", "ambiguous", "unknown", "unclear"}
    continuation_relations = {
        "follow-up",
        "followup",
        "continuation",
        "elliptical-follow-up",
    }
    revision_relations = {
        "revision",
        "correction",
        "superseded-plan",
        "new-topic",
        "standalone",
    }

    if issues:
        transition = "ambiguous"
    elif bridge_valid:
        transition = "cross-domain-bridge"
    elif explicit_cross_domain and different_domain:
        transition = "ambiguous"
        issues.append("invalid-cross-domain-bridge")
    elif relation in ambiguous_relations:
        transition = "ambiguous"
        issues.append("ambiguous-turn-transition")
    elif different_domain:
        transition = "domain-switch"
    elif not prior_intent and not prior_domains:
        transition = "revision"
    elif relation in continuation_relations:
        transition = "continuation"
    elif relation in revision_relations:
        transition = "revision"
    else:
        transition = "ambiguous"
        issues.append("unsupported-turn-relation")

    lineage_domains = set(current_domains)
    if transition == "cross-domain-bridge":
        lineage_domains.update(prior_domains)
    stale_task_domains = set(task_domains) - lineage_domains
    if stale_task_domains:
        issues.append("task-contract-domain-lineage-mismatch")

    may_reuse_prior_concepts = bool(
        transition in {"continuation", "cross-domain-bridge"}
        or (transition == "revision" and same_domain)
    )
    may_reuse_prior_evidence = transition in {
        "continuation",
        "cross-domain-bridge",
    }
    may_reuse_prior_task_contract = transition == "continuation"
    may_reuse_prior_template_metadata = transition == "continuation"
    decision = (
        "replan"
        if transition == "ambiguous" or issues
        else "bridge"
        if transition == "cross-domain-bridge"
        else "retain"
        if transition == "continuation"
        else "isolate"
    )
    normalized = {
        "kind": TURN_LINEAGE_KIND,
        "runId": _text(run_id),
        "latestIntentDigest": text_sha256(latest_intent),
        "priorIntentDigest": text_sha256(prior_intent) if prior_intent else "",
        "taskContractDigest": _canonical_sha256(contract),
        "declaredRelation": relation,
        "transition": transition,
        "decision": decision,
        "currentDomains": current_domains,
        "priorDomains": prior_domains,
        "taskContractDomains": task_domains,
        "latestConcepts": latest_concepts,
        "priorConcepts": prior_concepts,
        "explicitCrossDomain": bool(explicit_cross_domain),
        "bridgeConcepts": bridges,
        "mayReusePriorConcepts": may_reuse_prior_concepts,
        "mayReusePriorEvidence": may_reuse_prior_evidence,
        "mayReusePriorTaskContract": may_reuse_prior_task_contract,
        "mayReusePriorTemplateMetadata": may_reuse_prior_template_metadata,
        "requiresReboundOwnership": True,
        "status": "replan" if decision == "replan" else "pass",
        "mayFinalize": decision != "replan",
        "issues": list(dict.fromkeys(issues)),
    }
    return {
        **normalized,
        "lineageDigest": _canonical_sha256(normalized),
    }


def build_template_ownership_receipt(
    *,
    receipt_id: Any,
    run_id: Any,
    template_id: Any,
    latest_user_intent: Any,
    task_contract: Dict[str, Any],
    owner_domain: Any,
    concepts: Any,
    supported_domains: Any = (),
    cross_domain: bool = False,
    bridge_concepts: Any = (),
    turn_lineage_digest: Any = "",
    bound_output: Any = None,
    output_sha256: Any = "",
    output_concepts: Any = (),
) -> Dict[str, Any]:
    """Bind trusted deterministic template metadata to one intent and contract.

    This receipt must be emitted by the capability/template boundary, not inferred
    from answer prose. It lets the final gate distinguish an owned specialist
    answer from stale or cross-domain template leakage.
    """

    owner = _domain_items(owner_domain)
    domains = _domain_items(supported_domains)
    if owner and owner[0] not in domains:
        domains.insert(0, owner[0])
    output_was_supplied = bound_output is not None
    bound_output_text = _text(bound_output) if output_was_supplied else ""
    bound_output_sha256 = (
        text_sha256(bound_output_text)
        if output_was_supplied
        else _text(output_sha256)
    )
    bound_output_concepts = (
        _concept_tokens(bound_output_text)
        if output_was_supplied
        else _concept_tokens(output_concepts)
    )
    return {
        "kind": TEMPLATE_OWNERSHIP_KIND,
        "receiptId": _text(receipt_id),
        "runId": _text(run_id),
        "templateId": _text(template_id),
        "latestIntentDigest": text_sha256(latest_user_intent),
        "taskContractDigest": _canonical_sha256(task_contract),
        "ownerDomain": owner[0] if owner else "",
        "supportedDomains": domains,
        "concepts": _items(concepts),
        "crossDomain": bool(cross_domain),
        "bridgeConcepts": _items(bridge_concepts),
        "turnLineageDigest": _text(turn_lineage_digest),
        "outputSha256": bound_output_sha256,
        "outputConcepts": bound_output_concepts,
    }


def build_semantic_exclusion_receipt(
    *,
    receipt_id: Any,
    run_id: Any,
    latest_user_intent: Any,
    task_contract: Any,
    turn_lineage_digest: Any,
    constraints: Any,
) -> Dict[str, Any]:
    """Bind kernel-parsed subject exclusions to one run and turn lineage."""

    raw = constraints if isinstance(constraints, dict) else {}
    excluded_subjects = [
        {
            "constraintId": _text(item.get("constraintId")),
            "disposition": _text(item.get("disposition")).lower() or "excluded",
            "subject": _text(item.get("subject")),
            "concepts": _concept_tokens(item.get("concepts")),
            "discussionAllowed": item.get("discussionAllowed") is True,
        }
        for item in (raw.get("excludedSubjects") or [])
        if isinstance(item, dict) and _concept_tokens(item.get("concepts"))
    ]
    required_replacements = [
        {
            "constraintId": _text(item.get("constraintId")),
            "subject": _text(item.get("subject")),
            "concepts": _concept_tokens(item.get("concepts")),
        }
        for item in (raw.get("requiredReplacements") or [])
        if isinstance(item, dict) and _concept_tokens(item.get("concepts"))
    ]
    normalized = {
        "kind": SEMANTIC_EXCLUSION_KIND,
        "receiptId": _text(receipt_id),
        "runId": _text(run_id),
        "latestIntentDigest": text_sha256(latest_user_intent),
        "taskContractDigest": _canonical_sha256(
            task_contract if isinstance(task_contract, dict) else {}
        ),
        "turnLineageDigest": _text(turn_lineage_digest),
        "constraintKind": _text(raw.get("kind")),
        "constraintVersion": int(raw.get("version") or 0),
        "constraintScope": _text(raw.get("scope")),
        "excludedSubjects": excluded_subjects,
        "requiredReplacements": required_replacements,
        "excludedConcepts": sorted(
            {
                concept
                for item in excluded_subjects
                for concept in (item.get("concepts") or [])
            }
        ),
        "requiredConcepts": sorted(
            {
                concept
                for item in required_replacements
                for concept in (item.get("concepts") or [])
            }
        ),
        "discussionConcepts": sorted(
            {
                concept
                for item in excluded_subjects
                if item.get("discussionAllowed")
                for concept in (item.get("concepts") or [])
            }
        ),
    }
    return {
        **normalized,
        "receiptDigest": _canonical_sha256(normalized),
    }


def answer_relevance_contract(
    answer_text: Any,
    *,
    run_id: Any,
    latest_user_intent: Any,
    intent_domain: Any,
    task_contract: Any,
    template_ownership: Any,
    prior_intent_concepts: Any = (),
    evidence_concepts: Any = (),
    turn_lineage: Any = None,
    evidence_contexts: Any = (),
    semantic_exclusions: Any = None,
    require_template_ownership: bool = True,
) -> Dict[str, Any]:
    """Fail closed when specialist output is unrelated to the active contract.

    Concept comparison is deliberately generic. Domain authority comes from a
    typed ownership receipt emitted by the deterministic template boundary, not
    from a keyword blacklist or from a model's claim about its own answer.
    """

    latest_intent = _text(latest_user_intent)
    contract = task_contract if isinstance(task_contract, dict) else {}
    ownership = template_ownership if isinstance(template_ownership, dict) else {}
    lineage = turn_lineage if isinstance(turn_lineage, dict) else {}
    semantic_receipt = semantic_exclusions if isinstance(semantic_exclusions, dict) else {}
    expected_intent_digest = text_sha256(latest_intent)
    expected_contract_digest = _canonical_sha256(contract)
    requested_domains = _domain_items(intent_domain)
    contract_domains = _task_contract_domains(contract)
    lineage_domains = _domain_items(lineage.get("currentDomains"))
    if lineage.get("transition") == "cross-domain-bridge":
        for domain in _domain_items(lineage.get("priorDomains")):
            if domain not in lineage_domains:
                lineage_domains.append(domain)
    allowed_domains = list(lineage_domains or requested_domains)
    if not lineage:
        for domain in contract_domains:
            if domain not in allowed_domains:
                allowed_domains.append(domain)
    owner_domain = _domain_items(ownership.get("ownerDomain"))
    owner = owner_domain[0] if owner_domain else ""
    supported_domains = _domain_items(ownership.get("supportedDomains"))
    declared_concepts = _concept_tokens(ownership.get("concepts"))
    bridge_concepts = _concept_tokens(ownership.get("bridgeConcepts"))
    raw_latest_concepts = _concept_tokens(latest_intent)
    raw_contract_concepts = _concept_tokens(contract)
    semantic_issues: list[str] = []
    excluded_subjects = [
        item
        for item in (semantic_receipt.get("excludedSubjects") or [])
        if isinstance(item, dict)
    ]
    required_replacements = [
        item
        for item in (semantic_receipt.get("requiredReplacements") or [])
        if isinstance(item, dict)
    ]
    excluded_concepts = set(_concept_tokens(semantic_receipt.get("excludedConcepts")))
    discussion_concepts = set(_concept_tokens(semantic_receipt.get("discussionConcepts")))
    required_concepts = set(_concept_tokens(semantic_receipt.get("requiredConcepts")))
    if semantic_receipt:
        normalized_semantic = dict(semantic_receipt)
        supplied_semantic_digest = _text(normalized_semantic.pop("receiptDigest", ""))
        if semantic_receipt.get("kind") != SEMANTIC_EXCLUSION_KIND:
            semantic_issues.append("missing-semantic-exclusion-receipt")
        if not _text(semantic_receipt.get("receiptId")):
            semantic_issues.append("missing-semantic-exclusion-receipt-id")
        if not supplied_semantic_digest:
            semantic_issues.append("missing-semantic-exclusion-receipt-digest")
        elif supplied_semantic_digest != _canonical_sha256(normalized_semantic):
            semantic_issues.append("semantic-exclusion-integrity-mismatch")
        if _text(semantic_receipt.get("runId")) != _text(run_id):
            semantic_issues.append("semantic-exclusion-run-mismatch")
        if _text(semantic_receipt.get("latestIntentDigest")) != expected_intent_digest:
            semantic_issues.append("semantic-exclusion-intent-mismatch")
        if _text(semantic_receipt.get("taskContractDigest")) != expected_contract_digest:
            semantic_issues.append("semantic-exclusion-task-contract-mismatch")
        if not lineage or not _text(lineage.get("lineageDigest")):
            semantic_issues.append("missing-semantic-exclusion-turn-lineage")
        elif _text(semantic_receipt.get("turnLineageDigest")) != _text(
            lineage.get("lineageDigest")
        ):
            semantic_issues.append("semantic-exclusion-turn-lineage-mismatch")
        if semantic_receipt.get("constraintKind") != "semantic-exclusion-constraints":
            semantic_issues.append("invalid-semantic-exclusion-constraint-kind")
        if not excluded_subjects:
            semantic_issues.append("missing-semantic-excluded-subject")
    # Even when the user asks to discuss why a subject is excluded, that subject
    # is a typed discussion target—not positive proof that an answer may rely on
    # it. Discussion satisfaction is tracked separately below.
    excluded_from_support = set(excluded_concepts)
    latest_concepts = sorted(
        (set(raw_latest_concepts) - excluded_from_support) | required_concepts
    )
    contract_concepts = sorted(set(raw_contract_concepts) - excluded_from_support)
    may_reuse_prior_concepts = (
        not lineage or lineage.get("mayReusePriorConcepts") is True
    )
    raw_prior_concepts = _concept_tokens(prior_intent_concepts)
    prior_concepts = (
        _concept_tokens(lineage.get("priorConcepts"))
        if lineage and may_reuse_prior_concepts
        else raw_prior_concepts
        if may_reuse_prior_concepts
        else []
    )
    prior_concepts = sorted(set(prior_concepts) - excluded_from_support)
    raw_evidence_concepts = _concept_tokens(evidence_concepts)
    typed_evidence_concepts = list(raw_evidence_concepts) if not lineage else []
    accepted_evidence_contexts: list[Dict[str, Any]] = []
    rejected_evidence_contexts: list[Dict[str, Any]] = []
    current_lineage_domains = set(_domain_items(lineage.get("currentDomains")))
    prior_lineage_domains = set(_domain_items(lineage.get("priorDomains")))
    prior_digest = _text(lineage.get("priorIntentDigest"))
    for value in evidence_contexts or ():
        receipt = value if isinstance(value, dict) else {}
        receipt_id = _text(receipt.get("receiptId"))
        receipt_domains = set(_domain_items(receipt.get("domains")))
        receipt_intent_digest = _text(receipt.get("intentDigest"))
        receipt_issues: list[str] = []
        normalized_receipt = dict(receipt)
        supplied_receipt_digest = _text(
            normalized_receipt.pop("receiptDigest", "")
        )
        if receipt.get("kind") != CONTEXT_EVIDENCE_KIND:
            receipt_issues.append("missing-context-evidence-receipt")
        if not receipt_id:
            receipt_issues.append("missing-context-evidence-receipt-id")
        if not supplied_receipt_digest:
            receipt_issues.append("missing-context-evidence-receipt-digest")
        elif supplied_receipt_digest != _canonical_sha256(normalized_receipt):
            receipt_issues.append("context-evidence-integrity-mismatch")
        if _text(receipt.get("runId")) != _text(run_id):
            receipt_issues.append("context-evidence-run-mismatch")
        if _text(receipt.get("state")).lower() not in VERIFIED_SOURCE_STATES:
            receipt_issues.append("context-evidence-not-checked")
        if not receipt_domains:
            receipt_issues.append("missing-context-evidence-domain")
        if not _items(receipt.get("sourceReceiptIds")):
            receipt_issues.append("missing-context-evidence-source-receipt")
        binding_scope = _text(receipt.get("bindingScope"))
        if binding_scope:
            if binding_scope != "deterministic-read-only-specialist-answer":
                receipt_issues.append("invalid-context-evidence-binding-scope")
            if not _text(receipt.get("answerDigest")):
                receipt_issues.append("missing-context-evidence-answer-binding")
            elif _text(receipt.get("answerDigest")) != text_sha256(answer_text):
                receipt_issues.append("context-evidence-answer-binding-mismatch")
            if not _text(receipt.get("taskContractDigest")):
                receipt_issues.append("missing-context-evidence-task-contract-binding")
            elif _text(receipt.get("taskContractDigest")) != expected_contract_digest:
                receipt_issues.append("context-evidence-task-contract-mismatch")

        current_context = bool(
            receipt_intent_digest == expected_intent_digest
            and receipt_domains
            and receipt_domains.issubset(current_lineage_domains or set(allowed_domains))
        )
        prior_context = bool(
            lineage.get("mayReusePriorEvidence") is True
            and prior_digest
            and receipt_intent_digest == prior_digest
            and receipt_domains
            and receipt_domains.issubset(prior_lineage_domains)
        )
        if not current_context and not prior_context:
            receipt_issues.append("context-evidence-outside-active-turn-lineage")

        normalized_context = {
            **receipt,
            "receiptId": receipt_id,
            "domains": sorted(receipt_domains),
            "issues": list(dict.fromkeys(receipt_issues)),
        }
        if receipt_issues:
            rejected_evidence_contexts.append(normalized_context)
        else:
            accepted_evidence_contexts.append(normalized_context)
            typed_evidence_concepts.extend(_concept_tokens(receipt.get("concepts")))
    typed_evidence_concepts = sorted(
        set(typed_evidence_concepts) - excluded_from_support
    )
    support_concepts = sorted(
        set(latest_concepts)
        | set(contract_concepts)
        | set(prior_concepts)
        | set(typed_evidence_concepts)
    )
    output_concepts = _concept_tokens(answer_text)
    bound_output_sha256 = _text(ownership.get("outputSha256"))
    bound_output_concepts = _concept_tokens(ownership.get("outputConcepts"))
    output_binding_declared = bool(bound_output_sha256 or bound_output_concepts)
    output_binding_matches = bool(
        bound_output_sha256
        and bound_output_sha256 == text_sha256(answer_text)
        and set(bound_output_concepts) == set(output_concepts)
    )
    support_overlap = sorted(set(output_concepts) & set(support_concepts))
    latest_overlap = sorted(set(output_concepts) & set(latest_concepts))
    declared_output_overlap = sorted(
        (set(output_concepts) & set(declared_concepts)) - excluded_from_support
    )
    source_bound_evidence_overlap = sorted(
        {
            concept
            for receipt in accepted_evidence_contexts
            if receipt.get("bindingScope")
            == "deterministic-read-only-specialist-answer"
            and _text(receipt.get("intentDigest")) == expected_intent_digest
            and _text(receipt.get("answerDigest")) == text_sha256(answer_text)
            for concept in (
                set(output_concepts)
                & set(_concept_tokens(receipt.get("concepts")))
            )
        }
    )
    source_bound_latest_turn_satisfied = bool(
        require_template_ownership
        and output_binding_matches
        and declared_output_overlap
        and source_bound_evidence_overlap
        and len(_text(answer_text)) >= 12
        and len(output_concepts) >= 2
        and owner
        and owner in allowed_domains
        and owner in supported_domains
    )
    unsupported_specialist_concepts = sorted(
        (set(output_concepts) & set(declared_concepts)) - set(support_concepts)
    )
    cross_domain = ownership.get("crossDomain") is True
    issues: list[str] = list(semantic_issues)

    violated_exclusion_ids: list[str] = []
    semantic_violation_segments: list[Dict[str, Any]] = []
    for item in excluded_subjects:
        constraint_id = _text(item.get("constraintId")) or "unnamed-exclusion"
        disposition = _text(item.get("disposition")).lower() or "excluded"
        item_concepts = _concept_tokens(item.get("concepts"))
        segments = sorted(
            {
                segment
                for concept in item_concepts
                for segment in _semantic_substantive_mentions(
                    answer_text,
                    concept,
                    disposition=disposition,
                )
                if not (
                    disposition == "superseded"
                    and _semantic_distinct_active_qualification(
                        segment,
                        concept,
                        active_concepts=latest_concepts,
                        excluded_group_concepts=item_concepts,
                    )
                )
            }
        )
        if segments:
            violated_exclusion_ids.append(constraint_id)
            semantic_violation_segments.append(
                {
                    "constraintId": constraint_id,
                    "disposition": disposition,
                    "segments": segments[:4],
                }
            )
    missing_required_replacement_ids = [
        _text(item.get("constraintId")) or "unnamed-replacement"
        for item in required_replacements
        if not set(_concept_tokens(item.get("concepts"))) & set(output_concepts)
    ]
    if violated_exclusion_ids:
        issues.append("answer-violates-latest-turn-exclusion")
    if missing_required_replacement_ids:
        issues.append("answer-missing-required-replacement-concept")
    discussion_satisfied_concepts = sorted(
        {
            concept
            for item in excluded_subjects
            if item.get("discussionAllowed") is True
            for concept in _concept_tokens(item.get("concepts"))
            if concept in output_concepts
            and not _semantic_substantive_mentions(
                answer_text,
                concept,
                disposition=_text(item.get("disposition")).lower() or "excluded",
            )
        }
    )

    if not require_template_ownership and not lineage and not semantic_receipt:
        return {
            "kind": "answer-relevance-receipt",
            "status": "not-evaluated",
            "decision": "accept",
            "mayFinalize": True,
            "issues": [],
            "latestIntentDigest": expected_intent_digest,
            "taskContractDigest": expected_contract_digest,
            "allowedDomains": allowed_domains,
            "ownerDomain": owner,
            "supportedDomains": supported_domains,
            "supportOverlapConcepts": support_overlap,
            "unsupportedSpecialistConcepts": [],
        }

    if lineage:
        normalized_lineage = dict(lineage)
        supplied_lineage_digest = _text(normalized_lineage.pop("lineageDigest", ""))
        if lineage.get("kind") != TURN_LINEAGE_KIND:
            issues.append("missing-turn-lineage-receipt")
        if not supplied_lineage_digest:
            issues.append("missing-turn-lineage-digest")
        elif supplied_lineage_digest != _canonical_sha256(normalized_lineage):
            issues.append("turn-lineage-integrity-mismatch")
        if _text(lineage.get("runId")) != _text(run_id):
            issues.append("turn-lineage-run-mismatch")
        if _text(lineage.get("latestIntentDigest")) != expected_intent_digest:
            issues.append("turn-lineage-intent-mismatch")
        if _text(lineage.get("taskContractDigest")) != expected_contract_digest:
            issues.append("turn-lineage-task-contract-mismatch")
        if requested_domains and set(requested_domains) != set(
            _domain_items(lineage.get("currentDomains"))
        ):
            issues.append("intent-domain-turn-lineage-mismatch")
        if lineage.get("status") != "pass" or not lineage.get("mayFinalize"):
            issues.append("turn-lineage-replan-required")
        if raw_evidence_concepts:
            issues.append("unscoped-evidence-concepts")
        if raw_prior_concepts and not set(raw_prior_concepts).issubset(
            set(_concept_tokens(lineage.get("priorConcepts")))
        ):
            issues.append("unscoped-prior-intent-concepts")
        if lineage.get("requiresReboundOwnership") is True and require_template_ownership:
            if _text(ownership.get("turnLineageDigest")) != supplied_lineage_digest:
                issues.append("template-ownership-turn-lineage-mismatch")

    if not latest_intent:
        issues.append("missing-latest-user-intent")
    if not contract:
        issues.append("missing-task-contract")
    if not allowed_domains:
        issues.append("missing-intent-domain")
    if require_template_ownership and ownership.get("kind") != TEMPLATE_OWNERSHIP_KIND:
        issues.append("missing-template-ownership-receipt")
    if require_template_ownership and not _text(ownership.get("receiptId")):
        issues.append("missing-template-ownership-receipt-id")
    if require_template_ownership and not _text(ownership.get("templateId")):
        issues.append("missing-template-id")
    if not _text(run_id):
        issues.append("missing-expected-run-id")
    elif require_template_ownership and _text(ownership.get("runId")) != _text(run_id):
        issues.append("template-ownership-run-mismatch")
    if require_template_ownership and _text(ownership.get("latestIntentDigest")) != expected_intent_digest:
        issues.append("template-ownership-intent-mismatch")
    if require_template_ownership and _text(ownership.get("taskContractDigest")) != expected_contract_digest:
        issues.append("template-ownership-contract-mismatch")
    if require_template_ownership and not owner:
        issues.append("missing-template-owner-domain")
    elif require_template_ownership and allowed_domains and owner not in allowed_domains:
        issues.append("template-owner-domain-not-allowed")
    if require_template_ownership and owner and owner not in supported_domains:
        issues.append("template-owner-not-in-supported-domains")
    if require_template_ownership and output_binding_declared and not output_binding_matches:
        issues.append("template-output-binding-mismatch")
    if require_template_ownership and not declared_concepts:
        issues.append("missing-template-concepts")
    elif require_template_ownership and not declared_output_overlap:
        issues.append("template-output-concept-mismatch")
    if not support_overlap and not discussion_satisfied_concepts:
        issues.append("answer-has-no-active-contract-concept")
    if (
        lineage
        and lineage.get("transition") != "continuation"
        and not latest_overlap
        and not discussion_satisfied_concepts
        and not source_bound_latest_turn_satisfied
    ):
        issues.append("answer-has-no-latest-turn-concept")

    if require_template_ownership and len(allowed_domains) > 1:
        if not cross_domain:
            issues.append("cross-domain-ownership-not-declared")
        else:
            missing_domains = set(allowed_domains) - set(supported_domains)
            if missing_domains:
                issues.append("cross-domain-support-incomplete")
            if not bridge_concepts:
                issues.append("missing-cross-domain-bridge-concepts")
            else:
                if not set(bridge_concepts) & set(support_concepts):
                    issues.append("cross-domain-bridge-not-in-active-contract")
                if not set(bridge_concepts) & set(output_concepts):
                    issues.append("cross-domain-bridge-not-in-answer")
    elif require_template_ownership and cross_domain:
        issues.append("cross-domain-ownership-without-multi-domain-contract")

    issues = list(dict.fromkeys(issues))
    failed_domain_or_support = bool(
        {
            "template-owner-domain-not-allowed",
            "answer-has-no-active-contract-concept",
            "template-output-concept-mismatch",
            "answer-has-no-latest-turn-concept",
        }
        & set(issues)
    )
    return {
        "kind": "answer-relevance-receipt",
        "status": "replan" if issues else "pass",
        "decision": "replan" if issues else "accept",
        "mayFinalize": not issues,
        "issues": issues,
        "latestIntentDigest": expected_intent_digest,
        "taskContractDigest": expected_contract_digest,
        "allowedDomains": allowed_domains,
        "ownerDomain": owner,
        "supportedDomains": supported_domains,
        "crossDomain": cross_domain,
        "latestIntentConcepts": latest_concepts,
        "rawLatestIntentConcepts": raw_latest_concepts,
        "taskContractConcepts": contract_concepts,
        "rawTaskContractConcepts": raw_contract_concepts,
        "priorIntentConcepts": prior_concepts,
        "rawPriorIntentConcepts": raw_prior_concepts,
        "evidenceConcepts": typed_evidence_concepts,
        "rawEvidenceConcepts": raw_evidence_concepts,
        "acceptedEvidenceContextIds": [
            item.get("receiptId") for item in accepted_evidence_contexts
        ],
        "rejectedEvidenceContextIds": [
            item.get("receiptId") for item in rejected_evidence_contexts
        ],
        "rejectedEvidenceContexts": rejected_evidence_contexts,
        "answerConcepts": output_concepts,
        "templateConcepts": declared_concepts,
        "bridgeConcepts": bridge_concepts,
        "supportOverlapConcepts": support_overlap,
        "latestIntentOverlapConcepts": latest_overlap,
        "sourceBoundLatestTurnSatisfied": source_bound_latest_turn_satisfied,
        "sourceBoundEvidenceOverlapConcepts": source_bound_evidence_overlap,
        "templateOutputOverlapConcepts": declared_output_overlap,
        "templateOutputBound": output_binding_matches,
        "templateOutputSha256": bound_output_sha256,
        "templateBoundOutputConcepts": bound_output_concepts,
        "unsupportedSpecialistConcepts": (
            unsupported_specialist_concepts if failed_domain_or_support else []
        ),
        "templateOwnership": ownership,
        "turnLineage": lineage,
        "turnTransition": _text(lineage.get("transition")),
        "turnLineageDecision": _text(lineage.get("decision")),
        "semanticExclusionReceipt": semantic_receipt,
        "excludedConcepts": sorted(excluded_concepts),
        "excludedPositiveSupportConcepts": sorted(excluded_from_support),
        "discussionConcepts": sorted(discussion_concepts),
        "discussionSatisfiedConcepts": discussion_satisfied_concepts,
        "requiredReplacementConcepts": sorted(required_concepts),
        "violatedExclusionIds": list(dict.fromkeys(violated_exclusion_ids)),
        "missingRequiredReplacementIds": list(
            dict.fromkeys(missing_required_replacement_ids)
        ),
        "semanticViolationSegments": semantic_violation_segments,
    }


class AnswerRelevanceError(ValueError):
    """Raised when a final answer must be replanned for relevance."""

    def __init__(self, receipt: Dict[str, Any]):
        self.receipt = dict(receipt or {})
        issues = ", ".join(self.receipt.get("issues") or ["answer-relevance-failed"])
        super().__init__(f"Answer relevance contract requires replan: {issues}")


def answer_urls(value: Any) -> list[str]:
    return list(
        dict.fromkeys(
            match.rstrip(".,;:!?") for match in _URL_RE.findall(_text(value))
        )
    )


def build_source_receipt(
    *,
    receipt_id: Any,
    run_id: Any,
    claim_text: Any,
    source_type: Any,
    locator: Any,
    content_sha256: Any,
    observed_at: Any,
    source_id: Any = "",
    state: str = "checked",
) -> Dict[str, Any]:
    """Format provenance already produced by a trusted source reader.

    This helper does not retrieve or verify a source. Callers must never build a
    receipt from model-written URL text; the retrieval or local-reader boundary
    owns the observed content hash and timestamp.
    """

    normalized_type = _text(source_type).lower()
    return {
        "kind": SOURCE_RECEIPT_KIND,
        "receiptId": _text(receipt_id),
        "runId": _text(run_id),
        "claimDigest": text_sha256(claim_text),
        "sourceType": normalized_type,
        "retrievalMethod": SOURCE_METHODS.get(normalized_type, ""),
        "locator": _text(locator),
        "sourceId": _text(source_id),
        "state": _text(state).lower(),
        "contentSha256": _text(content_sha256).lower(),
        "observedAt": _text(observed_at),
    }


def validate_source_receipt(
    value: Any,
    *,
    expected_run_id: Any,
    expected_claim_digest: Any,
) -> Dict[str, Any]:
    receipt = value if isinstance(value, dict) else {}
    source_type = _text(receipt.get("sourceType")).lower()
    method = _text(receipt.get("retrievalMethod")).lower()
    locator = _text(receipt.get("locator") or receipt.get("path"))
    issues = []

    if _text(receipt.get("kind")) != SOURCE_RECEIPT_KIND:
        issues.append("missing-structured-source-receipt")
    if not _text(receipt.get("receiptId")):
        issues.append("missing-source-receipt-id")
    if source_type not in SOURCE_TYPES:
        issues.append("invalid-source-type")
    elif method != SOURCE_METHODS[source_type]:
        issues.append("source-method-type-mismatch")
    if not _text(expected_run_id):
        issues.append("missing-expected-run-id")
    elif _text(receipt.get("runId")) != _text(expected_run_id):
        issues.append("source-receipt-run-mismatch")
    if _text(receipt.get("claimDigest")) != _text(expected_claim_digest):
        issues.append("source-receipt-claim-mismatch")
    if _text(receipt.get("state")).lower() not in VERIFIED_SOURCE_STATES:
        issues.append("source-not-checked")
    if not _SHA256_RE.fullmatch(_text(receipt.get("contentSha256"))):
        issues.append("missing-source-content-hash")
    if not _text(receipt.get("observedAt")):
        issues.append("missing-source-observation-time")
    if not locator:
        issues.append("missing-source-locator")
    elif source_type == "web":
        parsed = urlparse(locator)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            issues.append("invalid-web-source-locator")
    elif source_type == "runtime-state":
        parsed = urlparse(locator)
        if parsed.scheme != "runtime" or not (parsed.netloc or parsed.path):
            issues.append("invalid-runtime-source-locator")
    elif locator.lower().startswith(("http://", "https://")):
        issues.append("local-source-has-web-locator")

    normalized = {
        "kind": _text(receipt.get("kind")),
        "receiptId": _text(receipt.get("receiptId")),
        "runId": _text(receipt.get("runId")),
        "claimDigest": _text(receipt.get("claimDigest")),
        "sourceType": source_type,
        "retrievalMethod": method,
        "locator": locator,
        "sourceId": _text(receipt.get("sourceId")),
        "state": _text(receipt.get("state")).lower(),
        "contentSha256": _text(receipt.get("contentSha256")).lower(),
        "observedAt": _text(receipt.get("observedAt")),
        "receiptStatus": "verified" if not issues else "unverified",
        "issues": issues,
    }
    return normalized


def source_provenance_contract(
    answer_text: Any,
    evidence: Optional[Iterable[Dict[str, Any]]],
    *,
    run_id: Any,
) -> Dict[str, Any]:
    """Calibrate source status from receipts, never from URL-shaped prose."""

    claim_digest = text_sha256(answer_text)
    receipts = [
        validate_source_receipt(
            item,
            expected_run_id=run_id,
            expected_claim_digest=claim_digest,
        )
        for item in (evidence or ())
        if isinstance(item, dict)
    ]
    verified = [item for item in receipts if item.get("receiptStatus") == "verified"]
    web_locators = {
        _text(item.get("locator"))
        for item in verified
        if item.get("sourceType") == "web" and _text(item.get("locator"))
    }
    urls = answer_urls(answer_text)
    unreceipted_urls = [url for url in urls if url not in web_locators]
    issues = list(
        dict.fromkeys(
            issue
            for receipt in receipts
            for issue in (receipt.get("issues") or [])
            if _text(issue)
        )
    )
    if urls and not verified:
        issues.append("url-text-without-source-receipt")
    elif unreceipted_urls:
        issues.append("unreceipted-answer-url")
    issues = list(dict.fromkeys(issues))
    source_types = sorted(
        {_text(item.get("sourceType")) for item in verified if _text(item.get("sourceType"))}
    )
    has_verified_source = bool(verified)
    all_answer_urls_receipted = not unreceipted_urls
    return {
        "kind": "source-provenance-contract",
        "status": (
            "verified"
            if has_verified_source and all_answer_urls_receipted
            else "partially-grounded"
            if has_verified_source
            else "unverified"
        ),
        "claimDigest": claim_digest,
        "runId": _text(run_id),
        "receiptCount": len(receipts),
        "verifiedReceiptCount": len(verified),
        "sourceTypes": source_types,
        "answerUrls": urls,
        "unreceiptedAnswerUrls": unreceipted_urls,
        "mayClaimGrounded": has_verified_source,
        "mayClaimCited": has_verified_source and all_answer_urls_receipted,
        "mayClaimVerified": has_verified_source and all_answer_urls_receipted,
        "issues": issues,
        "receipts": receipts,
    }


def terminal_state_contract(
    requested_status: Any,
    *,
    answer_text: Any,
    evidence_requirement: Any = "none",
    source_provenance: Any = None,
    steering_receipt: Any = None,
    semantic_contract: Any = None,
    semantic_proof_required: bool = False,
    answer_relevance: Any = None,
) -> Dict[str, Any]:
    """Derive one honest terminal state from typed completion receipts.

    The contract never inspects answer wording. It preserves useful partial text
    while preventing incomplete evidence, steering, semantic proof, or relevance
    work from being labeled complete.
    """

    requested = _text(requested_status).lower() or "complete"
    if requested not in FINAL_STATES:
        raise ValueError(
            "Requested terminal status must be complete, bounded, blocked, or failed."
        )
    requirement = _text(evidence_requirement).lower() or "none"
    provenance = source_provenance if isinstance(source_provenance, dict) else {}
    steering = steering_receipt if isinstance(steering_receipt, dict) else {}
    semantic = semantic_contract if isinstance(semantic_contract, dict) else {}
    relevance = answer_relevance if isinstance(answer_relevance, dict) else {}
    reasons: list[Dict[str, Any]] = []

    def add_reason(state: str, code: str, kind: str, **details: Any) -> None:
        reasons.append(
            {
                "kind": kind,
                "code": code,
                "state": state,
                **details,
            }
        )

    if requested != "complete":
        add_reason(
            requested,
            f"requested-{requested}",
            "requested-terminal-state",
        )

    permission_key = EVIDENCE_REQUIREMENTS.get(requirement)
    if permission_key is None:
        add_reason(
            "failed",
            "invalid-evidence-requirement",
            "evidence",
            requirement=requirement,
        )
    elif permission_key and not provenance.get(permission_key):
        add_reason(
            "bounded",
            f"required-evidence-not-{requirement}",
            "evidence",
            requirement=requirement,
            provenanceStatus=_text(provenance.get("status")) or "unverified",
            verifiedReceiptCount=int(provenance.get("verifiedReceiptCount") or 0),
        )

    if steering:
        steering_status = _text(steering.get("status")).lower() or "unknown"
        try:
            accepted_through = int(steering.get("acceptedThrough") or 0)
            applied_through = int(steering.get("appliedThrough") or 0)
            if accepted_through < 0 or applied_through < 0 or applied_through > accepted_through:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            add_reason(
                "failed",
                "invalid-steering-revision-receipt",
                "steering",
                status=steering_status,
            )
        else:
            if accepted_through > applied_through:
                add_reason(
                    "blocked",
                    "accepted-steering-not-applied",
                    "steering",
                    status=steering_status,
                    acceptedThrough=accepted_through,
                    appliedThrough=applied_through,
                )
            elif steering_status == "failed":
                add_reason(
                    "failed",
                    "steering-application-failed",
                    "steering",
                    status=steering_status,
                    acceptedThrough=accepted_through,
                    appliedThrough=applied_through,
                )

    if semantic:
        semantic_status = _text(semantic.get("status")).lower()
        semantic_issues = _items(semantic.get("issues"))
        if semantic.get("kind") != "command-completion-contract":
            add_reason(
                "failed",
                "invalid-semantic-completion-contract",
                "semantic-completion",
                status=semantic_status or "invalid",
                issues=semantic_issues,
            )
        elif semantic_status != "pass":
            add_reason(
                "failed",
                "semantic-completion-not-proven",
                "semantic-completion",
                status=semantic_status or "missing",
                issues=semantic_issues,
            )
    elif semantic_proof_required:
        add_reason(
            "failed",
            "missing-semantic-completion-contract",
            "semantic-completion",
            status="missing",
            issues=[],
        )

    if relevance and (
        relevance.get("mayFinalize") is False
        or _text(relevance.get("status")).lower() == "replan"
        or _text(relevance.get("decision")).lower() == "replan"
    ):
        add_reason(
            "blocked",
            "answer-relevance-replan-required",
            "answer-relevance",
            status=_text(relevance.get("status")) or "replan",
            issues=_items(relevance.get("issues")),
        )

    final_status = max(
        (requested, *(_text(reason.get("state")) for reason in reasons)),
        key=lambda state: TERMINAL_STATE_PRIORITY.get(state, -1),
    )
    reason_codes = list(
        dict.fromkeys(_text(reason.get("code")) for reason in reasons if reason.get("code"))
    )
    return {
        "kind": "terminal-state-receipt",
        "requestedStatus": requested,
        "status": final_status,
        "statusAdjusted": final_status != requested,
        "mayClaimComplete": final_status == "complete",
        "helpfulPartialPreserved": bool(_text(answer_text)) and final_status != "complete",
        "answerDigest": text_sha256(answer_text),
        "evidenceRequirement": requirement,
        "reasonCodes": reason_codes,
        "reasons": reasons,
    }


@dataclass(frozen=True)
class AnswerRevision:
    stage: str
    source_sha256: str
    result_sha256: str
    reason: str = ""


@dataclass(frozen=True)
class AnswerEnvelope:
    objective: str
    text: str
    run_id: str = ""
    status: str = "draft"
    stage: str = "primary-worker"
    evidence: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    evidence_provenance: Dict[str, Any] = field(default_factory=dict)
    relevance_context: Dict[str, Any] = field(default_factory=dict)
    answer_relevance: Dict[str, Any] = field(default_factory=dict)
    terminal_context: Dict[str, Any] = field(default_factory=dict)
    terminal_state: Dict[str, Any] = field(default_factory=dict)
    provenance: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    artifacts: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    gaps: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    revisions: Tuple[AnswerRevision, ...] = field(default_factory=tuple)
    final_text_sha256: str = ""
    created_at: float = field(default_factory=time.time)
    version: int = ENVELOPE_VERSION

    @classmethod
    def from_text(
        cls,
        text: Any,
        objective: Any = "",
        run_id: Any = "",
    ) -> "AnswerEnvelope":
        return cls(
            objective=_text(objective),
            text=_text(text),
            run_id=_text(run_id),
        )

    def revise(
        self,
        text: Any,
        stage: str,
        reason: str = "",
        gaps: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        next_text = _text(text)
        revision = AnswerRevision(
            stage=_text(stage) or "revision",
            source_sha256=text_sha256(self.text),
            result_sha256=text_sha256(next_text),
            reason=_text(reason),
        )
        return replace(
            self,
            text=next_text,
            stage=revision.stage,
            gaps=tuple(gaps or ()),
            revisions=self.revisions + (revision,),
            evidence_provenance=source_provenance_contract(
                next_text,
                self.evidence,
                run_id=self.run_id,
            ),
            answer_relevance=self._evaluate_relevance(next_text),
            terminal_state={},
        )

    def with_evidence(self, evidence: Optional[Iterable[Dict[str, Any]]]) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        items = tuple(item for item in (evidence or ()) if isinstance(item, dict))
        return replace(
            self,
            evidence=items,
            evidence_provenance=source_provenance_contract(
                self.text,
                items,
                run_id=self.run_id,
            ),
            terminal_state={},
        )

    def with_provenance(self, provenance: Optional[Iterable[Dict[str, Any]]]) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        return replace(
            self,
            provenance=tuple(item for item in (provenance or ()) if isinstance(item, dict)),
            terminal_state={},
        )

    def with_relevance_context(
        self,
        *,
        latest_user_intent: Any,
        intent_domain: Any,
        task_contract: Dict[str, Any],
        template_ownership: Optional[Dict[str, Any]],
        prior_intent_concepts: Any = (),
        evidence_concepts: Any = (),
        turn_lineage: Optional[Dict[str, Any]] = None,
        evidence_contexts: Optional[Iterable[Dict[str, Any]]] = None,
        semantic_exclusions: Optional[Dict[str, Any]] = None,
        require_template_ownership: bool = True,
    ) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        context = {
            "latest_user_intent": _text(latest_user_intent),
            "intent_domain": _items(intent_domain),
            "task_contract": dict(task_contract or {}),
            "template_ownership": dict(template_ownership or {}),
            "prior_intent_concepts": _items(prior_intent_concepts),
            "evidence_concepts": _items(evidence_concepts),
            "turn_lineage": dict(turn_lineage or {}),
            "evidence_contexts": tuple(
                dict(item)
                for item in (evidence_contexts or ())
                if isinstance(item, dict)
            ),
            "semantic_exclusions": dict(semantic_exclusions or {}),
            "require_template_ownership": bool(require_template_ownership),
        }
        return replace(
            self,
            relevance_context=context,
            answer_relevance=answer_relevance_contract(
                self.text,
                run_id=self.run_id,
                **context,
            ),
            terminal_state={},
        )

    def with_terminal_context(
        self,
        *,
        evidence_requirement: Any = "none",
        steering_receipt: Optional[Dict[str, Any]] = None,
        semantic_contract: Optional[Dict[str, Any]] = None,
        semantic_proof_required: bool = False,
    ) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        context = {
            "evidence_requirement": _text(evidence_requirement).lower() or "none",
            "steering_receipt": dict(steering_receipt or {}),
            "semantic_contract": dict(semantic_contract or {}),
            "semantic_proof_required": bool(semantic_proof_required),
        }
        return replace(self, terminal_context=context, terminal_state={})

    def _evaluate_relevance(self, text: Any) -> Dict[str, Any]:
        if not self.relevance_context:
            return {}
        return answer_relevance_contract(
            text,
            run_id=self.run_id,
            **self.relevance_context,
        )

    def finalize(self, status: str, stage: str = "final-gate") -> "AnswerEnvelope":
        normalized = _text(status).lower()
        if normalized not in FINAL_STATES:
            raise ValueError(
                "Answer envelope status must be complete, bounded, blocked, or failed."
            )
        relevance = self._evaluate_relevance(self.text)
        if (
            relevance
            and not relevance.get("mayFinalize", False)
            and not self.terminal_context
        ):
            raise AnswerRelevanceError(relevance)
        evidence_provenance = source_provenance_contract(
            self.text,
            self.evidence,
            run_id=self.run_id,
        )
        terminal_state = terminal_state_contract(
            normalized,
            answer_text=self.text,
            source_provenance=evidence_provenance,
            answer_relevance=relevance,
            **self.terminal_context,
        )
        return replace(
            self,
            status=terminal_state["status"],
            stage=_text(stage) or "final-gate",
            final_text_sha256=text_sha256(self.text),
            evidence_provenance=evidence_provenance,
            answer_relevance=relevance,
            terminal_state=terminal_state,
        )

    def verify_final_integrity(self, text: Any) -> bool:
        if self.status not in FINAL_STATES or not self.final_text_sha256:
            return False
        return self.final_text_sha256 == text_sha256(text)

    def public_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["created_at"] = round(float(self.created_at), 3)
        return value


def synthetic_envelope_check() -> Dict[str, Any]:
    base = AnswerEnvelope.from_text("Draft answer", objective="Compare A and B")
    revised = base.revise("Qualified answer", "analytical-repair", reason="removed unsupported claim").with_provenance(
        [
            {
                "kind": "technical-claim-audit",
                "verdict": "bounded",
                "unsupportedCount": 1,
                "cacheHit": False,
            }
        ]
    )
    final = revised.finalize("complete")
    bounded = AnswerEnvelope.from_text(
        "Which mounting pattern should I use?",
        objective="Create a mounting bracket",
    ).finalize("bounded")
    invented_url_text = "The source confirms it: https://invented.invalid/datasheet"
    invented_url = AnswerEnvelope.from_text(
        invented_url_text,
        objective="Check a sourced claim",
        run_id="run-invented",
    ).with_evidence(
        [
            {
                "title": "Model-written citation",
                "url": "https://invented.invalid/datasheet",
                "snippet": "No retrieval occurred.",
            }
        ]
    ).finalize("complete")
    checked_web_text = "The checked source is https://example.test/datasheet"
    checked_web = AnswerEnvelope.from_text(
        checked_web_text,
        objective="Check a sourced claim",
        run_id="run-web",
    ).with_evidence(
        [
            build_source_receipt(
                receipt_id="web-1",
                run_id="run-web",
                claim_text=checked_web_text,
                source_type="web",
                locator="https://example.test/datasheet",
                content_sha256=text_sha256("retrieved datasheet bytes"),
                observed_at="2026-08-06T06:20:00Z",
            )
        ]
    ).finalize("complete")
    local_text = "The local report records a passing result."
    checked_local = AnswerEnvelope.from_text(
        local_text,
        objective="Read local evidence",
        run_id="run-local",
    ).with_evidence(
        [
            build_source_receipt(
                receipt_id="local-1",
                run_id="run-local",
                claim_text=local_text,
                source_type="local-file",
                locator="/workspace/report.md",
                content_sha256=text_sha256("local report content"),
                observed_at="2026-08-06T06:20:01Z",
            )
        ]
    ).finalize("complete")
    vault_text = "The cached source-vault manual states the configured limit."
    checked_vault = AnswerEnvelope.from_text(
        vault_text,
        objective="Read cached source evidence",
        run_id="run-vault",
    ).with_evidence(
        [
            build_source_receipt(
                receipt_id="vault-1",
                run_id="run-vault",
                claim_text=vault_text,
                source_type="source-vault",
                locator="source-vault://3d-printing/manual-1",
                content_sha256=text_sha256("cached manual content"),
                observed_at="2026-08-06T06:20:02Z",
                source_id="manual-1",
            )
        ]
    ).finalize("complete")
    relevance_intent = (
        "With Web Access disabled, does a URL written by the model count as "
        "retrieved evidence?"
    )
    relevance_contract = {
        "kind": "answer-task-contract",
        "domains": ["evidence-provenance"],
        "mustDo": ["answer the retrieval and confidence boundary"],
    }
    wrong_domain_text = (
        "For the lightweight vehicle, use a 72 V motor controller and set the "
        "battery current limit conservatively."
    )
    wrong_domain_ownership = build_template_ownership_receipt(
        receipt_id="owner-wrong",
        run_id="run-wrong-domain",
        template_id="vehicle-controller-guide",
        latest_user_intent=relevance_intent,
        task_contract=relevance_contract,
        owner_domain="vehicle-motion-control",
        supported_domains=["vehicle-motion-control"],
        concepts=["lightweight vehicle", "motor controller", "battery current limit"],
    )
    wrong_domain_draft = AnswerEnvelope.from_text(
        wrong_domain_text,
        objective=relevance_intent,
        run_id="run-wrong-domain",
    ).with_relevance_context(
        latest_user_intent=relevance_intent,
        intent_domain="evidence-provenance",
        task_contract=relevance_contract,
        template_ownership=wrong_domain_ownership,
    )
    wrong_domain_blocked = False
    try:
        wrong_domain_draft.finalize("complete")
    except ValueError:
        wrong_domain_blocked = True

    specialist_intent = (
        "How should I size a motor controller from battery voltage and current limit?"
    )
    specialist_contract = {
        "kind": "answer-task-contract",
        "domains": ["vehicle-motion-control"],
        "mustDo": ["relate controller voltage to battery voltage and current limit"],
    }
    specialist_text = (
        "Choose a motor controller above the maximum battery voltage, then set its "
        "current limit within the battery rating."
    )
    specialist_ownership = build_template_ownership_receipt(
        receipt_id="owner-specialist",
        run_id="run-specialist",
        template_id="vehicle-controller-guide",
        latest_user_intent=specialist_intent,
        task_contract=specialist_contract,
        owner_domain="vehicle-motion-control",
        supported_domains=["vehicle-motion-control"],
        concepts=["motor controller", "battery voltage", "current limit"],
    )
    same_domain = AnswerEnvelope.from_text(
        specialist_text,
        objective=specialist_intent,
        run_id="run-specialist",
    ).with_relevance_context(
        latest_user_intent=specialist_intent,
        intent_domain="vehicle-motion-control",
        task_contract=specialist_contract,
        template_ownership=specialist_ownership,
    ).finalize("complete")

    comparison_intent = (
        "Compare source provenance controls with safety-case traceability for release decisions."
    )
    comparison_contract = {
        "kind": "comparison-task-contract",
        "allowedDomains": ["evidence-provenance", "safety-assurance"],
        "mustDo": ["connect source receipts to safety-case traceability"],
    }
    comparison_text = (
        "Source receipts establish evidence provenance; safety-case traceability "
        "connects that evidence to release decisions."
    )
    comparison_ownership = build_template_ownership_receipt(
        receipt_id="owner-comparison",
        run_id="run-comparison",
        template_id="cross-domain-evidence-comparison",
        latest_user_intent=comparison_intent,
        task_contract=comparison_contract,
        owner_domain="evidence-provenance",
        supported_domains=["evidence-provenance", "safety-assurance"],
        concepts=["source receipts", "evidence provenance", "safety-case traceability"],
        cross_domain=True,
        bridge_concepts=["evidence", "traceability", "release decisions"],
    )
    cross_domain = AnswerEnvelope.from_text(
        comparison_text,
        objective=comparison_intent,
        run_id="run-comparison",
    ).with_relevance_context(
        latest_user_intent=comparison_intent,
        intent_domain="evidence-provenance",
        task_contract=comparison_contract,
        template_ownership=comparison_ownership,
    ).finalize("complete")
    switch_prior = "Find the manufacturer rating and source for the FluxDrive X1 controller."
    switch_intent = (
        "Never mind the rating or source. What controller voltage headroom "
        "should I use for a 72 V lightweight kart?"
    )
    switch_contract = {
        "kind": "controller-voltage-sizing-task",
        "domains": ["engineering-power-conversion"],
        "mustDo": ["size controller voltage headroom from the 72 V pack"],
    }
    switch_lineage = turn_lineage_contract(
        run_id="run-lineage-switch",
        latest_user_intent=switch_intent,
        current_domain="engineering-power-conversion",
        task_contract=switch_contract,
        declared_relation="follow-up",
        prior_user_intent=switch_prior,
        prior_domain="source-resolution",
    )
    switch_ownership = build_template_ownership_receipt(
        receipt_id="owner-lineage-switch",
        run_id="run-lineage-switch",
        template_id="controller-voltage-sizing",
        latest_user_intent=switch_intent,
        task_contract=switch_contract,
        owner_domain="engineering-power-conversion",
        concepts=["controller", "voltage headroom", "72 V pack"],
        turn_lineage_digest=switch_lineage.get("lineageDigest"),
    )
    stale_switch_evidence = build_context_evidence_receipt(
        receipt_id="stale-source-context",
        run_id="run-lineage-switch",
        intent_text=switch_prior,
        domain="source-resolution",
        concepts=["manufacturer rating", "FluxDrive X1"],
        source_receipt_ids=["source-prior"],
    )
    lineage_switch = AnswerEnvelope.from_text(
        "Use the 72 V pack's maximum voltage to choose controller voltage headroom.",
        objective=switch_intent,
        run_id="run-lineage-switch",
    ).with_relevance_context(
        latest_user_intent=switch_intent,
        intent_domain="engineering-power-conversion",
        task_contract=switch_contract,
        template_ownership=switch_ownership,
        prior_intent_concepts=[switch_prior],
        turn_lineage=switch_lineage,
        evidence_contexts=[stale_switch_evidence],
    ).finalize("complete")
    ambiguous_lineage = turn_lineage_contract(
        run_id="run-lineage-ambiguous",
        latest_user_intent="What about certification instead?",
        current_domain="airworthiness-regulation",
        task_contract={
            "kind": "certification-question-task",
            "domains": ["airworthiness-regulation"],
        },
        declared_relation="ambiguous",
        prior_user_intent=specialist_intent,
        prior_domain="vehicle-motion-control",
    )
    ambiguous_ownership = build_template_ownership_receipt(
        receipt_id="owner-lineage-ambiguous",
        run_id="run-lineage-ambiguous",
        template_id="certification-question",
        latest_user_intent="What about certification instead?",
        task_contract={
            "kind": "certification-question-task",
            "domains": ["airworthiness-regulation"],
        },
        owner_domain="airworthiness-regulation",
        concepts=["certification"],
        turn_lineage_digest=ambiguous_lineage.get("lineageDigest"),
    )
    lineage_ambiguous = AnswerEnvelope.from_text(
        "The certification target needs clarification.",
        objective="What about certification instead?",
        run_id="run-lineage-ambiguous",
    ).with_relevance_context(
        latest_user_intent="What about certification instead?",
        intent_domain="airworthiness-regulation",
        task_contract={
            "kind": "certification-question-task",
            "domains": ["airworthiness-regulation"],
        },
        template_ownership=ambiguous_ownership,
        turn_lineage=ambiguous_lineage,
    ).with_terminal_context().finalize("complete")
    evidence_bounded = AnswerEnvelope.from_text(
        "No checked source reached this run; attach the primary source to continue.",
        objective="Answer from checked evidence",
        run_id="run-evidence-bounded",
    ).with_terminal_context(
        evidence_requirement="grounded",
    ).finalize("complete")
    verified_evidence_complete = AnswerEnvelope.from_text(
        checked_web_text,
        objective="Check a sourced claim",
        run_id="run-web",
    ).with_evidence(
        checked_web.evidence
    ).with_terminal_context(
        evidence_requirement="verified",
    ).finalize("complete")
    steering_blocked = AnswerEnvelope.from_text(
        "This partial answer remains useful, but the accepted steering is not applied.",
        objective="Apply the latest steering",
        run_id="run-steering",
    ).with_terminal_context(
        steering_receipt={
            "status": "accepted",
            "acceptedThrough": 2,
            "appliedThrough": 1,
        },
    ).finalize("complete")
    semantic_failed = AnswerEnvelope.from_text(
        "The command returned zero, but semantic completion is unproven.",
        objective="Complete the current action",
        run_id="run-semantic",
    ).with_terminal_context(
        semantic_contract={
            "kind": "command-completion-contract",
            "status": "fail",
            "issues": ["missing-semantic-completion-receipt"],
        },
        semantic_proof_required=True,
    ).finalize("complete")
    relevance_terminal = wrong_domain_draft.with_terminal_context().finalize("complete")
    mutation_blocked = False
    try:
        final.revise("Changed after final", "late-guard")
    except ValueError:
        mutation_blocked = True
    ok = (
        base.status == "draft"
        and len(revised.revisions) == 1
        and len(revised.provenance) == 1
        and revised.provenance[0].get("kind") == "technical-claim-audit"
        and final.verify_final_integrity("Qualified answer")
        and bounded.verify_final_integrity("Which mounting pattern should I use?")
        and bounded.status == "bounded"
        and not final.verify_final_integrity("Changed after final")
        and mutation_blocked
        and invented_url.evidence_provenance.get("status") == "unverified"
        and not invented_url.evidence_provenance.get("mayClaimGrounded")
        and "url-text-without-source-receipt"
        in (invented_url.evidence_provenance.get("issues") or [])
        and checked_web.evidence_provenance.get("status") == "verified"
        and checked_web.evidence_provenance.get("sourceTypes") == ["web"]
        and checked_local.evidence_provenance.get("status") == "verified"
        and checked_local.evidence_provenance.get("sourceTypes") == ["local-file"]
        and checked_vault.evidence_provenance.get("status") == "verified"
        and checked_vault.evidence_provenance.get("sourceTypes") == ["source-vault"]
        and wrong_domain_draft.answer_relevance.get("status") == "replan"
        and "template-owner-domain-not-allowed"
        in (wrong_domain_draft.answer_relevance.get("issues") or [])
        and wrong_domain_blocked
        and same_domain.answer_relevance.get("status") == "pass"
        and same_domain.answer_relevance.get("mayFinalize")
        and cross_domain.answer_relevance.get("status") == "pass"
        and cross_domain.answer_relevance.get("crossDomain")
        and switch_lineage.get("transition") == "domain-switch"
        and switch_lineage.get("decision") == "isolate"
        and lineage_switch.status == "complete"
        and lineage_switch.answer_relevance.get("priorIntentConcepts") == []
        and lineage_switch.answer_relevance.get("rejectedEvidenceContextIds")
        == ["stale-source-context"]
        and lineage_ambiguous.status == "blocked"
        and ambiguous_lineage.get("decision") == "replan"
        and final.status == "complete"
        and final.terminal_state.get("mayClaimComplete")
        and evidence_bounded.status == "bounded"
        and evidence_bounded.terminal_state.get("reasonCodes")
        == ["required-evidence-not-grounded"]
        and evidence_bounded.verify_final_integrity(evidence_bounded.text)
        and verified_evidence_complete.status == "complete"
        and verified_evidence_complete.terminal_state.get("mayClaimComplete")
        and steering_blocked.status == "blocked"
        and "accepted-steering-not-applied"
        in (steering_blocked.terminal_state.get("reasonCodes") or [])
        and semantic_failed.status == "failed"
        and "semantic-completion-not-proven"
        in (semantic_failed.terminal_state.get("reasonCodes") or [])
        and relevance_terminal.status == "blocked"
        and "answer-relevance-replan-required"
        in (relevance_terminal.terminal_state.get("reasonCodes") or [])
    )
    return {
        "status": "pass" if ok else "fail",
        "revisionCount": len(revised.revisions),
        "provenanceCount": len(revised.provenance),
        "finalIntegrity": final.verify_final_integrity("Qualified answer"),
        "mutationBlocked": mutation_blocked,
        "inventedUrlStatus": invented_url.evidence_provenance.get("status"),
        "checkedWebStatus": checked_web.evidence_provenance.get("status"),
        "checkedLocalStatus": checked_local.evidence_provenance.get("status"),
        "checkedSourceVaultStatus": checked_vault.evidence_provenance.get("status"),
        "wrongDomainStatus": wrong_domain_draft.answer_relevance.get("status"),
        "wrongDomainFinalizationBlocked": wrong_domain_blocked,
        "sameDomainStatus": same_domain.answer_relevance.get("status"),
        "crossDomainStatus": cross_domain.answer_relevance.get("status"),
        "lineageSwitchStatus": lineage_switch.answer_relevance.get("status"),
        "lineageSwitchDecision": switch_lineage.get("decision"),
        "lineageAmbiguousStatus": lineage_ambiguous.status,
        "ordinaryTerminalStatus": final.status,
        "evidenceTerminalStatus": evidence_bounded.status,
        "verifiedEvidenceTerminalStatus": verified_evidence_complete.status,
        "steeringTerminalStatus": steering_blocked.status,
        "semanticTerminalStatus": semantic_failed.status,
        "relevanceTerminalStatus": relevance_terminal.status,
    }
