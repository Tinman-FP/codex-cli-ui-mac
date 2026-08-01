"""Generic turn understanding and execution policy for Codex CLI UI.

This module is intentionally domain-light. It identifies the shape of a turn,
the evidence it needs, and whether a deterministic capability or a reasoning
worker should own the response. Product-specific handlers remain in the legacy
server while they are migrated behind explicit capabilities.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse


KERNEL_VERSION = 1

_URL_RE = re.compile(r"https?://[^\s<>\]\[()]+", flags=re.IGNORECASE)
_FILE_RE = re.compile(
    r"(?<![\w.-])(?:~?/|/)?(?:[^\s/]+/)*[^\s/]+\.(?:cfg|conf|ini|json|jsonl|yaml|yml|toml|md|txt|csv|xlsx|pdf|docx|py|js|ts|tsx|jsx|html|css|gcode|3mf|stl|step|stp|obj|scad|f3d|f3z)(?![\w.-])",
    flags=re.IGNORECASE,
)

_ACTION_TERMS = (
    "add",
    "analyze",
    "analyse",
    "apply",
    "build",
    "change",
    "clean up",
    "cleanup",
    "compare these files",
    "create",
    "debug",
    "design",
    "edit",
    "find",
    "generate",
    "fix",
    "implement",
    "install",
    "map",
    "model",
    "modify",
    "pull",
    "remove",
    "replace",
    "restart",
    "review the code",
    "run",
    "stage",
    "test",
    "update",
    "verify",
    "wire",
)
_EXECUTION_TERMS = (
    "analyze",
    "analyse",
    "build",
    "create",
    "design",
    "generate",
    "make",
    "model",
    "perform",
    "run",
    "stage",
)
_TECHNICAL_SOURCE_TERMS = (
    "datasheet",
    "dimensions",
    "dimension of",
    "engineering details",
    "instruction manual",
    "manual for",
    "mounting pattern",
    "pinout",
    "spec sheet",
    "specification",
    "technical drawing",
    "technical details",
)
_EXPLICIT_RESEARCH_TERMS = (
    "do the research",
    "do not forget the research",
    "look up",
    "research before",
    "research designing",
    "research the",
    "search the web",
    "source-backed research",
    "your research",
)
_COMPATIBILITY_TERMS = (
    "can i use",
    "compatible with",
    "compatibility",
    "will it work with",
    "will this work with",
)
_LOCAL_SURFACE_TERMS = (
    "this app",
    "this mac",
    "this machine",
    "codex cli ui",
    "dashboard",
    "device tab",
    "model health",
    "panel",
    "local file",
    "workspace",
    "repo",
    "repository",
    "server.py",
    "app.js",
)
_LOCAL_PRODUCT_SURFACE_TERMS = (
    "this app",
    "codex cli ui",
    "orca codex",
    "orcaslicer codex",
    "tinmanx",
    "tinmanx1",
    "repo",
    "repository",
    "server.py",
    "app.js",
)
_MARKET_TERMS = (
    "best",
    "top ",
    "top-",
    "for sale",
    "buy",
    "recommend",
    "on the market",
    "coming to market",
    "available",
    "where can i find",
    "where can i buy",
)
_VOLATILE_TERMS = (
    "right now",
    "currently",
    "current ",
    "today",
    "latest",
    "upcoming",
    "next few months",
    "price",
    "budget",
    "under $",
    "less than $",
    "in stock",
    "preorder",
    "release",
    "on the market",
    "for sale",
)
_SCIENTIFIC_TERMS = (
    "scientific evidence",
    "peer-reviewed",
    "peer reviewed",
    "published study",
    "research paper",
    "test data",
    "measured data",
    "datasheet evidence",
    "does it actually",
    "actually improve",
    "prove that",
)
_COMPARISON_TERMS = (
    " compare ",
    "comparison",
    " versus ",
    " vs ",
    "better",
    "stronger",
    "difference between",
    "equivalent",
    "equivilant",
    "which one",
)
_QUESTION_PREFIXES = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "which",
    "who",
    "is ",
    "are ",
    "do ",
    "does ",
    "can ",
    "could ",
    "would ",
    "will ",
    "should ",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _latest_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if _text(message.get("role")).lower() == "user":
            return _text(message.get("text"))
    return ""


def _prior_substantive_context(messages: Sequence[Dict[str, Any]]) -> bool:
    user_turns = 0
    for message in messages or []:
        if _text(message.get("role")).lower() == "user" and _text(message.get("text")):
            user_turns += 1
    return user_turns > 1


def _previous_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    seen_latest = False
    for message in reversed(messages or []):
        if _text(message.get("role")).lower() != "user":
            continue
        text = _text(message.get("text"))
        if not text:
            continue
        if not seen_latest:
            seen_latest = True
            continue
        return text
    return ""


def _has_message_attachments(messages: Sequence[Dict[str, Any]]) -> bool:
    for message in messages or []:
        attachments = message.get("attachments")
        if isinstance(attachments, list) and attachments:
            return True
        if isinstance(message.get("attachment"), dict):
            return True
    return False


def _has(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    for raw_term in terms:
        term = str(raw_term or "").strip().lower()
        if not term:
            continue
        if " " in term or not re.fullmatch(r"[a-z0-9_+-]+", term):
            if term in lower:
                return True
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", lower):
            return True
    return False


def _urls(query: str) -> List[str]:
    return [match.rstrip(".,;:!?") for match in _URL_RE.findall(query)][:4]


def _file_refs(query: str) -> List[str]:
    values: List[str] = []
    # URLs often end in names such as ``manual.pdf`` or ``index.html``.
    # Remove public-source spans before classifying local paths so one object
    # cannot be routed as both a web source and a local file.
    local_text = _URL_RE.sub(" ", query)
    for match in _FILE_RE.findall(local_text):
        value = match.rstrip(".,;:!?")
        if value and value not in values:
            values.append(value)
    return values[:8]


def _object_refs(urls: Sequence[str], files: Sequence[str]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    for value in files:
        refs.append({"type": "local-or-attached-file", "name": Path(value).name})
    for value in urls:
        host = urlparse(value).netloc or value
        refs.append({"type": "public-source", "name": host})
    return refs[:8]


def _clean_comparison_option(value: str) -> str:
    cleaned = value.strip(" `\"'()[]{}:-,.?!;")
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _compact_comparison_options(value: str) -> List[str]:
    """Parse an ordinary two-to-five item choice list without product-specific rules."""
    candidate = " ".join(_text(value).split()).strip(" ,;:.?!")
    if not candidate:
        return []
    # A choice list often ends with the condition that governs the choice.
    # Keep that condition in the intent frame, but do not attach it to the
    # final option name or force the parser into a two-item fallback.
    candidate = re.split(
        r"(?i)\s+\b(?:if|when|where|provided\s+that|assuming)\b",
        candidate,
        maxsplit=1,
    )[0].strip(" ,;:.?!")
    parts = re.split(
        r"\s*,\s*(?:and|or)\s+|\s*,\s*|\s+(?:versus|vs\.?)\s+|\s+or\s+",
        candidate,
        flags=re.IGNORECASE,
    )
    values: List[str] = []
    for part in parts:
        cleaned = _clean_comparison_option(part)
        if not cleaned or len(cleaned.split()) > 9:
            return []
        if re.search(
            r"(?i)\b(?:should|would|could|can|what|which|why|when|where|how)\b",
            cleaned,
        ):
            return []
        if cleaned.lower() not in {item.lower() for item in values}:
            values.append(cleaned)
    return values if 2 <= len(values) <= 5 else []


def _comparison_object_refs(query: str) -> List[Dict[str, str]]:
    text = " ".join(_text(query).split())
    list_patterns = (
        r"(?i)\b(?:would|should|could|can)\s+(?:i|we|you)\s+(?:build(?:\s+.{1,35}?)?\s+around|choose|select|pick|use)\s+(.{5,180}?)(?=[?;]|$)",
        r"(?i)\b(?:choose|select|pick|compare)\s+(?:between\s+)?(.{5,180}?)(?=[?;]|$)",
    )
    for pattern in list_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        values = _compact_comparison_options(match.group(1))
        if values:
            return [{"type": "comparison-option", "name": value} for value in values]
    patterns = (
        r"(?i)\bare\s+(.{2,70}?)\s+(?:good enough|sufficient|adequate)\s+or\s+should\s+(?:i|we)\s+(?:use|choose|select|spend for)\s+(.{2,70}?)(?=[?.!,;]|$)",
        r"(?i)\b(?:should|would|could|can)\s+(?:i|we)\s+(?:base\s+.{1,60}?\s+on|use|choose|select)\s+(.{2,60}?)\s+(?:or|versus|vs\.?)\s+(.{2,60}?)(?=[?.!,;]|$)",
        r"(?i)\bcompare\s+(.{2,80}?)\s+(?:and|versus|vs\.?|or)\s+(.{2,80}?)(?=\s+(?:for|as|in|at|under|with|which|what|when)\b|[?.!,;]|$)",
        r"(?i)\b(?:which is|what is)\s+(?:better|stronger)\s+(.{2,60}?)\s+(?:or|versus|vs\.?)\s+(.{2,60}?)(?=\s+(?:for|as|in|at|under|with|which|what|when)\b|[?.!,;]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        values = []
        for value in match.groups():
            cleaned = _clean_comparison_option(value)
            if cleaned and cleaned.lower() not in {item.lower() for item in values}:
                values.append(cleaned)
        if len(values) == 2:
            return [{"type": "comparison-option", "name": value} for value in values]
    return []


def _comparison_criteria(query: str, refs: Sequence[Dict[str, str]]) -> List[str]:
    text = " ".join(_text(query).split())
    match = re.search(r"(?i)\bcompare\s+(.+?)(?=[?.;]|$)", text)
    candidate = match.group(1).strip() if match else ""
    if candidate:
        candidate = re.split(
            r"(?i)\b(?:and\s+)?what\s+(?:could|would|might)\s+reverse\b|\bunless\b",
            candidate,
            maxsplit=1,
        )[0].strip(" ,")
        if " for " in candidate.lower():
            before, after = re.split(r"(?i)\s+for\s+", candidate, maxsplit=1)
            ref_names = [str(ref.get("name") or "").lower() for ref in refs if isinstance(ref, dict)]
            if any(name and name in before.lower() for name in ref_names):
                candidate = after
    raw_parts = re.split(r"\s*,\s*|\s+and\s+", candidate) if candidate else []
    ref_names = [str(ref.get("name") or "").lower() for ref in refs if isinstance(ref, dict)]
    criteria: List[str] = []
    for raw in raw_parts:
        value = re.sub(r"(?i)^and\s+", "", raw.strip())
        value = re.sub(r"(?i)^(?:them|these|the options?)\s+(?:on|for|by|across)\s+", "", value)
        value = re.sub(r"(?i)^(?:on|for|by|across)\s+", "", value).strip(" .,:;-")
        lower_value = value.lower()
        if not value or len(value.split()) > 12:
            continue
        if any(name and (lower_value == name or name in lower_value) for name in ref_names):
            continue
        if lower_value in {"them", "these", "the options", "both"}:
            continue
        if lower_value not in {item.lower() for item in criteria}:
            criteria.append(value)
    if not criteria:
        adjective = re.search(r"(?i)\b(?:better|stronger)\b", text)
        if adjective and re.search(r"(?i)\b(?:which|what|than|versus|vs\.?|or)\b", text):
            criteria.append(adjective.group(0).lower())
    return criteria[:10]


def _vague_action_without_context(query: str, messages: Sequence[Dict[str, Any]]) -> bool:
    if _prior_substantive_context(messages):
        return False
    normalized = re.sub(r"[^a-z0-9\s]", " ", query.lower())
    normalized = " ".join(normalized.split())
    if len(normalized.split()) > 8:
        return False
    return bool(
        re.fullmatch(
            r"(?:(?:can|could|would|will) you )?(?:fix|change|update|do|continue|finish|run|apply|review)(?: it| this| that| the same)?(?: please)?",
            normalized,
        )
    )


def _missing_referent_without_context(query: str, messages: Sequence[Dict[str, Any]]) -> bool:
    if _prior_substantive_context(messages) or _has_message_attachments(messages) or _urls(query) or _file_refs(query):
        return False
    normalized = re.sub(r"[^a-z0-9&\s]", " ", query.lower())
    normalized = " ".join(normalized.split())
    patterns = (
        r"(?:let s|lets|please)?\s*(?:do|choose|use|apply)\s+(?:option\s+)?\d+(?:\s*(?:&|and)?\s*\d+)+",
        r".*\bthese\s+\d+\b(?!\s+(?:sites?|files?|models?|parts?|options?|designs?|geometr(?:y|ies)))\b.*",
        r".*\bthose settings\b.*",
        r".*\bthat one(?: too)?\b.*",
        r".*\bthe other (?:printer|profile|file|machine|part)\b.*",
        r".*\bsame place as last time\b.*",
    )
    if any(re.fullmatch(pattern, normalized) for pattern in patterns):
        return True
    if (
        len(normalized.split()) <= 20
        and re.search(r"\b(?:use|work|compatible|connect)\b", normalized)
        and re.search(r"\b(?:for|with|on|to)\s+(?:this|that|it)\s*$", normalized)
    ):
        return True
    generic_referent = re.search(r"\b(?:these|those)\s+([a-z][a-z0-9_-]*)\b", normalized)
    return bool(
        generic_referent
        and len(normalized.split()) <= 10
        and generic_referent.group(1) not in {"are", "can", "could", "do", "is", "should", "will", "would"}
    )


def build_clarification_question(messages: Sequence[Dict[str, Any]], frame: Dict[str, Any]) -> str:
    """Return one natural question for a kernel-confirmed missing referent."""

    query = _latest_user_text(messages)
    lower = query.lower()
    numbers = re.findall(r"\b\d+\b", query)
    if len(numbers) >= 2 and re.search(r"\b(?:do|choose|use|apply)\b", lower):
        joined = ", ".join(numbers[:-1]) + f", and {numbers[-1]}"
        return f"Which option list do {joined} refer to?"
    if re.search(r"\b(?:same|other (?:printer|profile|file|machine|part)|that one)\b", lower):
        return "What previous action should I repeat, and which exact target should I apply it to?"
    referent = re.search(r"\b(?:these|those)\s+([a-z][a-z0-9_-]*)\b", lower)
    if referent:
        noun = referent.group(1)
        return f"Which {noun} are you referring to?"
    incomplete_use = re.search(
        r"\b(?:use|connect)\s+(.{2,100}?)\s+(?:for|with|on|to)\s+(?:this|that|it)\s*\??$",
        query,
        flags=re.IGNORECASE,
    )
    if incomplete_use:
        named_object = incomplete_use.group(1).strip(" `\"'.,:;-")
        named_object = re.sub(r"^(?:a|an|the)\s+", "", named_object, flags=re.IGNORECASE)
        if named_object:
            return f"What do you want the {named_object} to do in this system?"
    missing = frame.get("missingInfo") if isinstance(frame.get("missingInfo"), list) else []
    if missing:
        return f"What should I use for {str(missing[0]).rstrip('.')}?"
    return "What exactly should I work on, and what result do you want?"


def select_intent_frame(
    messages: Sequence[Dict[str, Any]],
    legacy_frame: Optional[Dict[str, Any]],
    generic_frame: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Prefer bounded legacy capabilities, but reject legacy semantic conflicts."""

    legacy = dict(legacy_frame or {})
    generic = dict(generic_frame or {})
    if not legacy:
        return generic
    if not generic:
        legacy.setdefault("source", "bounded-legacy-intent")
        return legacy

    query = _latest_user_text(messages).lower()
    legacy_domain = _text(legacy.get("domain"))
    if legacy_domain == "engineering_power_conversion":
        generic_is_comparison = _text(generic.get("domain")) in {"knowledge_comparison", "engineering_tradeoff"}
        explicit_power_operation = bool(
            re.search(
                r"\b(?:convert|conversion|equivalent horsepower|equivilant horsepower|how many (?:hp|horsepower)|"
                r"what (?:is the )?(?:horsepower|hp|kw|kilowatt)|what size .{0,24}(?:motor|controller)|"
                r"size (?:the |a )?(?:motor|controller)|motor sizing|controller sizing|"
                r"(?:shaft )?torque (?:at|required|needed)|battery current|required current|phase current)\b",
                query,
            )
        )
        if generic_is_comparison and not explicit_power_operation:
            generic["rejectedLegacyDomain"] = legacy_domain
            generic["rejectedLegacyReason"] = (
                "Power units describe the operating point, but the main predicate asks for a comparison or design tradeoff."
            )
            return generic
        asks_about_power = bool(
            re.search(
                r"\b(?:horsepower|hp|kilowatts?|kw|watts?|rpm|torque|battery current|phase current|"
                r"continuous power|peak power|rated power|power rating|motor sizing|controller sizing|"
                r"size (?:the |a )?(?:motor|controller)|convert .{0,24}(?:power|horsepower|kw))\b",
                query,
            )
        )
        if not asks_about_power:
            generic["rejectedLegacyDomain"] = legacy_domain
            generic["rejectedLegacyReason"] = "The full request does not ask for a power conversion or motor/controller sizing operation."
            return generic

    legacy.setdefault("source", "bounded-legacy-intent")
    return legacy


def build_generic_intent_frame(messages: Sequence[Dict[str, Any]], cwd: str = "") -> Dict[str, Any]:
    """Build a reusable intent frame when no high-confidence capability frame exists."""

    query = _latest_user_text(messages)
    if not query:
        return {}
    lower = f" {query.lower()} "
    previous = _previous_user_text(messages)
    previous_lower = f" {previous.lower()} "
    normalized_query = re.sub(r"\s+", " ", query.lower()).strip(" \t\r\n?.!")
    capability_introspection = bool(
        (
            re.search(r"\b(?:your|you(?:r)?|codex(?: cli ui)?)\b", normalized_query)
            and re.search(r"\bcapabilit(?:y|ies)\b", normalized_query)
        )
        or re.fullmatch(
            r"(?:can|could) you (?:give|show|tell) me (?:a )?(?:high level |high-level )?(?:overview|list|summary) of (?:what you can do|your capabilities)(?: to help me)?",
            normalized_query,
        )
        or re.fullmatch(r"what (?:exactly )?can you do(?: for me| to help me)?", normalized_query)
        or re.fullmatch(r"how can you help me", normalized_query)
        or re.fullmatch(
            r"what (?:local )?(?:tools|access|permissions|integrations) do you (?:currently )?have",
            normalized_query,
        )
        or bool(
            re.search(r"\b(?:capabilit(?:y|ies)|what you can do|tools and access)\b", previous_lower)
            and re.fullmatch(r"(?:which|what) of (?:those|these) can you (?:actually )?use(?: right now| in this (?:repo|project|session))?", normalized_query)
        )
    )
    urls = _urls(query)
    files = _file_refs(query)
    has_action = _has(lower, _ACTION_TERMS)
    local_surface = bool(files) or _has(lower, _LOCAL_SURFACE_TERMS)
    local_product_surface = _has(lower, _LOCAL_PRODUCT_SURFACE_TERMS)
    scientific = _has(lower, _SCIENTIFIC_TERMS)
    market_followup = bool(
        previous
        and _has(previous_lower, _MARKET_TERMS)
        and (_has(previous_lower, _VOLATILE_TERMS) or "$" in previous)
        and re.search(r"\b(?:what about|how about|anything from|and (?:what|how) about)\b", lower)
    )
    functional_comparison = bool(
        "better solution" in lower
        and " than " in lower
        and re.search(r"\b(?:to use (?:as|for|to)|for)\b", lower)
    )
    market = (
        _has(lower, _MARKET_TERMS) and (_has(lower, _VOLATILE_TERMS) or "$" in query)
    ) or market_followup
    market = market and not functional_comparison
    explicit_comparison = _has(
        lower,
        tuple(term for term in _COMPARISON_TERMS if term not in {"better", "stronger"}),
    )
    comparative_adjective_question = bool(
        re.search(r"\b(?:which|what)\b[^?\n]{0,120}\b(?:better|stronger)\b", lower)
        or re.search(r"\b(?:better|stronger)\b[^?\n]{0,120}\b(?:than|versus|vs\.?|or)\b", lower)
    )
    parsed_comparison_refs = _comparison_object_refs(query)
    comparison = explicit_comparison or functional_comparison or comparative_adjective_question or bool(parsed_comparison_refs)
    engineering_tradeoff = bool(
        comparison
        and (
            re.search(
                r"\b\d+(?:\.\d+)?\s*(?:vdc|vac|v|kw|w|a|amps?|khz|hz|rpm|nm|n\s*m|psi|mpa|gpa|°c|c)\b",
                lower,
            )
            or _has(
                lower,
                (
                    "efficiency",
                    "thermal design",
                    "fault tolerance",
                    "gate drive",
                    "gate-drive",
                    " emi",
                    "switching loss",
                    "conduction loss",
                    "duty cycle",
                    "backlash",
                    "stiffness",
                    "load holding",
                    "power density",
                ),
            )
        )
    )
    technical_source_lookup = _has(lower, _TECHNICAL_SOURCE_TERMS)
    compatibility = bool(
        _has(lower, _COMPATIBILITY_TERMS)
        or re.search(r"\b(?:will|would|can|could)\s+.{1,100}?\s+work\s+with\b", lower)
        or re.search(r"\bwork\s+with\s+(?:a|an|the|this|that|my)\b", lower)
    )
    explicit_research = _has(lower, _EXPLICIT_RESEARCH_TERMS)
    explicit_execution = _has(lower, _EXECUTION_TERMS)
    behavior_guidance = bool(
        re.search(r"\bwhen i ask you\b", lower)
        or _has(
            lower,
            (
                "don't default to",
                "dont default to",
                "how you answer",
                "how you respond",
                "your responses",
                "go a bit deeper",
            ),
        )
    )
    structural_execution = explicit_execution and (
        _has(lower, ("finite element", "fea", "structural analysis"))
        or ("design and analyze" in lower and _has(lower, (" load", "safety factor", "stress")))
    )
    aero_execution = explicit_execution and _has(
        lower,
        (" cfd", "computational fluid", "airflow analysis", "flow simulation"),
    )
    diagram_execution = explicit_execution and _has(
        lower,
        ("block diagram", "wiring diagram", "wiring schematic", "schematic diagram"),
    )
    cad_execution = explicit_execution and _has(
        lower,
        (
            " cad",
            "fusion 360",
            "openscad",
            "step file",
            "step model",
            "stl model",
            "stl file",
            "cad files",
            "3d printable file",
            "printable 3d file",
            "printable file",
            "3d printable model",
            "printable model",
            "3d model file",
        ),
    )
    question = query.rstrip().endswith("?") or lower.lstrip().startswith(_QUESTION_PREFIXES)
    clarification = _vague_action_without_context(query, messages) or _missing_referent_without_context(query, messages)

    domain = "conversation"
    target_surface = "conversation.answer"
    action_type = "answer_or_continue_conversation"
    requested_change = "Understand the full request and respond to the user's actual objective."
    expected_output = "A direct, natural answer sized to the request."
    evidence_need = "none"
    capability = "conversation_reasoning"
    missing: List[str] = []
    forbidden: List[str] = ["unrelated-legacy-answer-family"]
    tags: List[str] = ["generic-kernel"]
    confidence = 0.72

    if capability_introspection:
        domain = "agent_runtime_capabilities"
        target_surface = "codex_cli_ui.current_runtime"
        action_type = "summarize_verified_runtime_capabilities"
        requested_change = "Explain what the active local agent can do in this session using current access, tool, and integration evidence."
        expected_output = "A concise, human-readable capability overview grounded in the active runtime rather than generic model defaults."
        evidence_need = "current-runtime-inventory"
        capability = "runtime_capability_introspection"
        forbidden.extend(
            [
                "generic-chatbot-capability-disclaimer",
                "deny-current-filesystem-or-shell-access-without-runtime-evidence",
                "claim-unverified-plugin-or-machine-integration",
            ]
        )
        tags.extend(["runtime-self-knowledge", "verified-capability-inventory"])
        confidence = 0.98
    elif clarification:
        domain = "clarification"
        target_surface = "conversation.missing_referent"
        action_type = "ask_one_focused_clarification"
        requested_change = "Recover the missing target or desired end state before acting."
        expected_output = "One concise clarification question."
        evidence_need = "missing-user-context"
        capability = "clarification"
        missing = ["the target object or prior action the user wants changed"]
        forbidden.extend(["guess-the-target", "unrelated-technical-answer"])
        tags.append("missing-referent")
        confidence = 0.96
    elif structural_execution:
        domain = "structural_fea_work"
        target_surface = "local.structural_analysis_artifacts"
        action_type = "run_structural_preflight_and_analysis"
        requested_change = "Use the supplied geometry, loads, constraints, and material assumptions to stage and verify a structural-analysis result."
        expected_output = "A real structural preflight/analysis artifact or one precise missing-input blocker."
        evidence_need = "geometry-loads-constraints-material"
        capability = "structural_fea"
        forbidden.extend(["generic-material-answer", "fake-fea-result", "analysis-without-geometry"])
        tags.extend(["artifact-work", "structural-fea", "capability-first"])
        confidence = 0.93
    elif aero_execution:
        domain = "aero_cfd_work"
        target_surface = "local.flow_analysis_artifacts"
        action_type = "run_flow_preflight_and_analysis"
        requested_change = "Use the supplied geometry and boundary conditions to stage and verify a CFD/airflow analysis."
        expected_output = "A real CFD preflight/analysis artifact or one precise missing-input blocker."
        evidence_need = "geometry-and-boundary-conditions"
        capability = "aero_cfd"
        forbidden.extend(["generic-airflow-advice", "fake-cfd-result", "analysis-without-geometry"])
        tags.extend(["artifact-work", "aero-cfd", "capability-first"])
        confidence = 0.92
    elif diagram_execution:
        domain = "engineering_diagram_work"
        target_surface = "local.engineering_diagram_artifacts"
        action_type = "create_engineering_diagram"
        requested_change = "Create the requested editable engineering diagram from the stated components and interfaces."
        expected_output = "An editable diagram artifact with the unverified interfaces clearly marked."
        evidence_need = "component-and-interface-details"
        capability = "engineering_diagram"
        forbidden.extend(["text-only-diagram-description", "invented-pinout"])
        tags.extend(["artifact-work", "engineering-diagram", "capability-first"])
        confidence = 0.9
    elif cad_execution:
        domain = "cad_artifact_work"
        target_surface = "local.cad_artifacts"
        action_type = "create_cad_artifact"
        requested_change = "Create the requested CAD artifact from the available geometry and constraints, or ask for the one missing dimension set needed to proceed."
        expected_output = "A usable local CAD artifact with verification, or one focused geometry blocker."
        evidence_need = "geometry-and-design-constraints"
        capability = "cad_artifact"
        forbidden.extend(["claim-created-without-file", "unrelated-analysis-tool"])
        tags.extend(["artifact-work", "cad", "capability-first"])
        confidence = 0.9
    elif scientific:
        domain = "scientific_evidence_review"
        target_surface = "knowledge.scientific_evidence"
        action_type = "review_scientific_evidence"
        requested_change = "Answer the stated claim using measured, datasheet, standard, or peer-reviewed evidence."
        expected_output = "An evidence-bounded conclusion that separates measurements, mechanisms, and uncertainty."
        evidence_need = "scientific-or-primary-evidence"
        capability = "scientific_evidence_review"
        forbidden.extend(["generic-process-advice", "unsupported-certainty"])
        tags.extend(["scientific-evidence", "model-first"])
        confidence = 0.91
    elif market and not (local_product_surface and has_action):
        domain = "current_market_research"
        target_surface = "knowledge.current_market"
        action_type = "research_current_options"
        requested_change = "Find and compare current exact products, availability, pricing, or release information."
        expected_output = "A source-backed shortlist of exact models or a clear statement of what could not be verified."
        evidence_need = "current-web-evidence"
        capability = "current_web_research"
        forbidden.extend(["stale-model-memory", "source-title-as-product", "generic-marketplace-list"])
        tags.extend(["current-market", "model-first"])
        confidence = 0.9
    elif files:
        domain = "local_file_work" if has_action else "local_file_evidence"
        target_surface = "local.files"
        action_type = "inspect_or_modify_local_files" if has_action else "inspect_local_files"
        requested_change = "Use the named or attached files as primary evidence before answering."
        expected_output = "A file-grounded result, artifact, or precise blocker."
        evidence_need = "local-file-evidence"
        capability = "local_file_work" if has_action else "local_file_retrieval"
        forbidden.extend(["web-before-local-file", "pretend-file-read"])
        tags.extend(["local-file", "capability-first"])
        confidence = 0.9
    elif behavior_guidance:
        domain = "conversation"
        target_surface = "conversation.behavior_guidance"
        action_type = "apply_conversation_guidance"
        requested_change = "Apply the user's standing interaction guidance to future work without pretending it is a code-edit request."
        expected_output = "A natural acknowledgment that states the behavioral change precisely."
        evidence_need = "conversation-context"
        capability = "conversation_reasoning"
        forbidden.extend(["fake-code-change", "unrelated-local-product-action"])
        tags.extend(["behavior-guidance", "model-first"])
        confidence = 0.9
    elif local_product_surface and has_action:
        domain = "local_product_action"
        target_surface = "local.product_or_codebase"
        action_type = "inspect_plan_execute_verify"
        requested_change = "Inspect the actual local implementation or state, make the requested bounded change, and verify it."
        expected_output = "A completed local change with proof, or one precise blocker/clarification."
        evidence_need = "local-code-or-state-evidence"
        capability = "local_code_agent"
        forbidden.extend(["generic-advice-instead-of-action", "claim-without-verification"])
        tags.extend(["local-action", "model-first"])
        confidence = 0.88
    elif urls:
        domain = "source_resolution"
        target_surface = "knowledge.supplied_source"
        action_type = "inspect_source_then_answer"
        requested_change = "Resolve the supplied source and answer the visible question rather than reacting to URL keywords."
        expected_output = "A source-grounded answer to the user's visible request."
        evidence_need = "supplied-source-evidence"
        capability = "source_backed_reasoning"
        forbidden.extend(["url-keyword-routing", "ignore-visible-question"])
        tags.extend(["supplied-url", "model-first"])
        confidence = 0.86
    elif explicit_research:
        domain = "research_synthesis"
        target_surface = "knowledge.research_synthesis"
        action_type = "research_then_answer"
        requested_change = "Research the complete subject requested, synthesize the relevant evidence, and answer the actual design or decision question."
        expected_output = "A source-backed research synthesis with concrete conclusions and clear evidence limits."
        evidence_need = "current-web-evidence"
        capability = "current_web_research"
        forbidden.extend(["skip-requested-research", "unrelated-artifact-generation", "source-list-without-synthesis"])
        tags.extend(["explicit-research", "model-first"])
        confidence = 0.9
    elif technical_source_lookup:
        domain = "technical_source_lookup"
        target_surface = "knowledge.primary_technical_source"
        action_type = "find_primary_source_then_answer"
        requested_change = "Find the exact technical fact requested and answer from a manufacturer, manual, drawing, or other primary source."
        expected_output = "A source-grounded technical answer or a precise statement of what could not be verified."
        evidence_need = "manufacturer-or-primary-source"
        capability = "source_backed_reasoning"
        forbidden.extend(["unrelated-local-file-scan", "runtime-recovery-boilerplate", "source-title-only-answer"])
        tags.extend(["technical-source", "model-first"])
        confidence = 0.87
    elif compatibility:
        domain = "technical_compatibility"
        target_surface = "knowledge.compatibility_decision"
        action_type = "identify_components_then_assess_compatibility"
        requested_change = "Identify the named components and assess compatibility from their actual roles, interfaces, and constraints."
        expected_output = "A direct compatibility judgment with the assumptions or one missing fact that would reverse it."
        evidence_need = "task-dependent-primary-source"
        capability = "source_backed_reasoning"
        forbidden.extend(["keyword-only-answer", "generic-marketplace-list", "unrelated-product-family"])
        tags.extend(["compatibility", "model-first"])
        confidence = 0.84
    elif comparison:
        domain = "engineering_tradeoff" if engineering_tradeoff else "knowledge_comparison"
        target_surface = "knowledge.engineering_tradeoff" if engineering_tradeoff else "knowledge.comparison"
        action_type = "compare_decision_factors"
        requested_change = "Compare the named options against the property or outcome the user actually asked about."
        expected_output = (
            "A source-bounded engineering recommendation with decision-driving assumptions and reversal conditions."
            if engineering_tradeoff
            else "A qualified recommendation or comparison with the decision-driving assumptions."
        )
        evidence_need = (
            "technical-primary-evidence"
            if engineering_tradeoff
            else "current-or-technical-evidence-if-claims-are-volatile"
        )
        capability = "conversation_reasoning"
        forbidden.extend(["keyword-only-answer", "unrelated-domain-template", "unsupported-technical-precision"])
        tags.extend(["comparison", "engineering-tradeoff" if engineering_tradeoff else "general-comparison", "model-first"])
        confidence = 0.88 if engineering_tradeoff else 0.83
    elif has_action:
        domain = "general_action"
        target_surface = "user.requested_work"
        action_type = "inspect_plan_execute_verify"
        requested_change = "Carry out the requested work after confirming the target and safety boundary from context."
        expected_output = "A real result with verification, or one focused blocker."
        evidence_need = "task-dependent"
        capability = "local_agent"
        forbidden.extend(["advice-only-when-action-was-requested", "fake-completion"])
        tags.extend(["action", "model-first"])
        confidence = 0.78
    elif question:
        domain = "knowledge_question"
        target_surface = "knowledge.answer"
        action_type = "reason_and_answer"
        requested_change = "Answer the whole question, preserving its qualifiers and context."
        expected_output = "A direct subject-matter answer with calibrated evidence and uncertainty."
        evidence_need = "task-dependent"
        capability = "conversation_reasoning"
        forbidden.extend(["keyword-only-answer", "unrelated-domain-template"])
        tags.extend(["question", "model-first"])
        confidence = 0.76

    refs = _object_refs(urls, files)
    if comparison and not refs:
        refs = parsed_comparison_refs
    comparison_criteria = _comparison_criteria(query, refs) if comparison else []
    if not refs:
        refs = [{"type": "user-described-target", "name": "target named in the latest request"}]
    return {
        "version": KERNEL_VERSION,
        "source": "generic-intelligence-kernel",
        "userGoal": requested_change,
        "domain": domain,
        "targetSurface": target_surface,
        "actionType": action_type,
        "objectRefs": refs,
        "comparisonCriteria": comparison_criteria,
        "requestedChange": requested_change,
        "expectedOutput": expected_output,
        "evidenceNeed": evidence_need,
        "knownConstraints": [
            "Interpret the full request before routing from individual keywords.",
            "Ask one focused question only when missing information changes the correct action or answer.",
            "Prefer a real tool result or evidence boundary over a fast generic response.",
        ],
        "missingInfo": missing,
        "routeCandidates": [capability],
        "forbiddenRoutes": forbidden,
        "frameTags": tags,
        "confidence": confidence,
        "cwd": cwd,
    }


def decide_execution(
    frame: Dict[str, Any],
    route_engine: str = "local",
    web_search: str = "live",
) -> Dict[str, Any]:
    """Choose deterministic capability-first versus model-first execution."""

    frame = frame if isinstance(frame, dict) else {}
    domain = _text(frame.get("domain"))
    action = _text(frame.get("actionType"))
    candidates = frame.get("routeCandidates") if isinstance(frame.get("routeCandidates"), list) else []
    capability = _text(candidates[0] if candidates else "conversation_reasoning")
    evidence_need = _text(frame.get("evidenceNeed"))

    deterministic_domains = {
        "agent_runtime_capabilities",
        "bounded_specialist_capability",
        "local_installation_status",
        "printer_job_eta",
        "clarification",
        "high_stakes_policy",
        "privacy_boundary",
        "safety_boundary",
    }
    capability_domains = {
        "aero_cfd_work",
        "cad_artifact_work",
        "engineering_diagram_work",
        "klipper_config_migration",
        "local_file_work",
        "local_file_evidence",
        "structural_fea_work",
    }
    research_domains = {
        "current_market_ranking",
        "current_market_research",
        "source_resolution",
        "technical_source_lookup",
        "technical_compatibility",
        "scientific_materials_evidence",
        "scientific_evidence_review",
        "material_property_evidence",
        "research_synthesis",
    }

    if domain in deterministic_domains or action == "ask_one_focused_clarification":
        return {
            "version": KERNEL_VERSION,
            "mode": "deterministic-capability",
            "selectedCapability": capability,
            "allowLegacyDirectAnswer": True,
            "useCompactPrompt": False,
            "engineOverride": "",
            "reason": "A bounded local-status, safety, or clarification capability can answer from verified state.",
        }
    if domain in capability_domains:
        return {
            "version": KERNEL_VERSION,
            "mode": "capability-first",
            "selectedCapability": capability,
            "allowLegacyDirectAnswer": True,
            "useCompactPrompt": False,
            "engineOverride": "",
            "reason": "The turn names a bounded local-file or artifact workflow with its own verification contract.",
        }
    if domain in research_domains or evidence_need in {
        "current-web-evidence",
        "scientific-or-primary-evidence",
        "technical-primary-evidence",
    }:
        return {
            "version": KERNEL_VERSION,
            "mode": "model-first",
            "selectedCapability": capability or "current_web_research",
            "allowLegacyDirectAnswer": False,
            "useCompactPrompt": True,
            "engineOverride": "local-research" if web_search == "live" else route_engine,
            "reason": "The answer needs synthesis from current or scientific evidence, not a stored response template.",
        }
    return {
        "version": KERNEL_VERSION,
        "mode": "model-first",
        "selectedCapability": capability or "conversation_reasoning",
        "allowLegacyDirectAnswer": False,
        "useCompactPrompt": True,
        "engineOverride": "local" if route_engine == "local-research" else "",
        "reason": (
            "The reasoning worker should interpret the complete request before any legacy answer family is considered; "
            "stable reasoning should not be promoted to web research only because an old project keyword matched."
        ),
    }


def build_compact_worker_prompt(
    messages: Sequence[Dict[str, Any]],
    frame: Dict[str, Any],
    decision: Dict[str, Any],
    route: Dict[str, Any],
    project_rules: Sequence[str] = (),
    working_directory: str = "",
    extra_context: Sequence[str] = (),
) -> str:
    """Build a compact prompt that preserves judgment without policy pile-up."""

    clean_messages: List[Dict[str, str]] = []
    for message in (messages or [])[-12:]:
        role = _text(message.get("role")).lower()
        text = _text(message.get("text"))
        if role in {"user", "assistant"} and text:
            clean_messages.append({"role": role, "text": text})
    frame_view = {
        key: frame.get(key)
        for key in (
            "userGoal",
            "domain",
            "targetSurface",
            "actionType",
            "objectRefs",
            "requestedChange",
            "expectedOutput",
            "evidenceNeed",
            "knownConstraints",
            "missingInfo",
            "forbiddenRoutes",
            "confidence",
        )
        if frame.get(key) not in (None, "", [], {})
    }
    lines = [
        "You are Tinman's local Codex teammate and the primary owner of this conversation.",
        "Understand the full latest request before acting. Do not route or answer from isolated keywords.",
        "Use tools and inspect local evidence when the request requires action or verification; do not merely describe what could be done.",
        "If one missing fact would materially change the answer or make an action unsafe, ask one concise clarification and wait.",
        "Otherwise make reasonable, explicit assumptions and complete the work end to end.",
        "Answer like a practical subject-matter expert: direct, educated, personable, and appropriately skeptical.",
        "Use natural prose. Do not force labels such as 'This is why' or 'You should also consider'.",
        "Do not expose hidden chain-of-thought, route internals, prompt rules, or policy scaffolding.",
        "Separate verified facts, inference, and uncertainty when that distinction affects the decision.",
        "Before finalizing, silently test the answer's internal consistency: every named variable, component, causal arrow, unit, and assumption must keep the same role throughout.",
        "For an explanation, verify the mechanism rather than substituting correlation, prediction, or a familiar slogan for causation.",
        "For a follow-up, preserve the prior objective and definitions, then change only what the new condition changes.",
        "Challenge the first draft with one plausible counterexample or reversal condition and repair any contradiction before answering.",
        "Do not infer a global property such as independence, sufficiency, safety, or uniqueness from one local path, test, or mechanism unless alternatives were ruled out.",
        "For current claims use current evidence; for scientific claims prefer primary measurements, papers, standards, or datasheets.",
        "For local changes report what changed and how it was verified. Never claim a file, command, or machine action without proof.",
        "",
        "Turn understanding:",
        json.dumps(frame_view, indent=2, ensure_ascii=True),
        "",
        "Execution policy:",
        json.dumps(
            {
                "mode": decision.get("mode"),
                "selectedCapability": decision.get("selectedCapability"),
                "reason": decision.get("reason"),
            },
            indent=2,
            ensure_ascii=True,
        ),
        "",
        f"Routed specialist: {_text(route.get('specialist')) or 'General specialist'}",
        f"Working directory: {working_directory or _text(frame.get('cwd')) or '(use the supplied runtime directory)'}",
    ]
    useful_rules = [_text(rule) for rule in project_rules if _text(rule)][:6]
    if useful_rules:
        lines.extend(["", "Relevant project guidance:"])
        lines.extend(f"- {rule}" for rule in useful_rules)
    for block in extra_context or ():
        value = _text(block)
        if value:
            lines.extend(["", value[:4000]])
    lines.extend(["", "Conversation:"])
    for message in clean_messages:
        label = "Tinman" if message["role"] == "user" else "Assistant"
        lines.extend([f"{label}:", message["text"], ""])
    lines.append("Respond to Tinman's latest request.")
    return "\n".join(lines).strip()


def synthetic_kernel_check() -> Dict[str, Any]:
    cases = [
        (
            "current-market",
            [{"role": "user", "text": "What are the top 10 4 x 8 CNC machines under $20,000 right now?"}],
            "current_market_research",
            "current_web_research",
            False,
        ),
        (
            "scientific",
            [{"role": "user", "text": "Is there scientific evidence that this treatment actually improves tensile strength?"}],
            "scientific_evidence_review",
            "scientific_evidence_review",
            False,
        ),
        (
            "local-action",
            [{"role": "user", "text": "Fix the status panel in Codex CLI UI and verify the change."}],
            "local_product_action",
            "local_code_agent",
            False,
        ),
        (
            "action-with-comparative-adjective",
            [
                {
                    "role": "user",
                    "text": (
                        "Create a slider for selected holes and bosses that moves from minimum reinforcement "
                        "for a slightly stronger part to the maximum allowed reinforcement."
                    ),
                }
            ],
            "general_action",
            "local_agent",
            False,
        ),
        (
            "comparison",
            [{"role": "user", "text": "Which is stronger for a loaded bracket, material A versus material B?"}],
            "knowledge_comparison",
            "conversation_reasoning",
            False,
        ),
        (
            "clarification",
            [{"role": "user", "text": "Can you fix it?"}],
            "clarification",
            "clarification",
            True,
        ),
        (
            "technical-source",
            [{"role": "user", "text": "Please find the dimensions of the chamber heater."}],
            "technical_source_lookup",
            "source_backed_reasoning",
            False,
        ),
        (
            "html-url-is-not-local-file",
            [
                {
                    "role": "user",
                    "text": (
                        "According to https://docs.python.org/3/library/asyncio-task.html, "
                        "what does TaskGroup do when one child task fails?"
                    ),
                }
            ],
            "source_resolution",
            "source_backed_reasoning",
            False,
        ),
        (
            "market-followup",
            [
                {"role": "user", "text": "What tool-changing printers are coming to market in the next few months?"},
                {"role": "assistant", "text": "I found several candidates."},
                {"role": "user", "text": "What about Sovol or Infimech?"},
            ],
            "current_market_research",
            "current_web_research",
            False,
        ),
        (
            "structural-artifact",
            [{"role": "user", "text": "Run FEA on the attached bracket for a 100 N load and safety factor 3."}],
            "structural_fea_work",
            "structural_fea",
            True,
        ),
        (
            "image-inspired-printable-cad",
            [
                {
                    "role": "user",
                    "text": "Create a 3d printable file of the blade similar to the attached image for a 270mm printer.",
                    "attachments": [{"name": "reference.png", "path": "/tmp/reference.png"}],
                }
            ],
            "cad_artifact_work",
            "cad_artifact",
            True,
        ),
    ]
    results = []
    for case_id, messages, expected_domain, expected_capability, expected_legacy in cases:
        frame = build_generic_intent_frame(messages)
        decision = decide_execution(frame, route_engine="local", web_search="live")
        passed = (
            frame.get("domain") == expected_domain
            and decision.get("selectedCapability") == expected_capability
            and bool(decision.get("allowLegacyDirectAnswer")) is expected_legacy
        )
        results.append(
            {
                "id": case_id,
                "passed": passed,
                "domain": frame.get("domain"),
                "capability": decision.get("selectedCapability"),
                "legacyDirect": decision.get("allowLegacyDirectAnswer"),
            }
        )
    conflict_messages = [
        {
            "role": "user",
            "text": "Compare aluminum and G10 for an electrically insulating motor-controller mounting plate in a hot enclosure.",
        }
    ]
    conflict_generic = build_generic_intent_frame(conflict_messages)
    conflict_selected = select_intent_frame(
        conflict_messages,
        {"domain": "engineering_power_conversion", "confidence": 0.94},
        conflict_generic,
    )
    results.append(
        {
            "id": "legacy-keyword-conflict-veto",
            "passed": (
                conflict_selected.get("domain") == "knowledge_comparison"
                and conflict_selected.get("rejectedLegacyDomain") == "engineering_power_conversion"
            ),
            "domain": conflict_selected.get("domain"),
            "capability": (conflict_selected.get("routeCandidates") or [""])[0],
            "legacyDirect": False,
        }
    )
    unit_context_tradeoff_messages = [
        {
            "role": "user",
            "text": (
                "For a 400 VDC, 150 kW traction inverter switching near 12 kHz, should I base the power stage "
                "on silicon IGBTs or silicon-carbide MOSFETs? Compare efficiency, thermal design, fault tolerance, "
                "gate-drive complexity, EMI, cost, and what could reverse your recommendation."
            ),
        }
    ]
    unit_context_generic = build_generic_intent_frame(unit_context_tradeoff_messages)
    unit_context_selected = select_intent_frame(
        unit_context_tradeoff_messages,
        {"domain": "engineering_power_conversion", "confidence": 0.94},
        unit_context_generic,
    )
    unit_context_refs = [item.get("name") for item in unit_context_selected.get("objectRefs") or []]
    results.append(
        {
            "id": "power-units-are-tradeoff-context",
            "passed": (
                unit_context_selected.get("domain") == "engineering_tradeoff"
                and unit_context_selected.get("rejectedLegacyDomain") == "engineering_power_conversion"
                and unit_context_refs == ["silicon IGBTs", "silicon-carbide MOSFETs"]
            ),
            "domain": unit_context_selected.get("domain"),
            "capability": (unit_context_selected.get("routeCandidates") or [""])[0],
            "legacyDirect": False,
        }
    )
    power_messages = [{"role": "user", "text": "What motor size provides 250 horsepower at 3500 RPM?"}]
    power_selected = select_intent_frame(
        power_messages,
        {"domain": "engineering_power_conversion", "confidence": 0.96},
        build_generic_intent_frame(power_messages),
    )
    results.append(
        {
            "id": "valid-power-intent-retained",
            "passed": power_selected.get("domain") == "engineering_power_conversion",
            "domain": power_selected.get("domain"),
            "capability": (power_selected.get("routeCandidates") or [""])[0],
            "legacyDirect": False,
        }
    )
    return {
        "status": "pass" if all(item["passed"] for item in results) else "fail",
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "results": results,
    }
