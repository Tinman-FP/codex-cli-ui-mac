"""Typed execution registry for post-intent Codex CLI UI capabilities.

The registry is intentionally declarative. Domain detection belongs to the
intelligence kernel; this module decides which executor is allowed to own the
selected intent after that decision has been made.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


REGISTRY_VERSION = 1


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
    priority: int = 50

    def public_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["version"] = REGISTRY_VERSION
        value["domains"] = list(self.domains)
        value["selected_capabilities"] = list(self.selected_capabilities)
        value["execution_modes"] = list(self.execution_modes)
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
        priority=99,
    ),
    CapabilitySpec(
        id="local-file-evidence",
        domains=("local_file_evidence", "local_file_work"),
        selected_capabilities=("local_file_retrieval", "local_file_work"),
        execution_modes=("capability-first",),
        executor="local-tool",
        handler_key="local_file_evidence",
        access_level="local-files",
        proof_policy="resolved local path plus read/compare result or exact blocker",
        review_policy="artifact-contract",
        priority=95,
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
        id="expert-comparison",
        domains=("knowledge_comparison", "engineering_tradeoff"),
        selected_capabilities=("conversation_reasoning", "cad-modeling-projects"),
        execution_modes=("model-first",),
        executor="reasoning-worker",
        handler_key="expert_comparison",
        access_level="conversation-and-optional-evidence",
        proof_policy="named options, decision criteria, qualified conclusion, and reversal conditions",
        review_policy="reasoning-audit",
        priority=80,
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
        id="engineering-advisory",
        domains=("engineering_advisory", "material_process_behavior"),
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
        selected_capabilities=("local_code_agent",),
        execution_modes=("model-first",),
        executor="local-agent",
        handler_key="local_product_action",
        access_level="local-workspace-and-tools",
        proof_policy="inspected target, bounded implementation, changed artifacts, and focused verification or exact blocker",
        review_policy="artifact-contract",
        priority=79,
    ),
    CapabilitySpec(
        id="conversation-reasoning",
        domains=("conversation", "knowledge_question"),
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


def registry_health() -> Dict[str, Any]:
    ids = [spec.id for spec in CAPABILITY_SPECS]
    handlers = [spec.handler_key for spec in CAPABILITY_SPECS]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    duplicate_handlers = sorted({value for value in handlers if handlers.count(value) > 1})
    required = {
        "focused-clarification",
        "bounded-specialist-capability",
        "local-installation-status",
        "local-file-evidence",
        "current-web-research",
        "source-backed-reasoning",
        "expert-comparison",
        "klipper-config-migration",
        "local-cad-artifact",
        "local-aero-cfd-artifact",
        "local-structural-fea-artifact",
        "local-engineering-diagram-artifact",
        "engineering-power-conversion",
        "engineering-advisory",
        "local-product-action",
        "conversation-reasoning",
    }
    missing = sorted(required.difference(ids))
    return {
        "status": "pass" if not duplicates and not duplicate_handlers and not missing else "fail",
        "count": len(CAPABILITY_SPECS),
        "duplicates": duplicates,
        "duplicateHandlers": duplicate_handlers,
        "missing": missing,
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
