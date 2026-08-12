#!/usr/bin/env python3
"""P235 adversaries for bounded Research + Apply author/recovery ownership."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


MESSAGES = [
    {
        "role": "user",
        "text": (
            "Research the captured local material guide and apply its verified sequence "
            "to the active profile workflow by staging a receipt and Project Apply plan."
        ),
    }
]
EVIDENCE = [
    {
        "id": "captured-material-guide",
        "source": "source-vault",
        "sourceId": "3d-printing/ellis-print-tuning-guide",
        "title": "Captured material tuning guide",
        "url": "https://ellis3dp.com/Print-Tuning-Guide/",
        "score": 10,
        "fetched": True,
        "sourceType": "technical-primary",
        "excerpt": "Captured evidence covers first layer, pressure advance, flow, cooling, and maximum volumetric flow.",
    }
]
PRIMARY_TEXT = "\n\n".join(
    [
        "Applied outcome: the captured source defines a bounded calibration sequence.",
        "Applied to project: I staged only the Research + Apply receipt and plan; no live profile or machine setting was changed.",
        "Verification: the evidence index and staged plan are the completion proof for this pass.",
    ]
)


def main():
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    route = {
        "projectId": "synthetic-research-project",
        "project": "Synthetic Research Project",
        "specialist": "Research Specialist",
        "engine": "research-apply",
        "effectiveProfile": "research-apply",
    }

    with tempfile.TemporaryDirectory(prefix="p235-research-apply-") as tmp:
        root = Path(tmp)
        run_index = {"value": 0}

        def artifact_functions(label, *, stage_error=False):
            target = root / label
            target.mkdir(parents=True, exist_ok=True)

            def write_receipt(messages, receipt_route, evidence, answer, cwd="", source_binding=None):
                report_path = target / "RESEARCH_APPLY.md"
                evidence_path = target / "evidence.json"
                report_path.write_text(answer + "\n", encoding="utf-8")
                evidence_path.write_text(
                    json.dumps(
                        {
                            "ok": True,
                            "query": server.latest_user_text(messages),
                            "route": receipt_route,
                            "evidence": evidence,
                            "sourceBinding": source_binding,
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                return {
                    "ok": True,
                    "reportPath": str(report_path),
                    "evidencePath": str(evidence_path),
                }

            def stage(messages, route=None, cwd="", research_receipt=None):
                if stage_error:
                    raise TimeoutError("synthetic artifact stage timeout")
                plan_path = target / "PROJECT_APPLY_PLAN.md"
                manifest_path = target / "apply_manifest.json"
                plan_path.write_text("synthetic project apply plan\n", encoding="utf-8")
                manifest_path.write_text(
                    json.dumps(
                        {
                            "ok": True,
                            "query": server.latest_user_text(messages),
                            "liveApplyRequested": False,
                            "applied": False,
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                return {
                    "ok": True,
                    "planPath": str(plan_path),
                    "manifestPath": str(manifest_path),
                    "liveApplyRequested": False,
                    "applied": False,
                    "orca": {},
                }

            return write_receipt, stage

        def run_fixture(label, generate, *, evidence_loader=None, binding_fn=None, stage_error=False):
            writer, stager = artifact_functions(label, stage_error=stage_error)
            started = time.perf_counter()
            result = server.run_research_apply(
                MESSAGES,
                dict(route),
                web_search="disabled",
                cwd=str(root),
                generate_fn=generate,
                receipt_writer=writer,
                project_apply_stager=stager,
                evidence_loader=(evidence_loader or (lambda _query, _route: [dict(EVIDENCE[0])])),
                evidence_binding_fn=binding_fn,
                prompt_builder=lambda *_args, **_kwargs: "synthetic source-bound research/apply prompt",
            )
            result["observedDurationMs"] = round((time.perf_counter() - started) * 1000)
            return result

        fast = run_fixture(
            "fast",
            lambda _prompt, **_kwargs: {"text": PRIMARY_TEXT},
        )
        fast_phase = fast.get("phaseReceipt") or {}
        add(
            "fast-primary-success-keeps-source-bound-artifacts",
            fast.get("model") == server.LOCAL_RESEARCH_MODEL
            and fast_phase.get("status") == "pass"
            and (fast_phase.get("author") or {}).get("status") == "complete"
            and fast_phase.get("sourceBindingStatus") == "pass"
            and (fast_phase.get("artifactPhase") or {}).get("status") == "pass"
            and all((fast_phase.get("artifacts") or {}).values())
            and Path((fast.get("receipt") or {}).get("reportPath") or "").is_file()
            and Path((fast.get("projectApply") or {}).get("manifestPath") or "").is_file(),
            fast_phase,
        )

        usable_after_timeout = run_fixture(
            "usable-after-timeout",
            lambda _prompt, **_kwargs: {
                "text": PRIMARY_TEXT,
                "error": "synthetic primary timeout after a usable draft",
            },
        )
        usable_phase = usable_after_timeout.get("phaseReceipt") or {}
        add(
            "primary-timeout-with-usable-draft-is-preserved",
            usable_after_timeout.get("model") == server.LOCAL_RESEARCH_MODEL
            and (usable_phase.get("author") or {}).get("status")
            == "usable-draft-after-error"
            and usable_phase.get("recoveryDraftUsed") is False
            and usable_phase.get("status") == "pass",
            usable_phase,
        )

        malformed = run_fixture(
            "malformed",
            lambda _prompt, **_kwargs: ["not", "typed", "metadata"],
        )
        malformed_phase = malformed.get("phaseReceipt") or {}
        add(
            "malformed-primary-recovers-with-prebuilt-evidence-draft",
            malformed.get("model") == "research-apply-fallback"
            and (malformed_phase.get("author") or {}).get("status") == "malformed"
            and malformed_phase.get("recoveryDraftUsed") is True
            and malformed_phase.get("status") == "pass",
            malformed_phase,
        )

        author_calls = {"count": 0}

        def no_evidence_author(_prompt, **_kwargs):
            author_calls["count"] += 1
            return {"text": PRIMARY_TEXT}

        no_evidence = run_fixture(
            "no-evidence",
            no_evidence_author,
            evidence_loader=lambda _query, _route: [],
        )
        add(
            "no-evidence-fails-before-author-or-artifacts",
            not no_evidence.get("text")
            and (no_evidence.get("phaseReceipt") or {}).get("reason")
            == "missing-source-evidence"
            and author_calls["count"] == 0
            and not (root / "no-evidence" / "RESEARCH_APPLY.md").exists(),
            no_evidence.get("phaseReceipt"),
        )

        review_timeout = server.research_apply_controller_review(
            fast.get("text"),
            fast_phase,
            {"error": "synthetic review timeout"},
        )
        add(
            "review-timeout-cannot-discard-controller-owned-candidate",
            review_timeout.get("text") == fast.get("text")
            and (review_timeout.get("receipt") or {}).get("status") == "pass"
            and (review_timeout.get("receipt") or {}).get("candidatePreserved") is True
            and (review_timeout.get("receipt") or {}).get("optionalReviewStatus")
            == "timeout",
            review_timeout.get("receipt"),
        )

        binding_calls = {"count": 0}

        def drifting_binding(query, evidence):
            binding_calls["count"] += 1
            value = server.research_apply_evidence_binding(query, evidence)
            if binding_calls["count"] > 1:
                value["evidenceSha256"] = "f" * 64
            return value

        drifted = run_fixture(
            "source-drift",
            lambda _prompt, **_kwargs: {"text": PRIMARY_TEXT},
            binding_fn=drifting_binding,
        )
        add(
            "source-drift-blocks-before-artifact-claims",
            not drifted.get("text")
            and (drifted.get("phaseReceipt") or {}).get("sourceBindingStatus")
            == "drifted"
            and (drifted.get("phaseReceipt") or {}).get("reason") == "source-drift"
            and not (root / "source-drift" / "RESEARCH_APPLY.md").exists(),
            drifted.get("phaseReceipt"),
        )

        controller_review = server.research_apply_controller_review(
            fast.get("text"),
            fast_phase,
        )
        semantic_route = dict(route)
        semantic_route["_researchApplyFinalizationReceipt"] = {
            "kind": "research-apply-finalization-receipt",
            "version": 1,
            "status": "pass",
            "modelReviewSkipped": True,
            "candidateSha256": server.text_sha256(fast.get("text")),
            "contentsRecorded": False,
        }
        semantic = server.research_apply_semantic_completion_receipt(
            MESSAGES,
            semantic_route,
            fast.get("text"),
            {
                "receipt": fast.get("receipt"),
                "projectApply": fast.get("projectApply"),
                "phaseReceipt": fast_phase,
                "controllerReview": controller_review.get("receipt"),
            },
        )
        add(
            "actual-staged-artifacts-and-source-binding-produce-semantic-proof",
            semantic.get("status") == "pass"
            and semantic.get("handled") is True
            and str(semantic.get("receiptId") or "").startswith("research-apply-"),
            semantic,
        )

        overrun_writer, _overrun_stager = artifact_functions("bounded-overrun")

        def slow_stage(*_args, **_kwargs):
            time.sleep(0.25)
            return {"ok": True}

        overrun_started = time.perf_counter()
        overrun = server.run_research_apply(
            MESSAGES,
            dict(route),
            web_search="disabled",
            cwd=str(root),
            generate_fn=lambda _prompt, **_kwargs: {"error": "synthetic primary timeout"},
            receipt_writer=overrun_writer,
            project_apply_stager=slow_stage,
            evidence_loader=lambda _query, _route: [dict(EVIDENCE[0])],
            artifact_budget_seconds=0.03,
            prompt_builder=lambda *_args, **_kwargs: "synthetic source-bound research/apply prompt",
        )
        overrun_elapsed_ms = round((time.perf_counter() - overrun_started) * 1000)
        overrun_phase = overrun.get("phaseReceipt") or {}
        overrun_review = server.research_apply_controller_review(
            overrun.get("text"),
            overrun_phase,
        )
        overrun_route = {
            **route,
            "capabilityPlan": {"review_policy": "reasoning-audit"},
            "_researchApplyControllerWorkflow": {
                "phaseReceipt": overrun_phase,
                "controllerReview": overrun_review.get("receipt") or {},
            },
        }
        add(
            "post-author-project-apply-overrun-is-bounded-and-model-free",
            bool(overrun.get("text"))
            and overrun_phase.get("status") == "block"
            and overrun_phase.get("reason") == "artifact-phase-timeout"
            and (overrun_phase.get("artifactPhase") or {}).get("projectApplyStatus")
            == "timeout"
            and overrun_elapsed_ms < 3_000
            and server.research_apply_controller_finalization_owns_answer(
                overrun_route,
                overrun.get("text"),
            )
            and not server.should_apply_generic_reasoning_final_gate(
                overrun_route,
                overrun.get("text"),
            ),
            {
                "phase": overrun_phase,
                "elapsedMs": overrun_elapsed_ms,
            },
        )

        disconnect_run_id = "p235-post-author-disconnect"
        server.register_live_run(disconnect_run_id)
        disconnect_writer, _disconnect_stager = artifact_functions("disconnect")

        def disconnected_stage(*_args, **_kwargs):
            time.sleep(0.02)
            server.cancel_live_run(disconnect_run_id)
            return {"ok": True}

        try:
            disconnected = server.run_research_apply(
                MESSAGES,
                {**route, "_liveRunId": disconnect_run_id},
                web_search="disabled",
                cwd=str(root),
                generate_fn=lambda _prompt, **_kwargs: {"error": "synthetic primary timeout"},
                receipt_writer=disconnect_writer,
                project_apply_stager=disconnected_stage,
                evidence_loader=lambda _query, _route: [dict(EVIDENCE[0])],
                artifact_budget_seconds=1.0,
                prompt_builder=lambda *_args, **_kwargs: "synthetic source-bound research/apply prompt",
            )
        finally:
            server.unregister_live_run(disconnect_run_id)
        add(
            "disconnected-client-cancels-post-author-artifact-finalization",
            disconnected.get("cancelled") is True
            and (disconnected.get("phaseReceipt") or {}).get("status") == "cancelled"
            and (disconnected.get("phaseReceipt") or {}).get("reason")
            == "cancelled-during-artifact-finalization"
            and ((disconnected.get("phaseReceipt") or {}).get("artifactPhase") or {}).get("status")
            == "cancelled",
            disconnected.get("phaseReceipt"),
        )

        incomplete = run_fixture(
            "incomplete",
            lambda _prompt, **_kwargs: {"error": "synthetic primary timeout"},
            stage_error=True,
        )
        incomplete_phase = incomplete.get("phaseReceipt") or {}
        incomplete_review = server.research_apply_controller_review(
            incomplete.get("text"),
            incomplete_phase,
        )
        add(
            "bounded-incomplete-artifacts-cannot-pass-controller-review",
            bool(incomplete.get("text"))
            and incomplete_phase.get("status") == "block"
            and incomplete_phase.get("reason") == "incomplete-artifacts"
            and (incomplete_review.get("receipt") or {}).get("status") == "block"
            and not incomplete_review.get("text"),
            {"phase": incomplete_phase, "review": incomplete_review.get("receipt")},
        )

        cancel_run_id = "p235-cancelled"
        server.register_live_run(cancel_run_id)
        server.cancel_live_run(cancel_run_id)
        try:
            cancelled = server.run_research_apply(
                MESSAGES,
                {**route, "_liveRunId": cancel_run_id},
                web_search="disabled",
                generate_fn=lambda _prompt, **_kwargs: {"text": PRIMARY_TEXT},
                evidence_loader=lambda _query, _route: [dict(EVIDENCE[0])],
            )
        finally:
            server.unregister_live_run(cancel_run_id)
        add(
            "cancellation-stops-before-evidence-author-or-artifacts",
            cancelled.get("cancelled") is True
            and (cancelled.get("phaseReceipt") or {}).get("status") == "cancelled"
            and (cancelled.get("phaseReceipt") or {}).get("reason")
            == "cancelled-before-evidence",
            cancelled.get("phaseReceipt"),
        )

        deadline_run_id = "p235-deadline"
        previous_run_id = server.current_request_run_id()
        server.RUN_REQUEST_CONTEXT.run_id = deadline_run_id
        server.register_request_deadline(
            deadline_run_id,
            0.05,
            now=time.monotonic() - 1.0,
        )
        try:
            deadline = server.run_research_apply(
                MESSAGES,
                dict(route),
                web_search="disabled",
                generate_fn=lambda _prompt, **_kwargs: {"text": PRIMARY_TEXT},
                evidence_loader=lambda _query, _route: [dict(EVIDENCE[0])],
            )
        finally:
            server.release_request_deadline(deadline_run_id)
            if previous_run_id:
                server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
        add(
            "expired-parent-deadline-fails-before-author-and-artifacts",
            not deadline.get("text")
            and (deadline.get("phaseReceipt") or {}).get("reason")
            == "request-deadline-before-author"
            and not (deadline.get("phaseReceipt") or {}).get("author"),
            deadline.get("phaseReceipt"),
        )

        cold_ms = int(fast.get("observedDurationMs") or 0)
        warm_ms = int(usable_after_timeout.get("observedDurationMs") or 0)
        author_budget_ms = int((fast_phase.get("author") or {}).get("budgetMs") or 0)
        add(
            "author-slice-and-synthetic-cold-warm-runtime-have-margin",
            0 < author_budget_ms <= 12_000
            and cold_ms < 3_000
            and warm_ms < 3_000,
            {
                "authorBudgetMs": author_budget_ms,
                "coldMs": cold_ms,
                "warmMs": warm_ms,
                "historicalBaselineMs": 92_152,
            },
        )

        private_canary = (
            "captured local material guide /Us" + "ers/private/Secret.3mf "
            "https://secret.invalid token=PRIVATE command --unsafe"
        )
        serialized_phase = json.dumps(fast_phase, sort_keys=True)
        add(
            "phase-receipt-is-metadata-only",
            private_canary not in serialized_phase
            and server.latest_user_text(MESSAGES) not in serialized_phase
            and str(root) not in serialized_phase
            and fast_phase.get("contentsRecorded") is False,
            fast_phase,
        )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "research-apply-route-owns-a-research-deadline-without-lending-it-to-author",
        server.request_deadline_budget_for_route(route, "fast")
        == (server.REQUEST_RESEARCH_BUDGET_SECONDS, "research-apply")
        and server.RESEARCH_APPLY_AUTHOR_BUDGET_SECONDS == 12.0
        and server.RESEARCH_APPLY_ARTIFACT_BUDGET_SECONDS == 8.0
        and server.RESEARCH_APPLY_FINALIZATION_RESERVE_SECONDS >= 5.0,
        {
            "routeBudget": server.request_deadline_budget_for_route(route, "fast"),
            "authorBudgetSeconds": server.RESEARCH_APPLY_AUTHOR_BUDGET_SECONDS,
            "artifactBudgetSeconds": server.RESEARCH_APPLY_ARTIFACT_BUDGET_SECONDS,
            "reserveSeconds": server.RESEARCH_APPLY_FINALIZATION_RESERVE_SECONDS,
        },
    )
    add(
        "p235-package-and-export-registration",
        "server:research-apply-phase-budget-p235" in source_text
        and "p235_research_apply_phase_budget_smoke.py" in source_text
        and "tools/p235_research_apply_phase_budget_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p235-research-apply-phase-budget",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
