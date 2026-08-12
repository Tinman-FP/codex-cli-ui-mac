"""Typed execution registry for post-intent Codex CLI UI capabilities.

The registry is intentionally declarative. Domain detection belongs to the
intelligence kernel; this module decides which executor is allowed to own the
selected intent after that decision has been made.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


REGISTRY_VERSION = 1


# These are the only registered capabilities whose executor is intentionally
# implemented by the historical direct-answer catalog. Every other registered
# capability owns its turn exclusively and must continue to its typed executor
# or model worker instead of wandering through unrelated legacy handlers.
LEGACY_FALLBACK_HANDLER_KEYS = frozenset({"bounded_specialist_direct"})


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    domains: Tuple[str, ...]
    selected_capabilities: Tuple[str, ...]
    execution_modes: Tuple[str, ...]
    executor: str
    handler_key: str
    access_level: str
    proof_policy: str
    review_policy: str = "contract-gated"
    relevance_policy: str = "task-contract"
    proof_requirements: Tuple[str, ...] = ()
    priority: int = 50
    execution_binding: str = "inline"

    def public_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["version"] = REGISTRY_VERSION
        value["domains"] = list(self.domains)
        value["selected_capabilities"] = list(self.selected_capabilities)
        value["execution_modes"] = list(self.execution_modes)
        value["proof_requirements"] = list(self.proof_requirements)
        return value


CAPABILITY_SPECS: Tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        id="focused-clarification",
        domains=("clarification",),
        selected_capabilities=("clarification",),
        execution_modes=("deterministic-capability",),
        executor="deterministic",
        handler_key="clarification",
        access_level="conversation-context",
        proof_policy="one focused question naming the missing target, referent, or decision-changing constraint",
        review_policy="deterministic",
        priority=110,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="local-installation-status",
        domains=("local_installation_status",),
        selected_capabilities=("local_installation_status", "codex-cli-ui-local-agent"),
        execution_modes=("deterministic-capability",),
        executor="deterministic",
        handler_key="local_installation_status",
        access_level="local-inventory-read-only",
        proof_policy="installed and readiness state from unified local inventories",
        review_policy="deterministic",
        priority=100,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="runtime-capability-introspection",
        domains=("agent_runtime_capabilities",),
        selected_capabilities=("runtime_capability_introspection",),
        execution_modes=("deterministic-capability",),
        executor="deterministic",
        handler_key="runtime_capability_introspection",
        access_level="active-session-runtime-inventory",
        proof_policy="current access level, working directory, web mode, registered capabilities, local tool inventory, and configured integration counts",
        review_policy="deterministic",
        priority=105,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="bounded-specialist-capability",
        domains=("bounded_specialist_capability",),
        selected_capabilities=("bounded_specialist_direct",),
        execution_modes=("deterministic-capability",),
        executor="deterministic",
        handler_key="bounded_specialist_direct",
        access_level="specialist-owned-local-or-stable-evidence",
        proof_policy="the confirmed specialist route must answer from its bounded local, stable, or previously verified evidence contract",
        review_policy="deterministic",
        relevance_policy="template-ownership-required",
        priority=99,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="local-file-evidence",
        domains=("local_file_evidence",),
        selected_capabilities=("local_file_retrieval",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="local_file_evidence",
        access_level="local-files",
        proof_policy="resolved local path plus read/compare result or exact blocker",
        review_policy="artifact-contract",
        priority=95,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="generated-artifact-followup",
        domains=("generated_artifact_followup",),
        selected_capabilities=("generated_artifact_followup",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="generated_artifact_followup",
        access_level="prior-generated-local-artifacts",
        proof_policy=(
            "prior assistant deliverable paths, exact selected artifact, preserved original, "
            "and revised or regenerated output path when a change is requested"
        ),
        review_policy="artifact-contract",
        priority=98,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="profile-settings-carryover",
        domains=("profile_settings_carryover",),
        selected_capabilities=("profile_settings_carryover",),
        execution_modes=("deterministic-capability",),
        executor="deterministic",
        handler_key="profile_settings_carryover",
        access_level="conversation-context",
        proof_policy=(
            "an explicitly named destination profile, concrete source settings from the "
            "preceding answer, and a truthful no-write boundary until an exact writable preset is resolved"
        ),
        review_policy="deterministic",
        relevance_policy="task-contract",
        priority=99,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="local-file-work",
        domains=("local_file_work",),
        selected_capabilities=("local_file_work", "local_code_agent"),
        execution_modes=("capability-first",),
        executor="local-agent",
        handler_key="local_file_work",
        access_level="authorized-local-files-and-tools",
        proof_policy="resolved local targets, operation-authority boundary, file-change receipt when authorized, and final verification or exact blocker",
        review_policy="artifact-contract",
        proof_requirements=(
            "controller-edit-if-mutation-authorized",
            "verified-final-reconciliation",
            "rollback-precludes-completion",
        ),
        priority=96,
    ),
    CapabilitySpec(
        id="local-file-analysis",
        domains=("local_file_analysis",),
        selected_capabilities=("local_file_analysis",),
        execution_modes=("model-first",),
        executor="local-agent",
        handler_key="local_file_analysis",
        access_level="read-only-local-files-and-tools",
        proof_policy="resolved named files, task-specific content analysis, command receipts, and exact requested output or blocker",
        review_policy="artifact-contract",
        priority=96,
    ),
    CapabilitySpec(
        id="klipper-config-migration",
        domains=("klipper_config_migration",),
        selected_capabilities=("klipper_config_migration", "printer-klipper-ops"),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="klipper_migration",
        access_level="read-only-printer-and-local-files",
        proof_policy="source snapshot, staged artifacts, pin evidence, and no-install boundary",
        review_policy="artifact-contract",
        priority=95,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="local-cad-artifact",
        domains=("cad_artifact_work",),
        selected_capabilities=("cad_artifact",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="cad_artifact",
        access_level="local-files-and-cad-toolchain",
        proof_policy="generated CAD/mesh artifact, dimensional envelope, assumptions, and fit or export verification",
        review_policy="artifact-contract",
        priority=96,
        execution_binding="router",
    ),
    CapabilitySpec(
        id="local-aero-cfd-artifact",
        domains=("aero_cfd_work",),
        selected_capabilities=("aero_cfd",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="aero_cfd",
        access_level="local-files-and-simulation-toolchain",
        proof_policy="geometry preflight, solver-ready artifacts or exact blocker, and validation boundary",
        review_policy="artifact-contract",
        priority=96,
    ),
    CapabilitySpec(
        id="local-structural-fea-artifact",
        domains=("structural_fea_work",),
        selected_capabilities=("structural_fea",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="structural_fea",
        access_level="local-files-and-simulation-toolchain",
        proof_policy="geometry, loads, constraints, material assumptions, solver artifact or exact blocker, and result limits",
        review_policy="artifact-contract",
        priority=96,
    ),
    CapabilitySpec(
        id="local-engineering-diagram-artifact",
        domains=("engineering_diagram_work",),
        selected_capabilities=("engineering_diagram",),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="engineering_diagram",
        access_level="local-files-and-diagram-toolchain",
        proof_policy="editable diagram artifact with sourced interfaces, unverified details marked, and rendered verification",
        review_policy="artifact-contract",
        priority=96,
    ),
    CapabilitySpec(
        id="ebay-marketplace-research",
        domains=("marketplace_listing_research",),
        selected_capabilities=("ebay_marketplace_research",),
        execution_modes=("model-first",),
        executor="research",
        handler_key="ebay_marketplace_research",
        access_level="free-public-ebay-pages-or-optional-official-browse-api",
        proof_policy="exact item pages, fetched listing fields, delivered-price boundary, seller and return evidence, rejected mismatches, and explicit authenticity unknowns",
        review_policy="marketplace-listing-audit",
        priority=90,
    ),
    CapabilitySpec(
        id="current-web-research",
        domains=(
            "current_market_ranking",
            "current_market_research",
            "research_synthesis",
            "scientific_evidence_review",
            "scientific_materials_evidence",
            "material_property_evidence",
        ),
        selected_capabilities=(
            "current_web_research",
            "scientific_evidence_review",
            "research-parts-reference",
            "tinmanx-slicer-research",
        ),
        execution_modes=("model-first",),
        executor="research",
        handler_key="local_research",
        access_level="free-public-web-and-local-model",
        proof_policy="traceable source evidence and source-bounded conclusion",
        review_policy="contract-gated",
        priority=85,
    ),
    CapabilitySpec(
        id="source-backed-reasoning",
        domains=("source_resolution", "technical_source_lookup", "technical_compatibility"),
        selected_capabilities=("source_backed_reasoning",),
        execution_modes=("model-first",),
        executor="research",
        handler_key="source_backed_research",
        access_level="supplied-source-free-public-web-and-local-model",
        proof_policy="resolved source identity, checked source text, direct answer to the visible request, and explicit evidence boundary",
        review_policy="source-fidelity-audit",
        priority=84,
    ),
    CapabilitySpec(
        id="engineering-primary-research",
        domains=("engineering_tradeoff",),
        selected_capabilities=("current_web_research",),
        execution_modes=("model-first",),
        executor="research",
        handler_key="engineering_primary_research",
        access_level="free-public-web-and-local-model",
        proof_policy=(
            "primary datasheet, application-note, standard, or measured evidence at the stated operating point; "
            "claim-bounded comparison; qualified recommendation; and reversal conditions"
        ),
        review_policy="technical-claim-audit",
        priority=86,
    ),
    CapabilitySpec(
        id="expert-comparison",
        domains=("knowledge_comparison",),
        selected_capabilities=("conversation_reasoning",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="expert_comparison",
        access_level="conversation-and-optional-evidence",
        proof_policy="named options, decision criteria, qualified conclusion, and reversal conditions",
        review_policy="reasoning-audit",
        priority=80,
    ),
    CapabilitySpec(
        id="printer-job-eta-reasoning",
        domains=("printer_job_eta",),
        selected_capabilities=("printer-klipper-ops",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="printer_job_eta_reasoning",
        access_level="conversation-and-read-only-printer-evidence",
        proof_policy=(
            "typed active-print context, supplied slicer and live-printer values, "
            "mechanism-versus-job-specific diagnosis boundary, and exact missing evidence"
        ),
        review_policy="reasoning-audit",
        priority=84,
    ),
    CapabilitySpec(
        id="local-app-product-state",
        domains=("local_app_product_bug",),
        selected_capabilities=("codex-cli-ui-local-agent",),
        execution_modes=("model-first",),
        executor="local-agent",
        handler_key="local_app_product_state",
        access_level="read-only-local-source-and-runtime-state",
        proof_policy=(
            "typed local product surface, current read-only source or runtime receipt, "
            "and an explicit no-mutation boundary"
        ),
        review_policy="artifact-contract",
        priority=83,
    ),
    CapabilitySpec(
        id="decision-metric-design",
        domains=("decision_metric_design",),
        selected_capabilities=("conversation_reasoning",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="decision_metric_design",
        access_level="conversation-context-and-user-supplied-metrics",
        proof_policy=(
            "outcome-aligned numerator, denominator and cohort definitions, "
            "unit consistency, mix-shift boundary, and calibrated uncertainty"
        ),
        review_policy="reasoning-audit",
        priority=82,
    ),
    CapabilitySpec(
        id="general-local-action",
        domains=("general_action",),
        selected_capabilities=("local_agent",),
        execution_modes=("model-first",),
        executor="local-agent",
        handler_key="general_local_action",
        access_level="operation-plan-bounded-local-tools",
        proof_policy=(
            "the latest typed operation plan, real execution receipts for allowed operations, "
            "and explicit preservation of prohibited, deferred, read-only, and live-machine boundaries"
        ),
        review_policy="artifact-contract",
        priority=78,
    ),
    CapabilitySpec(
        id="live-device-authority",
        domains=("live_device_action",),
        selected_capabilities=("live_device_authority",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="live_device_authority",
        access_level="conversation-only-live-device-authority-boundary",
        proof_policy=(
            "exclusive per-operation state and authority surface, exact physical target, current safe-state preflight, "
            "operation-appropriate backup or rollback, latest-request authorization receipt, and no live mutation from the reasoning worker"
        ),
        review_policy="artifact-contract",
        priority=98,
    ),
    CapabilitySpec(
        id="engineering-power-conversion",
        domains=("engineering_power_conversion",),
        selected_capabilities=("energy-power-research",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="engineering_power_conversion",
        access_level="conversation-math-and-optional-evidence",
        proof_policy="preserved units and operating point, transparent calculations, continuous-versus-peak boundary, controller or drivetrain assumptions, and reversal conditions",
        review_policy="calculation-contract",
        priority=82,
    ),
    CapabilitySpec(
        id="engineering-calculation",
        domains=("engineering_calculation",),
        selected_capabilities=("engineering_calculation",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="engineering_calculation",
        access_level="conversation-math-and-labeled-reference-assumptions",
        proof_policy="preserved inputs and units, correct equations, numerical substitutions and outputs, dimensional sanity check, assumptions, and acceptance conclusion",
        review_policy="calculation-contract",
        priority=83,
    ),
    CapabilitySpec(
        id="engineering-advisory",
        domains=("engineering_advisory", "engineering_tradeoff", "material_process_behavior"),
        selected_capabilities=(
            "engineering-diagrams",
            "cad-modeling-projects",
            "cnc-machining",
            "tinmanx-slicer-research",
            "printer-klipper-ops",
            "energy-power-research",
            "conversation_reasoning",
            "general",
        ),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="engineering_advisory",
        access_level="conversation-local-context-and-optional-evidence",
        proof_policy="complete objective and constraints, engineering tradeoffs, failure modes, safety boundary, validation path, and one focused clarification only when it changes the design",
        review_policy="engineering-contract",
        priority=81,
    ),
    CapabilitySpec(
        id="local-product-action",
        domains=("local_product_action",),
        selected_capabilities=("local_code_agent", "codex-cli-ui-local-agent"),
        execution_modes=("model-first",),
        executor="local-agent",
        handler_key="local_product_action",
        access_level="local-workspace-and-tools",
        proof_policy="inspected target, bounded implementation, changed artifacts, and focused verification or exact blocker",
        review_policy="artifact-contract",
        proof_requirements=(
            "controller-edit-if-mutation-authorized",
            "verified-noop-alternative-controller-resolution",
            "focused-test-if-test-authorized",
            "verified-final-reconciliation",
            "rollback-precludes-completion",
        ),
        priority=79,
    ),
    CapabilitySpec(
        id="conversation-reasoning",
        domains=("conversation", "knowledge_question", "decision_support"),
        selected_capabilities=("conversation_reasoning",),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="conversation_reasoning",
        access_level="conversation-context-and-optional-tools",
        proof_policy="complete objective, preserved qualifiers, internally consistent mechanism or argument, calibrated uncertainty, and a direct natural answer",
        review_policy="reasoning-audit",
        priority=70,
    ),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def resolve_capability(
    intent_frame: Optional[Dict[str, Any]],
    kernel_decision: Optional[Dict[str, Any]],
) -> Optional[CapabilitySpec]:
    frame = intent_frame if isinstance(intent_frame, dict) else {}
    decision = kernel_decision if isinstance(kernel_decision, dict) else {}
    domain = _text(frame.get("domain"))
    selected = _text(decision.get("selectedCapability"))
    mode = _text(decision.get("mode"))
    candidates = []
    for spec in CAPABILITY_SPECS:
        if domain not in spec.domains or mode not in spec.execution_modes:
            continue
        if spec.selected_capabilities and selected not in spec.selected_capabilities:
            continue
        candidates.append(spec)
    return max(candidates, key=lambda item: item.priority) if candidates else None


def build_capability_plan(
    intent_frame: Optional[Dict[str, Any]],
    kernel_decision: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    spec = resolve_capability(intent_frame, kernel_decision)
    if not spec:
        return {
            "version": REGISTRY_VERSION,
            "id": "unregistered",
            "executor": "legacy-compatibility",
            "handler_key": "legacy_dispatch",
            "registered": False,
            "proof_policy": "legacy path remains subject to task-contract and final-answer gates",
        }
    return {**spec.public_dict(), "registered": True}


def plan_allows_handler(plan: Optional[Dict[str, Any]], *handler_keys: str) -> bool:
    if not isinstance(plan, dict) or not plan.get("registered"):
        return False
    allowed = {_text(value) for value in handler_keys if _text(value)}
    return _text(plan.get("handler_key")) in allowed


def handler_keys_for_executor(
    executor: str,
    execution_binding: Optional[str] = None,
) -> Tuple[str, ...]:
    """Return the complete declared handler set for one executor family."""

    selected = _text(executor)
    selected_binding = _text(execution_binding)
    return tuple(
        sorted(
            spec.handler_key
            for spec in CAPABILITY_SPECS
            if spec.executor == selected
            and (not selected_binding or spec.execution_binding == selected_binding)
        )
    )


def plan_allows_legacy_fallback(
    plan: Optional[Dict[str, Any]],
    kernel_decision: Optional[Dict[str, Any]] = None,
) -> bool:
    """Keep registered intents inside their declared execution boundary.

    Unregistered intents retain the kernel's compatibility decision while the
    monolith is migrated incrementally. Registered intents may use the legacy
    catalog only when their handler explicitly declares that catalog as its
    executor boundary.
    """

    active_plan = plan if isinstance(plan, dict) else {}
    decision = kernel_decision if isinstance(kernel_decision, dict) else {}
    if active_plan.get("registered"):
        return _text(active_plan.get("handler_key")) in LEGACY_FALLBACK_HANDLER_KEYS
    return bool(decision.get("allowLegacyDirectAnswer", True))


def registry_health() -> Dict[str, Any]:
    ids = [spec.id for spec in CAPABILITY_SPECS]
    handlers = [spec.handler_key for spec in CAPABILITY_SPECS]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    duplicate_handlers = sorted({value for value in handlers if handlers.count(value) > 1})
    allowed_executors = {
        "deterministic",
        "local-agent",
        "local-tool",
        "reasoning-worker",
        "research",
    }
    invalid_executors = sorted(
        spec.id for spec in CAPABILITY_SPECS if spec.executor not in allowed_executors
    )
    invalid_bindings = sorted(
        spec.id for spec in CAPABILITY_SPECS if spec.execution_binding not in {"inline", "router"}
    )
    invalid_relevance_policies = sorted(
        spec.id
        for spec in CAPABILITY_SPECS
        if spec.relevance_policy not in {"task-contract", "template-ownership-required"}
    )
    invalid_legacy_fallbacks = sorted(
        spec.id
        for spec in CAPABILITY_SPECS
        if spec.handler_key in LEGACY_FALLBACK_HANDLER_KEYS
        and not (
            spec.executor == "deterministic"
            and spec.execution_modes == ("deterministic-capability",)
            and spec.relevance_policy == "template-ownership-required"
        )
    )
    required = {
        "focused-clarification",
        "bounded-specialist-capability",
        "generated-artifact-followup",
        "profile-settings-carryover",
        "local-installation-status",
        "local-file-evidence",
        "local-file-work",
        "local-file-analysis",
        "ebay-marketplace-research",
        "current-web-research",
        "source-backed-reasoning",
        "expert-comparison",
        "printer-job-eta-reasoning",
        "local-app-product-state",
        "decision-metric-design",
        "general-local-action",
        "live-device-authority",
        "klipper-config-migration",
        "local-cad-artifact",
        "local-aero-cfd-artifact",
        "local-structural-fea-artifact",
        "local-engineering-diagram-artifact",
        "engineering-power-conversion",
        "engineering-calculation",
        "engineering-advisory",
        "local-product-action",
        "conversation-reasoning",
    }
    missing = sorted(required.difference(ids))
    return {
        "status": (
            "pass"
            if not duplicates
            and not duplicate_handlers
            and not missing
            and not invalid_executors
            and not invalid_bindings
            and not invalid_relevance_policies
            and not invalid_legacy_fallbacks
            else "fail"
        ),
        "count": len(CAPABILITY_SPECS),
        "duplicates": duplicates,
        "duplicateHandlers": duplicate_handlers,
        "missing": missing,
        "invalidExecutors": invalid_executors,
        "invalidBindings": invalid_bindings,
        "invalidRelevancePolicies": invalid_relevance_policies,
        "invalidLegacyFallbacks": invalid_legacy_fallbacks,
        "legacyFallbackHandlers": sorted(LEGACY_FALLBACK_HANDLER_KEYS),
    }


def synthetic_registry_check(cases: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    for case in cases:
        plan = build_capability_plan(case.get("frame"), case.get("decision"))
        expected = _text(case.get("expected"))
        results.append(
            {
                "id": case.get("id"),
                "passed": _text(plan.get("id")) == expected,
                "actual": plan.get("id"),
                "expected": expected,
            }
        )
    health = registry_health()
    failed = [item for item in results if not item.get("passed")]
    return {
        "status": "pass" if health.get("status") == "pass" and not failed else "fail",
        "registry": health,
        "results": results,
        "failures": failed,
    }
