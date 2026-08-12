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
    r"(?<![\w.-])(?:~?/|/)?(?:[^\s/]+/)*[^\s/]+\.(?:cfg|conf|ini|json|jsonl|yaml|yml|toml|md|txt|log|csv|xlsx|pdf|docx|py|js|ts|tsx|jsx|html|css|gcode|3mf|stl|step|stp|obj|scad|f3d|f3z)(?=$|[\s,;:!?)}\]]|\.(?=\s|$))",
    flags=re.IGNORECASE,
)

_ACTION_TERMS = (
    "add",
    "analyze",
    "analyse",
    "apply",
    "build",
    "cancel",
    "change",
    "clean up",
    "cleanup",
    "compare",
    "compare these files",
    "create",
    "debug",
    "delete",
    "design",
    "download",
    "draft",
    "edit",
    "find",
    "generate",
    "regenerate",
    "rebuild",
    "fix",
    "implement",
    "inspect",
    "install",
    "flash",
    "heat",
    "home",
    "move",
    "map",
    "model",
    "modify",
    "pull",
    "prepare",
    "remove",
    "replace",
    "restart",
    "review the code",
    "run",
    "stage",
    "test",
    "update",
    "upload",
    "upload",
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
_PROGRAMMING_LANGUAGE_TERMS = (
    "python",
    "javascript",
    "typescript",
    "rust",
    "golang",
    " c++",
    "java",
    "bash",
    "shell script",
)
_PROGRAMMING_OUTPUT_TERMS = (
    "algorithm",
    "class",
    "code",
    "function",
    "implementation",
    "method",
    "program",
    "snippet",
)
_TECHNICAL_SOURCE_TERMS = (
    "datasheet",
    "dimensions",
    "dimension of",
    "engineering details",
    "instruction manual",
    "manufacturer rating",
    "manufacturer-rated",
    "manual for",
    "mounting pattern",
    "official source",
    "official url",
    "official documentation",
    "official docs",
    "pinout",
    "spec sheet",
    "specification",
    "source url",
    "technical drawing",
    "technical details",
)
_EXPLICIT_RESEARCH_TERMS = (
    "do the research",
    "do not forget the research",
    "look up",
    "research primary",
    "research before",
    "research designing",
    "research sources",
    "research this",
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
    "package health",
    "package-health",
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
    "package health",
    "package-health",
    "orca codex",
    "orcaslicer codex",
    "tinmanx",
    "tinmanx1",
    "repo",
    "repository",
    "server.py",
    "app.js",
)
_LOCAL_PRODUCT_UI_SURFACE_TERMS = (
    "model health",
    "device tab",
    "run log",
    "lower toolbar",
    "composer area",
    "composer work area",
    "chat area",
    "chat work area",
)
_DESIRED_UI_STATE_VERBS = (
    "add",
    "collapse",
    "display",
    "expand",
    "hide",
    "include",
    "move",
    "open",
    "reclaim",
    "render",
    "restore",
    "return",
    "show",
    "update",
)
_MARKET_TERMS = (
    "announced",
    "announcement",
    "availability",
    "best",
    "top ",
    "top-",
    "for sale",
    "buy",
    "recommend",
    "on the market",
    "coming to market",
    "available",
    "launch window",
    "preorder",
    "shipping window",
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
)
_ENGINEERING_CONDITION_TERMS = (
    "ambient",
    "chamber temp",
    "chamber temperature",
    "curing",
    "continuous load",
    "cyclic load",
    "duty cycle",
    "environment",
    "humidity",
    "mechanical load",
    "operating pressure",
    "operating speed",
    "operating temp",
    "operating temperature",
    "peak load",
    "pressure",
    "static load",
    "sustained load",
    "temperature",
    "setpoint",
    "temps",
    "thermal cycle",
    "vibration",
)
_ENGINEERING_OBJECT_TERMS = (
    "assembly",
    "bearing",
    "bed",
    "board",
    "bracket",
    "cable",
    "chamber",
    "component",
    "controller",
    "enclosure",
    "fixture",
    "frame",
    "heater",
    "housing",
    "joint",
    "machine",
    "material",
    "mount",
    "motor",
    "panel",
    "plate",
    "printer",
    "router",
    "sensor",
    "shaft",
    "spindle",
    "structure",
    "support",
)
_ENGINEERING_SYSTEM_TERMS = (
    "actuator",
    "compressor",
    "converter",
    "drive",
    "gearbox",
    "inverter",
    "machine",
    "motor",
    "power supply",
    "pump",
    "servo",
    "spindle",
    "transformer",
    "vfd",
    "variable frequency drive",
)
_ENGINEERING_PROCESS_TERMS = (
    "adhesive",
    "anneal",
    "annealing",
    "arc",
    "bond",
    "bonding",
    "braze",
    "brazing",
    "cast",
    "casting",
    "clamp",
    "clamping",
    "coat",
    "coating",
    "cut",
    "cutting",
    "drill",
    "drilling",
    "forge",
    "forging",
    "grind",
    "grinding",
    "heat treat",
    "heat-treated",
    "heat-treating",
    "machine",
    "machining",
    "mill",
    "milling",
    "paint",
    "press fit",
    "press-fit",
    "solder",
    "soldering",
    "spatter",
    "torch",
    "turning",
    "weld",
    "welding",
)
_MATERIAL_CLASS_TERMS = (
    "alloy",
    "aluminum",
    "carbon",
    "ceramic",
    "composite",
    "copper",
    "fiber",
    "glass",
    "graphite",
    "metal",
    "nylon",
    "plastic",
    "polymer",
    "resin",
    "steel",
)
_ENGINEERING_VALUE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:°\s*)?(?:c|f|k|rpm|hz|khz|v|vac|vdc|a|amps?|w|kw|psi|kpa|mpa|gpa|n|kn|lbf|nm|n\s*m|mm|cm)\b",
    flags=re.IGNORECASE,
)
_ENGINEERING_SUITABILITY_RE = re.compile(
    r"\b(?:would|will|can|could|is|are|does|do)\b[^?\n]{0,220}"
    r"\b(?:perform|work|handle|survive|withstand|suitable|appropriate|viable|good\s+(?:choice|fit)"
    r"|(?:remain|stay)\s+(?:dimensionally\s+)?(?:flat|stable|aligned|rigid|sealed|watertight|accurate|functional|reliable)"
    r"|maintain\s+(?:flatness|stability|alignment|rigidity|a\s+seal|accuracy|function|reliability))\b",
    flags=re.IGNORECASE,
)
_ENGINEERING_USAGE_DECISION_RE = re.compile(
    r"\b(?:can|could|would|should|is|are|do|does)\b[^?\n]{0,260}"
    r"\b(?:use|used\s+as|reuse|repurpose|substitute|replace|double\s+as|serve\s+as|work\s+as)\b",
    flags=re.IGNORECASE,
)
_ENGINEERING_PROCESS_DECISION_RE = re.compile(
    r"\b(?:can|could|would|should)\s+(?:(?:i|we)\s+)?"
    r"(?:adhere|anneal|bond|braze|cast|clamp|coat|cut|drill|forge|grind|heat[ -]?treat|"
    r"machine|mill|paint|press[ -]?fit|solder|turn|weld)\w*\b"
    r"|\b(?:can|could|would|should)\s+(?:this|that|it|the|my|our)\b[^?\n]{0,120}"
    r"\bbe\s+(?:annealed|bonded|brazed|cast|clamped|coated|cut|drilled|forged|ground|"
    r"heat[ -]?treated|machined|milled|painted|press[ -]?fit|soldered|turned|welded)\b",
    flags=re.IGNORECASE,
)
_COMPARISON_TERMS = (
    " compare ",
    "comparison",
    " versus ",
    " vs ",
    "torn between",
    "deciding between",
    "choose between",
    "better",
    "stronger",
    "difference between",
    "equivalent",
    "equivilant",
    "which one",
)
_DECISION_AXIS_TERMS = {
    "performance/throughput": (
        "performance", "throughput", "latency", "speed", "response time", "capacity",
        "frame rate", "fps", "accuracy", "resolution", "quality",
    ),
    "power/efficiency": (
        "low power", "lower power", "power use", "power draw", "power consumption", "energy use",
        "efficient", "efficiency", "battery life",
    ),
    "acoustics": ("silent", "quiet", "quieter", "noise", "noisy", "acoustic"),
    "thermal/cooling": ("thermal", "temperature", "heat", "cooling", "fanless", "fan"),
    "cost": ("cost", "budget", "price", "cheap", "cheaper", "expensive"),
    "reliability": ("reliability", "reliable", "uptime", "fault tolerance", "failure"),
    "serviceability": ("serviceability", "serviceable", "maintenance", "maintainability", "repair"),
    "compatibility/interfaces": (
        "compatibility", "compatible", "interface", "protocol", "connector", "integration",
    ),
    "size/weight": (
        "footprint", "compact", "small", "size", "weight", "mass", "lightweight",
    ),
    "safety": ("safety", "safe", "hazard", "protection", "fail safe", "fail-safe"),
    "durability/life": ("durability", "durable", "fatigue", "wear", "lifetime", "service life"),
}
_DECISION_QUANTITY_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s+(?:printer\s+)?(?:cameras?|streams?)|"
    r"\d+(?:\.\d+)?\s*(?:deg\s*)?(?:"
    r"p|fps|hz|khz|mhz|ghz|rpm|v|vac|vdc|a|amps?|w|kw|mw|wh|kwh|"
    r"psi|kpa|mpa|gpa|n|kn|lbf|nm|kg|mg|g|ml|l|mm|cm|m|in|inch|inches|ft|feet|"
    r"c|f|k|s|percent|%|seconds?|minutes?|hours?|days?|weeks?"
    r"))\b",
    flags=re.IGNORECASE,
)


def is_load_derived_drive_sizing(text: str) -> bool:
    """Identify drive sizing that must be derived from the load operating point.

    This is intentionally about semantic shape rather than a named vehicle or
    machine.  A motor's published kW rating can be converted directly, while a
    cart, conveyor, hoist, or winch load must first be reduced to force, torque,
    speed, power, and duty before a motor/controller architecture is selected.
    """

    query = _text(text).lower()
    if len(_DECISION_QUANTITY_RE.findall(query)) < 2:
        return False
    drive_system = bool(
        re.search(
            r"\b(?:motor|bldc|brushless|servo|drive|drivetrain|gearbox|reduction|"
            r"controller|esc|inverter)\b",
            query,
        )
    )
    requested_outputs = bool(
        re.search(
            r"\b(?:size|sizing|select|choose|target|need|required|requirement|"
            r"what|which|how much|calculate|compute|derive)\b[^?.\n]{0,220}"
            r"\b(?:motor|drive|drivetrain|gearbox|reduction|power|torque|current|"
            r"controller|inverter|ratio|architecture)\b",
            query,
        )
        or re.search(
            r"\b(?:motor|wheel|shaft|drum|controller|battery|phase)\s+"
            r"(?:power|torque|current|speed|rating)\b",
            query,
        )
    )
    operating_point_categories = (
        bool(
            re.search(
                r"\b(?:mass|weight|payload|load|force|tractive effort|cart|vehicle|agv|robot)\b"
                r"|\b\d+(?:\.\d+)?\s*(?:kg|lb|lbs|pounds?)\b",
                query,
            )
        ),
        bool(re.search(r"\b(?:speed|velocity|rpm|acceleration|climb|lift|travel rate)\b", query)),
        bool(re.search(r"\b(?:wheel|tire|tyre|drum|pulley|sprocket|radius|diameter)\b", query)),
        bool(re.search(r"\b(?:grade|incline|slope|rolling resistance|drag|friction)\b", query)),
        bool(re.search(r"\b(?:efficiency|losses|duty cycle|continuous|peak|duration)\b", query)),
    )
    return bool(
        drive_system
        and requested_outputs
        and operating_point_categories[0]
        and sum(operating_point_categories) >= 3
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

_CONTEXT_STOPWORDS = {
    "a", "about", "an", "and", "answer", "are", "as", "at", "be", "best",
    "can", "check", "could", "deal", "do", "does", "for", "from", "give",
    "help", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "perform", "please", "question", "search", "should", "tell", "the", "to",
    "use", "want", "what", "when", "where", "which", "will", "with", "would",
    "you",
}
_CONTEXT_CONTINUATION_RE = re.compile(
    r"(?i)^\s*(?:and\s+)?(?:what|how)\s+about\b|"
    r"^\s*(?:also\s+)?what\s+if\b|"
    r"^\s*now\s+(?:assume|suppose|use|change|set)\b|"
    r"^\s*(?:continue|keep going|go ahead|do it|let'?s do it|lets do it|what(?:'s| is) next)\b"
)
_CONTEXT_REFERENT_RE = re.compile(
    r"(?i)\b(?:it|that|this|those|these|them|same|former|latter|previous|prior|above|again|still)\b"
)
_CONTEXT_COMPARATIVE_REFERENT_RE = re.compile(
    r"(?i)\b(?:the\s+)?(?:smaller|larger|faster|slower|cheaper|costlier|lighter|"
    r"heavier|simpler|more\s+powerful|less\s+powerful|higher[- ]power|lower[- ]power)\s+"
    r"(?:one|option|choice|unit|model|machine|board|system)\b"
)
_CONTEXT_SELF_CONTAINED_ACTIVE_SURFACE_RE = re.compile(
    r"(?i)\b(?:this|the\s+current|current)\s+"
    r"(?:local\s+)?(?:app|application|workspace|repository|repo|conversation|chat|session)\b"
)


def _artifact_followup_referent(text: str) -> bool:
    """Recognize selection or revision language that depends on prior outputs."""

    lower = _text(text).lower().strip()
    if not lower:
        return False
    revision_action = bool(
        re.search(
            r"\b(?:apply|change|make|rename|revise|set|sync|update)\b",
            lower,
        )
    )
    artifact_surface = bool(
        re.search(
            r"\b(?:artifact|copy|editable\s+(?:file|source)|file|output|preview|"
            r"source|svg)\b",
            lower,
        )
    )
    elliptical_state = bool(
        re.search(
            r"\b(?:also|match(?:es|ing)?|same|too)\b|\bas\s+well\b",
            lower,
        )
    )
    return bool(
        re.search(
            r"\b(?:which|what)\s+(?:file|artifact|output|version|copy|one)\s+"
            r"(?:(?:should|do|can|would)\s+)?(?:(?:i|we|you)\s+)?"
            r"(?:open|use|edit|select|pick)\b",
            lower,
        )
        or re.search(
            r"\b(?:use|open|edit|select|pick|revise|update|change|regenerate)\s+"
            r"(?:the\s+)?(?:editable|source|preview|first|second|third|revised)\s+"
            r"(?:one|file|artifact|output|copy|version)\b",
            lower,
        )
        or re.search(
            r"\b(?:change|set|update|revise|rename|make|sync)\b[^.!?;]{0,80}"
            r"\b(?:editable|source|preview)\s+(?:file|artifact|output|copy)\b",
            lower,
        )
        or (revision_action and artifact_surface and elliptical_state)
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _message_text(message: Dict[str, Any]) -> str:
    """Normalize persisted/test and browser/API message payloads."""

    value = message.get("text")
    if value in (None, ""):
        value = message.get("content")
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                parts.append(_text(item.get("text") or item.get("content")))
            elif isinstance(item, str):
                parts.append(item.strip())
        return "\n".join(part for part in parts if part).strip()
    return _text(value)


def _latest_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if _text(message.get("role")).lower() == "user":
            return _message_text(message)
    return ""


def _prior_substantive_context(messages: Sequence[Dict[str, Any]]) -> bool:
    user_turns = 0
    for message in messages or []:
        if _text(message.get("role")).lower() == "user" and _message_text(message):
            user_turns += 1
    return user_turns > 1


def _previous_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    seen_latest = False
    for message in reversed(messages or []):
        if _text(message.get("role")).lower() != "user":
            continue
        text = _message_text(message)
        if not text:
            continue
        if not seen_latest:
            seen_latest = True
            continue
        return text
    return ""


def _topic_tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+(?:[-+.][a-z0-9]+)*", _text(value).lower()))
    return {
        token
        for token in tokens
        if len(token) >= 3 and token not in _CONTEXT_STOPWORDS
    }


def _dependency_topic_tokens(value: str) -> set[str]:
    """Keep bounded subject signals used only by explicit dependency phrases."""

    text = _text(value)
    tokens = set(_topic_tokens(text))
    for compound in re.findall(r"[a-z0-9]+(?:[-+.][a-z0-9]+)+", text.lower()):
        tokens.update(
            part
            for part in re.split(r"[-+.]", compound)
            if len(part) >= 3 and part not in _CONTEXT_STOPWORDS
        )
    # Uppercase technical abbreviations can also be ordinary stopwords when
    # lowercased (for example a bus name versus the modal verb "can").  Admit
    # them only inside the dependency detector, where both turns must agree.
    tokens.update(
        token.lower()
        for token in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text)
        if len(token) >= 2
    )
    return tokens


def _dependent_followup_referent(latest: str, previous: str) -> bool:
    """Recognize a dependent request without promoting a newly named subject."""

    lower = _text(latest).lower().strip()
    if not lower or not _text(previous):
        return False
    shared_subject = bool(
        _dependency_topic_tokens(latest) & _dependency_topic_tokens(previous)
    )
    risk_request = bool(
        re.search(
            r"\b(?:failure\s+modes?|failure\s+points?|risks?|hazards?|"
            r"weak\s+points?|what\s+(?:can|could|might)\s+go\s+wrong)\b",
            lower,
        )
    )
    explicit_risk_subject = bool(
        re.search(
            r"\b(?:failure\s+modes?|failure\s+points?|risks?|hazards?)\s+"
            r"(?:of|for|with|in)\s+(?:a|an|the|this|that)?\s*[a-z0-9]",
            lower,
        )
    )
    dependent_risk = bool(
        risk_request and (shared_subject or not explicit_risk_subject)
    )
    dependent_final_artifact = bool(
        shared_subject
        and re.search(
            r"\b(?:the|this|that)\s+(?:final|derived|revised|updated)\s+"
            r"(?:[a-z0-9+.-]+\s+){0,3}"
            r"(?:artifact|map|config(?:uration)?|file|diagram|document|plan|"
            r"model|source|output|preview|report|schema)\b",
            lower,
        )
    )
    selection_request = bool(
        re.search(
            r"^\s*(?:which|what)\s+(?:option|one|choice|approach|alternative)\b|"
            r"^\s*(?:which|what)\s+(?:would|should)\s+(?:i|we|you)\s+"
            r"(?:choose|pick|select|recommend)\b",
            lower,
        )
    )
    introduces_own_options = bool(
        re.search(r"\b(?:versus|vs\.?)\b|\b[^?.,;:]{1,60}\s+or\s+[^?.,;:]{1,60}", lower)
    )
    dependent_selection = bool(selection_request and not introduces_own_options)
    return dependent_risk or dependent_final_artifact or dependent_selection


def _latest_assistant_text_before_user(messages: Sequence[Dict[str, Any]]) -> str:
    """Return only the assistant turn immediately preceding the latest user."""

    latest_user_seen = False
    for message in reversed(messages or []):
        role = _text(message.get("role")).lower()
        text = _message_text(message)
        if role == "user" and text and not latest_user_seen:
            latest_user_seen = True
            continue
        if not latest_user_seen or not text:
            continue
        return text if role == "assistant" else ""
    return ""


def _explicit_independent_subject(
    latest: str,
    previous: str,
    assistant: str = "",
) -> bool:
    """Reject explicit topic switches without treating short answers as subjects."""

    lower = re.sub(r"\s+", " ", _text(latest).lower()).strip()
    if not lower:
        return False
    if re.search(
        r"^(?:actually|instead|separately|unrelated|new topic|different topic)\b|"
        r"\b(?:switch|change|move)\s+(?:the\s+)?(?:topic|subject|task|request)\b|"
        r"\b(?:new|different|unrelated|separate)\s+(?:topic|subject|task|request)\b",
        lower,
    ):
        return True
    context_tokens = _dependency_topic_tokens(previous) | _dependency_topic_tokens(
        assistant
    )
    shared_context = bool(_dependency_topic_tokens(latest) & context_tokens)
    if shared_context:
        return False
    independent_request = bool(
        re.search(
            r"^(?:please\s+)?(?:analy[sz]e|explain|compare|design|create|build|"
            r"draft|write|update|fix|research|calculate|implement)\b",
            lower,
        )
        or re.search(
            r"\b(?:failure\s+modes?|risks?|signals?|metrics?|next\s+steps?)\s+"
            r"(?:of|for|about|with|in|on)\s+(?:a|an|the|my|our|new)?\s*"
            r"[a-z0-9][a-z0-9+.-]*(?:\s+[a-z0-9][a-z0-9+.-]*)?",
            lower,
        )
    )
    return independent_request


def _focused_clarification_resolution(
    messages: Sequence[Dict[str, Any]],
    latest: str,
    previous: str,
) -> bool:
    """Recognize a short answer to the immediately preceding focused request."""

    substantive = [
        message
        for message in messages or []
        if _message_text(message)
        and _text(message.get("role")).lower() in {"user", "assistant"}
    ]
    if len(substantive) < 3:
        return False
    original, clarification, answer = substantive[-3:]
    if [
        _text(message.get("role")).lower()
        for message in (original, clarification, answer)
    ] != ["user", "assistant", "user"]:
        return False
    clarification_text = _message_text(clarification).strip()
    answer_text = _message_text(answer).strip()
    if (
        answer_text != _text(latest).strip()
        or not clarification_text
        or not answer_text
        or len(answer_text.split()) > 40
    ):
        return False
    focused_request = bool(
        clarification_text.endswith("?")
        and clarification_text.count("?") == 1
        and len(clarification_text) <= 900
    ) or bool(
        re.match(
            r"^(?:please\s+)?(?:provide|supply|choose|select|name|confirm|tell me|"
            r"give me|use)\b",
            clarification_text,
            flags=re.IGNORECASE,
        )
    )
    if not focused_request or _explicit_independent_subject(
        answer_text,
        previous,
        clarification_text,
    ):
        return False
    if answer_text.endswith("?"):
        context_tokens = _dependency_topic_tokens(previous) | _dependency_topic_tokens(
            clarification_text
        )
        shared_context = bool(
            _dependency_topic_tokens(answer_text) & context_tokens
        )
        dependent_question = bool(
            re.search(
                r"\b(?:what|which|how|where)\b[^?]{0,80}"
                r"\b(?:first|next|proceed|start|signal|metric|risk|result|"
                r"failure|source|option|choice)\b",
                answer_text,
                flags=re.IGNORECASE,
            )
        )
        if not (shared_context or dependent_question):
            return False
    return True


def _semantic_dependent_continuation(
    latest: str,
    previous: str,
    assistant: str = "",
) -> bool:
    """Recognize generic continuations whose object remains inherited."""

    lower = re.sub(r"\s+", " ", _text(latest).lower()).strip()
    if (
        not lower
        or not _text(previous)
        or _explicit_independent_subject(latest, previous, assistant)
    ):
        return False
    shared_context = bool(
        _dependency_topic_tokens(latest)
        & (
            _dependency_topic_tokens(previous)
            | _dependency_topic_tokens(assistant)
        )
    )
    inherited_request = bool(
        re.search(
            r"\b(?:what(?:'s| is)?|which|how|where)\b[^?.]{0,100}"
            r"\b(?:first|next|proceed|start|steps?|signals?|metrics?|denominators?|"
            r"risks?|failures?|hazards?|results?|rule out|sources?)\b",
            lower,
        )
        or re.search(
            r"\b(?:go ahead|proceed|continue|take (?:the|that|this) .{0,40} path|"
            r"smallest useful first step|what should we do first|"
            r"do not change anything yet|don't change anything yet|"
            r"keep (?:it|that|this) on hold|use (?:the )?existing|"
            r"data should come from|should come from the existing|"
            r"make (?:the|that|this) change|then test (?:it|that|this))\b",
            lower,
        )
    )
    supplied_values = bool(
        len(
            re.findall(
                r"\b\d+(?:\.\d+)?\s*(?:%|percent|ms|s|sec(?:onds?)?|min(?:utes?)?|"
                r"h|hr(?:s|ours?)?|kg|g|lb|mph|rpm|v|a|w|kw|psi|gpm|mm|cm|m)?\b",
                lower,
            )
        )
        >= 2
        and (
            shared_context
            or re.search(
                r"\b(?:value|values|number|numbers|details|data|evidence|source|"
                r"measurement|measurements|specifics)\b",
                _text(assistant).lower(),
            )
        )
    )
    inherited_object = bool(
        shared_context
        or _CONTEXT_REFERENT_RE.search(lower)
        or re.search(r"\b(?:there|those|these)\b", lower)
        or re.search(
            r"\b(?:smallest|first|next)\b[^?.]{0,40}\bsteps?\b",
            lower,
        )
        or re.search(
            r"\b(?:the|this|that|each)\s+(?:test|branch|decision|screen|"
            r"path|change|source|option|result|step|signal|metric|denominator)\b",
            lower,
        )
    )
    return bool((inherited_request and inherited_object) or supplied_values)


def turn_context_relationship(messages: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify whether the latest turn depends on the preceding user topic."""

    latest = _latest_user_text(messages)
    previous = _previous_user_text(messages)
    if not latest or not previous:
        return {
            "contextRelation": "standalone",
            "contextScope": "latest-turn",
            "sharedTopicTerms": [],
            "reason": "No earlier user topic is required for this turn.",
        }
    latest_tokens = _topic_tokens(latest)
    previous_tokens = _topic_tokens(previous)
    shared = sorted(latest_tokens & previous_tokens)
    lower = latest.lower().strip()
    assistant = _latest_assistant_text_before_user(messages)
    clarification_resolution = _focused_clarification_resolution(
        messages,
        latest,
        previous,
    )
    semantic_continuation = _semantic_dependent_continuation(
        latest,
        previous,
        assistant,
    )
    explicit_continuation = bool(_CONTEXT_CONTINUATION_RE.search(lower))
    # A demonstrative can name the active product surface rather than point
    # back to the preceding subject.  Remove only that explicit surface phrase
    # before looking for true pronoun/referent dependency; any additional
    # ``it``/``that``/artifact selection language still preserves follow-up
    # context.
    referent_text = _CONTEXT_SELF_CONTAINED_ACTIVE_SURFACE_RE.sub(" ", lower)
    referential = bool(
        _CONTEXT_REFERENT_RE.search(referent_text)
        or _CONTEXT_COMPARATIVE_REFERENT_RE.search(referent_text)
        or _artifact_followup_referent(lower)
        or _dependent_followup_referent(lower, previous)
        or re.search(
            r"\b(?:your|that|this|prior|previous)\s+"
            r"(?:recommendation|choice|decision|comparison|conclusion|result)\b",
            lower,
        )
        or re.search(
            r"\bthe\s+(?:recommendation|choice|decision|comparison|conclusion|"
            r"result|answer|question|request|instruction|rating|calculation|design)\b",
            lower,
        )
    )
    lexical_followup = bool(shared) and (
        len(shared) >= 2
        or len(shared) / max(1, min(len(latest_tokens), len(previous_tokens))) >= 0.2
    )
    if clarification_resolution:
        return {
            "contextRelation": "follow-up",
            "contextScope": "clarification-resolution",
            "sharedTopicTerms": shared[:8],
            "reason": "focused clarification resolution",
        }
    if explicit_continuation or referential or lexical_followup or semantic_continuation:
        reasons = []
        if explicit_continuation:
            reasons.append("continuation wording")
        if referential:
            reasons.append("prior-turn referent")
        if lexical_followup:
            reasons.append("shared subject terms")
        if semantic_continuation:
            reasons.append("dependent continuation")
        return {
            "contextRelation": "follow-up",
            "contextScope": "recent-thread",
            "sharedTopicTerms": shared[:8],
            "reason": ", ".join(reasons),
        }
    if len(latest_tokens) >= 2:
        return {
            "contextRelation": "new-topic",
            "contextScope": "latest-turn",
            "sharedTopicTerms": shared[:8],
            "reason": "The latest turn names a self-contained subject without a prior-turn referent.",
        }
    return {
        "contextRelation": "ambiguous",
        "contextScope": "recent-thread",
        "sharedTopicTerms": shared[:8],
        "reason": "The latest turn is too short to separate safely from recent context.",
    }


def typed_followup_constraint_update(
    latest_query: str,
    context_relationship: Dict[str, Any],
    prior_frame: Dict[str, Any],
) -> Dict[str, Any]:
    """Classify a one-input follow-up without inferring the replacement value."""

    latest = re.sub(r"\s+", " ", _text(latest_query)).strip()
    lower = latest.lower()
    if (
        not latest
        or context_relationship.get("contextRelation") != "follow-up"
        or not _text((prior_frame or {}).get("domain"))
    ):
        return {"status": "not-applicable"}
    changes_value = bool(
        re.search(r"\b(?:change|replace|set|update|switch|make|use)\b", lower)
    )
    requests_re_evaluation = bool(
        re.search(
            r"\b(?:recalculate|recompute|reevaluate|re-evaluate|recheck|rerun|"
            r"calculate again|compute again|apply (?:that|the change)|compare again)\b",
            lower,
        )
    )
    if not (changes_value and requests_re_evaluation):
        return {"status": "not-applicable"}
    numeric_replacement = bool(_DECISION_QUANTITY_RE.search(latest))
    categorical_replacement = bool(
        re.search(r"\bfrom\s+[^,.;?]{1,80}\s+to\s+[^,.;?]{1,80}", lower)
        or re.search(r"\breplace\s+[^,.;?]{1,80}\s+with\s+[^,.;?]{1,80}", lower)
        or re.search(r"\b(?:instead\s+of|rather\s+than)\s+[^,.;?]{1,80}", lower)
        or re.search(
            r"\b(?:change|set|update|switch)\s+"
            r"(?!(?:it|that|this|the\s+other(?:\s+one)?|the\s+newer(?:\s+one)?)\b)"
            r"[^,.;?]{1,80}\s+to\s+[^,.;?]{1,80}",
            lower,
        )
    )
    ambiguous_target = bool(
        re.search(
            r"\b(?:change|replace|set|update|switch|make|use)\s+"
            r"(?:it|that|this|the\s+other(?:\s+one)?|the\s+newer(?:\s+one)?)\b",
            lower,
        )
    )
    if ambiguous_target and not (numeric_replacement or categorical_replacement):
        return {
            "status": "ambiguous",
            "kind": "typed-constraint-update",
            "priorDomain": _text(prior_frame.get("domain")),
            "reason": "The turn requests reevaluation but does not identify the constraint or replacement value.",
        }
    if not (numeric_replacement or categorical_replacement):
        return {"status": "not-applicable"}
    return {
        "status": "resolved",
        "kind": "typed-constraint-update",
        "priorDomain": _text(prior_frame.get("domain")),
        "priorActionType": _text(prior_frame.get("actionType")),
        "priorCapability": _text((prior_frame.get("routeCandidates") or [""])[0]),
        "replacementKind": "numeric" if numeric_replacement else "categorical",
        "latestConstraint": latest,
        "supersession": "replace-only-named-input",
    }


def scope_messages_for_intent(
    messages: Sequence[Dict[str, Any]],
    frame: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Remove completed unrelated topics before workers and reviewers run."""

    relation = frame if isinstance(frame, dict) else turn_context_relationship(messages)
    if relation.get("contextScope") in {
        "clarification-resolution",
        "assistant-question-resolution",
    }:
        scoped = list(messages or [])
        for index in range(len(scoped) - 3, -1, -1):
            window = scoped[index:index + 3]
            if [
                _text(message.get("role")).lower()
                for message in window
            ] == ["user", "assistant", "user"]:
                return scoped[index:]
        return scoped
    semantic_exclusions = (
        relation.get("semanticExclusions")
        if isinstance(relation.get("semanticExclusions"), dict)
        else {}
    )
    supersedes_prior_subject = any(
        isinstance(item, dict)
        and _text(item.get("disposition")).lower() == "superseded"
        and item.get("discussionAllowed") is False
        for item in (semantic_exclusions.get("excludedSubjects") or [])
    )
    if supersedes_prior_subject:
        scoped = list(messages or [])
        latest_user_index = next(
            (
                index
                for index in range(len(scoped) - 1, -1, -1)
                if _text(scoped[index].get("role")).lower() == "user"
                and _message_text(scoped[index])
            ),
            -1,
        )
        if latest_user_index > 0:
            # Compare generic frames on both sides of the explicit abandonment.
            # This avoids carrying a superseded task into a new typed domain while
            # preserving prior values for same-domain constraint replacements.
            current_generic = build_generic_intent_frame(scoped)
            prior_generic = build_generic_intent_frame(scoped[:latest_user_index])
            current_domain = _text(current_generic.get("domain"))
            prior_domain = _text(prior_generic.get("domain"))
            if current_domain and prior_domain and current_domain != prior_domain:
                return [scoped[latest_user_index]]
    if relation.get("contextScope") != "latest-turn":
        scoped = list(messages or [])
        if relation.get("contextRelation") != "follow-up":
            return scoped
        user_indexes = [
            index
            for index, message in enumerate(scoped)
            if _text(message.get("role")).lower() == "user" and _message_text(message)
        ]
        if len(user_indexes) < 2:
            return scoped
        start_index = user_indexes[-1]
        for position in range(len(user_indexes) - 1, 0, -1):
            previous_index = user_indexes[position - 1]
            current_index = user_indexes[position]
            pair_relation = turn_context_relationship(
                [scoped[previous_index], scoped[current_index]]
            )
            if pair_relation.get("contextRelation") == "new-topic":
                start_index = current_index
                break
            start_index = previous_index
        return scoped[start_index:]
    for message in reversed(messages or []):
        if _text(message.get("role")).lower() == "user" and _message_text(message):
            return [message]
    return []


def _has_message_attachments(messages: Sequence[Dict[str, Any]]) -> bool:
    for message in messages or []:
        attachments = message.get("attachments")
        if isinstance(attachments, list) and attachments:
            return True
        if isinstance(message.get("attachment"), dict):
            return True
    return False


_ATTACHED_LOCAL_FILE_EXTENSIONS = {
    ".bash", ".c", ".cc", ".cjs", ".conf", ".cpp", ".csv", ".css",
    ".cfg", ".gco", ".gcode", ".go", ".h", ".hpp", ".htm", ".html",
    ".ini", ".java", ".js", ".json", ".jsx", ".log", ".md", ".mjs",
    ".nc", ".pdf", ".py", ".pyi", ".rs", ".scss", ".sh", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml", ".zsh",
}


def _attachment_file_refs(messages: Sequence[Dict[str, Any]]) -> List[str]:
    """Return supported local attachment references as typed file evidence."""

    values: List[str] = []
    for message in messages or []:
        raw_items = list(message.get("attachments") or [])
        if isinstance(message.get("attachment"), dict):
            raw_items.append(message.get("attachment"))
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name")).strip()
            path = _text(item.get("path")).strip()
            candidate = path or name
            if not candidate:
                continue
            suffix = Path(name or candidate).suffix.lower()
            if suffix not in _ATTACHED_LOCAL_FILE_EXTENSIONS:
                continue
            if candidate not in values:
                values.append(candidate)
    return values[:8]


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


def _decision_support_request(value: str) -> bool:
    """Recognize a request for judgment even when it names a future action."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text:
        return False
    return bool(
        re.search(
            r"\b(?:help\s+(?:me|us)\s+(?:decide|choose|think\s+(?:it|this)\s+through)|"
            r"think\s+(?:it|this)\s+through\s+with\s+(?:me|us)|"
            r"tell\s+(?:me|us)\s+(?:what|which)\s+(?:decision|approach|option|structure|path)|"
            r"what\s+(?:decision|approach|option|structure|path)\s+should\s+come\s+first|"
            r"which\s+(?:option|approach|structure|path)\s+should\s+(?:i|we)|"
            r"decid(?:e|ing)\s+(?:whether|between)|"
            r"worried\s+(?:that\s+)?(?:i(?:'m|\s+am)|we(?:'re|\s+are))\s+optimi[sz]ing)\b",
            text,
        )
    )


_OPERATION_DISCUSSION_TERMS = (
    "add",
    "apply",
    "build",
    "change",
    "create",
    "delete",
    "edit",
    "fix",
    "install",
    "record",
    "remove",
    "restart",
    "pause",
    "resume",
    "start",
    "run",
    "save",
    "search",
    "stop",
    "test",
    "update",
)

_OPERATION_PLAN_PATTERNS = (
    ("inspect", r"\b(?:inspect|review|check|diagnose|view|compare)\b|\bread\b(?![- ]only\b)"),
    ("explain", r"\b(?:explain|describe|summarize|tell\s+me)\b"),
    ("research", r"\b(?:research|search|find|look\s+up)\b"),
    ("download", r"\b(?:download|fetch)\b"),
    ("draft", r"\b(?:draft|stage|prepare)\b"),
    ("create", r"\b(?:create|build|rebuild|generate|regenerate|re-generate|make(?!\s+changes?\b))\b"),
    ("run", r"\b(?:run|execute)\b"),
    ("test", r"\b(?:test|verify|validate)\b"),
    ("fix", r"\b(?:fix|repair|correct)\b"),
    ("edit", r"\b(?:edit|modif(?:y|ies|ied|ying)|patch|rewrite)\b"),
    ("change", r"\b(?:change|alter|update|make\s+changes?)\b"),
    ("upload", r"\b(?:upload|deploy|publish|push)\b"),
    ("install", r"\b(?:install|flash)\b"),
    ("restart", r"\b(?:restart|reboot|reload)\b"),
    ("cancel", r"\b(?:cancel|stop|abort)(?:ing|ped|s)?\b"),
    ("pause", r"\b(?:pause|suspend)(?:d|s|ing)?\b"),
    ("resume", r"\b(?:resume|start)(?:d|s|ing)?\b"),
    ("heat", r"\b(?:heat|preheat)(?:ing|ed|s)?\b|\bset\b(?=[^.!?]{0,80}\b(?:temperature|temp|nozzle|bed|chamber)\b)"),
    ("move", r"\b(?:move|home|jog)(?:d|s|ing)?\b"),
    ("control-output", r"\b(?:toggle|switch)(?:ed|es|ing)?\b|\bturn\b(?=[^.!?]{0,80}\b(?:on|off)\b)"),
    ("delete", r"\b(?:delete|remove|erase|wipe)\b"),
    ("buy", r"\b(?:buy|purchase|order)\b"),
    ("contact", r"\b(?:contact|message|email|call)\b"),
    ("record", r"\b(?:record|save|store)\b"),
)

_MUTATING_OPERATION_NAMES = {
    "create",
    "download",
    "draft",
    "fix",
    "edit",
    "change",
    "upload",
    "install",
    "restart",
    "cancel",
    "pause",
    "resume",
    "heat",
    "move",
    "control-output",
    "delete",
    "buy",
    "contact",
    "record",
}

_EXECUTABLE_OPERATION_NAMES = _MUTATING_OPERATION_NAMES | {
    "inspect",
    "research",
    "run",
    "test",
}

_OPERATION_STATE_PRECEDENCE = {
    "allowed-now": 1,
    "discussed": 2,
    "deferred": 3,
    "prohibited": 4,
}

_LOCAL_ARTIFACT_ACTION_RE = re.compile(
    r"\b(?P<action>create|build|rebuild|generate|regenerate|re-generate|design|make|model|draw|draft|prepare|save|write|export|render|produce)\b"
    r"(?P<object>(?:\.(?=[a-z0-9]{1,8}\b)|[^.!?;]){0,140})",
    flags=re.IGNORECASE,
)
_DESIRED_LOCAL_ARTIFACT_RE = re.compile(
    r"\b(?P<action>i\s+need|i\s+want|i\s+would\s+like|can\s+i\s+get|"
    r"(?:please\s+)?give\s+me|return(?:\s+the\s+answer)?\s+as|"
    r"(?:my\s+)?expected\s+output\s+is|the\s+deliverable\s+should\s+be|"
    r"(?:your|the)\s+output\s+(?:should|must|needs?\s+to)\s+be)\b"
    r"(?P<object>[^.!?;]{0,140})",
    flags=re.IGNORECASE,
)
_LOCAL_ARTIFACT_OBJECT_RE = re.compile(
    r"(?:\b(?:cad(?:\s+(?:file|model|drawing))?|drawing|diagram|drilling\s+template|"
    r"template\s+file|(?:3d[- ]?)?printable\s+(?:(?:[a-z0-9_-]+)\s+){0,3}(?:file|model|part|artifact|bracket|mount(?:ing\s+bracket)?|housing|adapter|duct|fixture|enclosure|cover|plate|spacer|clamp|coupler|component|object|design)|model\s+file|"
    r"report\s+file|saved\s+report|markdown\s+file|python\s+script|"
    r"(?:csv|json|text|image|source|code)\s+file|file|script|document|workbook|spreadsheet|presentation)\b|"
    r"\b(?:dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|markdown|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg)\b|"
    r"\.(?:dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg)\b)",
    flags=re.IGNORECASE,
)
_CAD_ARTIFACT_OBJECT_RE = re.compile(
    r"(?:\b(?:cad(?:\s+(?:file|model|drawing))?|drawing|drilling\s+template|"
    r"(?:3d[- ]?)?printable\s+(?:(?:[a-z0-9_-]+)\s+){0,3}(?:file|model|part|artifact|bracket|mount(?:ing\s+bracket)?|housing|adapter|duct|fixture|enclosure|cover|plate|spacer|clamp|coupler|component|object|design)|model\s+file)\b|"
    r"\b(?:dxf|step|stp|stl|scad|f3d|f3z)\b|"
    r"\.(?:dxf|step|stp|stl|scad|f3d|f3z)\b)",
    flags=re.IGNORECASE,
)
_DIAGRAM_ARTIFACT_OBJECT_RE = re.compile(
    r"\b(?:wiring|block|system|flow|control|electrical|pneumatic|hydraulic)\s+"
    r"(?:diagram|schematic)\b|\b(?:diagram|schematic)\b[^.!?;]{0,60}\b(?:wiring|interfaces?|connections?)\b",
    flags=re.IGNORECASE,
)


def _model_token_is_artifact_action(text: str, match_start: int) -> bool:
    """Distinguish the verb ``model`` from a product/CAD model noun.

    Artifact authority must come from request grammar, not from encountering a
    noun that happens to share an action spelling.  Keep direct imperatives and
    user-to-agent requests executable while rejecting phrases such as "a STEP
    CAD model and an STL mesh".
    """

    prefix = str(text or "")[: max(0, int(match_start))].lower()
    clause_prefix = re.split(r"[.!?;]", prefix)[-1].strip()
    return bool(
        re.fullmatch(r"(?:please)?", clause_prefix)
        or re.search(
            r"(?:\b(?:can|could|will|would)\s+you|"
            r"\bi\s+(?:want|need|would\s+like)\s+you\s+to|"
            r"\b(?:go\s+ahead|continue)\s+and|"
            r"\b(?:please|then))$",
            clause_prefix,
        )
    )


def _conceptual_comparison_answer_request(value: str) -> bool:
    """Treat ordinary comparisons as answers unless real evidence is targeted.

    ``compare`` is both a reasoning verb and a tool operation.  The speech act
    comes from its object: named concepts belong in the answer, while attached
    files, local paths, logs, configs, and URLs require inspection.  Keeping
    that distinction here prevents the operation ledger from turning every
    conceptual comparison into a local-action contract.
    """

    text = re.sub(r"\s+", " ", _text(value)).strip()
    lower = text.lower()
    comparison_grammar = bool(
        re.search(
            r"\b(?:compare|contrast)\b|"
            r"\b(?:difference|distinction)\s+between\b|"
            r"\bhow\s+does\b[^.!?;]{1,120}\bdiffer\s+from\b",
            lower,
        )
    )
    if not comparison_grammar:
        return False
    explicit_evidence_target = bool(
        _URL_RE.search(text)
        or _FILE_RE.search(text)
        or re.search(
            r"\b(?:attached|attachment|uploaded|provided\s+files?|local\s+files?|"
            r"these\s+(?:two\s+)?files?|the\s+(?:two\s+)?files?|"
            r"current\s+(?:config|configuration|log|file)|previous\s+(?:config|configuration|log|file)|"
            r"config(?:uration)?\s+files?|log\s+files?|source\s+files?)\b",
            lower,
        )
    )
    return not explicit_evidence_target


def _comparison_speech_act(value: str) -> str:
    """Separate an explanation request from a choice or recommendation request."""

    lower = re.sub(r"\s+", " ", _text(value)).strip().lower()
    decision_request = bool(
        re.search(
            r"\b(?:which|what)\b[^.!?;]{0,120}\b(?:better|best|stronger|preferable|winner)\b|"
            r"\b(?:recommend|choose|pick|select|prefer|should\s+(?:i|we)\s+(?:use|choose|buy|pick)|"
            r"which\s+(?:one|option)|best\s+(?:choice|option|fit))\b",
            lower,
        )
    )
    if decision_request:
        return "decision"
    explanatory_request = bool(
        re.search(
            r"\b(?:what(?:'s|\s+is)\s+the\s+)?(?:difference|distinction)\s+between\b|"
            r"\bhow\s+(?:does|do)\b[^.!?;]{1,120}\bdiffer\s+from\b|"
            r"\bexplain\b[^.!?;]{0,80}\b(?:difference|distinction)\b",
            lower,
        )
    )
    return "explanation" if explanatory_request else "comparison"


def classify_output_authority(
    value: Any,
    operation_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Bind answer, action, or saved-artifact ownership to latest-turn grammar.

    Subject nouns such as ``CAD`` or ``report`` are not permission to create a
    file. A saved artifact requires a direct action-object pair whose operation
    is not prohibited, deferred, or merely discussed. The compact receipt is
    consumed by routing, task-contract, and completion ownership so those
    layers cannot independently reinterpret the same request.
    """

    text = re.sub(r"\s+", " ", _text(value)).strip()
    lower = text.lower()
    plan = operation_plan if isinstance(operation_plan, dict) else {}
    prohibited = {str(item or "") for item in (plan.get("prohibited") or [])}
    discussed = {str(item or "") for item in (plan.get("discussed") or [])}
    deferred = {
        str(item.get("operation") or "")
        for item in (plan.get("deferred") or [])
        if isinstance(item, dict)
    }
    blocked = prohibited | discussed | deferred

    desired_result_request = bool(
        _DESIRED_LOCAL_ARTIFACT_RE.search(text)
        and _LOCAL_ARTIFACT_OBJECT_RE.search(text)
    )
    information_question = bool(
        re.match(
            r"^(?:what|which|why|when|where|who|whose|how)\b",
            lower,
        )
        and not re.match(
            r"^what\s+i\s+(?:want|need|would\s+like)\b",
            lower,
        )
    )
    yes_no_information_question = bool(
        not desired_result_request
        and (
            re.match(
                r"^(?:is|are|was|were|do|does|did|should|has|have|had)\b",
                lower,
            )
            or re.match(
                r"^(?:can|could|will|would)\b(?!\s+you\s+(?:please\s+)?(?:create|build|rebuild|generate|regenerate|re-generate|design|make|model|draw|draft|prepare|save|write|export|render|produce)\b)",
                lower,
            )
        )
    )
    advisory_request = bool(
        information_question
        or yes_no_information_question
        or re.match(
            r"^(?:what\s+(?:would|will|could|might)\b|how\s+(?:do|would|should|can)\b|"
            r"should\s+(?:i|we)\b|which\b[^.!?]{0,100}\bshould\s+(?:i|we)\b|"
            r"can\s+you\s+(?:explain|describe|tell\s+me)\b|"
            r"(?:please\s+)?(?:explain|describe|tell\s+me)\s+(?:how|why|what)\b)",
            lower,
        )
    )
    answer_object = bool(
        re.search(
            r"\b(?:draft|build|give|make|write)\s+(?:me\s+)?(?:an?\s+|the\s+)?"
            r"(?:explanation|recommendation|answer|report-style\s+answer)\b|"
            r"\b(?:create|build|give)\s+(?:me\s+)?(?:an?\s+|the\s+)?(?:mental|conceptual)\s+model\b|"
            r"\b(?:build|deepen|improve)\s+(?:my|our|the)\s+understanding\b|"
            r"\bcompare\b[^.!?;]{0,140}\b(?:in\s+plain\s+language|conceptually|at\s+a\s+high\s+level|in\s+the\s+(?:answer|response|reply))\b",
            lower,
        )
        or _conceptual_comparison_answer_request(text)
    )
    explicit_persistence = bool(
        re.search(
            r"\b(?:save|export)\b[^.!?;]{0,100}(?:\bfile\b|\b(?:dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg)\b)|"
            r"\b(?:write|put)\b[^.!?;]{0,80}\b(?:to|into|as)\b[^.!?;]{0,60}(?:\bfile\b|\b(?:dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg)\b)",
            lower,
        )
    )
    negative_file_destination = bool(
        re.search(
            r"\b(?:do\s+not|don't|never)\s+(?:save|create|write|export)\b[^.!?;]{0,80}\bfile\b|"
            r"\b(?:do\s+not|don't|never)\s+save\s+(?:it|this|that|the\s+(?:draft|output|artifact))?(?:\s+yet|\s+for\s+now)?\b|"
            r"\bnot\s+(?:as|to)\s+(?:a\s+)?file\b",
            lower,
        )
    )
    positive_persistence = bool(
        explicit_persistence
        and not negative_file_destination
        and not ({"record", "create"} & blocked)
    )
    explicit_local_destination = bool(
        re.search(
            r"\b(?:save|store|write|put|create|generate|make)\b[^.!?;]{0,100}\b(?:locally|on\s+disk|in\s+/[a-z0-9_./-]+|at\s+/[a-z0-9_./-]+)\b|"
            r"\b(?:local|saved)\s+(?:file|artifact|copy)\b",
            lower,
        )
        and not ({"record", "create"} & blocked)
    )
    inline_destination = bool(
        re.search(
            r"\b(?:in|inside|within)\s+(?:the|this|your|my)?\s*(?:answer|response|reply|chat)\b|"
            r"\binline(?:\s+in\s+(?:the\s+)?(?:answer|response|reply|chat))?\b|"
            r"\b(?:show|display|put|give|write)\b[^.!?;]{0,80}\bhere\b|"
            r"\bhere\b[^.!?;]{0,70}\bnot\s+(?:as|to)\s+(?:a\s+)?file\b|"
            r"\bnot\s+(?:as|to)\s+(?:a\s+)?file\b",
            lower,
        )
    )
    force_conversation_destination = bool(
        inline_destination
        and not (positive_persistence or explicit_local_destination)
    )

    artifact_match: Optional[re.Match[str]] = None
    if (
        not advisory_request
        and not force_conversation_destination
        and (not answer_object or positive_persistence or explicit_local_destination)
    ):
        for candidate in _LOCAL_ARTIFACT_ACTION_RE.finditer(text):
            action = str(candidate.group("action") or "").lower()
            if action == "model" and not _model_token_is_artifact_action(
                text,
                candidate.start("action"),
            ):
                continue
            operation = {
                "save": "record",
                "export": "record",
                "write": "create",
                "design": "create",
                "model": "create",
                "draw": "create",
                "produce": "create",
                "render": "create",
                "build": "create",
                "rebuild": "create",
                "generate": "create",
                "regenerate": "create",
                "re-generate": "create",
                "make": "create",
            }.get(action, action)
            if operation in blocked:
                continue
            object_text = str(candidate.group("object") or "")
            if _LOCAL_ARTIFACT_OBJECT_RE.search(object_text):
                artifact_match = candidate
                break
        if artifact_match is None:
            # A request may contain more than one desired-result clause.  Do
            # not stop at an earlier broad "I would like..." phrase when a
            # later clause binds the actual deliverable and format (for
            # example, "the output should be a STEP file").
            for desired_candidate in _DESIRED_LOCAL_ARTIFACT_RE.finditer(text):
                if _LOCAL_ARTIFACT_OBJECT_RE.search(
                    str(desired_candidate.group("object") or "")
                ):
                    artifact_match = desired_candidate
                    break

    if artifact_match is not None:
        matched_text = artifact_match.group(0)
        raw_operation = str(artifact_match.group("action") or "").lower()
        canonical_operation = (
            "draft"
            if raw_operation in {"draft", "prepare"}
            else "record"
            if raw_operation in {"save", "export"}
            else "create"
        )
        artifact_class = (
            "diagram"
            if _DIAGRAM_ARTIFACT_OBJECT_RE.search(matched_text)
            else "cad"
            if _CAD_ARTIFACT_OBJECT_RE.search(matched_text)
            else "document"
        )
        requested_format_matches = re.findall(
            r"(?:\.|\b)(dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|markdown|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg)\b",
            matched_text,
            flags=re.IGNORECASE,
        )
        requested_format = (
            str(requested_format_matches[-1] or "").lower()
            if requested_format_matches
            else ""
        )
        if requested_format == "markdown":
            requested_format = "md"
        return {
            "kind": "typed-output-contract",
            "version": 1,
            "mode": "local-artifact",
            "authoritySurface": "local-artifact",
            "artifactClass": artifact_class,
            "targetKind": f"{artifact_class}-artifact",
            "requestedFormat": requested_format,
            "state": "allowed-now",
            "binding": "explicit-action-object-pair",
            "operation": canonical_operation,
            "confidence": 0.98,
            "reason": "A direct action is bound to an explicit saved artifact or file format and is not blocked by the operation ledger.",
        }

    explicitly_authorized_external_action = bool(
        any(
            isinstance(item, dict)
            and item.get("state") == "allowed-now"
            and str(item.get("operation") or "") in _EXECUTABLE_OPERATION_NAMES
            and str(item.get("authoritySurface") or "") != "conversation"
            for item in (plan.get("operations") or [])
        )
    )
    if force_conversation_destination or (
        (advisory_request or answer_object)
        and not explicitly_authorized_external_action
    ):
        allowed_mutations = []
    else:
        allowed_mutations = [
        str(item or "")
        for item in (plan.get("allowedNow") or [])
        if str(item or "") in _EXECUTABLE_OPERATION_NAMES
        ]
    if (
        allowed_mutations
        and not answer_object
        and (
            _explicit_action_request(text)
            or (
                _local_product_ui_surface_request(text)
                and _explicit_desired_ui_state_change(text)
            )
        )
    ):
        surfaces = list((plan.get("authorityBySurface") or {}).keys())
        surface = surfaces[0] if len(surfaces) == 1 else "mixed"
        return {
            "kind": "typed-output-contract",
            "version": 1,
            "mode": "live-device" if surface == "live-device" else "local-action",
            "authoritySurface": surface,
            "artifactClass": "",
            "targetKind": "authorized-action",
            "requestedFormat": "",
            "state": "allowed-now",
            "binding": "typed-operation-plan",
            "operations": allowed_mutations,
            "confidence": 0.94,
            "reason": "The normalized operation ledger contains a positively authorized external operation without an explicit saved-artifact target.",
        }

    return {
        "kind": "typed-output-contract",
        "version": 1,
        "mode": "conversation-answer",
        "authoritySurface": "conversation",
        "artifactClass": "",
        "targetKind": "answer",
        "requestedFormat": "",
        "state": "not-requested",
        "binding": (
            "explicit-answer-object"
            if answer_object
            else "explicit-conversation-destination"
            if force_conversation_destination
            else "advisory-or-question"
            if advisory_request or lower.endswith("?")
            else "no-authorized-artifact-output"
        ),
        "confidence": 0.96 if advisory_request or answer_object or force_conversation_destination or lower.endswith("?") else 0.78,
        "reason": "No positively authorized action is bound to a saved artifact target in the latest request.",
    }


def _bind_local_artifact_output_plan(
    operation_plan: Optional[Dict[str, Any]],
    output_contract: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Make an accepted saved-output contract executable by the typed worker."""

    plan = dict(operation_plan or {})
    contract = output_contract if isinstance(output_contract, dict) else {}
    if not (
        contract.get("mode") == "local-artifact"
        and contract.get("state") == "allowed-now"
    ):
        return plan
    raw_action = str(contract.get("operation") or "").lower()
    primary_operation = (
        "draft"
        if raw_action in {"draft", "prepare"}
        else "record"
        if raw_action in {"save", "export", "record"}
        else "create"
    )
    required_operations = [primary_operation]
    if contract.get("requestedFormat") and "record" not in required_operations:
        required_operations.append("record")

    operations = [
        dict(item)
        for item in (plan.get("operations") or [])
        if isinstance(item, dict)
    ]
    for operation in required_operations:
        replaced = False
        for item in operations:
            if (
                str(item.get("operation") or "") == operation
                and str(item.get("state") or "") == "allowed-now"
            ):
                item["authoritySurface"] = "local-artifact"
                item["condition"] = str(item.get("condition") or "")
                replaced = True
        if not replaced:
            operations.append(
                {
                    "operation": operation,
                    "state": "allowed-now",
                    "condition": "authorized by the explicit saved-output contract",
                    "authoritySurface": "local-artifact",
                }
            )

    allowed = list(
        dict.fromkeys(
            [
                *[str(item or "") for item in (plan.get("allowedNow") or []) if str(item or "")],
                *required_operations,
            ]
        )
    )
    authority_by_surface: Dict[str, Dict[str, Any]] = {}
    for surface in ("conversation", "local-artifact", "live-device", "request-target"):
        surface_items = [
            item for item in operations if item.get("authoritySurface") == surface
        ]
        if not surface_items:
            continue
        authority_by_surface[surface] = {
            "allowedNow": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "allowed-now"
            ],
            "prohibited": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "prohibited"
            ],
            "deferred": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "deferred"
            ],
            "discussed": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "discussed"
            ],
        }
    return {
        **plan,
        "operations": operations,
        "allowedNow": allowed,
        "readOnly": False,
        "authorityBySurface": authority_by_surface,
        "authorityVersion": max(2, int(plan.get("authorityVersion") or 0)),
    }


def _bind_conversation_output_plan(
    operation_plan: Optional[Dict[str, Any]],
    output_contract: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Prevent answer-shaping verbs from becoming local mutation authority."""

    plan = dict(operation_plan or {})
    contract = output_contract if isinstance(output_contract, dict) else {}
    if contract.get("mode") != "conversation-answer" or not plan:
        return plan
    # The answer destination does not revoke a separately authorized read/run
    # action.  "Run the test, then report the result here" legitimately owns
    # both an execution and a conversational result.  Advisory run/test
    # mentions have already been marked discussed by the operation parser;
    # only answer-shaping mutations still need destination reconciliation.
    demoted = _MUTATING_OPERATION_NAMES
    research_answer = any(
        isinstance(item, dict)
        and item.get("operation") == "research"
        and item.get("state") == "allowed-now"
        for item in plan.get("operations") or []
    )
    operations = []
    for raw_item in plan.get("operations") or []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if (
            research_answer
            and item.get("operation") == "create"
            and item.get("state") == "allowed-now"
        ):
            item["authoritySurface"] = "conversation"
            item["condition"] = "compile the requested research result in the answer"
        if (
            item.get("state") == "allowed-now"
            and item.get("operation") in demoted
            and item.get("authoritySurface") in {"local-artifact", "request-target"}
        ):
            item["state"] = "discussed"
            item["authoritySurface"] = "conversation"
            item["condition"] = "the requested destination is the conversation, not a saved artifact"
        operations.append(item)
    allowed = [
        str(item.get("operation") or "")
        for item in operations
        if item.get("state") == "allowed-now" and item.get("operation")
    ]
    prohibited = [
        str(item.get("operation") or "")
        for item in operations
        if item.get("state") == "prohibited" and item.get("operation")
    ]
    discussed = [
        str(item.get("operation") or "")
        for item in operations
        if item.get("state") == "discussed" and item.get("operation")
    ]
    deferred_items = [
        item for item in operations if item.get("state") == "deferred"
    ]
    authority_by_surface: Dict[str, Dict[str, Any]] = {}
    for surface in ("conversation", "local-artifact", "live-device", "request-target"):
        surface_items = [item for item in operations if item.get("authoritySurface") == surface]
        if not surface_items:
            continue
        authority_by_surface[surface] = {
            "allowedNow": [item["operation"] for item in surface_items if item.get("state") == "allowed-now"],
            "prohibited": [item["operation"] for item in surface_items if item.get("state") == "prohibited"],
            "deferred": [item["operation"] for item in surface_items if item.get("state") == "deferred"],
            "discussed": [item["operation"] for item in surface_items if item.get("state") == "discussed"],
        }
    return {
        **plan,
        "operations": operations,
        "allowedNow": allowed,
        "prohibited": prohibited,
        "discussed": discussed,
        "deferred": deferred_items,
        "readOnly": not bool(set(allowed) & _MUTATING_OPERATION_NAMES),
        "authorityBySurface": authority_by_surface,
        "authorityVersion": max(2, int(plan.get("authorityVersion") or 0)),
    }

_LIVE_DEVICE_OPERATION_NAMES = {
    "inspect",
    "change",
    "upload",
    "install",
    "restart",
    "cancel",
    "pause",
    "resume",
    "heat",
    "move",
    "control-output",
}

_LIVE_DEVICE_MUTATION_NAMES = _LIVE_DEVICE_OPERATION_NAMES - {"inspect"}


def _live_device_context(value: str) -> bool:
    """Recognize a physical printer/controller surface without stealing code work."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text:
        return False
    named_physical_target = bool(
        re.search(
            r"\b(?:qidi(?:\s+plus\s+4)?|rat\s*rig|bambu(?:\s+h2d|\s+x1c)|"
            r"kraken(?:\s+controller(?:\s+board)?)?|klipper|moonraker)\b",
            text,
        )
    )
    physical_surface = bool(
        re.search(
            r"\b(?:live\s+printer|current\s+print|print\s+job|printer\s+firmware|"
            r"printer\.cfg|controller\s+board|nozzle|heated?\s+bed|bed\s+temperature|"
            r"chamber\s+light|case\s+light|axes?|toolhead|printer\s+camera)\b",
            text,
        )
    )
    generic_printer_target = bool(
        re.search(r"\b(?:the|this|that|my|our|current)\s+printer\b", text)
        and not re.search(r"\bprinter\s+(?:compatibility|ui|interface|table|code|class|object|module)\b", text)
    )
    local_code_surface = bool(
        re.search(
            r"\b(?:server\.py|app\.js|styles\.css|codebase|source\s+code|"
            r"codex\s+cli\s+ui|local\s+service|compatibility\s+table)\b",
            text,
        )
    )
    return bool(
        (named_physical_target or physical_surface or generic_printer_target)
        and (named_physical_target or physical_surface or not local_code_surface)
    )


def _operation_authority_surface(value: str, operation: str) -> str:
    """Bind an operation to the surface whose state it can change or inspect."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if operation in {"explain"}:
        return "conversation"
    if operation in {"research", "download", "draft", "create"}:
        return "local-artifact"
    if operation in {"inspect", "change", "edit", "fix"} and re.search(
        r"\bprinter\.cfg\b", text
    ):
        return "local-artifact"
    explicit_local_file_scope = bool(
        re.search(
            r"\b(?:local|locally|draft|staged?|saved)\b[^.!?]{0,80}\b(?:file|config|printer\.cfg|artifact|copy|snapshot)\b|"
            r"\b(?:file|config|printer\.cfg|artifact|copy|snapshot)\b[^.!?]{0,80}\b(?:local|locally|draft|staged?|saved)\b",
            text,
        )
    )
    if operation in {"inspect", "change", "edit", "fix"} and explicit_local_file_scope:
        return "local-artifact"
    if _live_device_context(text) and operation in _LIVE_DEVICE_OPERATION_NAMES:
        return "live-device"
    if re.search(
        r"\b(?:file|folder|directory|repo(?:sitory)?|workspace|server\.py|app\.js|"
        r"styles\.css|code|config(?:uration)?|local\s+service)\b",
        text,
    ):
        return "local-artifact"
    return "request-target"

_SEMANTIC_CONSTRAINT_STOPWORDS = _CONTEXT_STOPWORDS | {
    "also",
    "any",
    "instead",
    "just",
    "mind",
    "never",
    "not",
    "now",
    "only",
    "previous",
    "prior",
    "rather",
    "then",
    "using",
    "without",
}


def _semantic_constraint_concepts(value: str) -> List[str]:
    """Return subject concepts without treating polarity words as subjects."""

    return sorted(
        {
            token
            for token in re.findall(r"[a-z0-9]+", _text(value).lower())
            if token.isdigit()
            or (
                len(token) >= 3
                and token not in _SEMANTIC_CONSTRAINT_STOPWORDS
            )
        }
    )


def _extract_semantic_exclusions(value: str) -> Dict[str, Any]:
    """Type latest-turn subject exclusions separately from operation authority.

    The result describes answer subjects/objectives that were retired or excluded;
    it does not authorize or prohibit tools. A downstream run/lineage-bound receipt
    owns enforcement at finalization.
    """

    text = re.sub(r"\s+", " ", _text(value)).strip()
    if not text:
        return {}

    exclusions: List[Dict[str, Any]] = []
    replacements: List[Dict[str, Any]] = []
    seen_exclusions = set()
    seen_replacements = set()

    def add_exclusion(
        phrase: str,
        *,
        disposition: str,
        discussion_allowed: bool = False,
    ) -> None:
        normalized_phrase = re.split(
            r"\b(?:for|in\s+order\s+to|so\s+that)\b",
            _text(phrase),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" \t\r\n,;:.!?\"'")
        concepts = _semantic_constraint_concepts(normalized_phrase)
        key = (disposition, tuple(concepts))
        if not concepts or key in seen_exclusions:
            return
        seen_exclusions.add(key)
        exclusions.append(
            {
                "constraintId": f"exclude-{len(exclusions) + 1}",
                "disposition": disposition,
                "subject": normalized_phrase,
                "concepts": concepts,
                "discussionAllowed": bool(discussion_allowed),
            }
        )

    def add_replacement(phrase: str) -> None:
        normalized_phrase = re.split(
            r"\b(?:for|in\s+order\s+to|so\s+that)\b",
            _text(phrase),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" \t\r\n,;:.!?\"'")
        concepts = _semantic_constraint_concepts(normalized_phrase)
        key = tuple(concepts)
        if not concepts or key in seen_replacements:
            return
        seen_replacements.add(key)
        replacements.append(
            {
                "constraintId": f"require-{len(replacements) + 1}",
                "subject": normalized_phrase,
                "concepts": concepts,
            }
        )

    explanation_pattern = re.compile(
        r"\b(?:explain|describe|tell\s+(?:me|us))\s+(?:the\s+reasons?\s+)?why\s+"
        r"(?:(?:we|i|you|one)\s+)?(?:(?:should|must|ought\s+to)\s+)?"
        r"(?:not|never)\s+(?:to\s+)?(?:use|rely\s+on|cite|include|consider)\s+"
        r"(?P<excluded>[^.!?;,:]+)",
        flags=re.IGNORECASE,
    )
    explanation_spans = []
    for match in explanation_pattern.finditer(text):
        add_exclusion(
            match.group("excluded"),
            disposition="excluded",
            discussion_allowed=True,
        )
        explanation_spans.append(match.span())

    correction_patterns = (
        re.compile(
            r"(?:^|[.!?;]\s*)not\s+(?P<excluded>[^;,.!?]+)\s*[;,.]\s*"
            r"(?:instead\s+)?(?:use|choose|select|switch\s+to|make\s+it)\s+"
            r"(?P<required>[^.!?;]+)",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:use|choose|select|switch\s+to|make\s+it)\s+"
            r"(?P<required>[^,;.!?]+)\s*,\s*not\s+(?P<excluded>[^;.!?]+)",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"\brather\s+than\s+(?P<excluded>[^,;.!?]+)\s*[,;]\s*"
            r"(?:use|choose|select|switch\s+to)\s+(?P<required>[^.!?;]+)",
            flags=re.IGNORECASE,
        ),
    )
    correction_spans = []
    for pattern in correction_patterns:
        for match in pattern.finditer(text):
            add_exclusion(match.group("excluded"), disposition="superseded")
            add_replacement(match.group("required"))
            correction_spans.append(match.span())

    generic_patterns = (
        (
            "superseded",
            re.compile(r"\bnever\s+mind\s+(?P<excluded>[^.!?;,:]+)", re.IGNORECASE),
            False,
        ),
        (
            "excluded",
            re.compile(
                r"\b(?:ignore|exclude|omit|drop|discard|disregard|retire|abandon)\s+"
                r"(?P<excluded>[^.!?;,:]+)",
                re.IGNORECASE,
            ),
            False,
        ),
        (
            "excluded",
            re.compile(
                r"\b(?:do\s+not|don't|never)\s+"
                r"(?:use|rely\s+on|cite|include|consider)\s+"
                r"(?P<excluded>[^.!?;,:]+)",
                re.IGNORECASE,
            ),
            False,
        ),
        (
            "excluded",
            re.compile(
                r"\bwithout\s+(?:(?:using|relying\s+on|citing|including|considering)\s+)?"
                r"(?P<excluded>[^.!?;,:]+)",
                re.IGNORECASE,
            ),
            True,
        ),
    )
    protected_spans = explanation_spans + correction_spans
    for disposition, pattern, skip_operation_gerund in generic_patterns:
        for match in pattern.finditer(text):
            if any(
                match.start() >= start and match.end() <= end
                for start, end in protected_spans
            ):
                continue
            excluded_phrase = match.group("excluded")
            if skip_operation_gerund and re.match(
                r"(?:adding|applying|building|changing|creating|deleting|editing|fixing|"
                r"installing|recording|removing|restarting|running|saving|searching|"
                r"stopping|testing|updating|uploading)\b",
                excluded_phrase.strip(),
                flags=re.IGNORECASE,
            ):
                # This is an operation prohibition (for example, "without
                # changing files"), not an excluded answer subject.
                continue
            add_exclusion(excluded_phrase, disposition=disposition)

    if not exclusions and not replacements:
        return {}
    return {
        "kind": "semantic-exclusion-constraints",
        "version": 1,
        "scope": "latest-turn-answer-semantics",
        "excludedSubjects": exclusions,
        "requiredReplacements": replacements,
        "excludedConcepts": sorted(
            {
                concept
                for item in exclusions
                for concept in (item.get("concepts") or [])
            }
        ),
        "requiredConcepts": sorted(
            {
                concept
                for item in replacements
                for concept in (item.get("concepts") or [])
            }
        ),
        "discussionConcepts": sorted(
            {
                concept
                for item in exclusions
                if item.get("discussionAllowed")
                for concept in (item.get("concepts") or [])
            }
        ),
    }


def _extract_operation_plan(value: str) -> Dict[str, Any]:
    """Capture operation order, prohibitions, and hold points from one request."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text:
        return {}
    # Corpus labels and UI headings are context, not grammatical subjects.
    # Strip one short leading label before deciding whether a verb is an
    # advisory mention (for example, "Calibration: How should I set...").
    polarity_text = re.sub(r"^[^:]{1,80}:\s*", "", text)
    advisory_operation_reference = bool(
        re.search(
            r"^(?:what|which)\b[^.!?]{0,140}\b(?:would|should|could)\s+"
            r"(?:i|we|you)\b|"
            r"\b(?:what|which)\s+(?:command|test|benchmark|check|inspection|tool|step)\b"
            r"[^.!?]{0,120}\bshould\s+(?:i|we)\b|"
            r"\b(?:tell\s+me|name|recommend|state)\b[^.!?]{0,140}"
            r"\b(?:command|test|benchmark|check|inspection|tool|step)\b"
            r"[^.!?]{0,80}\b(?:i|we|you)\s+(?:would|should|could)\b|"
            r"\b(?:what|which)\s+(?:commands?|tests?|benchmarks?|checks?|inspections?|tools?|steps?)\b"
            r"[^.!?]{0,120}\b(?:need|require)\s+(?:(?:an?|another|a\s+fresh)\s+)?"
            r"(?:run|rerun|execution|check|test)\b|"
            r"\b(?:explain|describe|tell\s+me)\b[^.!?]{0,100}\bhow\s+"
            r"(?:(?:i|we|you)\s+(?:would|should|could)\b|to\b)",
            polarity_text,
        )
    )
    advisory_or_diagnostic_mention = bool(
        re.match(
            r"^(?:how\s+(?:do|would|should)\s+i|should\s+i|is\s+it\s+safe\s+to|"
            r"when\s+should\s+(?:i|we|you)|why\s+(?:did|does|has|would)|"
            r"what\s+(?:happens|would\s+happen)\s+if)\b",
            polarity_text,
        )
        or advisory_operation_reference
    )
    diagnostic_stop_criterion_question = bool(
        re.search(
            r"^(?:what|which)\s+(?:observations?|results?|evidence|conditions?|signals?|readings?)\b"
            r"[^.!?]{0,160}\b(?:stop|abort|halt|end)\b[^.!?]{0,100}"
            r"\b(?:diagnostic\s+)?(?:test|experiment|trial)\b|"
            r"^(?:what|which)\b[^.!?]{0,120}\bmake\s+(?:me|us|you)\s+"
            r"(?:stop|abort|halt|end)\b[^.!?]{0,100}"
            r"\b(?:diagnostic\s+)?(?:test|experiment|trial)\b",
            polarity_text,
        )
    )
    direct_heat_request = bool(
        re.search(
            r"^(?:(?:please|now)\s+|go\s+ahead\s+(?:and\s+)?|"
            r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
            r"i\s+(?:want|need)\s+(?:you\s+)?to\s+)?"
            r"(?:heat|preheat|set\b[^.!?]{0,50}\b(?:temperature|temp|nozzle|bed|chamber))\b",
            polarity_text,
        )
    )
    mentions: List[Dict[str, Any]] = []
    for name, pattern in _OPERATION_PLAN_PATTERNS:
        for match in re.finditer(pattern, text):
            matched_text = match.group(0).strip().lower()
            if diagnostic_stop_criterion_question and name in {
                "create",
                "cancel",
                "test",
            }:
                continue
            # A physical quantity or condition is not an actuator command.
            # Only imperative/request syntax promotes heat/setpoint language
            # into the operation ledger.
            if name == "heat" and not direct_heat_request:
                continue
            # "How do I read a tower/chart/result?" asks for interpretation,
            # not permission to inspect a live device. An imperative read of
            # current target state remains an operation.
            if (
                name == "inspect"
                and matched_text == "read"
                and advisory_or_diagnostic_mention
            ):
                continue
            # Diagnostic stop criteria do not mean cancel/stop a live job.
            # Keep direct "stop the current print" commands intact.
            if (
                name == "cancel"
                and matched_text.startswith("stop")
                and re.search(
                    r"\bstop\s+(?:the|this|a|an)\s+"
                    r"(?:[a-z0-9-]+\s+){0,4}(?:test|experiment|trial)\b",
                    text,
                )
                and not re.search(r"\b(?:print|job|machine|printer)\b", match.group(0) + text[match.end() : match.end() + 60])
            ):
                continue
            prefix = text[max(0, match.start() - 120) : match.start()]
            suffix = text[match.end() : min(len(text), match.end() + 140)]
            clause_prefix = re.split(r"[.!?;]", prefix)[-1]
            clause_suffix = re.split(r"[,;]|\b(?:then|but)\b", suffix, maxsplit=1)[0]
            prohibited = bool(
                re.search(
                    r"\b(?:do\s+not|don't|never|without|must\s+not|should\s+not|shouldn't)\b[^.!?;]{0,110}$",
                    clause_prefix,
                )
            )
            external_lookup_scope = bool(
                re.search(
                    r"\bwithout\s+(?:(?:using|browsing|searching|accessing|checking)\s+)?"
                    r"(?:the\s+)?(?:web|internet|online)\b[^.!?;]{0,60}$",
                    clause_prefix,
                )
            )
            if name == "explain" and external_lookup_scope:
                prohibited = False
            discussed = bool(
                re.search(
                    r"\b(?:what|which)\s+(?:would|will|could|might|may)\b[^.!?;]{0,60}$",
                    clause_prefix,
                )
                or (
                    re.search(r"\b(?:the|a|this|that)\s+$", clause_prefix)
                    and re.match(r"\s*(?:does|means|is|would|could|might)\b", suffix)
                )
            )
            quote_prefix = text[: match.start()]
            quoted_operation = bool(
                (quote_prefix.count("'") % 2)
                or (quote_prefix.count('"') % 2)
                or (
                    re.search(r"\b(?:explain|describe|define)\s+(?:the\s+)?(?:phrase|word|text|command)\b", text)
                    and name not in {"explain"}
                )
            )
            discussed = bool(
                discussed
                or quoted_operation
                or (advisory_or_diagnostic_mention and name != "explain")
            )
            suffix_condition_match = re.search(
                r"\b(?:only\s+)?(?:after|if|when|once|until)\b[^.!?;]{0,100}",
                clause_suffix,
            )
            prefix_condition_match = re.search(
                r"\b(?:only\s+)?(?:after|if|when|once|until)\b[^.!?;]{0,100},?\s*$",
                clause_prefix,
            )
            condition_match = suffix_condition_match or prefix_condition_match
            condition = condition_match.group(0).strip(" ,.") if condition_match else ""
            authorization_hold = bool(
                condition
                and re.search(
                    r"\b(?:i|we)\s+(?:confirm|approve|authorize|give\s+permission)\b|"
                    r"\b(?:my|our|user)\s+(?:confirmation|approval|permission|authorization)\b",
                    condition,
                )
            )
            deferred = bool(authorization_hold and not prohibited and not discussed)
            mentions.append(
                {
                    "operation": name,
                    "position": match.start(),
                    "state": (
                        "prohibited"
                        if prohibited
                        else "discussed"
                        if discussed
                        else "deferred"
                        if deferred
                        else "allowed-now"
                    ),
                    "condition": condition,
                    "authoritySurface": _operation_authority_surface(text, name),
                }
            )
    mentions.sort(key=lambda item: (int(item.get("position") or 0), str(item.get("operation") or "")))
    # Every operation has one final state. Explicit prohibition outranks a hold,
    # a hold outranks discussion, and discussion outranks an otherwise executable
    # mention. This prevents one verb from appearing in both allowed and blocked
    # authority sets merely because the request repeats it.
    selected_by_operation: Dict[str, Dict[str, Any]] = {}
    first_position: Dict[str, int] = {}
    for item in mentions:
        operation = str(item.get("operation") or "")
        first_position.setdefault(operation, int(item.get("position") or 0))
        current = selected_by_operation.get(operation)
        if current is None or _OPERATION_STATE_PRECEDENCE.get(
            str(item.get("state") or ""), 0
        ) > _OPERATION_STATE_PRECEDENCE.get(str(current.get("state") or ""), 0):
            selected_by_operation[operation] = item
    compact_mentions = [
        {key: value for key, value in selected_by_operation[operation].items() if key != "position"}
        for operation in sorted(first_position, key=lambda name: (first_position[name], name))
    ]
    if not compact_mentions:
        return {}
    allowed = [item["operation"] for item in compact_mentions if item.get("state") == "allowed-now"]
    prohibited = [item["operation"] for item in compact_mentions if item.get("state") == "prohibited"]
    discussed = [item["operation"] for item in compact_mentions if item.get("state") == "discussed"]
    deferred_items = [item for item in compact_mentions if item.get("state") == "deferred"]
    deferred_operation_names = {
        str(item.get("operation") or "") for item in deferred_items if isinstance(item, dict)
    }
    read_only = bool(
        advisory_or_diagnostic_mention
        or re.search(r"\bread[- ]only\b", text)
        or (
            allowed
            and set(allowed).issubset({"inspect", "explain", "research"})
        )
        or (
            (prohibited or deferred_operation_names)
            and set(allowed).issubset({"inspect", "explain", "research", "run", "test"})
            and bool((set(prohibited) | deferred_operation_names) & _MUTATING_OPERATION_NAMES)
        )
    )
    authority_by_surface: Dict[str, Dict[str, Any]] = {}
    for surface in ("conversation", "local-artifact", "live-device", "request-target"):
        surface_items = [
            item for item in compact_mentions if item.get("authoritySurface") == surface
        ]
        if not surface_items:
            continue
        authority_by_surface[surface] = {
            "allowedNow": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "allowed-now"
            ],
            "prohibited": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "prohibited"
            ],
            "deferred": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "deferred"
            ],
            "discussed": [
                item["operation"]
                for item in surface_items
                if item.get("state") == "discussed"
            ],
        }
    if "live-device" in authority_by_surface:
        authority_by_surface["live-device"]["mutationAllowed"] = bool(
            set(authority_by_surface["live-device"].get("allowedNow") or [])
            & _LIVE_DEVICE_MUTATION_NAMES
        )
    return {
        "operations": compact_mentions,
        "allowedNow": allowed,
        "prohibited": prohibited,
        "discussed": discussed,
        "deferred": deferred_items,
        "readOnly": read_only,
        "requiresConfirmation": any(
            re.search(r"\b(?:confirm|approve|permission|authorize)\w*\b", str(item.get("condition") or ""))
            for item in deferred_items
        ),
        "authorityBySurface": authority_by_surface,
        "authorityVersion": 1,
    }


def _live_device_target_refs(value: str) -> List[Dict[str, Any]]:
    """Extract bounded physical targets without treating a generic printer noun as exact."""

    text = re.sub(r"\s+", " ", _text(value)).strip()
    patterns = (
        (r"\bQidi\s+Plus\s+4\b", "printer", "Qidi Plus 4"),
        (r"\bRat\s*Rig\b", "printer", "Rat Rig"),
        (r"\bBambu\s+H2D\b", "printer", "Bambu H2D"),
        (r"\bBambu\s+X1C\b", "printer", "Bambu X1C"),
        (r"\bKraken(?:\s+controller(?:\s+board)?)?\b", "controller-board", "Kraken controller board"),
    )
    refs: List[Dict[str, Any]] = []
    for pattern, ref_type, name in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            refs.append({"type": ref_type, "name": name, "binding": "latest-turn-explicit"})
    if re.search(r"\bKlipper\b", text, flags=re.IGNORECASE):
        refs.append({"type": "live-service", "name": "Klipper", "binding": "latest-turn-explicit"})
    return refs


def _live_device_action_request(value: str, operation_plan: Dict[str, Any]) -> bool:
    if not _live_device_context(value):
        return False
    live_items = [
        item
        for item in (operation_plan.get("operations") or [])
        if isinstance(item, dict)
        and item.get("state") != "discussed"
        and item.get("authoritySurface") == "live-device"
    ]
    operation_names = {str(item.get("operation") or "") for item in live_items}
    active_live_operations = {
        str(item.get("operation") or "")
        for item in live_items
        if item.get("state") in {"allowed-now", "deferred"}
    }
    explanatory_live_hold = bool(
        any(item.get("state") == "prohibited" for item in live_items)
        and "explain" in set(operation_plan.get("allowedNow") or [])
        and not any(
            item.get("authoritySurface") == "local-artifact"
            and item.get("state") == "allowed-now"
            for item in (operation_plan.get("operations") or [])
            if isinstance(item, dict)
        )
    )
    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    direct_heat_request = bool(
        re.search(
            r"^(?:(?:please|now)\s+|go\s+ahead\s+(?:and\s+)?|"
            r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
            r"i\s+(?:want|need)\s+(?:you\s+)?to\s+)?"
            r"(?:heat|preheat|set\b[^.!?]{0,50}\b(?:temperature|temp|nozzle|bed|chamber))\b",
            text,
        )
    )
    if "heat" in active_live_operations and not direct_heat_request:
        active_live_operations.discard("heat")
    eta_diagnostic = bool(
        re.search(
            r"\b(?:eta|estimated?\s+(?:completion|finish)|completion\s+(?:time|estimate)|"
            r"remaining\s+time|time\s+remaining|what\s+time\s+will[^?.]{0,80}\bprint\s+finish|"
            r"when\s+will[^?.]{0,80}\bprint\s+finish)\b",
            text,
        )
    )
    if eta_diagnostic and not operation_names & _LIVE_DEVICE_MUTATION_NAMES:
        return False
    status_intent = bool(
        re.search(
            r"\b(?:current|installed|status|state|temperature|temp|camera|version|telemetry)\b",
            text,
        )
        and re.search(r"\b(?:check|inspect|read|view|show|report|download|fetch|capture|what|is|are)\b", text)
        and (
            any(
                item.get("operation") == "inspect"
                and item.get("state") == "allowed-now"
                for item in live_items
            )
            or _live_device_target_refs(text)
            or re.search(r"\b(?:current|this|that|my|our)\s+printer\b", text)
        )
        and (
            any(item.get("operation") == "inspect" for item in live_items)
            or re.search(
                r"\b(?:temperature|temp|camera|telemetry|firmware\s+version|"
                r"printer\s+state|print\s+state|job\s+state|print_stats)\b",
                text,
            )
        )
    )
    return bool(
        active_live_operations & _LIVE_DEVICE_OPERATION_NAMES
        or status_intent
        or explanatory_live_hold
    )


def _constrain_live_device_operation_plan(value: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Keep local staging available while fail-closing live-device mutation."""

    result = dict(plan or {})
    operations = [
        dict(item)
        for item in (result.get("operations") or [])
        if isinstance(item, dict) and str(item.get("operation") or "").strip()
    ]
    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not any(item.get("operation") == "inspect" for item in operations) and re.search(
        r"\b(?:check|inspect|read|view|show|report)\b|\bcamera\b[^.!?]{0,80}\b(?:snapshot|image|frame|download)\b|\b(?:snapshot|image|frame|download)\b[^.!?]{0,80}\bcamera\b",
        text,
    ):
        operations.insert(
            0,
            {
                "operation": "inspect",
                "state": "allowed-now",
                "condition": "read-only live-device status requested",
                "authoritySurface": "live-device",
            },
        )

    held_live_mutations: List[str] = []
    normalized: List[Dict[str, Any]] = []
    for item in operations:
        operation = str(item.get("operation") or "")
        surface = str(item.get("authoritySurface") or _operation_authority_surface(text, operation))
        if (
            surface == "request-target"
            and _live_device_context(text)
            and operation in _LIVE_DEVICE_OPERATION_NAMES
        ):
            surface = "live-device"
        item["authoritySurface"] = surface
        if (
            surface == "live-device"
            and operation in _LIVE_DEVICE_MUTATION_NAMES
            and item.get("state") == "allowed-now"
        ):
            user_condition = str(item.get("condition") or "").strip()
            item["state"] = "deferred"
            item["condition"] = (
                (user_condition + "; and " if user_condition else "")
                + "after controller validation of the exact target, current safe state, "
                "rollback boundary where required, and latest-request authorization receipt"
            )
            held_live_mutations.append(operation)
        normalized.append(item)

    allowed = [str(item["operation"]) for item in normalized if item.get("state") == "allowed-now"]
    prohibited = [str(item["operation"]) for item in normalized if item.get("state") == "prohibited"]
    discussed = [str(item["operation"]) for item in normalized if item.get("state") == "discussed"]
    deferred = [item for item in normalized if item.get("state") == "deferred"]
    authority_by_surface: Dict[str, Dict[str, Any]] = {}
    for surface in ("conversation", "local-artifact", "live-device", "request-target"):
        surface_items = [item for item in normalized if item.get("authoritySurface") == surface]
        if not surface_items:
            continue
        authority_by_surface[surface] = {
            "allowedNow": [item["operation"] for item in surface_items if item.get("state") == "allowed-now"],
            "prohibited": [item["operation"] for item in surface_items if item.get("state") == "prohibited"],
            "deferred": [item["operation"] for item in surface_items if item.get("state") == "deferred"],
            "discussed": [item["operation"] for item in surface_items if item.get("state") == "discussed"],
        }
    if "live-device" in authority_by_surface:
        authority_by_surface["live-device"].update(
            {
                "mutationAllowed": False,
                "preflightRequired": bool(
                    set(held_live_mutations)
                    or set(authority_by_surface["live-device"].get("deferred") or [])
                ),
            }
        )
    active_mutation_intent = bool(
        [
            item
            for item in normalized
            if item.get("operation") in _MUTATING_OPERATION_NAMES
            and item.get("state") in {"allowed-now", "deferred"}
        ]
    )
    explicit_hold = bool(prohibited) and not active_mutation_intent
    inspection_only = bool(normalized) and not active_mutation_intent
    return {
        **result,
        "operations": normalized,
        "allowedNow": allowed,
        "prohibited": prohibited,
        "discussed": discussed,
        "deferred": deferred,
        "readOnly": bool(
            explicit_hold
            or inspection_only
            or (result.get("readOnly") and not active_mutation_intent)
        ),
        "requiresConfirmation": bool(result.get("requiresConfirmation") or held_live_mutations),
        "authorityBySurface": authority_by_surface,
        "authorityVersion": 1,
    }


def _defer_unresolved_target_operations(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Prevent a pronoun-only mutation from carrying executable authority."""

    result = dict(plan or {})
    operations: List[Dict[str, Any]] = []
    for raw in result.get("operations") or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if (
            item.get("state") == "allowed-now"
            and item.get("operation") in _LIVE_DEVICE_MUTATION_NAMES
        ):
            item["state"] = "deferred"
            item["condition"] = "after the user identifies the exact target"
            item["authoritySurface"] = "unresolved-target"
        operations.append(item)
    allowed = [item["operation"] for item in operations if item.get("state") == "allowed-now"]
    prohibited = [item["operation"] for item in operations if item.get("state") == "prohibited"]
    discussed = [item["operation"] for item in operations if item.get("state") == "discussed"]
    deferred = [item for item in operations if item.get("state") == "deferred"]
    return {
        **result,
        "operations": operations,
        "allowedNow": allowed,
        "prohibited": prohibited,
        "discussed": discussed,
        "deferred": deferred,
        "readOnly": False,
        "requiresConfirmation": bool(deferred),
        "authorityBySurface": {
            "unresolved-target": {
                "allowedNow": [],
                "prohibited": prohibited,
                "deferred": [item["operation"] for item in deferred],
                "discussed": discussed,
                "mutationAllowed": False,
            }
        },
        "authorityVersion": 1,
    }


def _operation_discussion_request(value: str) -> bool:
    """Distinguish talking about an operation from requesting that operation."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text or not _has(text, _OPERATION_DISCUSSION_TERMS):
        return False
    operation_pattern = "|".join(
        sorted((re.escape(term) for term in _OPERATION_DISCUSSION_TERMS), key=len, reverse=True)
    )
    direct_request = bool(
        re.match(rf"^(?:please\s+|now\s+)?(?:{operation_pattern})\b", text)
        or re.match(
            rf"^(?:can|could|would|will)\s+you\b[^.!?]{{0,60}}\b(?:{operation_pattern})\b",
            text,
        )
        or re.match(
            rf"^i\s+(?:want|need|would\s+like|'d\s+like)\s+you\s+to\b[^.!?]{{0,50}}"
            rf"\b(?:{operation_pattern})\b",
            text,
        )
    )
    if direct_request:
        return False
    metalinguistic_cue = bool(
        re.search(
            rf"\b(?:if|when|before)\s+i\s+(?:say|write|mention|use|ask\s+you\s+to|press|click|select)?"
            rf"[^.!?]{{0,80}}\b(?:{operation_pattern})\b",
            text,
        )
        or re.search(
            rf"\b(?:word|phrase|command|button|control)\b[^.!?]{{0,50}}\b(?:{operation_pattern})\b|"
            rf"\b(?:{operation_pattern})\b[^.!?]{{0,50}}\b(?:word|phrase|command|button|control)\b",
            text,
        )
        or re.search(
            r"\b(?:does\s+that\s+mean|what\s+happens\s+when|how\s+do\s+you\s+decide\s+whether|"
            r"how\s+do\s+you\s+interpret|will\s+not\s+actually|won't\s+actually|"
            r"does\s+not\s+authorize|doesn't\s+authorize)\b",
            text,
        )
    )
    agent_context = bool(
        re.search(r"\b(?:you|your|agent|assistant|codex|system|app|ui|model)\b", text)
    )
    question_shape = "?" in _text(value) or bool(
        re.search(r"^(?:what|why|how|when|where|does|do|did|is|are|will|would|can|could|if|before)\b", text)
    )
    return metalinguistic_cue and agent_context and question_shape


def _explicit_action_request(value: str) -> bool:
    """Distinguish an instruction from a question that merely names an action."""

    text = re.sub(r"\s+", " ", _text(value)).strip()
    if not text or not _has(text, _ACTION_TERMS) or _operation_discussion_request(text):
        return False
    action_pattern = "|".join(
        sorted(
            (re.escape(term.strip()) for term in _ACTION_TERMS if term.strip()),
            key=len,
            reverse=True,
        )
    )
    operation_plan = _extract_operation_plan(text)
    allowed_now = set(operation_plan.get("allowedNow") or [])
    if _decision_support_request(text):
        followon_execution = re.search(
            rf"(?i)\b(?:then|and\s+then|after\s+(?:that|we\s+decide|you\s+decide))\b"
            rf"[^.!?]{{0,40}}\b(?:{action_pattern})\b",
            text,
        )
        if not followon_execution:
            return False
    direct_shape = bool(
        re.search(
            rf"(?i)(?:^|[.!?]\s+)(?:please\s+)?(?:{action_pattern})\b",
            text,
        )
        or re.search(
            rf"(?i)\b(?:can|could|would|will)\s+(?:you|we)\b[^.!?]{{0,80}}\b(?:{action_pattern})\b",
            text,
        )
        or re.search(
            rf"(?i)\b(?:i\s+(?:want|need|would\s+like|'d\s+like)\s+you\s+to|"
            rf"let(?:'s|\s+us)|go\s+ahead\s+and)\b[^.!?]{{0,50}}\b(?:{action_pattern})\b",
            text,
        )
        or re.search(
            rf"(?i)\b(?:then|after\s+that)\b(?![^.!?]{{0,80}}\bonly\s+(?:if|after|when|once|until)\b)"
            rf"[^.!?]{{0,45}}\b(?:{action_pattern})\b",
            text,
        )
    )
    if not direct_shape:
        return False
    # A verb that is explicitly prohibited or held until later cannot make the
    # current turn executable by itself. Other allowed work in the same request
    # can still own the turn.
    if operation_plan.get("operations"):
        return bool(allowed_now)
    return True


def _local_product_ui_surface_request(value: str) -> bool:
    """Recognize unambiguous local-app surfaces without capturing physical panels."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text:
        return False
    if _has(f" {text} ", _LOCAL_PRODUCT_UI_SURFACE_TERMS):
        return True
    ui_qualifier = (
        r"(?:app|application|codex(?: cli ui)?|composer|chat|device|interface|screen|"
        r"tab|toolbar|ui|user interface|view|window|workspace)"
    )
    app_surface = r"(?:dashboard|panel)"
    return bool(
        re.search(rf"\b{ui_qualifier}\b[^.!?]{{0,48}}\b{app_surface}\b", text)
        or re.search(rf"\b{app_surface}\b[^.!?]{{0,48}}\b{ui_qualifier}\b", text)
    )


def _explicit_desired_ui_state_change(value: str) -> bool:
    """Treat stated UI end states as requests, while preserving design questions."""

    text = re.sub(r"\s+", " ", _text(value)).strip().lower()
    if not text:
        return False
    if re.search(
        r"^(?:do|would|could|should|what|how|why|is|are)\b|"
        r"\b(?:do you think|would it be better|what do you think|should we)\b",
        text,
    ):
        return False
    verb_pattern = "|".join(
        sorted((re.escape(term) for term in _DESIRED_UI_STATE_VERBS), key=len, reverse=True)
    )
    return bool(
        re.search(
            rf"(?:^|[.!?]\s+|,\s*)(?:please\s+)?(?:{verb_pattern})\b",
            text,
        )
        or re.search(
            rf"\bi\s+(?:(?:also|als)\s+)?(?:want|need|would like|'d like)\s+"
            rf"[^.!?]{{1,100}}?\s+to\s+(?:{verb_pattern})\b",
            text,
        )
        or re.search(
            rf"(?:^|[.!?]\s+)(?:the\s+)?[^.!?]{{1,100}}?\s+"
            rf"(?:needs?\s+to|must|should)\s+(?:{verb_pattern})\b",
            text,
        )
    )


def _desired_local_ui_operation_plan(value: Any) -> Dict[str, Any]:
    """Authorize the canonical local UI workflow without crossing hold points."""

    plan = dict(value) if isinstance(value, dict) else {}
    operations = [
        dict(item)
        for item in (plan.get("operations") or [])
        if isinstance(item, dict)
    ]
    allowed = [
        str(item)
        for item in (plan.get("allowedNow") or [])
        if str(item).strip()
    ]
    prohibited = {
        str(item)
        for item in (plan.get("prohibited") or [])
        if str(item).strip()
    }
    deferred_names = {
        str(item.get("operation") or "")
        for item in (plan.get("deferred") or [])
        if isinstance(item, dict) and str(item.get("operation") or "").strip()
    }
    mutation_held = bool(
        plan.get("readOnly")
        or (prohibited | deferred_names) & _MUTATING_OPERATION_NAMES
    )
    existing_states = {
        (str(item.get("operation") or ""), str(item.get("state") or ""))
        for item in operations
    }
    for operation in ("inspect", "edit", "test"):
        if operation in prohibited or operation in deferred_names:
            continue
        if operation == "edit" and mutation_held:
            continue
        if operation not in allowed:
            allowed.append(operation)
        if (operation, "allowed-now") not in existing_states:
            operations.append(
                {
                    "operation": operation,
                    "state": "allowed-now",
                    "condition": "required by the requested local UI state change",
                }
            )
    return {
        **plan,
        "operations": operations,
        "allowedNow": allowed,
        "prohibited": list(plan.get("prohibited") or []),
        "discussed": list(plan.get("discussed") or []),
        "deferred": list(plan.get("deferred") or []),
        "readOnly": bool(plan.get("readOnly") or mutation_held),
        "requiresConfirmation": bool(plan.get("requiresConfirmation")),
    }


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


def _analytical_local_file_request(query: str, files: Sequence[str]) -> bool:
    """Return true when named files need task-specific content analysis.

    The bounded local comparator owns ordinary same/different/similarity
    questions. Counts, filtered evidence, quotations, duplicate detection,
    ordering, and other requested projections need a tool-capable reasoning
    pass over the actual files instead of a fixed similarity summary.
    """

    if not files:
        return False
    text = re.sub(r"\s+", " ", _text(query)).lower()
    return bool(
        re.search(
            r"\b(?:count|counts|counting|how many|quote|quotes|quoted|extract|"
            r"matching lines?|occurrences?|references? to|contains? more|"
            r"duplicates?|duplicate keys?|setting names?|sort|rank|top\s+\d+|"
            r"largest|smallest|list (?:only )?(?:the )?(?:matching|lines?|entries?|keys?))\b",
            text,
        )
    )


def _object_refs(urls: Sequence[str], files: Sequence[str]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    for value in files:
        refs.append({"type": "local-or-attached-file", "name": Path(value).name})
    for value in urls:
        host = urlparse(value).netloc or value
        refs.append({"type": "public-source", "name": host})
    return refs[:8]


def _engineering_suitability_subject(query: str) -> str:
    match = re.search(
        r"(?i)\b(?:would|will|can|could|is|are|does|do)\s+"
        r"(?:a|an|the|this|that|my)?\s*(.+?)\s+"
        r"(?:perform|work|handle|survive|withstand|be\s+suitable|be\s+appropriate|be\s+viable|be\s+a\s+good\s+(?:choice|fit)"
        r"|(?:remain|stay)\s+(?:dimensionally\s+)?(?:flat|stable|aligned|rigid|sealed|watertight|accurate|functional|reliable)"
        r"|maintain\s+(?:flatness|stability|alignment|rigidity|a\s+seal|accuracy|function|reliability))\b",
        _text(query),
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip(" ,;:.?!")[:180]


def _engineering_usage_subject(query: str) -> str:
    """Extract the physical object in a fabrication or substitution decision."""

    text = _text(query)
    patterns = (
        r"(?i)\b(?:can|could|would|should)\s+(?:i|we)\s+(?:use|reuse|repurpose)\s+"
        r"(?:an|a|the|this|that|my|our)?\s*(.+?)\s+(?:as|for|instead\s+of)\b",
        r"(?i)\b(?:can|could|would|should|is|are)\s+(?:an|a|the|this|that|my|our)?\s*"
        r"(.+?)\s+(?:be\s+used\s+as|double\s+as|serve\s+as|work\s+as|replace|substitute)\b",
        r"(?i)\b(?:can|could|would|should)\s+(?:i|we)\s+"
        r"(?:adhere|anneal|bond|braze|cast|clamp|coat|cut|drill|forge|grind|heat[ -]?treat|"
        r"machine|mill|paint|press[ -]?fit|solder|turn|weld)\w*\s+"
        r"(?:an|a|the|this|that|my|our)?\s*(.+?)(?=\s+(?:if|when|while|without|before|after|using|with)\b|[?.]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        subject = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:.?!")
        subject = re.sub(
            r"(?i)\s+(?:on|in|at)\s+(?:an?|the|my|our)\s+"
            r"(?:mill|lathe|router|machine|press|welder|bench)\b.*$",
            "",
            subject,
        ).strip(" ,;:.?!")
        if subject and len(subject) <= 180:
            return subject
    return ""


def _engineering_system_refs(query: str) -> List[Dict[str, str]]:
    """Keep named system layers available to follow-ups and recovery paths."""

    text = _text(query).lower().replace("‑", "-")
    aliases = (
        ("VFD", (r"\bvfd\b", r"\bvariable\s+frequency\s+drive\b", r"\binverter\s+drive\b")),
        ("motor", (r"\bmotor\b",)),
        (
            "reciprocating compressor",
            (
                r"\breciprocating\b[^.!?\n]{0,50}\bcompressor\b",
                r"\bpiston\b[^.!?\n]{0,30}\bcompressor\b",
            ),
        ),
        ("compressor", (r"\bcompressor\b",)),
        ("pump", (r"\bpump\b",)),
        ("servo", (r"\bservo\b",)),
        ("actuator", (r"\bactuator\b",)),
        ("gearbox", (r"\bgearbox\b",)),
        ("transformer", (r"\btransformer\b",)),
        ("power supply", (r"\bpower\s+supply\b",)),
        ("converter", (r"\bconverter\b",)),
        (
            "electric ducted fan",
            (
                r"\belectric\s+ducted\s+fan\b",
                r"\bducted\s+fan\b",
                r"\bedf\b",
            ),
        ),
        ("propulsor", (r"\bpropulsor\b",)),
        ("turbine", (r"\bturbine\b",)),
    )
    names: List[str] = []
    for name, patterns in aliases:
        if any(re.search(pattern, text) for pattern in patterns):
            if name == "compressor" and "reciprocating compressor" in names:
                continue
            names.append(name)
    if not names:
        architecture_match = re.search(
            r"^\s*(?:(?:i mean|it is|it's|the architecture is|we are building)\s+)?"
            r"(?:(?:a|an|the)\s+)?([^,.?]{3,80}?)(?=\s+(?:for|with|using|rated)\b|[,?.]|$)",
            text,
        )
        if architecture_match:
            architecture = re.sub(r"\s+", " ", architecture_match.group(1)).strip(" -")
            if architecture and not re.fullmatch(r"(?:yes|no|that|this|it)", architecture):
                names.append(architecture)
    return [
        {"type": "engineering-system-component", "name": name}
        for name in names[:6]
    ]


def _is_engineering_suitability_text(value: str) -> bool:
    text = _text(value)
    # Calculation prompts commonly end with instructions such as "show your
    # work".  Remove those answer-format phrases before looking for the verb
    # "work" as a suitability predicate; otherwise an earlier "is" can span
    # the sentence and turn a calculation into a material-suitability request.
    suitability_text = re.sub(
        r"(?i)\bshow\s+(?:(?:all|the|your)\s+)?(?:work|calculations?|steps?)\b",
        " ",
        text,
    )
    lower = f" {text.lower()} "
    return bool(
        _ENGINEERING_SUITABILITY_RE.search(suitability_text)
        and _has(lower, _ENGINEERING_OBJECT_TERMS)
        and (
            _ENGINEERING_VALUE_RE.search(text)
            or _has(lower, _ENGINEERING_CONDITION_TERMS)
        )
    )


def _is_engineering_advisory_text(value: str) -> bool:
    """Recognize a technical design judgment without domain-specific answers."""

    text = _text(value)
    lower = f" {text.lower()} "
    technical_context = bool(
        _has(lower, (*_ENGINEERING_OBJECT_TERMS, *_ENGINEERING_SYSTEM_TERMS))
        and (
            _ENGINEERING_VALUE_RE.search(text)
            or _has(lower, _ENGINEERING_CONDITION_TERMS)
            or _has(lower, _ENGINEERING_SYSTEM_TERMS)
            or _has(lower, _ENGINEERING_PROCESS_TERMS)
        )
    )
    if not technical_context:
        return False
    return bool(
        re.search(
            r"(?i)\b(?:is|are|would|will|can|could|should|does|do)\b[^?\n]{0,240}"
            r"\b(?:safe|unsafe|sound\s+design|good\s+design|viable|appropriate|suitable|"
            r"work|perform|handle|survive|withstand)\b",
            text,
        )
        or re.search(
            r"(?i)\b(?:what|which)\b[^?\n]{0,160}"
            r"\b(?:make|makes|change|changes|remain|remains|still\s+appl(?:y|ies))\b[^?\n]{0,120}"
            r"\b(?:safe|unsafe|sound|recommendation|design|rating|rated|limit|constraint)\b",
            text,
        )
        or re.search(
            r"(?i)\b(?:tell|explain)\s+me\b[^?\n]{0,100}"
            r"\b(?:safe|unsafe|failure\s+modes?|tradeoffs?|what\s+information)\b",
            text,
        )
        or re.search(
            r"(?i)\b(?:would|should|could)\s+you\b[^?\n]{0,80}"
            r"\b(?:build|design|choose|select|use)\b[^?\n]{0,80}\b(?:around|with|from|between)\b",
            text,
        )
        or re.search(
            r"(?i)\b(?:does|would|will)\s+(?:that|this|it)\b[^?\n]{0,80}\bchange\b"
            r"[^?\n]{0,80}\b(?:answer|recommendation|choice|design|conclusion)\b",
            text,
        )
        or re.search(
            r"(?i)\b(?:does|would)\s+(?:that|this|it)\s+make\s+"
            r"(?:(?:engineering|technical|practical)\s+)?sense\b",
            text,
        )
        or re.search(
            r"(?i)\bam\s+i\s+(?:solving|fixing|addressing|optimizing|controlling)\b"
            r"[^?\n]{0,100}\bwrong\s+problem\b",
            text,
        )
        or re.search(
            r"(?i)\bam\s+i\s+(?:making\s+(?:a|the)\s+mistake|"
            r"thinking\s+about\s+(?:this|it)\s+(?:correctly|the\s+right\s+way)|"
            r"overthinking\s+(?:this|it))\b",
            text,
        )
        or re.search(
            r"(?i)\bi\s+(?:am|'m)\s+(?:leaning\s+toward|tempted\s+to)\b",
            text,
        )
        or (
            _ENGINEERING_USAGE_DECISION_RE.search(text)
            and _has(lower, _ENGINEERING_PROCESS_TERMS)
        )
        or _ENGINEERING_PROCESS_DECISION_RE.search(text)
    )


def _multi_layer_power_system_design_text(value: str) -> bool:
    """Separate complete power-chain design from a closed arithmetic request."""

    text = _text(value).lower().replace("‑", "-")
    if not text:
        return False
    converter = bool(
        re.search(
            r"\b(?:vfd|variable\s+frequency\s+drive|inverter|converter|motor\s+drive)\b",
            text,
        )
    )
    actuator = bool(re.search(r"\b(?:motor|actuator|servo)\b", text))
    source_or_phase = bool(
        re.search(
            r"\b(?:batter(?:y|ies)|bms|dc\s+bus|generator|alternator|shore\s+power|"
            r"single[- ]phase|three[- ]phase|phase\s+conversion|input\s+phase)\b",
            text,
        )
    )
    driven_load = bool(
        re.search(
            r"\b(?:compressor|pump|fan|blower|spindle|conveyor|winch|hoist|"
            r"propeller|vehicle|machine|load|process)\b",
            text,
        )
    )
    system_decision = bool(
        re.search(
            r"\b(?:architecture|topology|protection|protect|safeguard|size|sizing|"
            r"verify|before\s+buying|before\s+purchasing|can\s+i|will\s+it|"
            r"what\s+(?:current|rating|facts?|information))\b",
            text,
        )
    )
    return bool(converter and actuator and source_or_phase and driven_load and system_decision)


def _is_fault_isolation_experiment_text(value: str) -> bool:
    """Recognize requests for a discriminating physical diagnostic experiment."""

    text = _text(value)
    lower = text.lower()
    if not lower:
        return False
    physical_context = bool(
        re.search(
            r"\b(?:machine|printer|motor|driver|axis|bearing|mechanical|electrical|thermal|"
            r"temperature|vibration|pressure|flow|power|voltage|current|sensor|actuator|"
            r"motion|binding|derating|dropout|fault|failure|intermittent|under load)\b",
            lower,
        )
    )
    experiment_cue = bool(
        re.search(
            r"\b(?:smallest|minimum|controlled|discriminating|diagnostic)\s+(?:bench\s+)?(?:test|experiment)\b|"
            r"\b(?:design|run|set up|structure|plan)\b[^?.\n]{0,80}\b(?:test|experiment|trial)\b|"
            r"\b(?:test|experiment)\s+(?:sequence|matrix|plan)\b",
            lower,
        )
    )
    discrimination_cue = bool(
        re.search(
            r"\b(?:separat\w*|distinguish\w*|isolat\w*|discriminat\w*|rule\s+(?:in|out)|"
            r"each\s+branch|competing\s+(?:cause|mechanism|hypothes))\b",
            lower,
        )
    )
    software_only = bool(
        re.search(r"\b(?:unit tests?|test suite|mock(?:ing)?|function|class|module|api endpoint|code path)\b", lower)
        and not re.search(r"\b(?:machine|printer|motor|driver|axis|mechanical|electrical|thermal|hardware)\b", lower)
    )
    return bool(physical_context and experiment_cue and discrimination_cue and not software_only)


def _fault_isolation_hypothesis_refs(value: str) -> List[Dict[str, str]]:
    """Extract user-named competing mechanisms without interpreting their truth."""

    text = re.sub(r"\s+", " ", _text(value)).strip()
    match = re.search(
        r"(?i)\b(?:separat\w*|distinguish\w*|isolat\w*)\s+(.{3,220}?)(?=[?.]|$)",
        text,
    )
    if not match:
        return []
    raw = re.sub(r"\b(?:and|or)\b", ",", match.group(1), flags=re.I)
    refs: List[Dict[str, str]] = []
    for item in raw.split(","):
        name = re.sub(r"\s+", " ", item).strip(" -:;,.?")
        name = re.sub(r"^(?:between|among|the)\s+", "", name, flags=re.I)
        if 2 <= len(name) <= 80 and name.lower() not in {"causes", "mechanisms", "hypotheses"}:
            refs.append({"type": "fault-hypothesis", "name": name})
    return refs[:6] if len(refs) >= 2 else []


def _is_decision_metric_design_text(value: str) -> bool:
    """Recognize questions about choosing an outcome-aligned rate or denominator."""

    text = _text(value)
    lower = text.lower()
    if not lower:
        return False
    outcome_context = bool(
        re.search(
            r"\b(?:fail(?:ed|ure|ures|ing)?|defects?|incidents?|errors?|returns?|reliability|"
            r"downtime|scrap|yield|success(?:es)?|complaints?|outages?|injur(?:y|ies)|events?)\b",
            lower,
        )
    )
    exposure_context = bool(
        re.search(
            r"\b(?:denominator|rate|ratio|per\s+(?:job|part|unit|hour|mile|cycle|customer|order|"
            r"attempt|start|day|week|kilogram|kg)|job\s+count|machine-hours?|operating\s+hours?|"
            r"units?\s+(?:run|produced)|volume|throughput|exposure|sample\s+size|far\s+more\s+jobs?)\b",
            lower,
        )
    )
    decision_context = bool(
        re.search(
            r"\b(?:actually\s+(?:got|getting|is|became)\s+worse|whether\s+.+\s+worse|"
            r"which\s+denominator|what\s+denominator|denominator\s+should|own\s+the\s+decision|"
            r"hide|hiding|mask|masking|drown(?:ing)?\s+out|compare|trend|reliability\s+actually)\b",
            lower,
        )
    )
    metric_intent = bool(
        re.search(
            r"\b(?:denominator|rate|ratio|per\s+(?:job|part|unit|hour|mile|cycle|customer|order|"
            r"attempt|start|day|week|kilogram|kg)|machine-hours?|operating\s+hours?|"
            r"sample\s+size|exposure|stratif\w*|mix\s+shift|which\s+metric|what\s+metric)\b",
            lower,
        )
        or re.search(
            r"\bmore\s+(?:failed|defective|returned|scrapped)\s+\w+\b[^.?!]{0,120}"
            r"\b(?:but|while|although)\b[^.?!]{0,120}\bmore\s+(?:jobs?|parts?|units?|hours?|volume)\b",
            lower,
        )
        or re.search(
            r"\b(?:raw\s+count|count\s+alone|reliability\s+actually|actually\s+got\s+worse|"
            r"hide|hiding|mask|masking|drown(?:ing)?\s+out)\b",
            lower,
        )
    )
    simple_arithmetic = bool(
        re.search(r"\b(?:calculate|compute)\b", lower)
        and re.search(r"\b\d+(?:\.\d+)?\b", lower)
        and not re.search(r"\b(?:which|what)\s+denominator\b|\b(?:hide|mask|mix|stratif)\w*\b", lower)
    )
    return bool(
        outcome_context
        and exposure_context
        and decision_context
        and metric_intent
        and not simple_arithmetic
    )


def _clean_comparison_option(value: str) -> str:
    cleaned = value.strip(" `\"'()[]{}:-,.?!;")
    cleaned = re.split(
        r"(?i)\s+and\s+(?:tell|show|explain|state|identify|give|walk)\s+(?:me\s+)?",
        cleaned,
        maxsplit=1,
    )[0]
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _comparison_option_is_substantive(value: str) -> bool:
    cleaned = _text(value).strip().lower()
    return bool(
        cleaned
        and cleaned
        not in {
            "it", "them", "those", "these", "the two", "both", "either", "the options",
        }
        and not re.match(
            r"^(?:give|tell|show|explain|state|identify|walk|help|let)\b",
            cleaned,
        )
    )


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


def _comparison_object_refs(
    query: str,
    context_refs: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    text = " ".join(_text(query).split())
    if _CONTEXT_COMPARATIVE_REFERENT_RE.search(text):
        inherited = [
            {"type": _text(item.get("type")) or "comparison-option", "name": _text(item.get("name"))}
            for item in (context_refs or [])
            if isinstance(item, dict)
            and _text(item.get("name"))
            and _text(item.get("name")) != "target named in the latest request"
        ]
        if len(inherited) >= 2:
            return inherited[:8]
    pronoun_compare = re.search(
        r"(?i)\bcompare\s+(?:them|these|those|the\s+two|both)\b",
        text,
    )
    if pronoun_compare:
        declared = []
        for match in re.finditer(
            r"(?:^|[;.!])\s*(?:option|plan|approach|candidate)?\s*"
            r"([A-Z][A-Za-z0-9_.-]{1,40})\s+"
            r"(?=(?:takes|requires|uses|has|costs|needs|removes|reduces|provides|offers|is)\b)",
            text[: pronoun_compare.start()],
        ):
            name = _clean_comparison_option(match.group(1))
            if name and name.lower() not in {item.lower() for item in declared}:
                declared.append(name)
        if 2 <= len(declared) <= 5:
            return [
                {"type": "comparison-option", "name": value}
                for value in declared
            ]
    stated_choice = re.search(
        r"(?i)\b(?:torn|deciding|choosing)\s+between\s+(.{2,100}?)\s+and\s+"
        r"(.{2,100}?)(?=[?.;]|\s+what\s+(?:would|could|should|might)\b|$)",
        text,
    )
    if stated_choice:
        values = [_clean_comparison_option(value) for value in stated_choice.groups()]
        if (
            all(values)
            and all(_comparison_option_is_substantive(value) for value in values)
            and all(1 <= len(value.split()) <= 14 for value in values)
            and values[0].lower() != values[1].lower()
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
    choose_over = re.search(
        r"(?i)\b(?:choose|select|pick|prefer)\s+(.{1,100}?)\s+over\s+"
        r"(?:an|a|the)?\s*(.{2,100}?)(?=\s+of\s+the\s+same\b|,\s*(?:or|and)\b|[?.;]|$)",
        text,
    )
    if choose_over:
        left, right = (_clean_comparison_option(value) for value in choose_over.groups())
        if left.lower() in {"it", "this", "that", "the candidate", "the first"}:
            declared = re.search(
                r"(?i)\b(?:the\s+)?(?:candidate|first\s+(?:candidate|option))\s+is\s+"
                r"(?:an|a|the)?\s*(.{2,100}?)(?=,\s*\d|[.;])",
                text,
            )
            if declared:
                left = _clean_comparison_option(declared.group(1))
            else:
                contextual_names = [
                    _text(item.get("name"))
                    for item in (context_refs or [])
                    if isinstance(item, dict)
                    and _text(item.get("name"))
                    and "current or prior-turn user-named" not in _text(item.get("name")).lower()
                    and _text(item.get("name")) != "target named in the latest request"
                ]
                left = contextual_names[0] if contextual_names else left
        values = [value for value in (left, right) if value and value.lower() not in {"it", "this", "that"}]
        if len(values) == 2 and values[0].lower() != values[1].lower():
            return [{"type": "comparison-option", "name": value} for value in values]
    shared_quantity = re.search(
        r"(?i)^\s*(?:a|an|the)?\s*(.{2,60}?)\s+and\s+(?:a|an|the)?\s*(.{2,60}?)\s+can\s+each\b",
        text,
    )
    if shared_quantity:
        values = [
            _clean_comparison_option(value)
            for value in shared_quantity.groups()
        ]
        if all(values):
            return [{"type": "comparison-option", "name": value} for value in values]
    paired_constructions = re.search(
        r"(?i)\bone\s+(?:uses|has|is\s+built\s+around)\s+(.{2,90}?)(?=\s+at\s+\d|[;,])"
        r"[^;.!?]{0,140}[;,]\s*(?:while\s+)?(?:the\s+)?other\s+(?:uses|has|is\s+built\s+around)\s+"
        r"(.{2,90}?)(?=\s+at\s+\d|[?.!,;]|$)",
        text,
    )
    if paired_constructions:
        values = [
            _clean_comparison_option(value)
            for value in paired_constructions.groups()
        ]
        if all(values):
            return [{"type": "comparison-option", "name": value} for value in values]
    # Preserve the two actual predicates in questions such as "Should the
    # motor ride on the carriage, or stay at the base?" A later instruction
    # like "Compare them and give me the first test" refers back to these
    # alternatives; its pronoun and command are not option names.
    paired_predicate_choice = re.search(
        r"(?i)\bshould\s+(.{3,150}?)\s*,?\s+or\s+(.{3,150}?)(?=[?;]|$)",
        text,
    )
    if paired_predicate_choice:
        values = [
            _clean_comparison_option(value)
            for value in paired_predicate_choice.groups()
        ]
        if (
            all(values)
            and all(_comparison_option_is_substantive(value) for value in values)
            and not re.match(r"(?i)^(?:i|we|you)\b", values[0])
            and all(2 <= len(value.split()) <= 18 for value in values)
            and values[0].lower() != values[1].lower()
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
    difference_between = re.search(
        r"(?i)\b(?:difference|distinction)\s+between\s+(.{2,80}?)\s+and\s+"
        r"(.{2,80}?)(?=\s+(?:for|as|in|at|under|when|where|which|what)\s+|[?.!,;]|$)",
        text,
    )
    if difference_between:
        values = [_clean_comparison_option(value) for value in difference_between.groups()]
        if (
            len(values) == 2
            and values[0].lower() != values[1].lower()
            and all(_comparison_option_is_substantive(value) for value in values)
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
    differs_from = re.search(
        r"(?i)\bhow\s+does\s+(.{2,80}?)\s+differ\s+from\s+"
        r"(.{2,80}?)(?=\s+(?:for|as|in|at|under|when|where|which|what)\s+|[?.!,;]|$)",
        text,
    )
    if differs_from:
        values = [_clean_comparison_option(value) for value in differs_from.groups()]
        if (
            len(values) == 2
            and values[0].lower() != values[1].lower()
            and all(_comparison_option_is_substantive(value) for value in values)
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
    # Prefer the explicit two-option grammar before the broader comma/list
    # grammar. Otherwise trailing deliverables such as "recommend a direction"
    # or "name the first test" can become fake comparison options.
    direct_compare_pair = re.search(
        r"(?i)\bcompare\s+(.{2,80}?)\s+(?:and|with|versus|vs\.?|or)\s+"
        r"(.{2,80}?)(?=\s+(?:for|as|in|at|under|with|which|what|when)\s+|[?.!,;]|$)",
        text,
    )
    if direct_compare_pair:
        values = [_clean_comparison_option(value) for value in direct_compare_pair.groups()]
        if (
            len(values) == 2
            and values[0].lower() != values[1].lower()
            and all("," not in value for value in values)
            and all(_comparison_option_is_substantive(value) for value in values)
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
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
        r"(?i)\bcompare\s+(.{2,80}?)\s+(?:and|with|versus|vs\.?|or)\s+(.{2,80}?)(?=\s+(?:for|as|in|at|under|with|which|what|when)\s+|[?.!,;]|$)",
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
        if len(values) == 2 and all(
            _comparison_option_is_substantive(value) for value in values
        ):
            return [{"type": "comparison-option", "name": value} for value in values]
    return []


def _decision_support_object_refs(query: str) -> List[Dict[str, str]]:
    """Preserve alternatives named inside an ordinary deliberation request."""

    text = " ".join(_text(query).split())
    match = re.search(
        r"(?i)\b(?:decid(?:e|ing)\s+whether|choos(?:e|ing)\s+whether|"
        r"trying\s+to\s+decide\s+whether)\s+(.{2,180}?)\s+or\s+"
        r"(.{2,140}?)(?=[.?!;]|$)",
        text,
    )
    if not match:
        between = re.search(
            r"(?i)\b(?:decid(?:e|ing)|choos(?:e|ing)|torn)\s+between\s+"
            r"(.{2,140}?)\s+and\s+(.{2,140}?)(?=[.?!;]|$)",
            text,
        )
        match = between
    if not match:
        return []

    left, right = (_clean_comparison_option(value) for value in match.groups())
    left = re.sub(
        r"(?i)^(?:(?:i|we)\s+should\s+|(?:my|our|the)\s+.{1,80}?\s+should\s+|to\s+)",
        "",
        left,
    ).strip()
    if re.match(r"(?i)^by\s+", right) and re.search(r"(?i)\s+by\s+", left):
        shared_action = re.split(r"(?i)\s+by\s+", left, maxsplit=1)[0].strip()
        right = f"{shared_action} {right}"
    values = [left, right]
    if (
        not all(_comparison_option_is_substantive(value) for value in values)
        or values[0].lower() == values[1].lower()
        or any(len(value.split()) > 18 for value in values)
    ):
        return []
    return [{"type": "decision-option", "name": value} for value in values]


def _decision_support_concerns(query: str) -> List[str]:
    """Extract only risks or criteria the user explicitly named."""

    text = " ".join(_text(query).split())
    concerns: List[str] = []
    match = re.search(
        r"(?i)\b(?:worried|concerned)\b[^.?!;]{0,100}?\b(?:hide|hides|miss|misses|"
        r"ignore|ignores|understate|understates|overlook|overlooks)\s+"
        r"(.{2,120}?)(?=[.?!;]|$)",
        text,
    )
    if match:
        phrase = match.group(1).strip(" ,")
        shared_suffix = ""
        suffix_match = re.search(r"(?i)\b(risk|cost|time|quality|reliability|margin)\s*$", phrase)
        if suffix_match:
            shared_suffix = suffix_match.group(1).lower()
        for raw in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", phrase):
            value = raw.strip(" ,")
            if shared_suffix and not re.search(rf"(?i)\b{re.escape(shared_suffix)}\b", value):
                value = f"{value} {shared_suffix}"
            if value and len(value.split()) <= 8 and value.lower() not in {item.lower() for item in concerns}:
                concerns.append(value)
    return concerns[:6]


def _comparison_criteria(query: str, refs: Sequence[Dict[str, str]]) -> List[str]:
    text = " ".join(_text(query).split())
    match = re.search(r"(?i)\bcompare\s+(.+?)(?=[?.;]|$)", text)
    candidate = match.group(1).strip() if match else ""
    if candidate:
        candidate = re.split(
            r"(?i),\s*(?:and\s+)?(?:recommend|state|name|identify|give|tell|show|explain)\b",
            candidate,
            maxsplit=1,
        )[0].strip(" ,")
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
    priority_candidate = ""
    for pattern in (
        r"(?i)([^.!?]{2,140}?)\s+matters?\s+more\s+than\s+[^.!?]{1,80}",
        r"(?i)\b(?:care\s+most\s+about|prioriti[sz]e|priority\s+is|priorities\s+are)\s+([^.!?]{2,140})",
    ):
        priority_match = re.search(pattern, text)
        if priority_match:
            priority_candidate = priority_match.group(1).strip(" ,")
            break
    evidence_candidate = ""
    if re.search(r"(?i)\b(?:data(?:sheet)?|evidence|information|measurements?|tests?)\b[^?]{0,160}\benough\b", text):
        evidence_match = re.search(
            r"(?i)\bfor\s+([^?]{2,140}?)(?=,\s*(?:or\s+)?what\s+(?:evidence|data|information|measurements?|tests?)\b|[?])",
            text,
        )
        if evidence_match:
            evidence_candidate = evidence_match.group(1).strip(" ,")
    raw_parts: List[str] = []
    for value in (candidate, priority_candidate, evidence_candidate):
        if value:
            raw_parts.extend(re.split(r"\s*,\s*|\s+and\s+", value))
    ref_names = [str(ref.get("name") or "").lower() for ref in refs if isinstance(ref, dict)]
    criteria: List[str] = []
    for raw in raw_parts:
        value = re.sub(r"(?i)^and\s+", "", raw.strip())
        value = re.sub(r"(?i)^(?:them|these|the options?)\s+(?:on|for|by|across)\s+", "", value)
        value = re.sub(r"(?i)^(?:on|for|by|across)\s+", "", value).strip(" .,:;-")
        value = re.split(
            r"(?i)\s+(?:for|at|under|with)\s+(?=(?:a|an|the)?\s*\d)",
            value,
            maxsplit=1,
        )[0].strip(" .,:;-")
        lower_value = value.lower()
        if not value or len(value.split()) > 12:
            continue
        if any(name and (lower_value == name or name in lower_value) for name in ref_names):
            continue
        if lower_value in {"them", "these", "the options", "both"}:
            continue
        if lower_value not in {item.lower() for item in criteria}:
            criteria.append(value)
    # Comparative adjectives express the decision operation, not a measurable
    # criterion. Treating "better" or "stronger" as an axis makes a complete
    # mechanism-based answer fail merely because it does not repeat that word.
    return criteria[:10]


_REPRESENTATION_SEMANTICS_SIGNAL_RE = re.compile(
    r"\b(?:file\s+formats?|formats?|representations?|encodings?|schemas?|"
    r"seriali[sz](?:ation|ed|ing)?|interchange|round[- ]?trip|import(?:er|ing)?|"
    r"export(?:er|ing)?|mesh(?:es)?|raster|vector|source\s+code|bytecode|"
    r"native\s+(?:file|format|model|document)|authoring\s+(?:file|format|model)|"
    r"feature\s+history|design\s+intent|editability|later\s+editing|"
    r"application\s+data\s+model|lossy|lossless)\b",
    flags=re.IGNORECASE,
)
_REPRESENTATION_NAME_RE = re.compile(
    r"^(?:[A-Z0-9]{2,8}|Protocol\s+Buffers?|compiled\s+bytecode|source\s+code|"
    r"(?:native|interchange|derived)\s+.{1,40})$"
)


def _representation_semantic_family(query: str, options: Sequence[str]) -> str:
    """Classify the layer vocabulary without assigning facts to either option."""

    text = " ".join([_text(query), *[_text(item) for item in options]]).lower()
    families = (
        (
            "geometry",
            r"\b(?:cad|step|stp|stl|mesh|brep|b-rep|geometry|geometric|solid\s+model)\b",
        ),
        (
            "data-serialization",
            r"\b(?:json|protocol\s+buffers?|protobuf|seriali[sz]|application\s+data\s+model|"
            r"wire\s+format|field\s+number|unknown[- ]field)\b",
        ),
        (
            "document",
            r"\b(?:docx?|pdf|document|word\s+processing|page\s+layout)\b",
        ),
        (
            "image",
            r"\b(?:svg|png|jpe?g|gif|tiff|raster|vector|logo|image|pixel)\b",
        ),
        (
            "program",
            r"\b(?:source\s+code|bytecode|compiled|executable|binary\s+program|decompil)\b",
        ),
    )
    scores = [
        (len(re.findall(pattern, text, flags=re.IGNORECASE)), family)
        for family, pattern in families
    ]
    score, family = max(scores, default=(0, "general"))
    return family if score else "general"


def _representation_semantics_contract(
    query: str,
    refs: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    """Describe representation reasoning without assigning facts to formats."""

    options = [
        _text(item.get("name")).strip()
        for item in refs
        if isinstance(item, dict)
        and item.get("type") in {"comparison-option", "decision-option"}
        and _text(item.get("name")).strip()
    ]
    if len(options) < 2:
        return {}
    signal = bool(_REPRESENTATION_SEMANTICS_SIGNAL_RE.search(_text(query)))
    name_pair_signal = all(
        _REPRESENTATION_NAME_RE.fullmatch(option.strip()) for option in options[:2]
    )
    if not (signal or name_pair_signal):
        return {}
    semantic_family = _representation_semantic_family(query, options)
    family_vocabulary = {
        "geometry": ["geometry", "topology", "facets", "curves and surfaces", "feature history", "CAD toolchain"],
        "data-serialization": ["fields", "values", "identifiers", "application meaning", "schema evolution", "producer and consumer"],
        "document": ["document structure", "layout", "styles", "fonts", "pagination", "editing application"],
        "image": ["vectors", "pixels", "resolution", "color", "layers", "graphics toolchain"],
        "program": ["instructions", "symbols", "types", "control structure", "compiler", "runtime"],
        "general": ["stored content", "source state", "conversion", "importer", "exporter", "toolchain"],
    }
    family_method = {
        "geometry": [
            "Separate exact or faceted stored geometry from native feature construction and constraints.",
            "Describe reconstruction and later editing through the actual CAD importer/exporter path.",
        ],
        "data-serialization": [
            "Separate syntax-level names, identifiers, primitive values, and schema fields from application meaning, invariants, and runtime behavior.",
            "Explicitly state that the serialized payload is separate from the live application model and runtime state.",
            "A readable name does not preserve application meaning. Frame compatibility as a relationship between potentially different producer and consumer schema versions whose field changes follow the applicable rules.",
            "When evolution matters, cover backward and forward compatibility, unknown members, and identifier reuse without promising exact parsing or no data loss. Avoid the words required and optional in source-free representation explanations because those labels belong to an applicable schema, profile, syntax, or edition.",
            "For every named representation, separately cover backward compatibility, forward compatibility, unknown-member handling, and identifier-reuse behavior instead of letting one option stand in for the whole comparison.",
            "Define backward compatibility only as a newer reader consuming older payloads and forward compatibility only as an older reader consuming newer payloads before applying those directions to each representation; do not add a promise of no error or failure to either definition.",
            "Describe compatibility, unknown-member, and identifier-reuse consequences as conditional on the applicable schema and implementation unless evidence establishes an inevitable result.",
            "Ignoring or skipping an unknown member does not prove whether a later serializer preserves or drops it; bind that behavior to the specific runtime or toolchain.",
            "A missing member is absent rather than an unknown member available to ignore; describe absence through the applicable schema and consumer behavior.",
            "Keep reader roles attached to the direction: backward uses a newer reader with an older payload, while forward uses an older reader with a newer payload.",
        ],
        "document": [
            "Separate editable document structure from rendered appearance and from the source application's private editing state.",
            "Describe font, layout, pagination, and re-editing behavior through the specific document toolchain.",
        ],
        "image": [
            "Separate vector or pixel content from editor layers, effects, and source-document state.",
            "Describe scaling, rasterization, color, and later editing through the graphics toolchain.",
        ],
        "program": [
            "Separate stored instructions and symbols from source-level names, types, comments, and build state.",
            "Describe recompilation or reconstruction through the compiler, runtime, and available symbol information.",
        ],
        "general": [
            "Separate stored content from source state and describe recovery through the actual toolchain.",
        ],
    }
    forbidden_vocabulary = {
        "geometry": ["unknown fields", "field reuse", "bytecode", "pagination"],
        "data-serialization": ["design intent", "feature history", "sketch constraints", "parametric history", "CAD geometry", "source history"],
        "document": ["triangle facets", "unknown fields", "field reuse", "bytecode", "parametric history"],
        "image": ["feature history", "unknown fields", "field reuse", "bytecode", "pagination"],
        "program": ["triangle facets", "unknown fields", "field reuse", "pagination", "pixel resolution"],
        "general": [],
    }
    return {
        "kind": "representation-semantics-contract",
        "version": 2,
        "scope": "comparison-reasoning",
        "semanticFamily": semantic_family,
        "familyVocabulary": family_vocabulary.get(
            semantic_family,
            family_vocabulary["general"],
        ),
        "familyMethod": family_method.get(
            semantic_family,
            family_method["general"],
        ),
        "forbiddenFamilyVocabulary": forbidden_vocabulary.get(
            semantic_family,
            forbidden_vocabulary["general"],
        ),
        "layers": [
            "native-authoring-or-runtime-state",
            "stored-interchange-or-serialized-payload",
            "derived-or-lossy-delivery-representation",
            "import-export-schema-profile-and-toolchain-behavior",
        ],
        "requiredDistinctions": [
            "Classify what each representation actually stores instead of inferring behavior from its name.",
            "Separate native authoring or runtime state from an interchange, serialized, or derived payload.",
            "Separate what a standard or schema permits from what a particular exporter, importer, profile, or toolchain preserves.",
            "State the round-trip, conversion-loss, and later-editing boundary relevant to the user's objective.",
            "When using exact, lossless, or self-describing, name the layer: bytes or lexical form, decoded values, schema-defined meaning, or native application semantics.",
            "For versioned schemas, separate backward and forward compatibility, unknown-field behavior, and field reuse from a blanket synchronized-version requirement.",
        ],
        "forbiddenInferences": [
            "editable-means-native-history-preserved",
            "geometry-or-data-present-means-source-constraints-or-behavior-preserved",
            "standard-permits-metadata-means-every-export-contains-it",
            "successful-import-means-lossless-round-trip",
            "syntactically-self-describing-means-application-semantics-are-self-describing",
            "compatible-schema-evolution-requires-identical-synchronized-schema-versions",
        ],
    }


def _decision_axes(value: str) -> List[Dict[str, str]]:
    """Extract user-stated decision priorities without assigning option facts."""

    text = _text(value).lower()
    rows: List[Dict[str, str]] = []
    for axis, terms in _DECISION_AXIS_TERMS.items():
        matches = [term for term in terms if _has(text, (term,))]
        if matches:
            rows.append({"axis": axis, "signal": matches[0]})
    return rows


def _decision_quantities(values: Sequence[str]) -> List[str]:
    quantities: List[str] = []
    for value in values:
        for match in _DECISION_QUANTITY_RE.finditer(_text(value)):
            quantity = re.sub(r"\s+", " ", match.group(0)).strip()
            if quantity.lower() not in {item.lower() for item in quantities}:
                quantities.append(quantity)
    return quantities[:16]


def _compute_system_decision_shape(text: str, option_count: int = 0) -> bool:
    """Recognize platform choices defined by a compute workload, not product keywords."""

    lower = _text(text).lower()
    return bool(
        option_count >= 2
        and _has(
            lower,
            (
                "local box",
                "local server",
                "compute server",
                "host machine",
                "inference",
                "workload",
                "camera streams",
                "video streams",
                "command center",
            ),
        )
        and _has(
            lower,
            (
                "run",
                "watch",
                "process",
                "detect",
                "detection",
                "display",
                "monitor",
                "host",
                "should i use",
                "which should",
            ),
        )
    )


def decision_preflight_clarifying_question(
    messages: Sequence[Dict[str, Any]],
    brief: Optional[Dict[str, Any]],
) -> str:
    """Ask one workload-closing question before comparing unsupported platform capabilities."""

    decision = brief if isinstance(brief, dict) else {}
    if decision.get("decisionContext") != "compute-workload":
        return ""
    options = [_text(value) for value in decision.get("options") or [] if _text(value)]
    if len(options) < 2:
        return ""
    user_text = "\n".join(
        _message_text(message)
        for message in messages or []
        if _text(message.get("role")).lower() == "user" and _message_text(message)
    )
    lower = user_text.lower()
    resolution_known = bool(
        re.search(r"\b\d{3,4}\s*p\b", lower)
        or re.search(r"\b\d{3,5}\s*[x×]\s*\d{3,5}\b", lower)
        or _has(lower, ("resolution is", "at 720p", "at 1080p", "at 1440p", "at 4k"))
    )
    frame_rate_known = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:fps|frames? per second)\b", lower))
    concurrency_known = _has(
        lower,
        (
            "simultaneously",
            "concurrently",
            "at the same time",
            "all streams at once",
            "all cameras at once",
            "one at a time",
            "sequentially",
        ),
    )
    performance_target_known = bool(
        re.search(r"\b(?:under|within|less than|max(?:imum)?)\s+\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?)\b", lower)
        or _has(
            lower,
            (
                "alert latency",
                "detection latency",
                "minimum accuracy",
                "false positive",
                "missed detection",
                "yolo",
                "model size",
                "inference model",
            ),
        )
    )
    if concurrency_known and performance_target_known and resolution_known and frame_rate_known:
        return ""
    if len(options) == 2:
        option_text = f"{options[0]} and {options[1]}"
    else:
        option_text = ", ".join(options[:-1]) + f", and {options[-1]}"
    camera_count = next(
        (
            match.group(0)
            for match in re.finditer(
                r"\b\d+(?:\.\d+)?\s+(?:printer\s+)?(?:cameras?|streams?)\b",
                lower,
            )
        ),
        "the camera streams",
    )
    camera_display = (
        f"the {camera_count}"
        if re.match(r"^\d", camera_count)
        else camera_count
    )
    if not resolution_known or not frame_rate_known:
        return (
            f"Before I choose among {option_text}, what resolution and analyzed frame rate should each of "
            f"{camera_display} use, and do they all need inference at the same time?"
        )
    if not concurrency_known and not performance_target_known:
        return (
            f"That narrows it. Before I choose among {option_text}, do all {camera_count} need inference at the same time, "
            "and what maximum alert latency or minimum detection performance should the system meet?"
        )
    if not concurrency_known:
        return (
            f"That narrows it. Before I choose among {option_text}, do all {camera_count} need inference at the same time?"
        )
    return (
        f"That narrows it. Before I choose among {option_text}, what maximum alert latency or minimum detection performance should the system meet?"
    )


def _axis_is_priority_change(
    text: str,
    axis_row: Dict[str, str],
    prior_axis_names: set[str],
    allow_new_axis: bool = True,
) -> bool:
    lower = _text(text).lower()
    signal = re.escape(_text(axis_row.get("signal")).lower())
    if not signal:
        return False
    clause = next(
        (
            part
            for part in re.split(r"[.;?!]|\band\b|\bbut\b", lower)
            if re.search(rf"(?<![a-z0-9]){signal}(?![a-z0-9])", part)
        ),
        lower,
    )
    preference_match = re.search(
        rf"\b(?:want|prefer)\b(?P<bridge>[^.;?!]{{0,90}})"
        rf"(?<![a-z0-9]){signal}(?![a-z0-9])",
        lower,
    )
    preference_is_task_assignment = bool(
        preference_match
        and re.search(
            r"\bto\s+(?:watch|detect|monitor|control|run|process|display|drive|host|inspect|track)\b",
            preference_match.group("bridge"),
        )
    )
    explicitly_weighted = bool(
        (
            preference_match
            and not preference_is_task_assignment
        )
        or re.search(
            rf"\b(?:prioriti[sz]e|care\s+most\s+about|most\s+important)\b[^.;?!]{{0,90}}"
            rf"(?<![a-z0-9]){signal}(?![a-z0-9])",
            lower,
        )
        or re.search(
            rf"(?<![a-z0-9]){signal}(?![a-z0-9])[^.;?!]{{0,50}}"
            r"\b(?:matters?\s+more|is\s+more\s+important|is\s+(?:a\s+)?priority)\b",
            lower,
        )
    )
    comparative_signal = _text(axis_row.get("signal")).lower() in {
        "low power", "lower power", "quiet", "quieter", "silent", "lightweight", "compact",
    }
    condition_with_value = bool(_DECISION_QUANTITY_RE.search(clause))
    return bool(
        explicitly_weighted
        or comparative_signal
        or (
            allow_new_axis
            and axis_row.get("axis") not in prior_axis_names
            and not condition_with_value
        )
    )


def build_decision_brief(
    messages: Sequence[Dict[str, Any]],
    frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Represent a decision turn without supplying product facts or a winner.

    The brief makes the user's operating point and priority changes explicit so
    the worker can reason from one stable comparison frame. It intentionally
    does not score options; that remains the reasoning worker's job.
    """

    frame = dict(frame or {})
    structural_frame = frame
    if not frame.get("objectRefs") or not frame.get("comparisonCriteria"):
        generic_frame = build_generic_intent_frame(messages, cwd=_text(frame.get("cwd")))
        if generic_frame:
            structural_frame = {
                **generic_frame,
                **frame,
                "objectRefs": frame.get("objectRefs") or generic_frame.get("objectRefs") or [],
                "comparisonCriteria": (
                    frame.get("comparisonCriteria")
                    or generic_frame.get("comparisonCriteria")
                    or []
                ),
                "contextRelation": frame.get("contextRelation") or generic_frame.get("contextRelation"),
                "contextScope": frame.get("contextScope") or generic_frame.get("contextScope"),
            }
    scoped = scope_messages_for_intent(messages, structural_frame)
    user_turns = [
        _message_text(message)
        for message in scoped
        if _text(message.get("role")).lower() == "user" and _message_text(message)
    ]
    if not user_turns:
        return {}
    latest = user_turns[-1]
    prior_turns = user_turns[:-1]
    latest_axes = _decision_axes(latest)
    prior_axes = _decision_axes("\n".join(prior_turns))
    criteria = [
        _text(item)
        for item in (structural_frame.get("comparisonCriteria") or [])
        if _text(item)
    ][:10]
    options: List[str] = []
    for item in structural_frame.get("objectRefs") or []:
        if not isinstance(item, dict):
            continue
        ref_type = _text(item.get("type")).lower()
        name = _text(item.get("name"))
        if (
            not name
            or name == "target named in the latest request"
            or "current or prior-turn user-named" in name.lower()
            or ref_type in {"public-source", "local-or-attached-file"}
            or name.lower() in {value.lower() for value in options}
        ):
            continue
        options.append(name)
    prior_quantities = _decision_quantities(prior_turns)
    latest_quantities = _decision_quantities([latest])
    operating_constraints = [*prior_quantities]
    for value in latest_quantities:
        if value.lower() not in {item.lower() for item in operating_constraints}:
            operating_constraints.append(value)
    changed_conditions = [
        value
        for value in latest_quantities
        if value.lower() not in {item.lower() for item in prior_quantities}
    ]
    prior_axis_names = {item["axis"] for item in prior_axes}
    changed_weights = [
        item
        for item in latest_axes
        if _axis_is_priority_change(
            latest,
            item,
            prior_axis_names,
            allow_new_axis=structural_frame.get("contextRelation") == "follow-up",
        )
    ]
    explicit_priorities: List[Dict[str, str]] = []
    for turn in user_turns:
        for item in _decision_axes(turn):
            if (
                _axis_is_priority_change(
                    turn,
                    item,
                    set(),
                    allow_new_axis=False,
                )
                and item not in explicit_priorities
            ):
                explicit_priorities.append(item)
    comparison_axes: List[str] = []
    for value in [*criteria, *(item["axis"] for item in prior_axes), *(item["axis"] for item in latest_axes)]:
        if value and value.lower() not in {item.lower() for item in comparison_axes}:
            comparison_axes.append(value)
    decision_domains = {
        "decision_support",
        "engineering_advisory",
        "engineering_power_conversion",
        "engineering_tradeoff",
        "knowledge_comparison",
        "material_process_behavior",
        "technical_compatibility",
    }
    decision_context = (
        "compute-workload"
        if _compute_system_decision_shape("\n".join(user_turns), len(options))
        else "general"
    )
    decision_shape = bool(
        len(options) >= 2
        or criteria
        or structural_frame.get("actionType")
        in {
            "compare_decision_factors",
            "reason_about_decision",
            "reassess_engineering_conclusion_with_new_constraints",
        }
        or structural_frame.get("domain")
        in {"engineering_tradeoff", "knowledge_comparison", "technical_compatibility"}
    )
    if not decision_shape or (
        frame.get("domain") not in decision_domains
        and structural_frame.get("domain") not in decision_domains
    ):
        return {}
    unresolved_axes = list(comparison_axes)
    if options and operating_constraints:
        unresolved_axes.append("option capability at the same stated operating point")
    if any(item["axis"] in {"acoustics", "thermal/cooling", "power/efficiency"} for item in latest_axes):
        unresolved_axes.append("exact implementation and complete-system behavior")
    unresolved_axes = list(dict.fromkeys(unresolved_axes))[:10]
    explanatory_comparison = (
        structural_frame.get("comparisonSpeechAct") == "explanation"
    )
    if explanatory_comparison:
        highest_leverage = ""
    elif decision_context == "compute-workload":
        user_context = "\n".join(user_turns).lower()
        has_resolution_and_rate = bool(
            re.search(r"\b\d{3,4}\s*p\b", user_context)
            and re.search(r"\b\d+(?:\.\d+)?\s*(?:fps|frames? per second)\b", user_context)
        )
        highest_leverage = (
            "whether all streams require simultaneous inference and the acceptable alert latency or detection target"
            if has_resolution_and_rate
            else "camera resolution, analyzed frame rate, and whether all streams require simultaneous inference"
        )
    elif options and operating_constraints:
        highest_leverage = (
            "minimum acceptable task performance at the stated operating point; optimize secondary "
            "priorities only among options that clear it"
        )
    elif "cost" in comparison_axes and not any("$" in value for value in user_turns):
        highest_leverage = "budget or total-cost ceiling that would eliminate an option"
    elif options:
        highest_leverage = "success criterion or failure condition that would make one option preferable"
    elif comparison_axes:
        highest_leverage = "required outcome and the condition that would reverse the conclusion"
    else:
        highest_leverage = "the one pass/fail requirement that defines success"
    return {
        "objective": latest[:500],
        "decisionType": "follow-up" if structural_frame.get("contextRelation") == "follow-up" else "standalone",
        "decisionContext": decision_context,
        "options": options[:8],
        "userSuppliedOperatingConstraints": operating_constraints,
        "changedOperatingConditions": changed_conditions,
        "explicitPriorities": explicit_priorities[:12],
        "changedPriorityWeights": changed_weights[:8],
        "comparisonAxesToHoldStable": comparison_axes[:10],
        "unresolvedAxes": unresolved_axes,
        "decisionRequested": not explanatory_comparison,
        "responseMode": (
            "explanation" if explanatory_comparison else "decision-comparison"
        ),
        "highestLeverageMissingInput": highest_leverage,
        "clarificationPolicy": (
            "Answer the requested distinctions directly; do not ask for a preference, choose a winner, add a reversal condition, or prescribe a validation test unless the user requests one."
            if explanatory_comparison
            else
            "Ask about the highest-leverage input only if no bounded recommendation is possible; "
            "otherwise state the working assumption and what would reverse the choice."
        ),
        "evidenceBoundary": "This brief contains user-stated decision structure only; it supplies no option facts or winner.",
    }


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


def _missing_local_artifact_inputs(
    query: str,
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Recognize an authorized file task whose source artifacts are absent."""

    if (
        _prior_substantive_context(messages)
        or _has_message_attachments(messages)
        or _urls(query)
        or _file_refs(query)
    ):
        return False
    normalized = re.sub(r"[^a-z0-9\s-]", " ", query.lower())
    normalized = " ".join(normalized.split())
    action = bool(
        re.search(
            r"\b(?:compare|inspect|review|merge|diff|update|edit|revise|repair|"
            r"summarize|convert|rewrite)\b",
            normalized,
        )
    )
    artifact_noun = (
        r"(?:files?|configs?|documents?|spreadsheets?|workbooks?|images?|"
        r"models?|drawings?|archives?)"
    )
    # Keep the missing identity grammatically bound to the artifact. A long
    # engineering request may contain unrelated words such as "these",
    # "model", or "all configurations" without referring to absent files.
    unidentified_artifact = bool(
        re.search(
            rf"\b(?:two|both|all|these|those|older|newer|other|original|revised|"
            rf"first|second)\s+(?:[a-z0-9_-]+\s+){{0,2}}{artifact_noun}\b",
            normalized,
        )
        or re.search(
            r"\b(?:the|a)\s+(?:source\s+)?(?:file|config|document|spreadsheet|"
            r"workbook|image|drawing|archive)\b",
            normalized,
        )
    )
    return bool(action and unidentified_artifact)


def _strength_improvement_without_context(
    query: str,
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Recognize a strength request whose object and success criterion are absent."""

    if (
        _prior_substantive_context(messages)
        or _has_message_attachments(messages)
        or _urls(query)
        or _file_refs(query)
    ):
        return False
    normalized = re.sub(r"[^a-z0-9\s-]", " ", query.lower())
    normalized = " ".join(normalized.split())
    if len(normalized.split()) > 16:
        return False
    asks_for_strength = bool(
        re.search(
            r"\b(?:make|redesign|change|improve|strengthen|reinforce)\b[^.?!]{0,50}"
            r"\b(?:stronger|strength|stiffer|stiffness|reinforced?)\b|"
            r"\b(?:strengthen|reinforce)\s+(?:it|this|that)\b",
            normalized,
        )
    )
    named_target = bool(
        re.search(
            r"\b(?:part|bracket|mount|duct|blade|rotor|shaft|beam|frame|housing|"
            r"panel|joint|fastener|material|profile|file|model|printer|assembly)\b",
            normalized,
        )
    )
    return asks_for_strength and not named_target


def _correction_request_shape(query: str) -> bool:
    """Recognize a request to revisit an earlier answer without inferring its domain."""

    normalized = re.sub(r"\s+", " ", _text(query).lower()).strip()
    if not normalized:
        return False
    refers_to_missing_answer = bool(
        re.search(
            r"\b(?:that|the|your|previous|last)\s+(?:answer|response|analysis|explanation)\b|"
            r"\bwhat\s+you\s+(?:said|told\s+me)\b",
            normalized,
        )
    )
    asks_for_correction = bool(
        re.search(
            r"\b(?:missed|misunderstood|wrong|incorrect|not\s+what\s+i\s+(?:asked|meant)|"
            r"slow\s+down|rethink|reason\s+from|look\s+again|try\s+again|correct)\b",
            normalized,
        )
    )
    return bool(refers_to_missing_answer and asks_for_correction)


def _context_dependent_correction_without_context(
    query: str,
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Catch corrections that refer to an answer or system absent from the thread."""

    if (
        _prior_substantive_context(messages)
        or _has_message_attachments(messages)
        or _urls(query)
        or _file_refs(query)
    ):
        return False
    return _correction_request_shape(query)


def _contextual_correction_with_context(
    query: str,
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Carry a real correction into the established topic instead of restarting."""

    return bool(_prior_substantive_context(messages) and _correction_request_shape(query))


def _positive_feedback_signals(value: str) -> set[str]:
    """Extract what the user is positively reinforcing, independent of exact wording."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if not normalized:
        return set()
    signals: set[str] = set()
    if re.search(
        r"^(?:thanks|thank\s+you|i\s+appreciate|much\s+appreciated|"
        r"nice|perfect|spot\s+on|great\s+work|good\s+work)\b",
        normalized,
    ):
        signals.add("appreciation")
    if re.search(
        r"\b(?:that|this)\s+(?:helps|helped|was\s+(?:useful|helpful)|makes\s+sense)\b",
        normalized,
    ):
        signals.add("useful")
    if re.search(
        r"\b(?:verified\s+facts?|facts?)\b.*\b(?:assumptions?|inference)\b|"
        r"\b(?:assumptions?|inference)\b.*\b(?:verified\s+facts?|facts?)\b",
        normalized,
    ):
        signals.add("evidence-boundary")
    if re.search(r"\b(?:caught|noticed|found|spotted)\b.*\b(?:missed|overlooked|important|mattered)\b", normalized):
        signals.add("insight")
    if re.search(
        r"\b(?:closer\s+to\s+how\s+i\s+(?:think|work)|how\s+i\s+think|"
        r"exactly\s+what\s+i\s+(?:needed|wanted)|hoping\s+for|hit\s+the\s+mark)\b",
        normalized,
    ):
        signals.add("working-fit")
    calibration_language = re.search(
        r"\b(?:measured|balanced|nuanced|didn'?t\s+(?:oversell|overstate|force)|"
        r"without\s+(?:overselling|overstating|forcing)|not\s+trying\s+to\s+sell)\b",
        normalized,
    )
    feedback_subject = re.search(
        r"\b(?:answer|response|explanation|recommendation|conclusion|felt|way\s+you|you\s+were)\b",
        normalized,
    )
    if calibration_language and feedback_subject:
        signals.add("calibration")
    if re.search(r"\b(?:clear|clarity|depth|thorough|well\s+reasoned|thoughtful)\b", normalized):
        signals.add("clarity-depth")
    if re.search(r"\b(?:this|that)\s+is\s+(?:better|right|much\s+better)\b", normalized):
        signals.add("improvement")
    return signals


def _social_acknowledgement_turn(value: str) -> bool:
    """Recognize a complete low-information social turn without swallowing a follow-up ask."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if not normalized or len(normalized.split()) > 30 or "?" in normalized:
        return False
    acknowledgement = bool(_positive_feedback_signals(normalized))
    followup_ask = bool(
        re.search(
            r"\b(?:but|however|now|next|also|can\s+you|could\s+you|would\s+you|"
            r"will\s+you|please|fix|change|create|find|compare|calculate|explain|"
            r"keep\s+going|continue|proceed|carry\s+on|go\s+ahead|let'?s\s+do|"
            r"what(?:'s|\s+is)\s+next)\b",
            normalized,
        )
    )
    return bool(acknowledgement and not followup_ask)


def _social_acknowledgement_response(value: str) -> str:
    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    signals = _positive_feedback_signals(normalized)
    if "evidence-boundary" in signals:
        return "I'm glad that distinction helped. I'll keep separating what we know from what we're inferring, especially when the recommendation depends on it."
    if "insight" in signals:
        return "Good. I'm glad we caught the part that mattered. I'll keep looking for the detail that changes the answer, not just the obvious surface."
    if "calibration" in signals:
        return "Good. I'll keep the recommendation direct without pretending the evidence is stronger than it is."
    if "working-fit" in signals and re.search(r"\b(?:closer|how\s+i\s+think)\b", normalized):
        return "That's useful feedback. I'll keep meeting the problem at that level instead of flattening it into a canned answer."
    if re.search(r"\b(?:exactly|hoping\s+for|needed|wanted|hit\s+the\s+mark)\b", normalized):
        return "I'm glad that landed, Tinman. I'll keep that same level of clarity and depth as we move forward."
    if re.search(r"\b(?:helps|helped|makes\s+sense)\b", normalized):
        return "Good. I'm glad it helped, Tinman. We'll keep the next step just as clear."
    if re.search(r"\b(?:great|good|perfect)\b", normalized):
        return "Thank you, Tinman. That is a useful signal about what is working, and I'll carry it forward."
    return "You're welcome, Tinman. We'll keep moving from here."


def _recurrent_problem_reengagement(
    value: str,
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Recognize a returned problem that needs presence and one context question."""

    if _prior_substantive_context(messages):
        return False
    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    frustration = bool(
        re.search(
            r"\b(?:frustrated|annoyed|discouraged|fed\s+up|back\s+to\s+this|"
            r"thought\s+(?:we|i)\s+(?:had\s+)?fixed)\b",
            normalized,
        )
    )
    recurrence = bool(
        re.search(
            r"\b(?:came\s+back|has\s+come\s+back|returned|is\s+back|happening\s+again|"
            r"failed\s+again|recurr(?:ed|ing)|after\s+.+\s+fixed)\b",
            normalized,
        )
    )
    collaborative_ask = bool(
        re.search(
            r"\b(?:second\s+set\s+of\s+eyes|fresh\s+(?:look|pass)|help\s+me|"
            r"could\s+use\s+(?:your\s+)?help|work\s+through\s+it)\b",
            normalized,
        )
    )
    return bool(frustration and recurrence and collaborative_ask)


def _recurrent_problem_reengagement_response(value: str) -> str:
    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if "fan" in normalized:
        question = "What machine or enclosure is this, and what exactly does the fan do when the problem returns?"
    elif "printer" in normalized:
        question = "Which printer is this, and what exactly happens when the problem returns?"
    else:
        question = "What machine or system is this, and what exactly happens when the problem returns?"
    return "That is frustrating, especially after it looked fixed. I'll take a fresh pass with you. " + question


def _interaction_stance(value: str) -> Dict[str, Any]:
    """Capture conversational posture without allowing it to redefine the task."""

    text = re.sub(r"\s+", " ", _text(value)).strip()
    lower = text.lower()
    greeting = ""
    if re.search(r"\b(?:good\s+)?morning\b", lower):
        greeting = "morning"
    elif re.search(r"\bgood\s+afternoon\b", lower):
        greeting = "afternoon"
    elif re.search(r"\bgood\s+evening\b", lower):
        greeting = "evening"
    elif re.match(r"^(?:hello|hi|hey)\b", lower):
        greeting = "hello"

    affect = "neutral"
    if re.search(r"\b(?:frustrated|fed\s+up|annoyed|tired\s+of|fighting\s+(?:it|this)|chasing\s+this)\b", lower):
        affect = "frustrated"
    elif re.search(r"\b(?:overwhelmed|scattered|too\s+many\s+directions|cannot\s+focus|can't\s+focus)\b", lower):
        affect = "overwhelmed"
    elif re.search(r"\b(?:disappointed|let\s+down|discouraged|unacceptable)\b", lower):
        affect = "disappointed"
    elif re.search(r"\b(?:excited|looking\s+forward|can't\s+wait|cannot\s+wait|this\s+is\s+fun)\b", lower):
        affect = "excited"
    elif re.search(
        r"\b(?:not\s+sure|uncertain|worried|concerned|second[- ]guessing|not\s+convinced|wondering\s+whether)\b",
        lower,
    ):
        affect = "uncertain"

    proposal_stance = "none"
    if re.search(
        r"\b(?:first\s+instinct|my\s+instinct|i\s+think|i\s+suspect|my\s+guess|"
        r"not\s+convinced|worried\s+that|concerned\s+that|push\s+back|am\s+i\s+missing|"
        r"solving\s+the\s+wrong\s+problem|optimizing\b[^.!?]{0,80}\bmissing)\b",
        lower,
    ):
        proposal_stance = "tentative-hypothesis"
    elif re.search(r"\b(?:i(?:'m|\s+am)\s+convinced|obviously|definitely\s+the\s+answer)\b", lower):
        proposal_stance = "strong-view"

    collaboration = bool(
        re.search(
            r"\b(?:help\s+me|work\s+(?:with\s+me|through)|think\s+(?:it|this)\s+through|"
            r"what\s+would\s+you\s+do|will\s+you|would\s+you|push\s+back)\b",
            lower,
        )
    )
    investment_match = re.search(
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
        r"(?:hours?|days?|mornings?|afternoons?|evenings?|weekends?|weeks?|months?)\b",
        lower,
    )
    investment = investment_match.group(0) if investment_match else ""
    if not investment:
        day_investment = re.search(
            r"\b(?:most\s+of\s+today|all\s+day|this\s+(?:morning|afternoon|evening))\b",
            lower,
        )
        investment = day_investment.group(0) if day_investment else ""
    if re.search(r"\b(?:before\s+i\s+spend|spend\s+more|waste\s+money|commit\s+money|buy\s+parts?)\b", lower):
        investment = f"{investment}; money".strip("; ")

    posture: List[str] = []
    if affect in {"frustrated", "disappointed"}:
        posture.extend(["acknowledge-once", "steady-and-practical"])
    elif affect == "overwhelmed":
        posture.extend(["reduce-cognitive-load", "choose-one-next-move"])
    elif affect == "excited":
        posture.append("share-energy-without-overselling")
    if proposal_stance == "tentative-hypothesis":
        posture.append("test-the-proposal-without-dismissing-it")
    elif proposal_stance == "strong-view":
        posture.append("disagree-clearly-when-evidence-requires")
    if collaboration:
        posture.append("work-alongside-the-user")
    if greeting:
        posture.append("return-the-greeting-briefly")
    result = {
        "greeting": greeting,
        "affect": affect,
        "proposalStance": proposal_stance,
        "collaborativeAsk": collaboration,
        "investmentCue": investment,
        "responsePosture": list(dict.fromkeys(posture)),
    }
    if (
        not greeting
        and affect == "neutral"
        and proposal_stance == "none"
        and not collaboration
        and not investment
        and not posture
    ):
        return {}
    return result


def _mixed_evidence_review_intake(value: str) -> bool:
    """Recognize a request to reconcile evidence before modifying a design."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if not normalized:
        return False
    evidence_families = sum(
        bool(re.search(pattern, normalized))
        for pattern in (
            r"\b(?:cad|model|assembly|drawing|blueprint|schematic)\b",
            r"\b(?:test\s+(?:notes?|results?|data)|measurements?|inspection\s+notes?)\b",
            r"\b(?:supplier|vendor|manufacturer)\s+(?:drawing|print|spec|document)",
            r"\b(?:manuals?|datasheets?|specifications?|requirements?)\b",
        )
    )
    conflict = bool(
        re.search(
            r"\b(?:contradictory|conflicting|disagree|(?:does|do(?:es)?n'?t|do\s+not)\s+match|mismatch|"
            r"inconsistent|which\s+(?:one|source)\s+to\s+trust|untangle)\b",
            normalized,
        )
    )
    asks_for_review = bool(
        re.search(
            r"\b(?:second\s+set\s+of\s+eyes|help\s+me|how\s+would\s+you\s+help|"
            r"review|reconcile|compare|untangle|sort\s+(?:it|this)\s+out)\b",
            normalized,
        )
    )
    design_hold = bool(
        re.search(
            r"\b(?:before\s+i\s+(?:make|machine|print|order|build)|before\s+(?:making|machining|printing|ordering|building)|"
            r"before\s+(?:the\s+)?next\s+(?:part|revision|prototype))\b",
            normalized,
        )
    )
    return bool(evidence_families >= 2 and conflict and asks_for_review and design_hold)


def _unspecified_multi_item_prioritization(value: str) -> bool:
    """Recognize a real prioritization request that omits the options to rank."""

    text = _text(value)
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if not normalized:
        return False
    has_multiple_items = bool(
        re.search(
            r"\b(?:two|three|four|five|several|multiple|a few|\d+)\s+"
            r"(?:(?:half[- ]finished|unfinished|open|active)\s+)?"
            r"(?:[a-z][a-z-]*\s+){0,2}"
            r"(?:projects?|tasks?|options?|initiatives?|repairs?|jobs?|directions?|paths?)\b",
            normalized,
        )
        or _named_prioritization_list(text)
    )
    asks_to_prioritize = bool(
        re.search(
            r"\b(?:competing\s+for\s+(?:my\s+)?attention|prioriti[sz]e|"
            r"decide\s+(?:which|what)|choose\s+(?:which|what)|which\s+.+\s+first|"
            r"decide\s+what\s+to\s+tackle\s+first|what\s+to\s+tackle\s+first|"
            r"what\s+to\s+do\s+next|where\s+to\s+(?:start|begin)|"
            r"help\s+me\s+(?:think\s+through|choose|decide)|"
            r"making\s+(?:a\s+)?little\s+progress\s+on\s+everything|finishing\s+nothing)\b",
            normalized,
        )
    )
    supplies_item_details = bool(
        re.search(r"\b(?:project|task|option|job)\s*#?\s*[1-9]\b", normalized)
        or re.search(
            r"\b(?:one|first)\s+(?:is|would be)\b[^.?!;:]{2,80}"
            r"\b(?:another|second)\s+(?:is|would be)\b",
            normalized,
        )
        or re.search(
            r"\b(?:projects?|tasks?|options?|jobs?|directions?|paths?)\s*:\s*\S",
            text,
            flags=re.IGNORECASE,
        )
        or len(re.findall(r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s+\S", text)) >= 2
    )
    return bool(has_multiple_items and asks_to_prioritize and not supplies_item_details)


def _work_progress_appraisal(value: str) -> bool:
    """Recognize a request for judgment about whether ongoing work is paying off."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if not normalized:
        return False
    asks_for_judgment = bool(
        re.search(
            r"\b(?:what(?:'s| is) your read|what do you (?:really )?think|"
            r"tell me honestly|be honest|can(?:not|'t) tell whether|"
            r"do you think (?:we|this)|are we (?:actually )?)\b",
            normalized,
        )
    )
    progress_language = bool(
        re.search(
            r"\b(?:meaningful|real|measurable) progress\b|"
            r"\b(?:actually )?(?:improving|getting better|moving in the right direction)\b|"
            r"\b(?:spinning our wheels|just (?:adding|added) (?:more )?code|"
            r"adding more machinery|more code rather than|larger answer catalog)\b",
            normalized,
        )
    )
    contrasts_activity_with_outcome = bool(
        re.search(r"\b(?:or|rather than|instead of|versus|vs\.?|just)\b", normalized)
        or "what's your read" in normalized
        or "what is your read" in normalized
    )
    return bool(asks_for_judgment and progress_language and contrasts_activity_with_outcome)


def _named_prioritization_list(value: str) -> bool:
    """Detect a natural list of competing work even without 'three projects'."""

    return bool(_named_prioritization_items(value))


def _named_prioritization_items(value: str) -> List[str]:
    """Extract named work items from an ordinary priority request."""

    text = _text(value)
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    candidate = ""
    for pattern in (
        (
            r"\b(?:bouncing|switching|choose|decide|choosing|deciding|torn)\s+between\b"
            r"\s+([^.?!]{2,420}?)(?=[.?!]|$)"
        ),
        (
            r"\b(?:working|making\s+progress)\s+on\b"
            r"\s+([^.?!]{2,420}?)(?=[.?!]|$)"
        ),
    ):
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ,;:")
            break
    if not candidate or not re.search(r"\band\b", candidate, flags=re.IGNORECASE):
        return []
    parts = re.split(
        r"\s*,\s*(?:and\s+)?|\s+and\s+",
        candidate,
        flags=re.IGNORECASE,
    )
    items: List[str] = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip(" ,;:")
        cleaned = re.sub(r"^(?:the|my|our)\s+", "", cleaned)
        if not cleaned or len(cleaned.split()) > 12:
            return []
        if cleaned not in items:
            items.append(cleaned)
    if 3 <= len(items) <= 6:
        return items
    if len(items) != 2:
        return []
    work_action = re.compile(
        r"^(?:finish(?:ing)?|fix(?:ing)?|repair(?:ing)?|clean(?:ing)?(?:\s+up)?|"
        r"validat(?:e|ing)|test(?:ing)?|calibrat(?:e|ing)|install(?:ing)?|"
        r"wir(?:e|ing)|design(?:ing)?|review(?:ing)?|document(?:ing)?|"
        r"build(?:ing)?|set(?:ting)?\s+up|work(?:ing)?\s+on)\b",
        flags=re.IGNORECASE,
    )
    return items if all(work_action.search(item) for item in items) else []


def _selected_work_next_step_followup(messages: Sequence[Dict[str, Any]]) -> bool:
    """Carry a user's chosen work item into one small, reversible next step."""

    if len(messages or []) < 3:
        return False
    latest = _latest_user_text(messages).lower()
    prior_users = [
        _message_text(message)
        for message in (messages or [])[:-1]
        if _text(message.get("role")).lower() == "user"
    ]
    prior_assistants = [
        _message_text(message).lower()
        for message in (messages or [])[:-1]
        if _text(message.get("role")).lower() == "assistant"
    ]
    prior_request = any(
        _unspecified_multi_item_prioritization(value)
        for value in prior_users[-3:]
    )
    assistant_requested_choice = any(
        re.search(
            r"\b(?:which one|which task|which project|which direction)\b",
            value,
        )
        for value in prior_assistants[-2:]
    )
    selected = bool(
        re.search(
            r"\b(?:let us|let's|i will|i'll|we will|we'll|go with|take|choose|start with)\b",
            latest,
        )
    )
    asks_for_first_step = bool(
        re.search(
            r"\b(?:smallest(?: useful)? first step|smallest(?: useful)? step|"
            r"first useful step|what (?:is|should be) the first step|"
            r"what should (?:i|we) do first|where (?:do|should) (?:i|we) start)\b",
            latest,
        )
    )
    return bool(
        prior_request
        and assistant_requested_choice
        and selected
        and asks_for_first_step
    )


def _multi_item_prioritization_followup(messages: Sequence[Dict[str, Any]]) -> bool:
    """Carry a prioritization clarification into the decision turn."""

    if len(messages or []) < 3:
        return False
    latest = _latest_user_text(messages).lower()
    prior_users = [
        _message_text(message)
        for message in (messages or [])[:-1]
        if _text(message.get("role")).lower() == "user"
    ]
    prior_assistants = [
        _message_text(message).lower()
        for message in (messages or [])[:-1]
        if _text(message.get("role")).lower() == "assistant"
    ]
    prior_request = any(
        _unspecified_multi_item_prioritization(value)
        for value in prior_users[-3:]
    )
    assistant_requested_decision_fact = any(
        re.search(
            r"\b(?:which\s+one|competing\s+projects|blocking\s+committed\s+work|"
            r"restores?\s+a\s+capability|what\s+would\s+['\"]?done['\"]?\s+look\s+like)\b",
            value,
        )
        for value in prior_assistants[-2:]
    )
    supplies_decision_fact = bool(
        re.search(
            r"\b(?:block(?:s|ing|ed)?|deadline|due|promised|committed|customer|client|"
            r"no\s+deadline|usable|unusable|down|offline|needed\s+for|need\s+it\s+for|"
            r"restores?|unlocks?|depends?\s+on)\b",
            latest,
        )
    )
    return bool(prior_request and assistant_requested_decision_fact and supplies_decision_fact)


def _reflective_deliberation_kind(value: str) -> str:
    """Recognize when the user needs one useful decision question, not a framework dump."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip()
    if not normalized:
        return ""
    struggle = bool(
        re.search(
            r"\b(?:stuck|get\s+unstuck|going\s+in\s+circles|circling|rationali[sz]ing|"
            r"second[- ]guessing|overthinking|frustrated|can(?:not|'t)\s+tell|"
            r"do(?:\s+not|n't)\s+know\s+whether|not\s+sure\s+(?:whether|if)|"
            r"clever\s+or\s+overcomplicated|every\s+fix\b[^.?!]{0,80}\bnew\s+problem)\b",
            normalized,
        )
    )
    collaborative_ask = bool(
        re.search(
            r"\b(?:help\s+me|with\s+me|think\s+(?:it|this)\s+through|"
            r"talk\s+(?:it|this)\s+through|how\s+would\s+you\s+approach|"
            r"get\s+unstuck)\b",
            normalized,
        )
    )
    exploratory_hold = bool(
        collaborative_ask
        and re.search(r"\b(?:idea|concept|half[- ]formed|rough|early[- ]stage)\b", normalized)
        and re.search(
            r"\b(?:not\s+ready\s+to\s+(?:design|build|make)|"
            r"do\s+not\s+(?:design|build)|don't\s+(?:design|build)|"
            r"just\s+(?:talk|think)|concept\s+level)\b",
            normalized,
        )
    )
    if not ((struggle and collaborative_ask) or exploratory_hold):
        return ""
    if re.search(
        r"\b(?:purchase|buy(?:ing)?|shop\s+purchase|machine\s+i\s+(?:want|need)|"
        r"equipment\s+i\s+(?:want|need))\b",
        normalized,
    ):
        return "purchase"
    if re.search(
        r"\b(?:redesign|design\s+iteration|keep\s+iterating|start\s+over|"
        r"every\s+fix|another\s+problem)\b",
        normalized,
    ):
        return "iteration"
    if re.search(r"\b(?:idea|concept)\b", normalized) and re.search(
        r"\b(?:talk|think)\s+(?:it|this)\s+through\b",
        normalized,
    ):
        return "exploration"
    if re.search(r"\b(?:choice|decision|option|path|approach)\b", normalized):
        return "decision"
    return ""


def build_clarification_question(messages: Sequence[Dict[str, Any]], frame: Dict[str, Any]) -> str:
    """Return one natural question for a kernel-confirmed missing referent."""

    expected = _text(frame.get("expectedOutput"))
    if expected.endswith("?"):
        return expected

    query = _latest_user_text(messages)
    lower = query.lower()
    tags = {
        _text(value)
        for value in (frame.get("frameTags") or [])
        if _text(value)
    }
    if "named-multi-item-prioritization" in tags:
        return "Which one is currently blocking committed work or restores a capability you need for the next job?"
    if "multi-item-prioritization" in tags:
        return "What are the competing projects, what would 'done' look like for each, and what is blocking each one right now?"
    if "missing-local-artifact-inputs" in tags:
        return "What are the exact paths to the source files, or can you attach them here?"
    if "strength-requirements-clarification" in tags:
        return (
            "Which part are we strengthening, what load and direction does it see, "
            "and which failure mode or property should improve most: bending stiffness, "
            "tensile strength, impact resistance, heat resistance, layer adhesion, or fatigue life?"
        )
    numbers = re.findall(r"\b\d+\b", query)
    if len(numbers) >= 2 and re.search(r"\b(?:do|choose|use|apply)\b", lower):
        joined = ", ".join(numbers[:-1]) + f", and {numbers[-1]}"
        return f"Which option list do {joined} refer to?"
    if re.search(r"\b(?:same|other (?:printer|profile|file|machine|part)|that one)\b", lower):
        if re.search(r"\b(?:profile|settings)\b", lower):
            return "Which settings from the previous action should I copy, and which destination profile should receive them?"
        target_kind = (
            "target printer"
            if "printer" in lower
            else "exact target"
        )
        return f"What previous action should I repeat, and which {target_kind} should receive it?"
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

    # The generic parser owns latest-turn polarity even when a bounded legacy
    # specialist remains the selected domain. Do not make legacy routing infer
    # exclusions from nouns or operation prohibitions.
    if isinstance(generic.get("semanticExclusions"), dict):
        legacy["semanticExclusions"] = dict(generic["semanticExclusions"])

    query = _latest_user_text(messages).lower()
    legacy_domain = _text(legacy.get("domain"))
    generic_domain = _text(generic.get("domain"))
    output_contract = (
        generic.get("outputContract")
        if isinstance(generic.get("outputContract"), dict)
        else {}
    )
    output_mode = _text(output_contract.get("mode"))
    legacy_artifact_domains = {
        "cad_artifact_work",
        "aero_cfd_work",
        "structural_fea_work",
        "engineering_diagram_work",
        "local_file_work",
    }
    if output_mode == "conversation-answer" and legacy_domain in legacy_artifact_domains:
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The typed output contract requests a conversational answer and contains no positively authorized saved-artifact output. Subject or format nouns cannot create artifact authority."
        )
        return generic
    if output_mode == "local-artifact" and generic_domain in legacy_artifact_domains:
        generic["rejectedLegacyDomain"] = legacy_domain if legacy_domain != generic_domain else ""
        generic["rejectedLegacyReason"] = (
            "The typed output contract binds a direct action to an explicit local artifact and owns output polarity before legacy subject routing."
        )
        return generic
    if generic_domain == "agent_runtime_capabilities":
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The complete request asks how this agent, its memory, or a feedback control behaves. "
            "A command phrase mentioned as the subject of that question must not be executed as the command itself."
        )
        return generic
    if generic_domain == "live_device_action":
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The complete request targets a physical printer or controller. Its typed, per-surface authority plan must be evaluated before legacy progress, status, safety, local-file, or generic-action dispatch."
        )
        return generic
    if (
        generic_domain == "clarification"
        and _text(generic.get("actionType")) == "ask_one_focused_clarification"
    ):
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The complete request is missing a decision-changing target or input, so one focused clarification must own the turn before a legacy answer route can guess."
        )
        return generic
    file_owning_legacy_domains = {
        "klipper_config_migration",
        "cad_artifact_work",
        "aero_cfd_work",
        "structural_fea_work",
        "engineering_diagram_work",
    }
    if (
        generic_domain in {"local_file_evidence", "local_file_work", "local_file_analysis"}
        and (_file_refs(query) or _attachment_file_refs(messages))
        and legacy_domain not in file_owning_legacy_domains
    ):
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The request explicitly names local files, so their contents are primary evidence; "
            "keywords inside filenames must not select an unrelated legacy domain."
        )
        return generic
    if (
        generic_domain == "local_product_action"
        and _text(generic.get("actionType")) == "inspect_compare_diagnose_verify"
    ):
        generic["rejectedLegacyDomain"] = legacy_domain
        generic["rejectedLegacyReason"] = (
            "The user asked to inspect working local reference implementations against the current local output and trace the root cause; "
            "that is an execution diagnostic, not an abstract comparison answer."
        )
        return generic
    if (
        generic_domain == "local_product_action"
        and _text(generic.get("actionType")) == "inspect_explain_local_state"
        and legacy_domain == "local_app_product_bug"
        and _text(legacy.get("actionType")) != "inspect_explain_local_state"
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The typed product frame proves that the latest imperative requests a Model Health implementation; generic status nouns must not silently reduce authorized edit/test work to explanation-only."
        )
        generic["targetSurface"] = legacy.get("targetSurface") or generic.get("targetSurface")
        generic["actionType"] = legacy.get("actionType") or "modify_app_status_surface"
        generic["executionActionType"] = "inspect_plan_execute_verify"
        generic["objectRefs"] = list(legacy.get("objectRefs") or generic.get("objectRefs") or [])
        generic["requestedChange"] = legacy.get("requestedChange") or generic.get("requestedChange")
        generic["missingInfo"] = list(legacy.get("missingInfo") or generic.get("missingInfo") or [])
        generic["routeCandidates"] = ["codex-cli-ui-local-agent"]
        existing_plan = dict(generic.get("operationPlan") or {})
        existing_operations = [
            dict(item)
            for item in existing_plan.get("operations") or []
            if isinstance(item, dict)
            and _text(item.get("operation")) != "explain"
        ]
        existing_names = {
            _text(item.get("operation")) for item in existing_operations
        }
        allowed_now = [
            _text(item)
            for item in existing_plan.get("allowedNow") or []
            if _text(item) and _text(item) != "explain"
        ]
        for operation in ("inspect", "edit", "test"):
            if operation not in existing_names:
                existing_operations.append(
                    {
                        "operation": operation,
                        "state": "allowed-now",
                        "condition": "required by the explicit local UI implementation request",
                    }
                )
            if operation not in allowed_now:
                allowed_now.append(operation)
        generic["operationPlan"] = {
            **existing_plan,
            "operations": existing_operations,
            "allowedNow": allowed_now,
            "prohibited": list(existing_plan.get("prohibited") or []),
            "deferred": list(existing_plan.get("deferred") or []),
            "readOnly": False,
        }
        generic["expectedOutput"] = (
            "A verified local implementation or exact blocker, with source inspection, "
            "edit-or-verified-no-op, focused test, and reconciliation evidence."
        )
        generic["evidenceNeed"] = "local-source-change-and-focused-test-receipts"
        generic["knownConstraints"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("knownConstraints") or []),
                    *list(generic.get("knownConstraints") or []),
                ]
            )
        )
        generic["frameTags"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("frameTags") or []),
                    *list(generic.get("frameTags") or []),
                    "model-health-implementation",
                ]
            )
        )
        return generic
    if (
        generic_domain == "local_product_action"
        and _text(generic.get("actionType")) == "inspect_explain_local_state"
        and legacy_domain == "local_app_product_bug"
        and _text(legacy.get("actionType")) == "inspect_explain_local_state"
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The generic read-only local-state owner preserves the operation boundary, while the typed product frame retains the exact Model Health surface and printer context."
        )
        generic["targetSurface"] = legacy.get("targetSurface") or generic.get("targetSurface")
        generic["objectRefs"] = list(legacy.get("objectRefs") or generic.get("objectRefs") or [])
        generic["requestedChange"] = legacy.get("requestedChange") or generic.get("requestedChange")
        generic["missingInfo"] = list(legacy.get("missingInfo") or generic.get("missingInfo") or [])
        generic["routeCandidates"] = ["codex-cli-ui-local-agent"]
        generic["forbiddenRoutes"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("forbiddenRoutes") or []),
                    *list(generic.get("forbiddenRoutes") or []),
                ]
            )
        )
        generic["frameTags"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("frameTags") or []),
                    *list(generic.get("frameTags") or []),
                    "read-only-model-health-explanation",
                ]
            )
        )
        generic["knownConstraints"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("knownConstraints") or []),
                    *list(generic.get("knownConstraints") or []),
                ]
            )
        )
        read_only_plan = dict(generic.get("operationPlan") or {})
        read_only_operations = [
            dict(item)
            for item in read_only_plan.get("operations") or []
            if isinstance(item, dict)
            and _text(item.get("operation")) in {"inspect", "explain"}
        ]
        read_only_allowed = [
            _text(item)
            for item in read_only_plan.get("allowedNow") or []
            if _text(item) in {"inspect", "explain"}
        ]
        generic["operationPlan"] = {
            **read_only_plan,
            "operations": read_only_operations,
            "allowedNow": read_only_allowed,
            "readOnly": True,
        }
        return generic
    if (
        generic_domain in {"conversation", "general_action"}
        and legacy_domain == "local_app_product_bug"
        and _text(legacy.get("contextRelation")) == "follow-up"
    ):
        generic_operation_plan = (
            dict(generic.get("operationPlan"))
            if isinstance(generic.get("operationPlan"), dict)
            else {}
        )
        legacy_operation_plan = (
            dict(legacy.get("operationPlan"))
            if isinstance(legacy.get("operationPlan"), dict)
            else {}
        )
        operation_plan = generic_operation_plan or legacy_operation_plan
        generic["operationPlan"] = operation_plan
        mutation_allowed = bool(
            set(operation_plan.get("allowedNow") or [])
            & {"change", "create", "edit", "fix", "install", "restart", "upload", "write"}
        ) and not bool(operation_plan.get("readOnly"))
        generic["domain"] = "local_product_action"
        generic["targetSurface"] = legacy.get("targetSurface") or "codex_cli_ui.model_health"
        generic["actionType"] = (
            legacy.get("actionType")
            if mutation_allowed
            else "inspect_explain_local_state"
        )
        generic["executionActionType"] = "inspect_plan_execute_verify" if mutation_allowed else "inspect_explain_local_state"
        generic["objectRefs"] = list(legacy.get("objectRefs") or [])
        generic["requestedChange"] = legacy.get("requestedChange") or generic.get("requestedChange")
        generic["knownConstraints"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("knownConstraints") or []),
                    *list(generic.get("knownConstraints") or []),
                ]
            )
        )
        generic["missingInfo"] = list(legacy.get("missingInfo") or [])
        generic["routeCandidates"] = ["codex-cli-ui-local-agent"]
        generic["forbiddenRoutes"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("forbiddenRoutes") or []),
                    *list(generic.get("forbiddenRoutes") or []),
                ]
            )
        )
        generic["frameTags"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("frameTags") or []),
                    *list(generic.get("frameTags") or []),
                    "model-health-follow-up",
                ]
            )
        )
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "A semantically linked Model Health continuation keeps the local product surface and latest operation authorization instead of becoming an unscoped action."
        )
        return generic
    if (
        generic_domain == "local_product_action"
        and _text(generic.get("actionType")) == "inspect_plan_execute_verify"
        and legacy_domain == "local_app_product_bug"
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The generic local code agent owns execution, while the typed product frame retains the exact UI surface, requested change, and answer-family vetoes."
        )
        generic["executionActionType"] = generic.get("actionType")
        for key in (
            "targetSurface",
            "actionType",
            "objectRefs",
            "requestedChange",
            "missingInfo",
            "routeCandidates",
            "forbiddenRoutes",
            "frameTags",
            "confidence",
        ):
            if legacy.get(key) not in (None, "", [], {}):
                generic[key] = legacy.get(key)
        generic["knownConstraints"] = list(
            dict.fromkeys(
                [
                    *list(legacy.get("knownConstraints") or []),
                    *list(generic.get("knownConstraints") or []),
                ]
            )
        )
        return generic
    if (
        generic_domain in {"engineering_advisory", "material_process_behavior"}
        and _text(generic.get("actionType")) == "evaluate_operating_suitability"
        and legacy_domain == "engineering_advisory"
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The generic frame preserves the more specific operating-suitability action and its proportionate review contract."
        )
        return generic
    if (
        generic_domain == "engineering_calculation"
        and legacy_domain == "engineering_advisory"
    ):
        legacy_tags = {
            _text(value)
            for value in (legacy.get("frameTags") or [])
            if _text(value)
        }
        if "electrical-distribution-protection" in legacy_tags:
            legacy.setdefault("source", "bounded-legacy-intent")
            legacy["refinedGenericDomain"] = generic_domain
            legacy["refinedGenericReason"] = (
                "The quantities parameterize a source-to-load topology and protection decision; "
                "they do not reduce the request to a standalone numerical result."
            )
            return legacy
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The complete request asks for numerical engineering outputs, so the calculation contract is more specific than general advisory routing."
        )
        return generic
    if (
        generic_domain == "engineering_tradeoff"
        and legacy_domain == "engineering_advisory"
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The complete request asks whether evidence supports choosing between named engineering options, "
            "so the tradeoff frame is more specific than general advisory routing."
        )
        return generic
    if (
        generic_domain == "knowledge_comparison"
        and legacy_domain == "engineering_advisory"
        and re.search(
            r"\b(?:using|use|based\s+on)\s+only\s+(?:(?:the|those|these)\s+)?"
            r"(?:supplied|provided|stated|given)\s+facts\b",
            query,
        )
        and len(
            [
                item
                for item in (generic.get("objectRefs") or [])
                if isinstance(item, dict)
                and item.get("type") == "comparison-option"
                and _comparison_option_is_substantive(_text(item.get("name")))
            ]
        )
        >= 2
    ):
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The request explicitly bounds the decision to user-supplied facts and names multiple options; "
            "a coincidental engineering token cannot replace that stable comparison owner."
        )
        return generic
    if (
        legacy_domain == "engineering_advisory"
        and _text(generic.get("actionType")) == "reassess_engineering_conclusion_with_new_constraints"
        and len(
            [
                item
                for item in (generic.get("objectRefs") or [])
                if isinstance(item, dict) and item.get("type") == "comparison-option"
            ]
        )
        >= 2
    ):
        if generic_domain == "knowledge_comparison":
            generic["domain"] = "engineering_tradeoff"
            generic["targetSurface"] = "knowledge.engineering.advisory_decision"
        generic["refinedLegacyDomain"] = legacy_domain
        generic["refinedLegacyReason"] = (
            "The follow-up preserves named engineering alternatives and adds decision constraints; keep typed engineering "
            "ownership while retaining the more specific comparison frame."
        )
        return generic
    if legacy_domain == "engineering_power_conversion":
        legacy_tags = {
            _text(value)
            for value in (legacy.get("frameTags") or [])
            if _text(value)
        }
        if (
            "mechanical-output-sizing" in legacy_tags
            and turn_context_relationship(messages).get("contextRelation") == "follow-up"
        ):
            # A generic comparison reading of words such as "instead of" must not
            # displace a typed sizing capability that owns the prior calculation.
            legacy.setdefault("source", "bounded-legacy-intent")
            return legacy
        generic_is_comparison = generic_domain in {"knowledge_comparison", "engineering_tradeoff"}
        explicit_power_operation = bool(
            re.search(
                r"\b(?:convert|conversion|equivalent horsepower|equivilant horsepower|how many (?:hp|horsepower)|"
                r"what (?:is the )?(?:horsepower|hp|kw|kilowatt)|what size .{0,24}(?:motor|controller)|"
                r"size (?:the |a )?(?:motor|controller)|motor sizing|controller sizing|"
                r"(?:motor|controller) .{0,32}\b(?:voltage|current|power|rating|headroom|limit)|"
                r"voltage headroom|(?:shaft )?torque (?:at|required|needed)|battery current|required current|phase current)\b",
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
                r"(?:motor|controller) .{0,32}\b(?:voltage|current|power|rating|headroom|limit)|"
                r"voltage headroom|size (?:the |a )?(?:motor|controller)|convert .{0,24}(?:power|horsepower|kw))\b",
                query,
            )
        )
        if not asks_about_power:
            generic["rejectedLegacyDomain"] = legacy_domain
            generic["rejectedLegacyReason"] = "The full request does not ask for a power conversion or motor/controller sizing operation."
            return generic

    legacy.setdefault("source", "bounded-legacy-intent")
    return legacy


def _inline_programming_answer_request(
    query: str,
    file_refs: Sequence[str],
    local_product_surface: bool,
) -> bool:
    """Separate code requested in the answer from codebase/file execution work."""
    lower = f" {query.lower()} "
    if file_refs or local_product_surface:
        return False
    if re.search(
        r"\b(?:save|write\s+to|edit|modify|patch|commit|install|deploy|execute|run)\b"
        r"[^.!?\n]{0,80}\b(?:file|repo|repository|project|codebase|script|tests?|test suite|command)\b",
        lower,
    ):
        return False
    if re.search(r"\b(?:file|repo|repository|codebase)\b", lower):
        return False
    programming_subject = bool(
        _has(lower, _PROGRAMMING_LANGUAGE_TERMS)
        or _has(lower, _PROGRAMMING_OUTPUT_TERMS)
        or re.search(
            r"\b(?:binary search|topological sort|kahn(?:'s)? algorithm|depth[- ]first search|"
            r"breadth[- ]first search|dynamic programming|linked list|hash table|recursion)\b",
            lower,
        )
    )
    answer_output = bool(
        re.search(
            r"\b(?:write|implement|show|provide|give|create|explain|demonstrate)\b"
            r"[^.!?\n]{0,140}\b(?:algorithm|class|code|function|implementation|method|program|snippet|python|javascript|typescript|rust|java)\b",
            lower,
        )
        or (
            programming_subject
            and _has(lower, ("include tests", "include examples", "edge case", "invariant"))
        )
    )
    return programming_subject and answer_output


def _programming_order_contract_question(query: str) -> str:
    """Ask for an order source only when a requested code guarantee depends on it."""
    lower = f" {query.lower()} "
    order_sensitive = bool(
        re.search(
            r"\b(?:stable|order[- ]preserving|preserve (?:the )?(?:input )?order)\b",
            lower,
        )
    )
    explicit_order_source = bool(
        re.search(
            r"\b(?:explicit (?:ordered )?(?:(?:node|item|task|record|key|vertex|value|element)s? )?(?:list|sequence)|"
            r"ordered (?:(?:node|item|task|record|key|vertex|value|element)s? )?(?:list|sequence)|"
            r"(?:nodes?|items?|tasks?|records?|keys?|vertices|values?|elements?) (?:list|sequence)|"
            r"graph (?:mapping|dictionary|dict)(?:'s)? key order|"
            r"mapping key order|dict(?:ionary)? key order|first appearance|lexicographic(?:al)? order|"
            r"priority (?:key|function)|ordering key|comparison function|comparator|original (?:index|position))\b",
            lower,
        )
    )
    if not order_sensitive or explicit_order_source:
        return ""
    if not re.search(r"\b(?:graph|node|vertex|topological|adjacency)\b", lower):
        return (
            "What should define the stable input order: an explicit ordered input list, "
            "the primary mapping's key order, or first appearance across the supplied collections?"
        )
    return (
        "What should define the stable input order: an explicit ordered node list, "
        "the graph mapping's key order, or first appearance across keys and adjacency lists?"
    )


def _resolved_clarification_query(messages: Sequence[Dict[str, Any]]) -> str:
    """Fold a short answer to a focused clarification back into its original request."""

    substantive = [
        message
        for message in messages
        if _message_text(message)
        and _text(message.get("role")).lower() in {"user", "assistant"}
    ]
    if len(substantive) < 3:
        return ""
    original, clarification, answer = substantive[-3:]
    if (
        _text(original.get("role")).lower() != "user"
        or _text(clarification.get("role")).lower() != "assistant"
        or _text(answer.get("role")).lower() != "user"
    ):
        return ""
    original_text = _message_text(original).strip()
    clarification_text = _message_text(clarification).strip()
    answer_text = _message_text(answer).strip()
    if (
        not original_text
        or not clarification_text.endswith("?")
        or clarification_text.count("?") != 1
        or len(clarification_text) > 420
        or not answer_text
        or answer_text.endswith("?")
        or len(answer_text.split()) > 40
    ):
        return ""
    if not re.match(
        r"^(?:what|which|where|when|who|how|do|does|did|is|are|should|would|could|can|please confirm)\b",
        clarification_text,
        flags=re.IGNORECASE,
    ):
        return ""
    output_clarification = bool(
        re.search(
            r"\b(?:format|file\s+type|save|saved|file|document|download|"
            r"destination|in\s+(?:the\s+)?(?:chat|answer|response)|inline)\b",
            clarification_text,
            flags=re.IGNORECASE,
        )
    )
    output_answer = bool(
        re.search(
            r"\b(?:dxf|step|stp|stl|scad|f3d|f3z|pdf|docx|xlsx|pptx|csv|"
            r"markdown|md|txt|json|yaml|yml|py|js|html|png|jpg|jpeg|svg|"
            r"spreadsheet|workbook|document|file|saved|locally|downloadable|"
            r"chat|answer|response|inline)\b",
            answer_text,
            flags=re.IGNORECASE,
        )
    )
    if output_clarification and output_answer:
        if re.search(
            r"\b(?:chat|answer|response|inline|here)\b",
            answer_text,
            flags=re.IGNORECASE,
        ) and not re.search(
            r"\b(?:file|saved|locally|downloadable|dxf|step|stp|stl|scad|f3d|f3z|"
            r"pdf|docx|xlsx|pptx|csv|markdown|md|txt|json|yaml|yml|py|js|html|"
            r"png|jpg|jpeg|svg)\b",
            answer_text,
            flags=re.IGNORECASE,
        ):
            return (
                f"{original_text.rstrip()} Deliver the requested output in the "
                "conversation, not as a saved file."
            )
        normalized_answer = answer_text.strip().rstrip(".!?")
        return (
            f"{original_text.rstrip()} Save the requested artifact as "
            f"{normalized_answer}."
        )
    return f"{original_text}\nUser-supplied clarification: {answer_text}"


def _assistant_question_project_progression(messages: Sequence[Dict[str, Any]]) -> bool:
    """Recognize a project answer followed by an explicit request to advance it."""

    substantive = [
        message
        for message in messages
        if _message_text(message)
        and _text(message.get("role")).lower() in {"user", "assistant"}
    ]
    if len(substantive) < 3:
        return False
    original, clarification, answer = substantive[-3:]
    if [
        _text(message.get("role")).lower()
        for message in (original, clarification, answer)
    ] != ["user", "assistant", "user"]:
        return False
    clarification_text = _message_text(clarification).strip()
    answer_text = _message_text(answer).strip().lower()
    if (
        not clarification_text.endswith("?")
        or clarification_text.count("?") != 1
        or len(clarification_text) > 900
    ):
        return False
    return bool(
        re.search(
            r"\b(?:what|which|where|how)\s+(?:should|do|can)\s+we\b[^?\n]{0,45}"
            r"\b(?:first|next|start|begin|proceed)\b",
            answer_text,
        )
        or re.search(
            r"\b(?:what(?:'s| is) the next step|where do we start|how should we proceed)\b",
            answer_text,
        )
    )


def is_agent_self_model_introspection(value: str) -> bool:
    """Recognize questions about this agent's memory, persistence, and correction loop."""

    normalized = re.sub(r"\s+", " ", _text(value).lower()).strip(" \t\r\n?.!")
    if not normalized:
        return False
    if re.search(
        r"\b(?:can|do) you (?:actually )?learn\b|"
        r"\bdo you have (?:the )?(?:ability|capability) to learn\b|"
        r"\bhow do you learn\b|"
        r"\bwhen you make (?:a )?mistake\b|"
        r"\bhow do you change your behavio(?:u)?r\b|"
        r"\bavoid (?:making|repeating) the same mistake\b|"
        r"\bwhen i correct you\b|"
        r"\bwhat happens? (?:when|after) i correct you\b|"
        r"\bdo you (?:actually )?get better\b[^?.]{0,80}\b(?:correct|mistake|feedback|apologi[sz]e)\b",
        normalized,
    ):
        return True

    feedback_control = bool(
        re.search(
            r"\b(?:fix this|good feedback|feedback|correction|"
            r"mark(?:ing)?\s+(?:an|the|this)\s+answer(?:\s+as\s+(?:bad|good|wrong|incorrect))?|"
            r"rat(?:e|ing)\s+(?:an|the|this)\s+answer|thumbs?[-\s]+(?:up|down))\b",
            normalized,
        )
    )
    agent_subject = bool(
        re.search(r"\b(?:you|your|codex(?: cli ui)?|this (?:agent|assistant|app))\b", normalized)
        or (
            feedback_control
            and re.search(
                r"\b(?:answer|button|thumbs?[-\s]+(?:up|down)|this app|codex)\b",
                normalized,
            )
        )
    )
    if not agent_subject:
        return False
    memory_boundary = bool(
        re.search(
            r"\b(?:remember|memory|conversation|chat|session|context)\b[^?.]{0,100}"
            r"\b(?:next|another|new|restart|reopen|close|persist|survive|disappear|retain|carry over|written|saved|stored)\b|"
            r"\b(?:what|which)\b[^?.]{0,80}\b(?:written down|saved|stored|persist(?:s|ed)?|survives?|disappears?)\b|"
            r"\b(?:restart|reopen|close|new (?:chat|conversation|session))\b[^?.]{0,100}"
            r"\b(?:remember|memory|conversation|chat|session|context|persist|survive|disappear|retain)\b",
            normalized,
        )
    )
    direct_feedback_command = bool(
        re.match(
            r"^(?:(?:please|now)\s+)?(?:can|could|would|will) you\s+(?:please\s+)?"
            r"(?:fix|repair|correct|change|update)\b|"
            r"^(?:(?:please|now)\s+)?fix this(?:\s*[:;,]|\s+(?:and|by|because|so|then|now)\b)",
            normalized,
        )
    )
    feedback_control_discussion = bool(
        feedback_control
        and (
            re.search(
                r"\b(?:press|click|select|choose|use|mark|rate|only|just)\b",
                normalized,
            )
            or re.search(
                r"\b(?:what|why|how|when|where|does|do|did|is|are|will|would|can|could)\b",
                normalized,
            )
            or re.search(
                r"\b(?:button|control|meaning|signal|lesson|feedback loop)\b",
                normalized,
            )
        )
    )
    correction_boundary = bool(
        not direct_feedback_command
        and feedback_control_discussion
        and re.search(
            r"\b(?:change|immediate|durable|permanent|persist|save|store|next|future|happen|record|regression|repair|"
            r"learn|teach|lesson|enough|sufficient|meaning|signal)\w*\b",
            normalized,
        )
    )
    return memory_boundary or correction_boundary


def is_local_verification_receipt_status_request(
    messages: Sequence[Dict[str, Any]],
) -> bool:
    """Recognize local verification-summary status without capturing unrelated receipts."""

    query = re.sub(r"\s+", " ", _latest_user_text(messages).lower()).strip()
    if not query:
        return False
    named_groups = {
        name
        for name, pattern in (
            ("package-health", r"\bpackage[- ]health\b"),
            ("live-smoke", r"\b(?:live[- ]smoke|live feedback smoke)\b"),
            ("public-export", r"\bpublic[- ]export\b"),
            ("ai-intent", r"\b(?:ai[- ]intent(?: 500)?|500[- ]question replay)\b"),
            ("runtime-exceptions", r"\bruntime exceptions?\b"),
            ("self-healing", r"\bself[- ]healing(?: queue)?\b"),
        )
        if re.search(pattern, query)
    }
    codex_scope = bool(re.search(r"\bcodex cli ui\b|\bour (?:boy|son)\b", query))
    verification_subject = bool(
        re.search(r"\bverification (?:receipts?|evidence|summary)\b", query)
    )
    local_evidence_subject = bool(
        codex_scope
        and re.search(r"\b(?:testing|tests?|receipts?|verification|evidence)\b", query)
    )
    named_group_subject = bool(
        named_groups
        and (
            len(named_groups) >= 2
            or re.search(r"\b(?:receipts?|verification|testing|tests?|evidence)\b", query)
        )
    )
    if not (verification_subject or local_evidence_subject or named_group_subject):
        return False

    unrelated_receipt_scope = bool(
        re.search(
            r"\b(?:expense|tax|invoice|payment|shipping|purchase|order|refund) receipts?\b|"
            r"\b(?:email|message) (?:delivery|read) receipts?\b|"
            r"\b(?:research citations?|citation evidence|evidence retrieval|source retrieval)\b",
            query,
        )
    )
    if unrelated_receipt_scope and not (codex_scope or named_groups):
        return False

    status_or_refresh = bool(
        re.search(
            r"\b(?:latest|current|fresh|stale|out[- ]of[- ]date|up[- ]to[- ]date|green|"
            r"pass(?:ed|ing)?|fail(?:ed|ing)?|unknown|missing|valid|expired|status)\b|"
            r"\b(?:re[- ]?run|rerunning|run again|refresh|freshen|rebuild)\b|"
            r"\bwhat (?:needs?|must|should) (?:be )?(?:run|rerun|refreshed|rebuilt)\b|"
            r"\b(?:show|list|where are|what are)\b[^?.]{0,80}\b(?:receipts?|verification evidence)\b|"
            r"\bwhat receipts? do (?:we|you) have\b",
            query,
        )
    )
    return status_or_refresh


def build_generic_intent_frame(messages: Sequence[Dict[str, Any]], cwd: str = "") -> Dict[str, Any]:
    """Build a reusable intent frame when no high-confidence capability frame exists."""

    latest_query = _latest_user_text(messages)
    resolved_clarification_query = _resolved_clarification_query(messages)
    query = resolved_clarification_query or latest_query
    if not query:
        return {}
    context_relationship = turn_context_relationship(messages)
    if resolved_clarification_query:
        context_relationship = {
            "contextRelation": "follow-up",
            "contextScope": "clarification-resolution",
            "contextRationale": "The latest user turn directly answers the assistant's focused clarification, so the supplied constraint belongs to the original request.",
        }
    elif _assistant_question_project_progression(messages):
        context_relationship = {
            "contextRelation": "follow-up",
            "contextScope": "assistant-question-resolution",
            "contextRationale": "The latest user turn answers the assistant's project-defining question and explicitly asks to advance the same project.",
        }
    lower = f" {query.lower()} "
    previous = _previous_user_text(messages)
    previous_lower = f" {previous.lower()} "
    prior_frame: Dict[str, Any] = {}
    if context_relationship.get("contextRelation") == "follow-up" and previous:
        latest_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if _text(messages[index].get("role")).lower() == "user"
                and _message_text(messages[index])
            ),
            -1,
        )
        if latest_user_index > 0:
            prior_frame = build_generic_intent_frame(messages[:latest_user_index], cwd=cwd)
    elif previous and re.search(
        r"\b(?:denominator|rate|ratio|per\s+\w+|machine-hours?|operating\s+hours?|"
        r"kilograms?|kg|volume|throughput|exposure|stratif\w*|work\s+mix)\b",
        query.lower(),
    ):
        latest_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if _text(messages[index].get("role")).lower() == "user"
                and _message_text(messages[index])
            ),
            -1,
        )
        if latest_user_index > 0:
            candidate_prior_frame = build_generic_intent_frame(
                messages[:latest_user_index], cwd=cwd
            )
            if candidate_prior_frame.get("domain") == "decision_metric_design":
                prior_frame = candidate_prior_frame
                context_relationship = {
                    "contextRelation": "follow-up",
                    "contextScope": "recent-thread",
                    "sharedTopicTerms": list(
                        context_relationship.get("sharedTopicTerms") or []
                    ),
                    "reason": "The latest turn supplies exposure or denominator data for the prior typed decision metric.",
                }
    typed_constraint_update = typed_followup_constraint_update(
        latest_query,
        context_relationship,
        prior_frame,
    )
    normalized_query = re.sub(r"\s+", " ", query.lower()).strip(" \t\r\n?.!")
    latest_normalized_query = re.sub(
        r"\s+", " ", latest_query.lower()
    ).strip(" \t\r\n?.!")
    agent_learning_introspection = is_agent_self_model_introspection(normalized_query)
    verification_receipt_status = is_local_verification_receipt_status_request(messages)
    operation_discussion = _operation_discussion_request(latest_query)
    runtime_state_introspection = bool(
        re.search(
            r"\b(?:what|which)\s+(?:is|are)\s+(?:the\s+)?(?:current\s+)?"
            r"(?:working directory|cwd|access level|permission(?:s)?|web search (?:state|mode|status))\b",
            latest_normalized_query,
        )
        or re.search(
            r"\b(?:web search|web (?:switch|toggle|mode|access))\b[^?.]{0,50}"
            r"\b(?:on|off|enabled|disabled|active|available|working)\b",
            latest_normalized_query,
        )
        or re.search(
            r"\b(?:is|are)\b[^?.]{0,50}\b(?:web search|web (?:switch|toggle|mode|access))\b",
            latest_normalized_query,
        )
        or re.search(
            r"\b(?:which|what)\s+(?:local\s+)?model\s+(?:are|do|did|will)\s+you\s+"
            r"(?:use|using)\b[^?.]{0,60}\b(?:response|reply|run|turn|right now|currently)\b",
            latest_normalized_query,
        )
        or re.search(
            r"\bwhat\s+model\s+(?:is|does)\s+(?:this|the)\s+(?:response|reply|run|turn)\b",
            latest_normalized_query,
        )
    )
    read_only_attachment_capability = bool(
        re.search(
            r"\b(?:can|could|do|will|would)\s+you\b[^?.]{0,90}"
            r"\b(?:compare|review|inspect|analy[sz]e|read)\b",
            latest_normalized_query,
        )
        and re.search(
            r"\b(?:attach(?:ed|ment)?|upload(?:ed)?|provide(?:d)?|send|file|config(?:uration)?)\b",
            latest_normalized_query,
        )
        and re.search(
            r"\b(?:read[- ]only|without (?:changing|editing|modifying)|do not (?:change|edit|modify)|"
            r"don't (?:change|edit|modify)|not (?:change|edit|modify))\b",
            latest_normalized_query,
        )
        and (
            re.search(
                r"\b(?:capabilit(?:y|ies)|ability|able)\b",
                latest_normalized_query,
            )
            or re.search(
                r"\b(?:once|after|when)\b[^?.]{0,55}"
                r"\b(?:attach|upload|provide|send)\w*\b",
                latest_normalized_query,
            )
        )
    )
    capability_introspection = bool(
        agent_learning_introspection
        or operation_discussion
        or runtime_state_introspection
        or read_only_attachment_capability
        or
        (
            re.search(
                r"\b(?:your|you(?:r)?|codex(?: cli ui)?|"
                r"this (?:app|application)|the (?:app|application))\b",
                latest_normalized_query,
            )
            and re.search(
                r"\bcapabilit(?:y|ies)\b",
                latest_normalized_query,
            )
        )
        or re.fullmatch(
            r"(?:can|could) you (?:give|show|tell) me (?:a )?(?:high level |high-level )?(?:overview|list|summary) of (?:what you can do|your capabilities)(?: to help me)?",
            normalized_query,
        )
        or re.fullmatch(r"what (?:exactly )?can you do(?: for me| to help me)?", normalized_query)
        or bool(
            re.search(r"\bwhat can you (?:actually )?do (?:with|for) me\b", normalized_query)
            and re.search(r"\b(?:on this mac|here|in this (?:session|app|project)|before we (?:start|begin|dive in))\b", normalized_query)
        )
        or bool(
            re.search(r"\bwhat (?:exactly )?can you do\b", normalized_query)
            and re.search(
                r"\b(?:this (?:session|run)|access|permissions?|tools?|capabilit(?:y|ies))\b",
                normalized_query,
            )
        )
        or bool(
            re.search(r"\bwhat (?:access|permissions?|tools?) do you have\b", normalized_query)
            and re.search(r"\b(?:you|your|session|run|right now|currently)\b", normalized_query)
        )
        or re.fullmatch(r"how can you help me", normalized_query)
        or re.fullmatch(
            r"what (?:local )?(?:tools|access|permissions|integrations) do you (?:currently )?have",
            normalized_query,
        )
        or bool(
            re.search(r"\b(?:capabilit(?:y|ies)|what you can do|tools and access)\b", previous_lower)
            and re.fullmatch(r"(?:which|what) of (?:those|these) can you (?:actually )?use(?: right now| in this (?:repo|project|session))?", normalized_query)
        )
        or bool(
            re.search(
                r"\b(?:you|your|this (?:session|run)|current local|lower toolbar)\b",
                normalized_query,
            )
            and (
                re.search(
                    r"\b(?:working directory|current directory|cwd|filesystem access|"
                    r"shell access|access level|permissions?|web search|web (?:switch|toggle|mode|access))\b",
                    normalized_query,
                )
                or bool(
                    re.search(
                        r"\bweb\b[^?.]{0,40}\b(?:on|off|enabled|disabled|active|available|working)\b",
                        normalized_query,
                    )
                    or re.search(
                        r"\b(?:on|off|enabled|disabled|active|available|working)\b[^?.]{0,40}\bweb\b",
                        normalized_query,
                    )
                )
                or re.search(
                    r"\bdirectory\b[^?]{0,40}\b(?:working|running)\b",
                    normalized_query,
                )
            )
        )
    )
    engineering_workstream_patterns = (
        r"\b(?:cad|parametric model(?:ing)?|geometry|drawing)\b",
        r"\b(?:cfd|computational fluid dynamics|flow simulation|fea|finite element|simulation|"
        r"vehicle dynamics|multibody dynamics|structural analysis|thermal analysis|rotor analysis)\b",
        r"\b(?:materials?|material selection|materials selection|material choice|metallurgy|structure|structural design)\b",
        r"\b(?:thrust|torque|power|thermal|stress|load|energy|propulsion|drive|motor|heater|pump|"
        r"shaft|joint|traction)\b[^?.]{0,32}\b(?:calculation|calculations|sizing|requirements?|analysis)\b",
        r"\b(?:source(?:d|s|ing)?|find|select)\b[^?.]{0,48}\b(?:components?|parts?|hardware|suppliers?)\b",
        r"\b(?:controls?|control system|electronics?|instrumentation|autonomy|automation|validation|testing|manufacturability)\b",
    )
    engineering_workstream_count = sum(
        1 for pattern in engineering_workstream_patterns if re.search(pattern, normalized_query)
    )
    engineering_constraint_count = sum(
        1
        for pattern in (
            r"\b(?:abs|asa|pla|petg|nylon|polycarbonate|peek|ultem|aluminum|steel|titanium|composite)\b",
            r"\b\d+(?:\.\d+)?\s*(?:rpm|kw|w|v|a|n|nm|kg|g|mm|cm|m|mph|km/h|psi|bar|pa|c|f)\b",
            r"\b(?:build volume|build envelope|work envelope|fit within|3d[- ]print(?:ed|able|ing)?|printed on|printer)\b",
            r"\b(?:continuous|peak|duty cycle|operating point|service life|safety factor|containment|balance)\b",
        )
        if re.search(pattern, normalized_query)
    )
    engineering_project_intake = bool(
        (engineering_workstream_count >= 2 or engineering_constraint_count >= 2)
        and re.search(
            r"\b(?:can|could|would|will) you help (?:me|us)\b|"
            r"\b(?:can|could|would|will) you (?:work|partner|collaborate) with (?:me|us)\b|"
            r"\bdo you have (?:the )?(?:ability|capability) to help\b|"
            r"\bif i (?:wanted|were|was going|decided) to (?:design|develop|engineer|build)\b",
            normalized_query,
        )
        and (
            re.search(
                r"\b(?:engine|turbine|vehicle|aircraft|machine|robot|rover|platform|manipulator|gantry|"
                r"printer|powertrain|controller|device|assembly|system|mechanism|structure|"
                r"chamber|cabinet|oven|rig|bench|skid|test stand)\b",
                normalized_query,
            )
            or re.search(
                r"\b(?:design|develop|engineer|build)\b\s+(?:(?:a|an|the|this|that|our|my)\s+)?"
                r"[a-z0-9][^?.]{2,100}",
                normalized_query,
            )
        )
    )
    engineering_project_definition_followup = bool(
        not engineering_project_intake
        and context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain") == "engineering_advisory"
        and prior_frame.get("actionType") == "scope_engineering_project"
    )
    urls = _urls(query)
    files = list(dict.fromkeys([*_file_refs(query), *_attachment_file_refs(messages)]))
    analytical_local_file = _analytical_local_file_request(query, files)
    decision_support = _decision_support_request(query)
    operation_plan = _extract_operation_plan(query)
    semantic_exclusions = _extract_semantic_exclusions(latest_query)
    if operation_discussion and operation_plan:
        discussed_operations = []
        discussed_mentions = []
        for item in operation_plan.get("operations") or []:
            operation = str(item.get("operation") or "").strip()
            if not operation or operation in discussed_operations:
                continue
            discussed_operations.append(operation)
            discussed_mentions.append(
                {
                    "operation": operation,
                    "state": "discussed",
                    "condition": "",
                    "authoritySurface": item.get("authoritySurface") or "request-target",
                }
            )
        operation_plan = {
            "operations": discussed_mentions,
            "allowedNow": [],
            "prohibited": [],
            "discussed": discussed_operations,
            "deferred": [],
            "readOnly": True,
            "requiresConfirmation": False,
        }
    local_product_surface = bool(
        _has(lower, _LOCAL_PRODUCT_SURFACE_TERMS)
        or _local_product_ui_surface_request(query)
    )
    desired_local_ui_change = bool(
        local_product_surface
        and _explicit_desired_ui_state_change(query)
    )
    has_action = bool(
        _explicit_action_request(query)
        or desired_local_ui_change
    )
    if desired_local_ui_change:
        operation_plan = _desired_local_ui_operation_plan(operation_plan)
    read_only_scope = bool(operation_plan.get("readOnly"))
    local_surface = bool(files) or _has(lower, _LOCAL_SURFACE_TERMS)
    explicit_local_action_target = bool(
        local_surface
        or local_product_surface
        or _has(
            lower,
            (
                "backup",
                "codebase",
                "button",
                "config file",
                "configuration",
                "control",
                "device",
                "dialog",
                "directory",
                "file",
                "folder",
                "form",
                "menu",
                "package",
                "printer",
                "repository",
                "server",
                "service",
                "slider",
                "source code",
                "tests",
                "test",
                "workspace",
            ),
        )
    )
    local_state_explanation = bool(
        local_product_surface
        and not files
        and re.search(
            r"\b(?:explain|describe|summarize|review|inspect|show|tell\s+me|why|what)\b",
            normalized_query,
        )
        and re.search(
            r"\b(?:failure|failures|failed|failing|error|errors|health|status|result|results|"
            r"log|logs|diagnostic|diagnostics|regression|regressions|issue|issues)\b",
            normalized_query,
        )
    )
    if local_state_explanation:
        existing_operations = [
            str(item.get("operation") or "")
            for item in operation_plan.get("operations") or []
            if isinstance(item, dict)
        ]
        implicit_operations = [
            operation
            for operation in ("inspect", "explain")
            if operation not in existing_operations
        ]
        if implicit_operations:
            operation_plan = {
                **operation_plan,
                "operations": [
                    {
                        "operation": operation,
                        "state": "allowed-now",
                        "condition": "required to ground the current-state explanation",
                    }
                    for operation in implicit_operations
                ]
                + list(operation_plan.get("operations") or []),
                "allowedNow": implicit_operations + list(operation_plan.get("allowedNow") or []),
            }
        deferred_operation_names = {
            str(item.get("operation") or "")
            for item in operation_plan.get("deferred") or []
            if isinstance(item, dict)
        }
        if (
            deferred_operation_names & _MUTATING_OPERATION_NAMES
            and set(operation_plan.get("allowedNow") or []).issubset(
                {"inspect", "explain", "research", "run", "test"}
            )
        ):
            operation_plan["readOnly"] = True
        read_only_scope = bool(operation_plan.get("readOnly"))
    if analytical_local_file:
        existing_operations = [
            str(item.get("operation") or "")
            for item in operation_plan.get("operations") or []
            if isinstance(item, dict)
        ]
        implicit_operations = [
            operation
            for operation in ("inspect", "explain")
            if operation not in existing_operations
        ]
        if implicit_operations:
            operation_plan = {
                **operation_plan,
                "operations": [
                    {
                        "operation": operation,
                        "state": "allowed-now",
                        "condition": "required to answer from the named local files",
                    }
                    for operation in implicit_operations
                ]
                + list(operation_plan.get("operations") or []),
                "allowedNow": implicit_operations + list(operation_plan.get("allowedNow") or []),
            }
        operation_plan["readOnly"] = True
        read_only_scope = True
    comparative_local_diagnostic = bool(
        re.search(
            r"\b(?:find|diagnose|trace|identify|investigate|look into|take a .*?look)\b"
            r"[^?.]{0,140}\b(?:problem|cause|bug|difference|preventing|incorrect|wrong|broken|desired output)\b",
            normalized_query,
        )
        and re.search(
            r"\b(?:correct|working|proper|reference|known-good|known good|does it properly|do it properly)\b",
            normalized_query,
        )
        and re.search(
            r"\b(?:our|current|local|locally|on this mac|have access|implementation|codebase|app|application|output)\b",
            normalized_query,
        )
        and re.search(r"\b(?:compare|compared|difference|versus|vs\.?|reference)\b", normalized_query)
    )
    inline_programming_answer = _inline_programming_answer_request(
        query,
        files,
        local_product_surface,
    )
    programming_order_question = (
        _programming_order_contract_question(query)
        if inline_programming_answer
        else ""
    )
    scientific = _has(lower, _SCIENTIFIC_TERMS)
    market_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and re.search(r"\b(?:what about|how about|anything from|and (?:what|how) about)\b", lower)
        and (
            (
                previous
                and _has(previous_lower, _MARKET_TERMS)
                and (_has(previous_lower, _VOLATILE_TERMS) or "$" in previous)
            )
            or prior_frame.get("domain")
            in {"current_market_ranking", "current_market_research", "marketplace_listing_research"}
        )
    )
    functional_comparison = bool(
        "better solution" in lower
        and " than " in lower
        and re.search(r"\b(?:to use (?:as|for|to)|for)\b", lower)
    )
    explicit_current_commerce_research = bool(
        re.search(r"\b(?:research|find|look\s+up|search|check)\b", lower)
        and re.search(
            r"\b(?:current|currently|today|latest|available|availability|in[ -]stock|"
            r"price|prices|pricing|listing|listings|for\s+sale|to\s+buy)\b",
            lower,
        )
        and re.search(
            r"\b(?:price|prices|pricing|listing|listings|availability|in[ -]stock|"
            r"exact\s+(?:product|model|item)|cite|citation|source|sources)\b",
            lower,
        )
    )
    present_market_price_language = bool(
        re.search(r"\b(?:current|currently|today'?s?|right\s+now|these\s+days|latest)\b", lower)
        and re.search(r"\b(?:price|prices|pricing|cost|costs|pay|going\s+for|how\s+much)\b", lower)
    )
    commerce_subject_binding = bool(
        re.search(
            r"\b(?:does|do|is|are|would|will)\s+(?:a|an|the|this|that|these|those|my|our|\d|[a-z])",
            lower,
        )
        or re.search(r"\b(?:price|cost)\s+(?:of|for)\s+\S", lower)
        or re.search(r"\b(?:pay\s+for|going\s+for)\b", lower)
        or re.search(r"\bhow\s+much\s+are\s+\S", lower)
    )
    abstract_resource_cost_question = bool(
        re.search(
            r"\b(?:algorithm|function|method|query|code|program|runtime|execution|"
            r"computation|computational|compute|time\s+complexity|space\s+complexity|"
            r"big[- ]?o|memory|api\s+call|token)\b",
            lower,
        )
        and re.search(
            r"\b(?:cost|costs|run|running|execute|execution|complexity|resource|resources)\b",
            lower,
        )
    ) or bool(
        re.search(r"\b(?:energy|electricity|power\s+consumption)\s+costs?\b", lower)
    )
    project_eta_cost_decoy = bool(
        re.search(
            r"\b(?:project|task|job)\b[^?\n]{0,100}\b(?:eta|finish|finished|completion|done)\b|"
            r"\b(?:eta|finish|finished|completion)\b[^?\n]{0,100}\b(?:project|task|job)\b",
            lower,
        )
    )
    current_commerce_price_question = bool(
        present_market_price_language
        and commerce_subject_binding
        and not abstract_resource_cost_question
        and not project_eta_cost_decoy
    )
    market = (
        _has(lower, _MARKET_TERMS) and (_has(lower, _VOLATILE_TERMS) or "$" in query)
    ) or market_followup or explicit_current_commerce_research or current_commerce_price_question
    market = market and not functional_comparison and not engineering_project_intake
    ebay_marketplace = bool(
        (
            " ebay" in lower
            and re.search(r"\b(?:find|search|compare|check|review|shop|buy|deal|listing|listings)\b", lower)
        )
        or (
            " ebay" in previous_lower
            and re.search(r"\b(?:check|compare|review)\b", lower)
            and re.search(r"\b(?:those|them|listings|options|results)\b", lower)
        )
    )
    explicit_comparison = _has(
        lower,
        tuple(term for term in _COMPARISON_TERMS if term not in {"better", "stronger"}),
    )
    comparative_adjective_question = bool(
        re.search(r"\b(?:which|what)\b[^?\n]{0,120}\b(?:better|stronger)\b", lower)
        or re.search(r"\b(?:better|stronger)\b[^?\n]{0,120}\b(?:than|versus|vs\.?|or)\b", lower)
    )
    parsed_comparison_refs = _comparison_object_refs(
        query,
        prior_frame.get("objectRefs") if isinstance(prior_frame, dict) else None,
    )
    parsed_decision_refs = _decision_support_object_refs(query) if decision_support else []
    comparison = explicit_comparison or functional_comparison or comparative_adjective_question or bool(parsed_comparison_refs)
    comparison_speech_act = _comparison_speech_act(query) if comparison else ""
    compute_system_tradeoff = bool(
        comparison and _compute_system_decision_shape(query, len(parsed_comparison_refs))
    )
    engineering_tradeoff = bool(
        comparison
        and (
            compute_system_tradeoff
            or re.search(
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
                    "flatness",
                    "dimensional stability",
                    "thermal conductivity",
                    "heat spreading",
                    "thermal expansion",
                    "torque",
                    "positioning accuracy",
                    "repeatability",
                ),
            )
        )
    )
    engineering_sizing_request = bool(
        re.search(r"\b(?:size|sizing|dimension|specify|select)\b", lower)
        and re.search(
            r"\b(?:heat exchanger|radiator|cooling loop|pump|piping|pipe|duct|fan|heatsink|"
            r"cable|wire|breaker|fuse|motor|gearbox|shaft|bearing|beam|bracket|battery|controller)\b",
            lower,
        )
    )
    load_derived_drive_sizing = is_load_derived_drive_sizing(query)
    engineering_sizing_completion_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain") == "engineering_calculation"
        and prior_frame.get("actionType") == "clarify_engineering_sizing_operating_point"
        and len(_DECISION_QUANTITY_RE.findall(query)) >= 2
        and re.search(
            r"\b(?:use|size|calculate|compute|design|select|go ahead|proceed)\b",
            lower,
        )
    )
    quantitative_engineering_question = bool(
        re.search(
            r"\b(?:how\s+(?:hot|cold|fast|slow|large|small|thick|thin|long|much|many)|"
            r"what\s+(?:temperature|load|force|speed|rpm|torque|power|current|voltage|"
            r"pressure|flow|clearance|interference|deflection|stress|strain))\b"
            r"(?![-\s]+(?:specific|related|risks?|factors?|considerations?|requirements?|ratings?))",
            lower,
        )
        and len(_DECISION_QUANTITY_RE.findall(query)) >= 2
        and (
            _has(lower, _ENGINEERING_OBJECT_TERMS)
            or _has(lower, _ENGINEERING_SYSTEM_TERMS)
            or _has(lower, _ENGINEERING_PROCESS_TERMS)
        )
    )
    engineering_sufficiency_calculation = bool(
        re.search(
            r"\b(?:is|are|will|would|can)\b[^?.\n]{0,90}\b"
            r"(?:brake|motor|actuator|spring|cylinder|shaft|screw|beam|cable|wire|fuse|breaker)\b"
            r"[^?.\n]{0,90}\b(?:enough|adequate|sufficient)\b",
            lower,
        )
        and len(_DECISION_QUANTITY_RE.findall(query)) >= 2
        and re.search(
            r"\b(?:load|mass|weight|force|torque|pressure|current|power|heat|temperature|flow|speed|fall|hold|support)\b",
            lower,
        )
        and (
            _has(lower, _ENGINEERING_OBJECT_TERMS)
            or _has(lower, _ENGINEERING_SYSTEM_TERMS)
            or _has(lower, _ENGINEERING_PROCESS_TERMS)
        )
    )
    # An explicit calculation over multiple unit-bearing quantities is already a
    # closed physical calculation even when the component noun is absent from the
    # engineering taxonomy.  Preserve that typed owner so a later "change only X
    # and recompute" turn cannot be misread as a local file mutation.
    explicit_unit_calculation = bool(
        re.search(
            r"\b(?:calculate|compute|estimate|solve|work\s+out)\b",
            lower,
        )
        and len(_DECISION_QUANTITY_RE.findall(query)) >= 2
    )
    multi_layer_power_system_design = _multi_layer_power_system_design_text(query)
    engineering_calculation = bool(
        not multi_layer_power_system_design
        and (
            engineering_sizing_request
            or load_derived_drive_sizing
            or engineering_sizing_completion_followup
            or quantitative_engineering_question
            or engineering_sufficiency_calculation
            or explicit_unit_calculation
            or (
            re.search(
                r"\b(?:calculate|compute|estimate|determine|solve|check|work\s+out)\b",
                lower,
            )
            and re.search(
                r"\b(?:stress|strain|deflection|displacement|factor\s+of\s+safety|safety\s+factor|"
                r"torque|voltage\s+drop|current|power|heat\s+flux|temperature\s+rise|thermal\s+resistance|"
                r"pressure\s+(?:drop|margin)|flow\s+rate|buckling|natural\s+frequency|section\s+modulus|moment\s+of\s+inertia)\b",
                lower,
            )
            and len(_DECISION_QUANTITY_RE.findall(query)) >= 2
            )
        )
    )
    engineering_decision_followup = bool(
        not engineering_sizing_completion_followup
        and context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain")
        in {
            "engineering_advisory",
            "engineering_calculation",
            "engineering_power_conversion",
            "engineering_tradeoff",
            "knowledge_comparison",
            "material_process_behavior",
            "technical_compatibility",
        }
        and (
            re.search(
                r"\b(?:does|would|will|is|are)\s+(?:that|this|it|those|these)\s+"
                r"(?:settle|decide|establish|prove|resolve|change)\b",
                lower,
            )
            or re.search(r"\b(?:what\s+changes?\s+if|what\s+if|assume|assuming|suppose|provided)\b", lower)
            or bool(_DECISION_QUANTITY_RE.search(query))
            or bool(_decision_axes(query))
            or bool(
                re.search(
                    r"\b(?:change|shift|set|make)\s+(?:the\s+)?"
                    r"(?:priority|criterion|criteria|weight|emphasis)\b",
                    lower,
                )
            )
            or (
                _CONTEXT_REFERENT_RE.search(lower)
                and re.search(
                    r"\b\d+(?:\.\d+)?\s*(?:vdc|vac|v|kw|w|a|arms|amps?|khz|hz|rpm|nm|psi|mpa|gpa|°c|c|%)\b",
                    lower,
                )
            )
        )
    )
    # Technical vocabulary is not itself a request for research. Stable
    # explanation questions such as schema-evolution comparisons belong to
    # expert reasoning unless the user explicitly asks for documentation,
    # verification, research, or supplies a source. Source availability must
    # not change the semantic owner of the question.
    technical_source_lookup = bool(_has(lower, _TECHNICAL_SOURCE_TERMS))
    compatibility = bool(
        _has(lower, _COMPATIBILITY_TERMS)
        or re.search(r"\b(?:will|would|can|could)\s+.{1,100}?\s+work\s+with\b", lower)
        or re.search(r"\bwork\s+with\s+(?:a|an|the|this|that|my)\b", lower)
    )
    prior_representation_semantics = (
        prior_frame.get("representationSemantics")
        if isinstance(prior_frame.get("representationSemantics"), dict)
        else {}
    )
    representation_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and prior_representation_semantics
        and (prior_frame.get("objectRefs") or [])
        and not re.search(
            r"\b(?:search|research|browse|look\s+up|find\s+(?:new|more|current)|"
            r"recheck|refresh|verify\s+(?:again|current))\b",
            normalized_query,
        )
        and (
            _CONTEXT_REFERENT_RE.search(lower)
            or re.search(
                r"\b(?:which\s+of\s+the\s+(?:two|three|options)|"
                r"based\s+on\s+what\s+you\s+(?:just\s+)?found|"
                r"compatibility\s+direction|schema\s+evolution|"
                r"unknown\s+(?:fields?|members?)|tag\s+reuse|round[ -]?trip)\b",
                lower,
            )
        )
    )
    engineering_suitability_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and previous
        and _is_engineering_suitability_text(previous)
    )
    engineering_suitability = bool(
        _is_engineering_suitability_text(query)
        or engineering_suitability_followup
    ) and not (engineering_tradeoff and len(parsed_comparison_refs) >= 2)
    fault_isolation_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain") == "engineering_advisory"
        and prior_frame.get("actionType") == "design_fault_isolation_experiment"
        and re.search(
            r"\b(?:log|signal|measure|instrument|sensor|encoder|telemetry|status|stop|abort|"
            r"rule\s+(?:in|out)|each\s+branch|result|evidence|observe|record)\w*\b",
            normalized_query,
        )
    )
    fault_isolation_experiment = bool(
        _is_fault_isolation_experiment_text(query) or fault_isolation_followup
    )
    decision_metric_followup = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain") == "decision_metric_design"
        and prior_frame.get("actionType") == "design_decision_aligned_metric"
        and re.search(
            r"\b(?:denominator|rate|ratio|per\s+\w+|hours?|jobs?|parts?|units?|miles?|cycles?|"
            r"kilograms?|kg|volume|throughput|exposure|hide|mask|stratif|weight|mix)\w*\b",
            normalized_query,
        )
    )
    decision_metric_design = bool(
        _is_decision_metric_design_text(query) or decision_metric_followup
    )
    engineering_advisory = bool(
        _is_engineering_advisory_text(query)
        or fault_isolation_experiment
        or multi_layer_power_system_design
    )
    reflective_deliberation_kind = _reflective_deliberation_kind(latest_query)
    material_process_behavior = bool(
        engineering_suitability
        and _has(
            lower + (previous_lower if engineering_suitability_followup else ""),
            _MATERIAL_CLASS_TERMS,
        )
    )
    engineering_decision_followup = bool(
        engineering_decision_followup
        and (
            not engineering_suitability
            or prior_frame.get("domain") == "engineering_calculation"
        )
    )
    output_contract = classify_output_authority(query, operation_plan)
    if output_contract.get("mode") == "local-artifact":
        operation_plan = _bind_local_artifact_output_plan(
            operation_plan,
            output_contract,
        )
    elif output_contract.get("mode") == "conversation-answer":
        operation_plan = _bind_conversation_output_plan(
            operation_plan,
            output_contract,
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
    structural_execution = explicit_execution and not engineering_project_intake and (
        _has(lower, ("finite element", "fea", "structural analysis"))
        or ("design and analyze" in lower and _has(lower, (" load", "safety factor", "stress")))
    )
    aero_execution = explicit_execution and not engineering_project_intake and _has(
        lower,
        (" cfd", "computational fluid", "airflow analysis", "flow simulation"),
    )
    diagram_execution = bool(
        output_contract.get("mode") == "local-artifact"
        and output_contract.get("artifactClass") == "diagram"
    )
    printable_artifact_execution = bool(
        explicit_execution
        and re.search(r"\b(?:3d[- ]?)?printable\b(?!\s*\.)", lower)
        and not re.search(
            r"\b(?:checklist|document|guide|instructions|list|report|settings)\b",
            lower,
        )
    )
    cad_execution = explicit_execution and not engineering_project_intake and (
        printable_artifact_execution
        or _has(
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
    )
    typed_local_artifact_output = bool(
        output_contract.get("mode") == "local-artifact"
        and output_contract.get("state") == "allowed-now"
    )
    typed_local_action_output = bool(
        output_contract.get("mode") == "local-action"
        and output_contract.get("state") == "allowed-now"
    )
    typed_cad_artifact_output = bool(
        typed_local_artifact_output
        and output_contract.get("artifactClass") == "cad"
    )
    cad_execution = bool(
        typed_cad_artifact_output
        and not engineering_project_intake
    )
    operation_names = {
        str(item.get("operation") or "")
        for item in (operation_plan.get("operations") or [])
        if isinstance(item, dict)
    }
    non_discussed_operation_names = {
        str(item.get("operation") or "")
        for item in (operation_plan.get("operations") or [])
        if isinstance(item, dict) and item.get("state") != "discussed"
    }
    live_device_lineage = bool(
        context_relationship.get("contextRelation") == "follow-up"
        and prior_frame.get("domain") == "live_device_action"
        and non_discussed_operation_names & _LIVE_DEVICE_OPERATION_NAMES
    )
    live_device_action = bool(
        (
            _live_device_action_request(query, operation_plan)
            and not local_product_surface
            and not engineering_suitability
            and not engineering_advisory
            and not reflective_deliberation_kind
        )
        or live_device_lineage
    )
    live_device_refs = _live_device_target_refs(query)
    prior_live_authority = (
        ((prior_frame.get("operationPlan") or {}).get("authorityBySurface") or {}).get(
            "live-device"
        )
        or {}
    )
    prior_live_target_lineage = bool(
        live_device_action
        and context_relationship.get("contextRelation") == "follow-up"
        and prior_live_authority
        and non_discussed_operation_names & _LIVE_DEVICE_OPERATION_NAMES
    )
    if live_device_lineage or prior_live_target_lineage:
        prior_live_refs = [
            dict(item)
            for item in (prior_frame.get("objectRefs") or [])
            if isinstance(item, dict)
            and item.get("type") in {"printer", "controller-board", "live-service"}
        ]
        live_device_refs = list(
            {
                (str(item.get("type") or ""), str(item.get("name") or "")): item
                for item in [*prior_live_refs, *live_device_refs]
            }.values()
        )
    ambiguous_live_mutation_referent = bool(
        not live_device_action
        and set(operation_plan.get("allowedNow") or [])
        & _LIVE_DEVICE_MUTATION_NAMES
        and re.search(
            r"^(?:(?:please|now)\s+|go\s+ahead\s+and\s+|"
            r"(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
            r"(?:cancel|stop|pause|resume|start|restart|reboot|install|flash|upload|"
            r"heat|home|move|turn)\s+(?:it|this|that|one)\b",
            normalized_query,
        )
    )
    if ambiguous_live_mutation_referent:
        operation_plan = _defer_unresolved_target_operations(operation_plan)
        read_only_scope = bool(operation_plan.get("readOnly"))
    if live_device_action:
        authority_context = " ".join(
            [query, *[str(item.get("name") or "") for item in live_device_refs]]
        )
        operation_plan = _constrain_live_device_operation_plan(
            authority_context,
            operation_plan,
        )
        read_only_scope = bool(operation_plan.get("readOnly"))

    # Publish the contract from the final normalized operation ledger. The
    # earlier classification only selects artifact ownership; live-device and
    # clarification constraints may refine operation state afterward.
    output_contract = classify_output_authority(query, operation_plan)

    question = query.rstrip().endswith("?") or lower.lstrip().startswith(_QUESTION_PREFIXES)
    work_progress_appraisal = _work_progress_appraisal(latest_query)
    unspecified_multi_item_prioritization = _unspecified_multi_item_prioritization(query)
    named_prioritization_items = (
        _named_prioritization_items(query)
        if unspecified_multi_item_prioritization
        else []
    )
    named_multi_item_prioritization = bool(named_prioritization_items)
    binary_work_prioritization = len(named_prioritization_items) == 2
    selected_work_next_step_followup = _selected_work_next_step_followup(messages)
    multi_item_prioritization_followup = _multi_item_prioritization_followup(messages)
    social_acknowledgement = _social_acknowledgement_turn(query)
    recurrent_problem_reengagement = _recurrent_problem_reengagement(query, messages)
    context_dependent_correction = _context_dependent_correction_without_context(
        query,
        messages,
    )
    contextual_correction = _contextual_correction_with_context(query, messages)
    mixed_evidence_review_intake = bool(
        not _has_message_attachments(messages)
        and _mixed_evidence_review_intake(query)
    )
    strength_improvement_clarification = _strength_improvement_without_context(
        query,
        messages,
    )
    missing_local_artifact_inputs = _missing_local_artifact_inputs(query, messages)
    if multi_item_prioritization_followup or selected_work_next_step_followup:
        # A direct answer to our clarification belongs to the established
        # decision task. Incidental words in that answer, such as describing
        # a project as a "new capability", must not start a self-capability
        # query or hand routing to whichever specialist keyword appears last.
        capability_introspection = False
    clarification = bool(
        not capability_introspection
        and not engineering_project_intake
        and (
            _vague_action_without_context(query, messages)
            or _missing_referent_without_context(query, messages)
            or missing_local_artifact_inputs
            or strength_improvement_clarification
            or context_dependent_correction
            or recurrent_problem_reengagement
            or mixed_evidence_review_intake
            or unspecified_multi_item_prioritization
            or typed_constraint_update.get("status") == "ambiguous"
            or ambiguous_live_mutation_referent
        )
    )

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
    additional_constraints: List[str] = []
    confidence = 0.72

    prohibited_operations = [
        str(item) for item in (operation_plan.get("prohibited") or []) if str(item).strip()
    ]
    deferred_operations = [
        item for item in (operation_plan.get("deferred") or []) if isinstance(item, dict)
    ]
    allowed_operations = [
        str(item) for item in (operation_plan.get("allowedNow") or []) if str(item).strip()
    ]
    if prohibited_operations:
        additional_constraints.append(
            "Do not perform explicitly prohibited operations in this turn: "
            + ", ".join(prohibited_operations)
            + "."
        )
        forbidden.append("perform-explicitly-prohibited-operation")
        tags.append("negative-scope-boundary")
    if deferred_operations:
        deferred_text = "; ".join(
            f"{item.get('operation')} ({item.get('condition') or 'until the stated condition is satisfied'})"
            for item in deferred_operations
        )
        additional_constraints.append(
            "Treat these operations as deferred hold points, not current authorization: "
            + deferred_text
            + "."
        )
        forbidden.append("perform-deferred-operation-before-hold-point")
        tags.append("deferred-operation-boundary")
    if read_only_scope:
        additional_constraints.append(
            "Keep execution read-only: gather and report evidence without changing files, services, accounts, purchases, or live machines."
        )
        forbidden.append("cross-read-only-boundary")
        tags.append("read-only-boundary")
    if len(allowed_operations) + len(deferred_operations) + len(prohibited_operations) >= 2:
        additional_constraints.append(
            "Preserve the user's operation order and hold points; completion of an earlier allowed step does not authorize a later prohibited or deferred step."
        )
        tags.append("operation-sequence")

    if live_device_action:
        live_operations = [
            item
            for item in (operation_plan.get("operations") or [])
            if isinstance(item, dict)
            and item.get("authoritySurface") == "live-device"
        ]
        live_mutation_operations = [
            str(item.get("operation") or "")
            for item in live_operations
            if item.get("operation") in _LIVE_DEVICE_MUTATION_NAMES
        ]
        active_live_mutation_operations = [
            str(item.get("operation") or "")
            for item in live_operations
            if item.get("operation") in _LIVE_DEVICE_MUTATION_NAMES
            and item.get("state") in {"allowed-now", "deferred"}
        ]
        live_inspection_allowed = any(
            item.get("operation") == "inspect" and item.get("state") == "allowed-now"
            for item in live_operations
        )
        local_stage_operations = [
            str(item.get("operation") or "")
            for item in (operation_plan.get("operations") or [])
            if isinstance(item, dict)
            and item.get("authoritySurface") == "local-artifact"
            and item.get("state") == "allowed-now"
        ]
        exact_physical_target = any(
            item.get("type") in {"printer", "controller-board"}
            for item in live_device_refs
        )
        domain = "live_device_action"
        target_surface = "live_device.printer_or_controller"
        action_type = (
            "stage_local_artifact_with_live_device_hold"
            if local_stage_operations and live_mutation_operations
            else "hold_live_device_mutation_for_preflight"
            if active_live_mutation_operations
            else "inspect_live_device_state_read_only"
            if live_inspection_allowed
            else "explain_live_device_change_read_only"
            if live_mutation_operations
            else "inspect_live_device_state_read_only"
        )
        requested_change = (
            "Preserve independently safe local preparation while holding every live-device mutation behind target-bound controller preflight."
            if local_stage_operations
            else "Inspect the exact live device read-only and report observed state without crossing a mutation boundary."
            if not active_live_mutation_operations
            else "Bind the requested live-device operations to the exact target and stop before mutation until every controller preflight requirement is satisfied."
        )
        expected_output = (
            "A target-bound read-only status receipt or a precise live-mutation blocker, plus any independently verified local staging result."
        )
        evidence_need = "typed-live-device-authority-and-current-preflight"
        capability = "live_device_authority"
        if not exact_physical_target and (
            active_live_mutation_operations or live_inspection_allowed
        ):
            missing.append("the exact physical printer or controller target")
        if set(active_live_mutation_operations) & {"install", "upload", "change"}:
            missing.append("a verified backup or rollback path for the active firmware or configuration")
        if set(active_live_mutation_operations) & {"install", "upload", "change", "restart", "heat", "move", "control-output"}:
            missing.append("current target state proving the requested live operation is safe")
        if set(active_live_mutation_operations) & {"cancel", "pause", "resume"}:
            missing.append("the current job identity and state for the exact target")
        if active_live_mutation_operations:
            missing.append("a latest-request-bound authorization and preflight receipt for the exact operations")
        forbidden.extend(
            [
                "legacy-printer-status-or-progress-template",
                "generic-local-agent-live-machine-execution",
                "local-file-capability-crossing-onto-live-device",
                "live-mutation-without-exact-target-and-current-preflight",
                "claim-live-device-result-without-run-bound-receipt",
            ]
        )
        additional_constraints.extend(
            [
                "Treat operation authority per target surface: local artifact preparation never authorizes printer upload, apply, restart, motion, heat, output, job control, or firmware change.",
                "A live-device mutation remains deferred until the controller validates the exact target, current safe state, operation-specific rollback boundary, and latest-request authorization receipt.",
                "Do not invoke shell, file, network, printer, camera, or service tools from the reasoning worker; report the missing preflight or observed controller receipt honestly.",
            ]
        )
        tags.extend(["live-device-authority", "target-bound", "model-first", "fail-closed"])
        confidence = 0.97
    elif verification_receipt_status:
        domain = "bounded_specialist_capability"
        target_surface = "codex_cli_ui.verification_summary"
        action_type = "summarize_local_verification_receipt_status"
        requested_change = (
            "Read the local Verification Summary and report which receipt groups are current, stale, passing, failing, or unknown, plus the exact refresh action for every non-passing group."
        )
        expected_output = (
            "A direct local-state summary whose status, age, coverage, and rerun actions match the saved verification receipts."
        )
        evidence_need = "local-code-or-state-evidence"
        capability = "bounded_specialist_direct"
        forbidden.extend(
            [
                "model-worker",
                "mcp-resource-search",
                "shell-search",
                "web-research",
                "unrelated-receipt-domain",
                "unsupported-no-rerun-needed-claim",
            ]
        )
        tags.extend(
            [
                "verification-receipt-status",
                "local-state-evidence",
                "bounded-specialist",
                "specialist-owner:verification-receipts",
            ]
        )
        confidence = 0.99
    elif social_acknowledgement:
        if _prior_substantive_context(messages):
            context_relationship = {
                "contextRelation": "follow-up",
                "contextScope": "recent-thread",
                "sharedTopicTerms": context_relationship.get("sharedTopicTerms") or [],
                "reason": "Positive feedback applies to the immediately preceding exchange.",
            }
        domain = "conversation"
        target_surface = "conversation.social_acknowledgement"
        action_type = "acknowledge_and_continue_naturally"
        requested_change = (
            "Receive the user's feedback naturally, carry the useful signal forward, and do not turn a complete social turn into a helpdesk invitation."
        )
        expected_output = _social_acknowledgement_response(query)
        evidence_need = "none"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "generic-customer-service-closing",
                "unnecessary-help-menu",
                "specialist-keyword-takeover",
                "model-latency-for-social-turn",
            ]
        )
        tags.extend(["social-acknowledgement", "lightweight-conversation"])
        confidence = 0.99
    elif work_progress_appraisal:
        domain = "conversation"
        target_surface = "conversation.work_progress_appraisal"
        action_type = "assess_work_progress_from_local_evidence"
        requested_change = (
            "Judge whether the ongoing work changed product behavior rather than merely increasing implementation volume, using current local receipts when available."
        )
        expected_output = (
            "A candid, collegial assessment that separates measured behavior change from code volume, names the strongest local proof, and identifies the architectural risk still worth watching."
        )
        evidence_need = "local-code-or-state-evidence"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "ask-user-for-commit-hash-before-reading-local-receipts",
                "equate-code-volume-with-progress",
                "generic-project-status-template",
                "unsupported-completion-claim",
            ]
        )
        tags.extend(
            [
                "work-progress-appraisal",
                "grounded-local-reflection",
                "conversational-judgment",
            ]
        )
        confidence = 0.98
    elif reflective_deliberation_kind:
        domain = "clarification"
        target_surface = "conversation.reflective_decision_input"
        action_type = "ask_one_focused_clarification"
        requested_change = (
            "Acknowledge the user's actual decision tension and ask for the one concrete fact that separates need from preference."
            if reflective_deliberation_kind == "purchase"
            else "Acknowledge the stalled iteration and ask for the one failing requirement that reveals whether to refine or restart."
            if reflective_deliberation_kind == "iteration"
            else "Welcome the exploratory idea and ask what useful job it must do before judging its complexity."
            if reflective_deliberation_kind == "exploration"
            else "Acknowledge the user's uncertainty and ask for the one outcome or constraint that changes the decision."
        )
        expected_output = (
            "I think your instinct is worth listening to; wanting a machine can make every feature look essential. What concrete job or bottleneck must this purchase solve that your current setup cannot?"
            if reflective_deliberation_kind == "purchase"
            else "That sounds like the point where more iteration can hide the real problem instead of solving it. What specific requirement gets worse each time you fix another one?"
            if reflective_deliberation_kind == "iteration"
            else "Yes, and we do not need to decide whether the idea is clever yet. What useful job must it do better than the simpler alternative?"
            if reflective_deliberation_kind == "exploration"
            else "It sounds like the decision is missing one controlling fact, not more options. What outcome must this choice protect above everything else?"
        )
        evidence_need = "missing-user-context"
        capability = "clarification"
        missing = [
            "the concrete job or bottleneck the purchase must solve"
            if reflective_deliberation_kind == "purchase"
            else "the requirement that repeatedly gets worse during iteration"
            if reflective_deliberation_kind == "iteration"
            else "the useful job that would justify the idea's added complexity"
            if reflective_deliberation_kind == "exploration"
            else "the outcome or constraint that controls the decision"
        ]
        forbidden.extend(
            [
                "generic-decision-framework-dump",
                "invented-financial-example",
                "invented-timeline-or-growth-forecast",
                "premature-option-ranking",
            ]
        )
        tags.extend(
            [
                "reflective-deliberation",
                f"reflective-deliberation:{reflective_deliberation_kind}",
                "clarify-before-framework",
            ]
        )
        confidence = 0.97
    elif recurrent_problem_reengagement:
        domain = "clarification"
        target_surface = "conversation.recurrent_problem_reengagement"
        action_type = "ask_one_focused_clarification"
        requested_change = (
            "Acknowledge the frustration, offer a fresh pass, preserve the named problem, and ask only for the missing machine or system plus the current returning symptom."
        )
        expected_output = _recurrent_problem_reengagement_response(query)
        evidence_need = "missing-conversation-context"
        capability = "clarification"
        missing = ["the machine or system and the exact returning behavior"]
        forbidden.extend(
            [
                "assume-pc-or-operating-system",
                "generic-diagnostic-questionnaire",
                "premature-component-advice",
                "model-latency-before-clarification",
            ]
        )
        tags.extend(
            [
                "recurrent-problem-reengagement",
                "emotion-aware-clarification",
                "clarify-before-diagnosis",
            ]
        )
        confidence = 0.98
    elif contextual_correction:
        domain = "conversation"
        target_surface = "conversation.corrected_prior_answer"
        action_type = "reassess_answer_from_user_correction"
        requested_change = (
            "Use the prior topic and the user's correction as the controlling evidence, then replace the weak answer with a narrower conclusion or discriminating next step."
        )
        expected_output = (
            "A direct, natural reassessment that addresses the missed qualifier, keeps causes provisional, and does not repeat the prior answer or restart intake."
        )
        evidence_need = "conversation-context"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "ignore-user-correction",
                "repeat-prior-answer",
                "invent-new-domain",
                "generic-framework-dump",
                "unsupported-primary-cause",
            ]
        )
        additional_constraints.extend(
            [
                "The latest turn corrects the prior answer. Treat the corrected qualifier as the center of the response.",
                "Preserve the established object and operating context from prior turns; do not reinterpret an engineering machine as a computer or a design review as CAD creation.",
            ]
        )
        tags.extend(["contextual-correction", "preserve-prior-object"])
        confidence = 0.97
    elif context_dependent_correction:
        domain = "clarification"
        target_surface = "conversation.missing_correction_context"
        action_type = "ask_one_focused_clarification"
        requested_change = (
            "Acknowledge the correction, avoid inventing the absent prior answer or system, and ask for the minimum context needed to reason from the user's symptom."
        )
        expected_output = (
            "You're right to pull me back to the symptom, but I do not have the earlier answer or the machine context in this thread. What machine or system is failing, and what changes between cold operation and the moment it fails?"
        )
        evidence_need = "missing-conversation-context"
        capability = "clarification"
        missing = ["the prior answer and the machine or system being corrected"]
        forbidden.extend(
            [
                "invent-prior-answer",
                "assume-computer-or-operating-system",
                "generic-diagnostic-checklist",
                "pretend-context-is-present",
            ]
        )
        tags.extend(["context-dependent-correction", "clarify-before-diagnosis"])
        confidence = 0.98
    elif mixed_evidence_review_intake:
        domain = "clarification"
        target_surface = "conversation.mixed_evidence_review_intake"
        action_type = "ask_one_focused_clarification"
        requested_change = (
            "Explain the evidence-reconciliation workflow and request the source set plus the immediate part or interface at risk before changing geometry."
        )
        expected_output = (
            "Yes. I would reconcile the model, test evidence, and supplier documents first, mark every conflict and unknown, then separate what is safe to use from what needs verification before changing geometry. Can you attach the source set together and identify the next part or interface you are about to make?"
        )
        evidence_need = "missing-local-source-set"
        capability = "clarification"
        missing = ["the referenced model, evidence, supplier documents, and immediate part or interface"]
        forbidden.extend(
            [
                "premature-cad-creation",
                "generic-mating-geometry-blocker",
                "choose-source-without-reconciliation",
                "claim-files-were-inspected",
            ]
        )
        tags.extend(["mixed-evidence-review-intake", "reconcile-before-design"])
        confidence = 0.98
    elif capability_introspection:
        domain = "agent_runtime_capabilities"
        target_surface = "codex_cli_ui.current_runtime"
        action_type = (
            "explain_learning_and_correction_loop"
            if agent_learning_introspection
            else "explain_operation_interpretation_policy"
            if operation_discussion
            else "confirm_read_only_attachment_capability"
            if read_only_attachment_capability
            else "summarize_verified_runtime_capabilities"
        )
        requested_change = (
            "Explain honestly how the agent adapts within a conversation and how feedback becomes durable behavior, memory, regression, or code changes."
            if agent_learning_introspection
            else "Explain how the agent distinguishes a requested operation from a quoted, hypothetical, or discussed operation, including the relevant safety and evidence boundary."
            if operation_discussion
            else "Confirm whether the active local agent can inspect and compare a later attachment without modifying its source, and state that boundary directly."
            if read_only_attachment_capability
            else "Explain what the active local agent can do in this session using current access, tool, and integration evidence."
        )
        expected_output = (
            "A direct, personable explanation that distinguishes conversation context from durable system learning and does not claim automatic weight retraining."
            if agent_learning_introspection
            else "A concise first-person explanation of whether the named operation would execute, what evidence or confirmation controls it, and what the agent would do if intent remains ambiguous."
            if operation_discussion
            else "A narrow yes/no capability answer that preserves the read-only boundary and does not expand into a general capability inventory."
            if read_only_attachment_capability
            else "A concise, human-readable capability overview grounded in the active runtime rather than generic model defaults."
        )
        evidence_need = (
            "local-feedback-and-correction-architecture"
            if agent_learning_introspection
            else "local-operation-routing-and-safety-policy"
            if operation_discussion
            else "current-runtime-inventory"
        )
        capability = "runtime_capability_introspection"
        forbidden.extend(
            [
                "generic-chatbot-capability-disclaimer",
                "deny-current-filesystem-or-shell-access-without-runtime-evidence",
                "claim-unverified-plugin-or-machine-integration",
            ]
        )
        tags.extend(
            ["runtime-self-knowledge", "learning-and-correction"]
            if agent_learning_introspection
            else ["runtime-self-knowledge", "operation-intent-policy"]
            if operation_discussion
            else ["runtime-self-knowledge", "verified-capability-inventory"]
        )
        confidence = 0.98
        if read_only_attachment_capability:
            operation_plan = {
                "operations": [
                    {
                        "operation": "inspect",
                        "state": "discussed",
                        "condition": "the attachment is not available in this turn; capability discussion only",
                        "authoritySurface": "local-artifact",
                    },
                    {
                        "operation": "change",
                        "state": "prohibited",
                        "condition": "the user explicitly requested a read-only comparison",
                        "authoritySurface": "local-artifact",
                    },
                ],
                "allowedNow": [],
                "prohibited": ["change"],
                "discussed": ["inspect"],
                "deferred": [],
                "readOnly": True,
                "requiresConfirmation": False,
                "authorityBySurface": {
                    "local-artifact": {
                        "allowedNow": [],
                        "prohibited": ["change"],
                        "deferred": [],
                        "discussed": ["inspect"],
                    }
                },
                "authorityVersion": 2,
            }
            tags.append("read-only-attachment-capability")
    elif decision_metric_design:
        domain = "decision_metric_design"
        target_surface = "knowledge.decision_metric"
        action_type = "design_decision_aligned_metric"
        requested_change = (
            "Choose outcome-aligned numerators, denominators, and comparison cohorts so changes in exposure or work mix do not masquerade as changes in reliability or performance."
        )
        expected_output = (
            "A direct metric recommendation that distinguishes event probability, exposure hazard, and consequence; keeps numerator and denominator units aligned; controls for mix shift; and states the uncertainty boundary."
        )
        evidence_need = "user-defined-outcome-exposure-and-comparison-periods"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "raw-count-conclusion",
                "mismatched-numerator-and-denominator",
                "one-denominator-for-different-decisions",
                "invented-duration-bins-or-data-schema",
                "statistical-significance-without-test",
                "specialist-routing-from-domain-noun",
            ]
        )
        additional_constraints.extend(
            [
                "Match the numerator to the unit at risk: failed jobs require jobs started, failed parts require parts produced, and time-based events require comparable exposure time.",
                "Keep event probability, exposure-normalized hazard, and consequence or waste as separate metrics because they answer different decisions.",
                "Compare like cohorts or standardize to the intended work mix before calling a period better or worse; machine, product, material, duration, and failure mode can be stratification variables rather than denominators.",
                "Do not call a rate change statistically significant without an uncertainty calculation, and do not invent bins, thresholds, examples, or data-column positions.",
                "On follow-up, preserve the original business question and explain how each newly supplied exposure measure changes what can be concluded.",
            ]
        )
        tags.extend(
            [
                "decision-metric-design",
                "denominator-semantics",
                "mix-shift-control",
                "follow-up-continuity" if decision_metric_followup else "exposure-normalization",
            ]
        )
        confidence = 0.97 if decision_metric_followup else 0.94
    elif engineering_project_intake:
        domain = "engineering_advisory"
        target_surface = "knowledge.engineering.project_intake"
        action_type = "scope_engineering_project"
        requested_change = (
            "Confirm the engineering support available, identify the architecture or operating-point ambiguity that controls the work, "
            "and ask one focused question before detailed design or sourcing begins."
        )
        expected_output = (
            "A natural expert intake response: answer the capability question, name the workstreams, expose the first decision-changing ambiguity, "
            "and ask one focused question without inventing calculations, components, or completed analysis."
        )
        evidence_need = "user-design-objective"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "premature-cad-or-solver-execution",
                "invented-component-or-source",
                "invented-operating-point",
                "shopping-before-requirements",
                "claim-completed-analysis",
            ]
        )
        tags.extend(["engineering-project-intake", "clarify-before-design", "model-first"])
        confidence = 0.96
    elif engineering_project_definition_followup:
        domain = "engineering_advisory"
        target_surface = "knowledge.engineering.project_definition"
        action_type = "advance_engineering_project_definition"
        requested_change = (
            "Use the architecture and targets supplied after project intake to define the first engineering phase, "
            "preserve every stated constraint, and identify the next decision that controls feasibility."
        )
        expected_output = (
            "A direct expert next-step answer that names what to do first, explains why that step controls the downstream "
            "CAD, simulation, sizing, and sourcing work, and asks at most one decision-changing question."
        )
        evidence_need = "user-defined-architecture-and-operating-targets"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "reset-to-project-intake",
                "treat-project-definition-as-option-reassessment",
                "drop-user-supplied-architecture-or-targets",
                "unrelated-domain-recovery-template",
                "premature-cad-or-solver-execution",
                "invented-component-or-source",
            ]
        )
        additional_constraints.extend(
            [
                "The previous assistant turn asked the project-defining question and the latest turn answered it. Advance the project instead of repeating intake or reassessing an unrelated prior recommendation.",
                "Carry every supplied architecture choice, operating target, mass or packaging limit, voltage, and mission condition into the first feasibility step.",
            ]
        )
        tags.extend(["engineering-project-definition", "intake-follow-up", "model-first"])
        confidence = 0.97
    elif selected_work_next_step_followup:
        context_relationship = {
            "contextRelation": "follow-up",
            "contextScope": "prioritization-selection",
            "sharedTopicTerms": context_relationship.get("sharedTopicTerms") or [],
            "reason": "The latest turn selects one of the previously named work items and asks to advance it.",
        }
        domain = "conversation"
        target_surface = "conversation.selected_work_first_step"
        action_type = "advance_selected_work_with_smallest_reversible_step"
        requested_change = (
            "Carry the user's chosen work item forward and name the smallest useful, reversible first step without reopening the priority decision."
        )
        expected_output = (
            "A short, context-aware first step that names the selected work, begins read-only for hardware or configuration tasks, and defines the proof needed before making changes."
        )
        evidence_need = "conversation-context"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "reset-to-prioritization-intake",
                "ask-user-to-repeat-selected-work",
                "premature-live-hardware-change",
                "generic-productivity-framework",
            ]
        )
        additional_constraints.extend(
            [
                "The latest turn selects one of the previously named work items. Preserve that selection and answer the requested first step.",
                "For wiring, controller, machine, or configuration work, begin with read-only reconciliation and do not touch live hardware or edit the active configuration.",
            ]
        )
        tags.extend(
            [
                "selected-work-next-step",
                "contextual-decision",
                "smallest-reversible-step",
            ]
        )
        confidence = 0.98
    elif multi_item_prioritization_followup:
        domain = "conversation"
        target_surface = "conversation.prioritization_decision"
        action_type = "rank_competing_work_from_supplied_constraints"
        requested_change = (
            "Use the supplied commitment, blocker, usability, dependency, and deadline facts to choose the next project and order the remaining work."
        )
        expected_output = (
            "A brief natural recommendation that names what to do first, explains the decisive supplied fact, and orders the remaining work without an empty scoring template."
        )
        evidence_need = "conversation-context"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "reset-to-prioritization-intake",
                "empty-scoring-table",
                "generic-typical-order",
                "invented-repair-step",
                "invented-tolerance-or-technical-threshold",
                "single-keyword-specialist-takeover",
            ]
        )
        additional_constraints.extend(
            [
                "This is the answer to the prior prioritization question. Keep the entire project list and use only the supplied urgency, commitment, blocker, usability, dependency, and deadline facts.",
                "Lead with the chosen project. Do not invent repair actions, technical tolerances, revenue claims, weekend availability, or a scoring system.",
                "Write exactly two short natural sentences under 100 words, without headings, a table, or numbered scoring. In the first sentence choose the project and cite only its supplied blocker, commitment, or deadline; in the second sentence order the remaining named work using only its supplied state.",
                "Do not add a hypothetical reversal example, a third sentence, or benefits, risks, consequences, and technical details the user did not supply.",
            ]
        )
        tags.extend(["multi-item-prioritization-followup", "contextual-decision", "model-first"])
        confidence = 0.97
    elif clarification:
        overwhelmed_prioritization = bool(
            unspecified_multi_item_prioritization
            and re.search(
                r"\b(?:head\s+is\s+(?:a\s+little\s+)?scattered|scattered|overwhelmed|"
                r"cannot\s+focus|can't\s+focus|too\s+many\s+directions)\b",
                lower,
            )
        )
        domain = "clarification"
        target_surface = (
            "conversation.prioritization_inputs"
            if unspecified_multi_item_prioritization
            else "conversation.missing_local_artifacts"
            if missing_local_artifact_inputs
            else "conversation.strength_requirements"
            if strength_improvement_clarification
            else "conversation.missing_referent"
        )
        action_type = "ask_one_focused_clarification"
        requested_change = (
            "Collect the minimum option, completion, and blocker facts needed to help the user choose what to do next."
            if unspecified_multi_item_prioritization
            else "Resolve the missing source artifacts before inspecting or changing local files."
            if missing_local_artifact_inputs
            else "Recover the missing target or desired end state before acting."
        )
        expected_output = (
            "Let's make this lighter. Which one blocks work you already committed to, or gives you back a capability you need next?"
            if overwhelmed_prioritization and named_multi_item_prioritization
            else "Let's get the noise down first. What are the competing directions, and which one creates the biggest problem if it waits until tomorrow?"
            if overwhelmed_prioritization
            else "One concise clarification question."
        )
        evidence_need = "missing-user-context"
        capability = "clarification"
        missing = (
            ["the competing items, the completion condition for each, and the current blocker for each"]
            if unspecified_multi_item_prioritization
            else ["the source file attachments or exact local paths"]
            if missing_local_artifact_inputs
            else [
                "the part or assembly to strengthen",
                "the governing load and load direction",
                "the failure mode or measurable success target",
            ]
            if strength_improvement_clarification
            else ["the target object or prior action the user wants changed"]
        )
        forbidden.extend(["guess-the-target", "unrelated-technical-answer"])
        tags.append(
            "named-multi-item-prioritization"
            if named_multi_item_prioritization
            else "multi-item-prioritization"
            if unspecified_multi_item_prioritization
            else "missing-local-artifact-inputs"
            if missing_local_artifact_inputs
            else "strength-requirements-clarification"
            if strength_improvement_clarification
            else "missing-referent"
        )
        if overwhelmed_prioritization:
            tags.append("overwhelmed-prioritization")
        if binary_work_prioritization:
            tags.append("binary-work-prioritization")
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
        tags.extend(
            [
                "artifact-work",
                "cad",
                "printable-physical-artifact"
                if printable_artifact_execution
                else "explicit-cad-format",
                "capability-first",
            ]
        )
        confidence = 0.9
    elif typed_local_artifact_output:
        domain = "general_action"
        target_surface = "local.generated_artifact"
        action_type = "inspect_plan_execute_verify"
        requested_change = (
            "Create the explicitly requested local artifact in the requested format, preserve the user's content constraints, and verify the saved output."
        )
        expected_output = "A saved local artifact with its path, requested-format proof, and focused verification, or one precise blocker."
        evidence_need = "local-artifact-path-format-and-verification"
        capability = "local_agent"
        forbidden.extend(
            [
                "conversation-only-answer-when-artifact-was-requested",
                "claim-created-without-path",
                "wrong-output-format",
            ]
        )
        tags.extend(["artifact-work", "generic-local-artifact", "capability-first"])
        confidence = 0.94
    elif comparative_local_diagnostic:
        domain = "local_product_action"
        target_surface = "local.reference_implementation_diagnostic"
        action_type = "inspect_compare_diagnose_verify"
        requested_change = (
            "Use the user-named working local implementations as reference evidence, inspect the current implementation, "
            "trace the behavioral difference to its cause, and verify the requested correction when the target is writable."
        )
        expected_output = (
            "A local-evidence diagnosis with the reference behavior, current behavior, root cause, changed files when applicable, "
            "and a focused verification result or one precise blocker."
        )
        evidence_need = "local-reference-app-and-code-evidence"
        capability = "local_code_agent"
        forbidden.extend(
            [
                "abstract-comparison-instead-of-local-inspection",
                "generic-troubleshooting-without-reference-evidence",
                "claim-root-cause-without-code-or-runtime-proof",
            ]
        )
        tags.extend(["local-reference-diagnostic", "root-cause", "model-first"])
        confidence = 0.95
    elif analytical_local_file:
        domain = "local_file_analysis"
        target_surface = "local.files"
        action_type = "analyze_local_files"
        requested_change = (
            "Resolve the named local files, inspect their contents read-only, and perform the exact requested "
            "counting, filtering, quotation, duplicate detection, ordering, or comparison operation."
        )
        expected_output = (
            "A direct file-grounded result in the requested shape, with every named file covered and the observed "
            "content or exact access blocker preserved."
        )
        evidence_need = "task-specific-local-file-evidence"
        capability = "local_file_analysis"
        forbidden.extend(
            [
                "fixed-similarity-summary-for-analytical-file-request",
                "keyword-route-from-file-content",
                "claim-file-content-without-tool-evidence",
            ]
        )
        tags.extend(["local-file", "analytical-file", "model-first"])
        confidence = 0.95
    elif local_state_explanation:
        domain = "local_product_action"
        target_surface = "local.product_state_evidence"
        action_type = "inspect_explain_local_state"
        requested_change = (
            "Inspect the current local product state read-only, explain the actual failures, errors, health, logs, or test results from evidence, "
            "and preserve every prohibited or confirmation-gated repair boundary."
        )
        expected_output = (
            "A current local-evidence explanation with the checked result or exact inspection blocker, followed by an explicit statement of what was not changed and what still requires confirmation."
        )
        evidence_need = "current-local-runtime-test-or-log-evidence"
        capability = "local_code_agent"
        forbidden.extend(
            [
                "generic-troubleshooting-without-current-local-evidence",
                "invent-package-or-dependency-failure",
                "perform-deferred-repair-before-confirmation",
                "claim-local-state-without-inspection",
            ]
        )
        tags.extend(["local-state-explanation", "read-only-diagnostic", "model-first"])
        confidence = 0.95
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
    elif ebay_marketplace:
        domain = "marketplace_listing_research"
        target_surface = "knowledge.marketplace.ebay"
        action_type = "search_and_verify_marketplace_listings"
        requested_change = "Find exact eBay item pages, inspect each viable listing, and compare the full delivered-value and seller-risk evidence."
        expected_output = "A readable best-deal recommendation with clickable exact item links, checked fields, rejected mismatches, and explicit unknowns."
        evidence_need = "current-marketplace-item-evidence"
        capability = "ebay_marketplace_research"
        forbidden.extend(
            [
                "claim-marketplace-access-is-unavailable-before-trying-public-item-pages",
                "buyer-guide-instead-of-listing",
                "search-snippet-as-complete-listing-check",
                "unverified-authenticity-claim",
            ]
        )
        tags.extend(["current-marketplace", "ebay", "model-first"])
        confidence = 0.95
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
        domain = "local_file_work" if has_action and not read_only_scope else "local_file_evidence"
        target_surface = "local.files"
        action_type = "inspect_or_modify_local_files" if has_action and not read_only_scope else "inspect_local_files"
        requested_change = "Use the named or attached files as primary evidence before answering."
        expected_output = "A file-grounded result, artifact, or precise blocker."
        evidence_need = "local-file-evidence"
        capability = "local_file_work" if has_action and not read_only_scope else "local_file_retrieval"
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
    elif representation_followup:
        domain = "knowledge_comparison"
        target_surface = "knowledge.comparison"
        action_type = "continue_representation_comparison"
        requested_change = (
            "Answer the representation follow-up from the established named options, definitions, and evidence boundary without resetting the topic."
        )
        expected_output = (
            "A direct contextual answer that applies the prior representation distinction to the latest question and states only what the prior checked result supports."
        )
        evidence_need = "conversation-context-with-prior-checked-evidence"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "reset-to-generic-component-compatibility",
                "drop-prior-comparison-options",
                "manufacture-engineering-operating-point",
                "repeat-source-research-without-request",
            ]
        )
        additional_constraints.extend(
            [
                "Preserve the prior named representations, semantic family, reader-direction definitions, and evidence boundaries.",
                "Answer from the immediately prior checked conclusion when the user says `based on what you just found`; do not demand a new operating point or unrelated datasheet.",
            ]
        )
        tags.extend(
            [
                "representation-follow-up",
                "follow-up-continuity",
                "model-first",
            ]
        )
        confidence = 0.97
    elif explicit_research:
        if engineering_tradeoff:
            domain = "engineering_tradeoff"
            target_surface = "knowledge.engineering_tradeoff"
            action_type = "research_then_compare_decision_factors"
            requested_change = (
                "Research primary technical evidence for the named options, then compare them at the user's "
                "operating point and make a qualified engineering recommendation."
            )
            expected_output = (
                "A primary-source-bounded engineering recommendation with decision-driving assumptions, "
                "reversal conditions, and explicit evidence limits."
            )
            evidence_need = "technical-primary-evidence"
            capability = "current_web_research"
            forbidden.extend(
                [
                    "skip-requested-research",
                    "source-list-without-synthesis",
                    "unsupported-technical-precision",
                ]
            )
            tags.extend(["explicit-research", "engineering-tradeoff", "primary-technical-evidence", "model-first"])
            confidence = 0.94
        else:
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
    elif technical_source_lookup and not engineering_tradeoff:
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
    elif fault_isolation_experiment:
        domain = "engineering_advisory"
        target_surface = "knowledge.engineering.diagnostic_experiment"
        action_type = "design_fault_isolation_experiment"
        requested_change = (
            "Design the smallest controlled experiment that distinguishes the user-named physical failure hypotheses, "
            "then state what the available observations can and cannot establish."
        )
        expected_output = (
            "A fault-isolation plan with a repeatable baseline, one controlled intervention at a time, truthful signal semantics, "
            "explicit stop conditions, and hypothesis-specific evidence boundaries."
        )
        evidence_need = "user-available-instrumentation-and-physical-test-evidence"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "invent-unavailable-instrumentation",
                "treat-command-as-observation",
                "drop-prior-hypotheses-on-follow-up",
                "declare-cause-from-one-correlated-signal",
                "invent-universal-stop-threshold",
            ]
        )
        additional_constraints.extend(
            [
                "Preserve every named failure hypothesis across follow-ups and change one experimental variable at a time.",
                "Distinguish controller commands and setpoints from measured electrical, thermal, mechanical, and position state.",
                "Never claim that a missing fault flag proves no transient occurred, or that commanded motion proves the mechanism actually moved.",
                "If the available instrumentation cannot rule out a branch, say so and name the minimum direct measurement or controlled intervention needed.",
                "Use component protection, documented limits, and observed unsafe behavior for stop conditions; do not invent numeric thresholds.",
            ]
        )
        tags.extend(
            [
                "engineering-advisory",
                "fault-isolation-experiment",
                "measurement-semantics",
                "follow-up-continuity" if fault_isolation_followup else "competing-hypotheses",
                "model-first",
            ]
        )
        confidence = 0.96 if fault_isolation_followup else 0.93
    elif typed_constraint_update.get("status") == "resolved":
        domain = str(prior_frame.get("domain") or "conversation")
        target_surface = str(prior_frame.get("targetSurface") or "conversation.answer")
        action_type = (
            "recompute_with_superseded_constraint"
            if domain == "engineering_calculation"
            else "reevaluate_with_superseded_constraint"
        )
        requested_change = (
            "Recompute the established calculation after replacing only the explicitly changed input; preserve every other supplied input, requested output, and assumption."
            if domain == "engineering_calculation"
            else "Reevaluate the established result after replacing only the explicitly changed rule or constraint; preserve every unaffected premise and requested output."
        )
        expected_output = (
            "An updated checked result for every originally requested output, with the changed input and comparison to the prior values explicit."
            if domain == "engineering_calculation"
            else "An updated conclusion that applies the replacement rule and states exactly what changed from the prior result."
        )
        evidence_need = str(prior_frame.get("evidenceNeed") or "conversation-context")
        capability = str(
            typed_constraint_update.get("priorCapability")
            or (prior_frame.get("routeCandidates") or ["conversation_reasoning"])[0]
        )
        additional_constraints.extend(
            [
                "Preserve the prior typed owner and replace only the explicitly named input; do not reinterpret a closed update as a new generic problem.",
                "Carry forward every unaffected premise, output role, evidence boundary, and assumption from the semantically linked turn.",
                "If the replacement target or value is not explicit, ask one focused clarification before tools or model work.",
            ]
        )
        forbidden.extend(
            [
                "promote-closed-update-to-deep-conditional-review",
                "drop-unaffected-prior-constraints",
                "invent-replacement-value",
                "reuse-stale-prior-result-without-recomputation",
            ]
        )
        tags.extend(
            [
                "typed-constraint-update",
                "closed-input-supersession",
                "follow-up-continuity",
                "model-first",
            ]
        )
        confidence = 0.97
    elif engineering_decision_followup:
        domain = str(prior_frame.get("domain") or "engineering_advisory")
        target_surface = str(prior_frame.get("targetSurface") or "knowledge.engineering_tradeoff")
        stable_comparison_followup = domain == "knowledge_comparison"
        action_type = (
            "reassess_comparison_with_new_priority"
            if stable_comparison_followup
            else "reassess_engineering_conclusion_with_new_constraints"
        )
        requested_change = (
            "Reassess the prior comparison using the latest priority while preserving the same alternatives and stable evidence boundary."
            if stable_comparison_followup
            else
            "Reassess the prior engineering conclusion using the latest constraints, preserving the same alternatives, "
            "decision objective, and evidence boundary."
        )
        expected_output = (
            "A conditional engineering reassessment that carries forward the established baseline, addresses every new condition, calculates only supported changes, and states directly whether the prior conclusion remains proven."
            if domain == "engineering_calculation"
            else "A direct statement of whether the changed priority reverses the recommendation, why, and what would still change the choice."
            if stable_comparison_followup
            else "A direct statement of what the new assumptions settle, what remains unresolved, and the next measurement or fact needed."
        )
        evidence_need = (
            str(prior_frame.get("evidenceNeed") or "conversation-context")
            if stable_comparison_followup
            else
            "engineering-principles-and-decision-changing-property-boundary"
            if domain == "engineering_calculation"
            else "engineering-context"
        )
        capability = (
            "engineering_calculation"
            if domain == "engineering_calculation"
            else "conversation_reasoning"
        )
        forbidden.extend(
            [
                "reset-to-general-question",
                "drop-prior-comparison-options",
                "invent-device-loss-or-thermal-values",
                "declare-winner-from-shared-boundary-conditions-alone",
            ]
        )
        additional_constraints.append(
            "Carry forward the prior engineering alternatives and objective; treat the latest quantities as added conditions, not as a new standalone topic."
        )
        if domain == "engineering_calculation":
            additional_constraints.extend(
                [
                    "Preserve the prior numerical baseline and visibly address every newly supplied dimension, load, operating condition, and limit.",
                    "Calculate only updated quantities supported by the supplied geometry and properties; do not invent a coefficient, derated property, geometry interpretation, source, or test to force an exact answer.",
                    "If a missing value changes the acceptance decision, state whether the prior conclusion is no longer proven and name the one decision-changing evidence or validation step instead of fabricating precision.",
                ]
            )
            forbidden.extend(
                [
                    "invent-updated-material-property",
                    "invent-stress-or-derating-coefficient",
                    "force-exact-reassessment-from-missing-inputs",
                ]
            )
        tags.extend(
            ["comparison-follow-up", "priority-update", "model-first"]
            if stable_comparison_followup
            else ["engineering-follow-up", "constraint-update", "model-first"]
        )
        confidence = 0.95
    elif engineering_suitability:
        domain = (
            "material_process_behavior"
            if material_process_behavior
            else "engineering_advisory"
        )
        target_surface = "knowledge.engineering_suitability"
        action_type = "evaluate_operating_suitability"
        requested_change = (
            "Evaluate whether the named material, component, or system is suitable under the stated operating conditions."
        )
        expected_output = (
            "A direct conditional engineering judgment covering the controlling property, system-level constraints, failure modes, and a practical validation boundary."
        )
        evidence_need = "technical-evidence-if-grade-or-rating-dependent"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "generic-yes-without-system-constraints",
                "unsupported-material-or-component-rating",
                "unrelated-product-or-prior-topic",
            ]
        )
        additional_constraints.extend(
            [
                "Preserve the construction and identity of the object the user named; do not silently replace it with a coated, filled, bonded, composite, or substrate-backed variant.",
                "If grade, construction, duty, or supporting interfaces change the conclusion, give conditional branches or ask one focused clarification instead of assuming a subtype.",
            ]
        )
        tags.extend(
            [
                "engineering-suitability",
                "material-process-behavior" if material_process_behavior else "operating-condition-evaluation",
                "model-first",
            ]
        )
        confidence = 0.9
    elif engineering_calculation:
        domain = "engineering_calculation"
        target_surface = "knowledge.engineering_calculation"
        sizing_needs_operating_point = bool(
            engineering_sizing_request
            and len(_DECISION_QUANTITY_RE.findall(query)) < 2
        )
        action_type = (
            "clarify_engineering_sizing_operating_point"
            if sizing_needs_operating_point
            else "derive_load_and_compare_drive_architectures"
            if load_derived_drive_sizing
            else "calculate_engineering_result"
        )
        requested_change = (
            "Collect the minimum design-driving load and boundary conditions before sizing the named engineering component or system."
            if sizing_needs_operating_point
            else (
                "Derive the required drive output from the supplied load and operating point, compare the named architectures on the same basis, and size every requested motor/controller quantity."
            )
            if load_derived_drive_sizing
            else "Solve the stated engineering calculation completely, preserving every supplied quantity, unit, orientation, and acceptance criterion."
        )
        expected_output = (
            "One focused question for the operating-point values that control the sizing result, without an invented numerical example."
            if sizing_needs_operating_point
            else (
                "A checked load-path calculation, numerical result for every requested output, and an architecture recommendation with duty, thermal, traction or transmission assumptions and reversal conditions."
            )
            if load_derived_drive_sizing
            else "A checked numerical engineering result with formulas, substitutions, units, assumptions, a sanity check, and a direct acceptance conclusion."
        )
        evidence_need = "engineering-principles-and-labeled-reference-assumptions"
        capability = "engineering_calculation"
        if sizing_needs_operating_point:
            missing = [
                "the design-driving load, allowable operating limits, and boundary conditions required for sizing"
            ]
        forbidden.extend(
            [
                "formula-only-answer",
                "ask-for-standard-reference-value-instead-of-estimating",
                "omit-requested-numerical-output",
                "dimensionally-inconsistent-equation",
                "unrelated-artifact-or-research-route",
                "invented-sizing-example-before-operating-point",
            ]
        )
        additional_constraints.extend(
            [
                "Complete the arithmetic for every requested output; a formula without substituted numerical results is not complete.",
                "When the user names a standard material grade or established physical constant, use a conventional reference value as an explicit engineering assumption when that supports the requested estimate; ask only when the exact value changes the safe conclusion.",
                "Check dimensions, compare the result with the stated limit or factor of safety, and say directly whether each case passes under the stated assumptions.",
            ]
        )
        if load_derived_drive_sizing:
            additional_constraints.extend(
                [
                    "Derive force, speed, torque, and power from the load-side operating point before selecting or rating a motor, controller, or transmission.",
                    "Compare every named architecture at the same wheel, drum, shaft, or load output; preserve transmission ratio direction and efficiency explicitly.",
                    "Separate steady-state from acceleration and continuous from peak duty. Distinguish DC source current from motor phase current and do not invent a phase-current target without a torque constant or motor map.",
                    "Give a provisional engineering recommendation from the supplied facts, then name the missing thermal, traction, duty, or component evidence that could reverse it.",
                ]
            )
            forbidden.extend(
                [
                    "ask-for-existing-motor-rating-before-deriving-load",
                    "convert-published-rating-instead-of-solving-load",
                    "omit-architecture-comparison",
                    "equate-battery-current-with-phase-current",
                ]
            )
        if sizing_needs_operating_point:
            additional_constraints.extend(
                [
                    "Do not invent a representative load, flow, temperature, duty cycle, material property, or equipment rating to avoid asking for the operating point.",
                    "Ask one focused question that groups the minimum values needed to make the sizing calculation meaningful.",
                ]
            )
        tags.extend(["engineering-calculation", "quantitative", "model-first"])
        if load_derived_drive_sizing:
            tags.extend(
                [
                    "load-derived-drive-sizing",
                    "architecture-comparison",
                    "engineering-tradeoff",
                ]
            )
        confidence = 0.94
    elif engineering_advisory:
        domain = "engineering_advisory"
        target_surface = "knowledge.engineering.advisory_decision"
        action_type = "answer_engineering_judgment"
        requested_change = (
            "Evaluate the complete technical design or operating decision from the stated topology, "
            "constraints, failure paths, and validation boundary."
        )
        expected_output = (
            "A direct engineering judgment that separates what is established, what remains conditional, "
            "and the one missing fact or measurement that could reverse the recommendation."
        )
        evidence_need = "engineering-context"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "keyword-only-answer",
                "action-route-for-a-question",
                "wrong-system-layer",
                "unsupported-technical-precision",
            ]
        )
        additional_constraints.append(
            "Reason through the complete physical system and duty cycle; do not reduce a design judgment to one repeated keyword or component name."
        )
        if multi_layer_power_system_design:
            additional_constraints.extend(
                [
                    "Build the complete power chain from source through conversion and drive, motor, driven load or process, normal control, protection, and safe stop behavior.",
                    "Keep source compatibility, converter input limits, converter output rating, motor mechanical duty, loaded startup, and process protection as separate design layers.",
                    "Use supplied quantities for bounded calculations, but do not turn the full architecture decision into a unit-conversion answer or require an unrelated rating before giving useful system guidance.",
                    "Name the exact manuals, nameplates, topology facts, and load-state evidence that must be verified before parts are purchased.",
                ]
            )
            forbidden.extend(
                [
                    "power-unit-conversion-only-answer",
                    "single-component-controller-sizing-answer",
                    "omit-source-converter-load-chain",
                    "treat-soft-start-as-loaded-start-proof",
                ]
            )
            tags.append("multi-layer-power-system-design")
        tags.extend(["engineering-advisory", "design-judgment", "model-first"])
        confidence = 0.9
    elif comparison:
        domain = "engineering_tradeoff" if engineering_tradeoff else "knowledge_comparison"
        target_surface = "knowledge.engineering_tradeoff" if engineering_tradeoff else "knowledge.comparison"
        action_type = "compare_decision_factors"
        requested_change = (
            "Explain the requested distinctions between the named options without turning the question into an unrequested choice."
            if comparison_speech_act == "explanation"
            else "Compare the named options against the property or outcome the user actually asked about."
        )
        expected_output = (
            "A source-bounded engineering recommendation with decision-driving assumptions and reversal conditions."
            if engineering_tradeoff
            else "A direct explanation of the requested distinctions and their practical consequences, without an unrequested recommendation or validation plan."
            if comparison_speech_act == "explanation"
            else "A qualified comparison with a recommendation only when the user asked for a choice."
        )
        evidence_need = (
            "engineering-context"
            if engineering_tradeoff
            else "current-or-technical-evidence-if-claims-are-volatile"
        )
        capability = "conversation_reasoning"
        forbidden.extend(["keyword-only-answer", "unrelated-domain-template", "unsupported-technical-precision"])
        tags.extend([
            "comparison",
            "engineering-tradeoff" if engineering_tradeoff else "general-comparison",
            f"comparison-speech-act:{comparison_speech_act}",
            "model-first",
        ])
        confidence = 0.88 if engineering_tradeoff else 0.83
    elif decision_support:
        domain = "decision_support"
        target_surface = "knowledge.decision_support"
        action_type = "reason_about_decision"
        requested_change = (
            "Identify the decision the user is actually trying to make, separate the objective from a convenient proxy, "
            "and recommend the smallest useful way to compare or test the alternatives."
        )
        expected_output = (
            "A direct, personable judgment with the controlling criteria, hidden costs or risks, a provisional next move, "
            "and at most one question whose answer could reverse it."
        )
        evidence_need = "user-context-and-current-evidence-only-when-needed"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "action-route-for-a-decision-question",
                "generic-checklist-without-a-decision",
                "invented-business-or-technical-precision",
                "confuse-a-test-strategy-with-an-instruction-to-run-tools",
            ]
        )
        additional_constraints.extend(
            [
                "Distinguish the outcome the user values from the metric, structure, or action they are considering as a proxy.",
                "Choose a provisional first move from the supplied context; do not return an unranked list of considerations.",
                "When a small real-world trial can close the decision, define what changes, what stays fixed, and what result would favor each option.",
            ]
        )
        tags.extend(["decision-support", "proxy-versus-outcome", "model-first"])
        confidence = 0.88
    elif programming_order_question:
        domain = "clarification"
        target_surface = "conversation.programming_contract"
        action_type = "ask_one_focused_clarification"
        requested_change = "Define the reference order required by the requested programming guarantee before selecting an API or algorithm."
        expected_output = programming_order_question
        evidence_need = "missing-user-context"
        capability = "clarification"
        missing = ["the authoritative input-order definition for the requested stability guarantee"]
        forbidden.extend(
            [
                "guess-reference-order",
                "implement-incompatible-api-before-clarification",
                "claim-incidental-discovery-order-is-stable",
            ]
        )
        tags.extend(["programming-contract-clarification", "order-semantics"])
        confidence = 0.97
    elif inline_programming_answer:
        domain = "conversation"
        target_surface = "conversation.programming_answer"
        action_type = "reason_and_answer"
        requested_change = (
            "Provide the requested code in the conversation and explain the named behavior, invariant, tests, or edge cases."
        )
        expected_output = "Concise runnable code with the requested explanation and examples."
        evidence_need = "none"
        capability = "conversation_reasoning"
        forbidden.extend(
            [
                "treat-inline-code-as-local-file-edit",
                "require-saved-artifact-proof",
                "claim-unrequested-local-execution",
            ]
        )
        tags.extend(["inline-programming", "model-first"])
        confidence = 0.9
    elif (
        typed_local_action_output
        or (
            has_action
            and explicit_local_action_target
            and output_contract.get("mode") != "conversation-answer"
        )
    ):
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
    operation_authority = operation_plan.get("authorityBySurface") or {}
    if live_device_refs and operation_authority.get("live-device"):
        refs = list(
            {
                (str(item.get("type") or ""), str(item.get("name") or "")): item
                for item in [*refs, *live_device_refs]
                if isinstance(item, dict) and item.get("name")
            }.values()
        )[:8]
    prioritization_items = _named_prioritization_items(
        previous
        if multi_item_prioritization_followup or selected_work_next_step_followup
        else query
    )
    if live_device_action:
        refs = live_device_refs or [
            {
                "type": "unresolved-live-device-target",
                "name": "physical target named or implied by the latest request",
            }
        ]
    elif verification_receipt_status:
        refs = [
            {
                "type": "local-verification-summary",
                "name": "Codex CLI UI Verification Summary",
            }
        ]
    elif engineering_calculation:
        refs = [
            {
                "type": "engineering-problem",
                "name": "engineering calculation described in the latest request",
            }
        ]
    if prioritization_items:
        refs = [
            {"type": "competing-work-item", "name": item}
            for item in prioritization_items
        ]
    elif comparative_local_diagnostic:
        refs = [
            {"type": "reference-implementation", "name": "working local implementations named by the user"},
            {"type": "diagnostic-target", "name": "the current local implementation and its observed output"},
        ]
    elif decision_support and parsed_decision_refs:
        refs = parsed_decision_refs
    elif comparison and parsed_comparison_refs and not engineering_calculation:
        refs = parsed_comparison_refs
    elif engineering_project_definition_followup and not refs:
        refs = [
            *[
                dict(item)
                for item in (prior_frame.get("objectRefs") or [])
                if isinstance(item, dict)
                and item.get("name")
                and item.get("type") != "user-described-target"
            ],
            *_engineering_system_refs(query),
        ][:8]
    elif typed_constraint_update.get("status") == "resolved" and not refs:
        refs = [
            dict(item)
            for item in (prior_frame.get("objectRefs") or [])
            if isinstance(item, dict) and item.get("name")
        ]
    elif engineering_decision_followup and not refs:
        refs = [
            dict(item)
            for item in (prior_frame.get("objectRefs") or [])
            if isinstance(item, dict) and item.get("name")
        ]
    if engineering_suitability and not refs:
        engineering_subject = _engineering_suitability_subject(query)
        if not engineering_subject and engineering_suitability_followup:
            engineering_subject = _engineering_suitability_subject(previous)
        if engineering_subject:
            refs = [{"type": "engineering-subject", "name": engineering_subject}]
    if fault_isolation_experiment and not refs:
        refs = _fault_isolation_hypothesis_refs(query)
        if not refs and fault_isolation_followup:
            refs = [
                dict(item)
                for item in (prior_frame.get("objectRefs") or [])
                if isinstance(item, dict)
                and item.get("type") == "fault-hypothesis"
                and item.get("name")
            ]
    if engineering_advisory and not refs:
        engineering_subject = _engineering_usage_subject(query)
        refs = (
            [{"type": "engineering-subject", "name": engineering_subject}]
            if engineering_subject
            else _engineering_system_refs(query)
        )
    if representation_followup:
        refs = [
            dict(item)
            for item in (prior_frame.get("objectRefs") or [])
            if isinstance(item, dict) and item.get("name")
        ]
        comparison = True
        comparison_speech_act = (
            _comparison_speech_act(query)
            or str(prior_frame.get("comparisonSpeechAct") or "comparison")
        )
    if comparison and not refs:
        refs = parsed_comparison_refs
    comparison_criteria = (
        []
        if engineering_calculation
        else _decision_support_concerns(query)
        if decision_support
        else _comparison_criteria(query, refs)
        if comparison
        else []
    )
    representation_semantics = (
        dict(prior_representation_semantics)
        if representation_followup
        else _representation_semantics_contract(query, refs)
        if comparison
        else {}
    )
    if representation_semantics:
        tags.append("representation-semantics")
        additional_constraints.extend(
            representation_semantics.get("requiredDistinctions") or []
        )
        forbidden.extend(
            representation_semantics.get("forbiddenInferences") or []
        )
    if engineering_decision_followup and not comparison_criteria:
        comparison_criteria = [
            str(item)
            for item in (prior_frame.get("comparisonCriteria") or [])
            if str(item or "").strip()
        ]
    if not refs:
        refs = [{"type": "user-described-target", "name": "target named in the latest request"}]
    context_constraint = (
        "Treat this as a new standalone topic; do not answer or summarize the completed prior task."
        if context_relationship.get("contextRelation") == "new-topic"
        else "Use prior turns only where the latest request refers to them."
    )
    return {
        "version": KERNEL_VERSION,
        "source": "generic-intelligence-kernel",
        "userGoal": requested_change,
        "domain": domain,
        "targetSurface": target_surface,
        "actionType": action_type,
        "objectRefs": refs,
        "comparisonCriteria": comparison_criteria,
        "comparisonSpeechAct": comparison_speech_act,
        "representationSemantics": representation_semantics,
        "operationPlan": operation_plan,
        "outputContract": output_contract,
        "semanticExclusions": semantic_exclusions,
        "requestedChange": requested_change,
        "expectedOutput": expected_output,
        "resolvedRequest": query if resolved_clarification_query else "",
        "evidenceNeed": evidence_need,
        "knownConstraints": [
            "Interpret the full request before routing from individual keywords.",
            "Ask one focused question only when missing information changes the correct action or answer.",
            "Prefer a real tool result or evidence boundary over a fast generic response.",
            context_constraint,
            *additional_constraints,
        ],
        "missingInfo": missing,
        "routeCandidates": [capability],
        "forbiddenRoutes": forbidden,
        "frameTags": tags,
        "confidence": confidence,
        "cwd": cwd,
        "interactionStance": _interaction_stance(query),
        "typedConstraintUpdate": (
            dict(typed_constraint_update)
            if typed_constraint_update.get("status") in {"resolved", "ambiguous"}
            else {}
        ),
        **(
            {"originalDomain": "verification-receipts"}
            if verification_receipt_status
            else {}
        ),
        **context_relationship,
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
        "profile_settings_carryover",
        "clarification",
        "high_stakes_policy",
        "privacy_boundary",
        "safety_boundary",
    }
    capability_domains = {
        "aero_cfd_work",
        "cad_artifact_work",
        "engineering_diagram_work",
        "generated_artifact_followup",
        "klipper_config_migration",
        "local_file_work",
        "local_file_evidence",
        "structural_fea_work",
    }
    research_domains = {
        "current_market_ranking",
        "current_market_research",
        "marketplace_listing_research",
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
        "current-marketplace-item-evidence",
        "scientific-or-primary-evidence",
        "technical-primary-evidence",
    }:
        explicit_marketplace_access = domain == "marketplace_listing_research"
        return {
            "version": KERNEL_VERSION,
            "mode": "model-first",
            "selectedCapability": capability or "current_web_research",
            "allowLegacyDirectAnswer": False,
            "useCompactPrompt": True,
            "engineOverride": (
                "local-research"
                if web_search == "live" or explicit_marketplace_access
                else "local"
            ),
            "reason": (
                "The user explicitly requested a bounded read-only marketplace search, so that named public source is authorized for this turn."
                if explicit_marketplace_access
                else "The answer needs synthesis from current or scientific evidence, not a stored response template."
            ),
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


def decision_support_response_contract(stage: str = "author") -> List[str]:
    """Keep author, repair, and verifier aligned on one human decision contract."""

    label = (
        "Decision-support candidate contract to verify:"
        if stage == "verification"
        else "Decision-support response contract:"
    )
    rules = [
        label,
        "- The user-facing answer has exactly three compact natural paragraphs separated by blank lines, with no other line breaks, headings, bullets, table, inline numbered criteria, or report scaffolding.",
        "- When interactionStance includes a greeting or investmentCue, paragraph 1 returns the greeting, calls the user Tinman rather than another personal name, briefly recognizes the stated effort, and makes a provisional choice before explaining it.",
        "- Paragraph 1 distinguishes the outcome the user values from the proxy, metric, or structure being considered; it does not merely restate the dilemma.",
        "- Paragraph 2 compares only the controlling criteria and hidden costs or risks using facts supplied by the user. It invents no sample size, price, threshold, legal claim, standard, option mechanism, or external fact.",
        "- The answer invents no customer, employee, supplier, or stakeholder motives, honesty, resistance, preferences, or behavior that Tinman did not supply.",
        "- Paragraph 3 applies both choices to the same historical, simulated, or otherwise controlled cases, states what stays fixed, and says what result favors each path. It never compares one choice on one case with the other choice on a different case.",
        "- A historical replay calculates how both choices would have performed on the same completed cases; it does not claim that two counterfactual choices both produced actual results.",
        "- The answer asks at most one question, and only when its answer could reverse the recommendation.",
        "- The full user-facing answer stays under 230 words and sounds like an experienced colleague thinking with Tinman, not an analyst filling out a form.",
    ]
    if stage == "verification":
        rules.append(
            "- Return `revise` if any candidate-contract item is absent, even when the factual discussion is otherwise plausible. Do not rewrite the candidate."
        )
    elif stage == "repair-json":
        rules.append(
            "- Return one JSON object only in the form {\"paragraphs\":[\"paragraph 1\",\"paragraph 2\",\"paragraph 3\"]}. Each array item is one paragraph with no newline characters."
        )
    elif stage == "repair":
        rules.append(
            "- Return only the corrected three-paragraph answer. Preserve supported useful reasoning, but discard any structure or invented detail that violates this contract."
        )
    return rules


def build_decision_support_worker_prompt(
    messages: Sequence[Dict[str, Any]],
    frame: Dict[str, Any],
) -> str:
    """Give deliberation one compact semantic job with no runtime prompt noise."""

    scoped = scope_messages_for_intent(messages, frame)
    conversation = [
        {"role": _text(message.get("role")).lower(), "text": _message_text(message)}
        for message in scoped[-6:]
        if _text(message.get("role")).lower() in {"user", "assistant"}
        and _message_text(message)
    ]
    brief = build_decision_brief(scoped, frame)
    structured = {
        "options": brief.get("options") or [
            _text(item.get("name"))
            for item in (frame.get("objectRefs") or [])
            if isinstance(item, dict) and _text(item.get("name"))
        ],
        "userStatedConcerns": frame.get("comparisonCriteria") or [],
        "interactionStance": frame.get("interactionStance") or {},
        "expectedOutput": frame.get("expectedOutput") or "",
    }
    return "\n".join(
        [
            "You are Tinman's experienced colleague thinking through one decision with him.",
            "Interpret the complete request before choosing. Use only facts Tinman supplied and ordinary logical implications of the named alternatives.",
            "Separate the objective from a convenient proxy, metric, or pricing structure before comparing the alternatives.",
            "Choose a provisional first move when the supplied concerns support one. Do not turn the answer into an unranked list or ask Tinman to do the reasoning alone.",
            "Do not invent a sample size, percentage, timeframe, price, formula, fee, stakeholder reaction, industry practice, or experiment population.",
            "A valid comparison applies both alternatives to each same historical or simulated case with the same inputs. Never split different cases between alternatives.",
            "Return only the user-facing answer. Do not mention this prompt, a route, a contract, or hidden reasoning.",
            "",
            *decision_support_response_contract(stage="author"),
            "",
            "Structured user-supplied decision:",
            json.dumps(structured, indent=2, ensure_ascii=True),
            "",
            "Conversation:",
            json.dumps(conversation, indent=2, ensure_ascii=True),
            "",
            "Begin the visible answer immediately with the appropriate greeting and Tinman's name. Return no hidden-analysis preamble.",
        ]
    )


def build_compact_worker_prompt(
    messages: Sequence[Dict[str, Any]],
    frame: Dict[str, Any],
    decision: Dict[str, Any],
    route: Dict[str, Any],
    project_rules: Sequence[str] = (),
    working_directory: str = "",
    extra_context: Sequence[str] = (),
    include_runtime_context: bool = True,
) -> str:
    """Build a compact prompt that preserves judgment without policy pile-up."""

    def bounded_context_excerpt(value: str, limit: int = 3200) -> str:
        if len(value) <= limit:
            return value
        head_limit = int(limit * 0.78)
        tail_limit = limit - head_limit - 2
        head = value[:head_limit].rsplit("\n", 1)[0].rstrip()
        tail = value[-tail_limit:].split("\n", 1)[-1].lstrip()
        return f"{head}\n{tail}".strip()

    scoped_messages = scope_messages_for_intent(messages, frame)
    clean_messages: List[Dict[str, str]] = []
    for message in scoped_messages[-12:]:
        role = _text(message.get("role")).lower()
        text = _message_text(message)
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
            "comparisonCriteria",
            "operationPlan",
            "semanticExclusions",
            "requestedChange",
            "expectedOutput",
            "resolvedRequest",
            "evidenceNeed",
            "knownConstraints",
            "missingInfo",
            "forbiddenRoutes",
            "confidence",
            "contextRelation",
            "contextScope",
            "sharedTopicTerms",
            "interactionStance",
            "reasoningArchetype",
        )
        if frame.get(key) not in (None, "", [], {})
    }
    decision_brief = build_decision_brief(scoped_messages, frame)
    lines = [
        "You are Tinman's local Codex teammate and the primary owner of this conversation.",
        "Understand the full latest request before acting. Do not route or answer from isolated keywords.",
        "Use tools and inspect local evidence when the request requires action or verification; do not merely describe what could be done.",
        "If one missing fact would materially change the answer or make an action unsafe, ask one concise clarification and wait.",
        "Otherwise make reasonable, explicit assumptions and complete the work end to end.",
        "Answer like a practical subject-matter expert: direct, educated, personable, and appropriately skeptical.",
        *(
            [
                "Use interactionStance only to choose the conversational posture: briefly recognize the user's moment, then do the work. Never turn it into therapy language, flattery, or a substitute for technical content."
            ]
            if frame_view.get("interactionStance")
            else []
        ),
        "Use natural prose. Do not force labels such as 'This is why' or 'You should also consider'.",
        "Do not expose hidden chain-of-thought, route internals, prompt rules, or policy scaffolding.",
        "Separate verified facts, inference, and uncertainty when that distinction affects the decision.",
        "Before finalizing, silently test the answer's internal consistency: every named variable, component, causal arrow, unit, and assumption must keep the same role throughout.",
        "For an explanation, verify the mechanism rather than substituting correlation, prediction, or a familiar slogan for causation.",
        "Challenge the first draft with one plausible counterexample or reversal condition and repair any contradiction before answering.",
        "For a choice among named options, compare all options on one stable set of criteria. A follow-up may change the recommendation because priorities changed, but it must not silently reverse a factual criterion ranking; state what changed and what did not.",
        "Do not infer a global property such as independence, sufficiency, safety, or uniqueness from one local path, test, or mechanism unless alternatives were ruled out.",
        "For current claims use current evidence; for scientific claims prefer primary measurements, papers, standards, or datasheets.",
        "For local changes report what changed and how it was verified. Never claim a file, command, or machine action without proof.",
        *(
            [
                "Treat operationPlan as an authorization boundary: execute only allowedNow operations, in order; do not perform prohibited operations; and do not perform deferred operations until their stated condition is actually satisfied. Every allowedNow run, inspect, create, draft, edit, fix, install, restart, delete, or upload operation must use an actual tool and produce a receipt; never substitute a proposed command list or imagined output for execution. In the final answer, explicitly report each prohibited or deferred hold point so the user can tell what did and did not happen."
            ]
            if frame_view.get("operationPlan")
            else []
        ),
        "",
        "Turn understanding:",
        # This packet is already typed; whitespace indentation adds hundreds
        # of prompt characters without adding model information. Keep the
        # complete contract while preserving the compact-worker budget.
        json.dumps(frame_view, ensure_ascii=True, separators=(",", ":")),
    ]
    if decision_brief:
        lines.extend(
            [
                "",
                "Decision brief:",
                json.dumps(decision_brief, indent=2, ensure_ascii=True),
                "Use the brief as a stable private comparison frame. Do not treat it as product evidence or a preselected answer.",
            ]
        )
    if frame.get("domain") == "decision_support":
        lines.extend(["", *decision_support_response_contract(stage="author")])
    lines.extend(
        [
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
        ]
    )
    if include_runtime_context:
        lines.extend(
            [
                "",
                f"Routed specialist: {_text(route.get('specialist')) or 'General specialist'}",
                f"Working directory: {working_directory or _text(frame.get('cwd')) or '(use the supplied runtime directory)'}",
            ]
        )
    if frame.get("contextRelation") == "follow-up":
        lines.insert(
            12,
            "This is a true follow-up: preserve the prior objective and definitions, then change only what the new condition changes.",
        )
    elif frame.get("contextScope") == "latest-turn":
        lines.insert(
            12,
            "This turn is standalone: answer only the latest request and do not continue, summarize, or disclaim an earlier topic.",
        )
    useful_rules = [_text(rule) for rule in project_rules if _text(rule)][:6]
    if useful_rules:
        lines.extend(["", "Relevant project guidance:"])
        lines.extend(f"- {rule}" for rule in useful_rules)
    for block in extra_context or ():
        value = _text(block)
        if value:
            lines.extend(["", bounded_context_excerpt(value)])
    lines.extend(["", "Conversation:"])
    for message in clean_messages:
        label = "Tinman" if message["role"] == "user" else "Assistant"
        lines.extend([f"{label}:", message["text"], ""])
    lines.append("Respond to Tinman's latest request.")
    return "\n".join(lines).strip()


def synthetic_kernel_check() -> Dict[str, Any]:
    cases = [
        (
            "verification-status-current-rerun",
            [{"role": "user", "text": "Which verification receipts are current, and what needs to be rerun?"}],
            "bounded_specialist_capability",
            "bounded_specialist_direct",
            True,
        ),
        (
            "verification-status-fresh-stale-pass-fail",
            [
                {
                    "role": "user",
                    "text": "For Codex CLI UI testing, what evidence is fresh or stale, what passed or failed, and which checks need another run?",
                }
            ],
            "bounded_specialist_capability",
            "bounded_specialist_direct",
            True,
        ),
        (
            "verification-status-named-groups",
            [{"role": "user", "text": "Are package health, live smoke, and public-export receipts current?"}],
            "bounded_specialist_capability",
            "bounded_specialist_direct",
            True,
        ),
        (
            "current-market",
            [{"role": "user", "text": "What are the top 10 4 x 8 CNC machines under $20,000 right now?"}],
            "current_market_research",
            "current_web_research",
            False,
        ),
        (
            "ebay-marketplace",
            [
                {"role": "user", "text": "Find the best deal on a 100W JPT MOPA fiber laser."},
                {"role": "assistant", "text": "I will compare current product pages."},
                {"role": "user", "text": "Now find the best deal on eBay and check the listings completely."},
            ],
            "marketplace_listing_research",
            "ebay_marketplace_research",
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
            "inline-programming-answer",
            [
                {
                    "role": "user",
                    "text": (
                        "Implement a stable topological sort in Python using Kahn's algorithm. "
                        "Use an explicit ordered node list as the stable input order. Explain the queue "
                        "invariant and include tests for a disconnected DAG and a cycle."
                    ),
                }
            ],
            "conversation",
            "conversation_reasoning",
            False,
        ),
        (
            "programming-order-contract-clarification",
            [
                {
                    "role": "user",
                    "text": (
                        "Implement a stable topological sort in Python using Kahn's algorithm. "
                        "Preserve input order when multiple nodes are ready and include tests."
                    ),
                }
            ],
            "clarification",
            "clarification",
            True,
        ),
        (
            "programming-order-contract-resolution",
            [
                {
                    "role": "user",
                    "text": (
                        "Implement a stable topological sort in Python using Kahn's algorithm. "
                        "Preserve input order when multiple nodes are ready and include tests."
                    ),
                },
                {
                    "role": "assistant",
                    "text": (
                        "What should define the stable input order: an explicit ordered node list, "
                        "the graph mapping's key order, or first appearance across keys and adjacency lists?"
                    ),
                },
                {"role": "user", "text": "Use an explicit ordered node list."},
            ],
            "conversation",
            "conversation_reasoning",
            False,
        ),
        (
            "programming-generic-explicit-order-source",
            [
                {
                    "role": "user",
                    "text": (
                        "Implement a deterministic dependency resolver in Python. "
                        "Use an explicit ordered item list to preserve input order and include tests."
                    ),
                }
            ],
            "conversation",
            "conversation_reasoning",
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
        (
            "printable-physical-artifact",
            [
                {
                    "role": "user",
                    "text": "Design a 3D printable mounting bracket for the assembly. Do not install it yet.",
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
    verification_status_negative_prompts = (
        "Which expense and tax receipts are current and need resubmitting?",
        "Are the invoice, payment, shipping, and purchase receipts valid?",
        "Did the customer receive the verification email read receipt?",
        "Which research citations and evidence retrieval records are current?",
        "Rerun the failing simulation and report the result.",
    )
    verification_status_negative_frames = [
        build_generic_intent_frame([{"role": "user", "text": prompt}])
        for prompt in verification_status_negative_prompts
    ]
    results.append(
        {
            "id": "verification-status-negative-boundaries",
            "passed": all(
                not is_local_verification_receipt_status_request(
                    [{"role": "user", "text": prompt}]
                )
                and frame.get("domain") != "bounded_specialist_capability"
                for prompt, frame in zip(
                    verification_status_negative_prompts,
                    verification_status_negative_frames,
                )
            ),
            "domain": "semantic-negative-boundaries",
            "capability": "bounded_specialist_direct",
            "legacyDirect": False,
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
    controller_domain_switch_messages = [
        {
            "role": "user",
            "text": "What is the current manufacturer-rated continuous power for the fictional Acme QZ-991 motor? Cite the official source URL.",
        },
        {
            "role": "assistant",
            "text": "I cannot verify that current rating without a checked manufacturer source.",
        },
        {
            "role": "user",
            "text": "Never mind the rating or source. What controller voltage headroom should I use for a 72 V lightweight kart?",
        },
    ]
    controller_domain_switch_selected = select_intent_frame(
        controller_domain_switch_messages,
        {
            "domain": "engineering_power_conversion",
            "actionType": "size_motor_controller_and_convert_power",
            "frameTags": ["engineering-power-conversion"],
            "confidence": 0.94,
        },
        build_generic_intent_frame(controller_domain_switch_messages),
    )
    results.append(
        {
            "id": "controller-voltage-domain-switch-retains-typed-owner",
            "passed": (
                controller_domain_switch_selected.get("domain")
                == "engineering_power_conversion"
                and not controller_domain_switch_selected.get("rejectedLegacyDomain")
            ),
            "domain": controller_domain_switch_selected.get("domain"),
            "capability": (
                controller_domain_switch_selected.get("routeCandidates") or [""]
            )[0],
            "legacyDirect": False,
        }
    )
    decision_brief_cases = [
        (
            "decision-brief-cross-domain-controls",
            [
                {
                    "role": "user",
                    "text": (
                        "Should I choose Controller Alpha, Controller Beta, or Controller Gamma? "
                        "Compare cost, throughput, and maintenance for a 48 V test stand."
                    ),
                },
                {"role": "assistant", "text": "That depends on the workload."},
                {
                    "role": "user",
                    "text": "What if the load is only 2 kW and I care most about quiet operation and low power?",
                },
            ],
            ["Controller Alpha", "Controller Beta", "Controller Gamma"],
            {"48 V", "2 kW"},
            {"acoustics", "power/efficiency"},
        ),
        (
            "decision-brief-cross-domain-materials",
            [
                {
                    "role": "user",
                    "text": "Should I choose Alloy A or Composite B? Compare stiffness, fatigue, and cost.",
                },
                {"role": "assistant", "text": "The choice depends on duty and environment."},
                {
                    "role": "user",
                    "text": "What if mass matters more and the service temperature is 120 C?",
                },
            ],
            ["Alloy A", "Composite B"],
            {"120 C"},
            {"size/weight"},
        ),
        (
            "decision-brief-evidence-sufficiency-followup",
            [
                {
                    "role": "user",
                    "text": (
                        "Would a graphite bed work with sustained chamber temperatures of 150 C? "
                        "I mean the substrate itself, not a coating."
                    ),
                },
                {"role": "assistant", "text": "The exact grade controls the answer."},
                {
                    "role": "user",
                    "text": (
                        "The candidate is an isotropic fine-grain graphite plate, 300 x 300 x 8 mm. "
                        "Hot flatness and even heat spreading matter more than weight. The seller lists in-plane "
                        "thermal conductivity but no through-thickness value. Is that datasheet enough to choose it "
                        "over a cast aluminum tooling plate of the same dimensions, or what evidence is still missing?"
                    ),
                },
            ],
            ["isotropic fine-grain graphite plate", "cast aluminum tooling plate"],
            {"150 C", "8 mm"},
            {"thermal/cooling", "size/weight"},
        ),
    ]
    for case_id, case_messages, expected_options, expected_quantities, expected_weight_axes in decision_brief_cases:
        brief_frame = build_generic_intent_frame(case_messages)
        brief = build_decision_brief(case_messages, brief_frame)
        weight_axes = {
            _text(item.get("axis"))
            for item in brief.get("changedPriorityWeights") or []
            if isinstance(item, dict)
        }
        passed = bool(
            brief.get("options") == expected_options
            and expected_quantities.issubset(set(brief.get("userSuppliedOperatingConstraints") or []))
            and expected_weight_axes.issubset(weight_axes)
            and "winner" in _text(brief.get("evidenceBoundary")).lower()
            and "performance" in _text(brief.get("highestLeverageMissingInput")).lower()
            and (
                case_id != "decision-brief-evidence-sufficiency-followup"
                or (
                    brief_frame.get("actionType") == "reassess_engineering_conclusion_with_new_constraints"
                    and brief_frame.get("comparisonCriteria") == ["Hot flatness", "even heat spreading"]
                )
            )
        )
        results.append(
            {
                "id": case_id,
                "passed": passed,
                "domain": brief_frame.get("domain"),
                "capability": "decision-brief",
                "legacyDirect": False,
            }
        )
    feedback_introspection_cases = (
        "What if I only press Fix this and do not explain what was wrong? Is that enough for you to learn the right lesson?",
        "When I click Fix this, what signal does that give you and what can become durable?",
        "Does marking an answer as bad actually change future behavior, or does it only affect this chat?",
    )
    feedback_frames = [
        select_intent_frame(
            [{"role": "user", "text": prompt}],
            {"domain": "knowledge_question", "confidence": 0.75},
            build_generic_intent_frame([{"role": "user", "text": prompt}]),
        )
        for prompt in feedback_introspection_cases
    ]
    direct_feedback_command_decoys = (
        "Fix this: the export is missing the corrected file.",
        "Can you fix this printer status bug and record the changes?",
        "Please fix this and save the corrected configuration locally.",
    )
    direct_feedback_frames = [
        build_generic_intent_frame([{"role": "user", "text": prompt}])
        for prompt in direct_feedback_command_decoys
    ]
    results.append(
        {
            "id": "feedback-control-metalinguistic-intent",
            "passed": (
                all(frame.get("domain") == "agent_runtime_capabilities" for frame in feedback_frames)
                and all(
                    frame.get("actionType") == "explain_learning_and_correction_loop"
                    for frame in feedback_frames
                )
                and all(
                    frame.get("domain") != "agent_runtime_capabilities"
                    for frame in direct_feedback_frames
                )
            ),
            "domain": feedback_frames[0].get("domain"),
            "capability": (feedback_frames[0].get("routeCandidates") or [""])[0],
            "legacyDirect": False,
        }
    )
    operation_discussion_cases = (
        "When I ask you to run tests, how do you decide which tests are enough before saying the problem is fixed?",
        "If I say search eBay, does that mean you use live web every time, or can you answer from cached results?",
        "What happens when I press Stop during a run? Does it cancel the model or only hide the output?",
        "If I mention the word delete while asking about safety, you will not actually delete anything just because that word appeared, right?",
        "Before I install anything, how do you decide whether installation is really what I asked for?",
    )
    operation_discussion_frames = [
        build_generic_intent_frame([{"role": "user", "text": prompt}])
        for prompt in operation_discussion_cases
    ]
    operation_command_cases = (
        "Run the package tests and report the failures.",
        "Search eBay for a current 100W JPT MOPA laser.",
        "Install the approved local package.",
        "Delete the generated scratch file after verifying its path.",
    )
    operation_command_frames = [
        build_generic_intent_frame([{"role": "user", "text": prompt}])
        for prompt in operation_command_cases
    ]
    results.append(
        {
            "id": "operation-predicate-versus-mention",
            "passed": (
                all(
                    frame.get("domain") == "agent_runtime_capabilities"
                    and frame.get("actionType") == "explain_operation_interpretation_policy"
                    for frame in operation_discussion_frames
                )
                and [frame.get("domain") for frame in operation_command_frames]
                == [
                    "general_action",
                    "marketplace_listing_research",
                    "general_action",
                    "general_action",
                ]
                and all(
                    frame.get("actionType") != "explain_operation_interpretation_policy"
                    for frame in operation_command_frames
                )
            ),
            "domain": operation_discussion_frames[0].get("domain"),
            "capability": (operation_discussion_frames[0].get("routeCandidates") or [""])[0],
            "legacyDirect": False,
        }
    )
    return {
        "status": "pass" if all(item["passed"] for item in results) else "fail",
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "results": results,
    }
