#!/usr/bin/env python3
"""Focused P192 typed proportionate-review and controller-boundary contract."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_registry
import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {"name": name, "status": "pass" if passed else "fail", "detail": detail}
    )


def route(prompt, *, web_search="disabled"):
    messages = [{"role": "user", "text": prompt}]
    return messages, server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web_search,
    )


reasoning_specs = [
    spec
    for spec in capability_registry.CAPABILITY_SPECS
    if spec.executor == "reasoning-worker" and spec.review_policy == "reasoning-audit"
]
check(
    "registered-reasoning-review-surface-is-finite-and-typed",
    {spec.id for spec in reasoning_specs}
    == {
        "conversation-reasoning",
        "expert-comparison",
        "printer-job-eta-reasoning",
        "decision-metric-design",
    },
    [spec.id for spec in reasoning_specs],
)


comparison_messages, comparison_route = route(
    "Compare event sourcing and CRUD for an audit-heavy inventory service, "
    "recommend a direction, state when you would reverse it, and name the first "
    "test you would run."
)
comparison_answer = (
    "Use event sourcing as the default for this audit-heavy inventory service because its append-only event "
    "history preserves who changed what and supports reconstruction of past state. CRUD is simpler to operate, "
    "but complete audit reconstruction then depends on additional history tables and disciplined write paths.\n\n"
    "CRUD becomes the better choice when the audit requirement only needs current-state accountability, the event "
    "model makes ordinary corrections or reads too costly, and a conventional audit log passes the same checks.\n\n"
    "The first test I would run is a representative inventory correction followed by a full state rebuild, verifying "
    "that the rebuilt quantity, actor, timestamp, and reason match the original transaction while a CRUD prototype "
    "is checked against the same audit query."
)
comparison_review_calls = []


def comparison_review(*_args, **_kwargs):
    comparison_review_calls.append(True)
    return {"payload": {}, "error": "deep reviewer should not run", "durationMs": 0}


comparison_audit = server.run_generic_reasoning_audit(
    comparison_messages,
    comparison_route,
    comparison_answer,
    review_fn=comparison_review,
    triage_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("small triage should not run for a controller-proven comparison")
    ),
)
check(
    "strong-stable-comparison-skips-deep-review-with-exact-obligation-proof",
    not comparison_review_calls
    and comparison_audit.get("deepReviewSkipped") is True
    and comparison_audit.get("controllerGateKind") == "stable-comparison"
    and comparison_audit.get("finalAnswer") == comparison_answer
    and (comparison_audit.get("obligationReceipt") or {}).get("status") == "pass"
    and all(
        item.get("controllerValidated") is True
        for item in (comparison_audit.get("obligationReceipt") or {}).get("items") or []
    ),
    comparison_audit,
)

missing_option_answer = (
    "Use event sourcing because its history supports audits. It becomes the better choice when audit reconstruction "
    "matters, and the first test should rebuild state from the event log."
)
invented_precision_answer = comparison_answer.replace(
    "additional history tables",
    "a 0.4 ms write path and additional history tables",
)
check(
    "comparison-missing-option-or-unsupported-precision-cannot-fast-accept",
    server.stable_expert_comparison_candidate_gate(
        comparison_messages, comparison_route, missing_option_answer
    ).get("accepted")
    is False
    and server.stable_expert_comparison_candidate_gate(
        comparison_messages, comparison_route, invented_precision_answer
    ).get("accepted")
    is False,
    {
        "missing": server.stable_expert_comparison_candidate_gate(
            comparison_messages, comparison_route, missing_option_answer
        ),
        "precision": server.stable_expert_comparison_candidate_gate(
            comparison_messages, comparison_route, invented_precision_answer
        ),
    },
)

precision_review_calls = []


def precision_review(*_args, **_kwargs):
    precision_review_calls.append(True)
    return {"payload": {}, "error": "deep reviewer should not run", "durationMs": 0}


precision_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    comparison_messages,
    comparison_route,
    invented_precision_answer,
)
precision_audit = server.run_generic_reasoning_audit(
    comparison_messages,
    comparison_route,
    invented_precision_answer,
    review_fn=precision_review,
    triage_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("triage should not run after request-bound precision cleanup")
    ),
)
check(
    "unsupported-precision-only-defect-is-removed-and-exact-remainder-revalidated",
    precision_cleanup.get("applied") is True
    and "0.4 ms" not in str(precision_cleanup.get("text") or "")
    and (precision_cleanup.get("gate") or {}).get("accepted") is True
    and not precision_review_calls
    and precision_audit.get("deepReviewSkipped") is True
    and precision_audit.get("repairApplied") is True
    and precision_audit.get("repairModel")
    == "deterministic-unsupported-precision-cleanup"
    and precision_audit.get("controllerGateKind")
    == "stable-comparison-precision-cleanup"
    and precision_audit.get("finalAnswer") == precision_cleanup.get("text")
    and (precision_audit.get("obligationReceipt") or {}).get("status") == "pass"
    and all(
        item.get("controllerValidated") is True
        for item in (precision_audit.get("obligationReceipt") or {}).get("items") or []
    ),
    {"cleanup": precision_cleanup, "audit": precision_audit},
)

critical_precision_answer = (
    "Event sourcing is preferable because it provides a 0.4 ms write path. "
    "CRUD becomes the better choice when the audit need is limited to current-state accountability, and the first "
    "test should compare reconstruction of one representative correction against a conventional audit log."
)
critical_cleanup = server.sanitize_stable_comparison_unsupported_precision(
    comparison_messages,
    comparison_route,
    critical_precision_answer,
)
check(
    "precision-cleanup-cannot-erase-a-critical-option-and-mint-completion",
    critical_cleanup.get("applied") is False
    and (critical_cleanup.get("gate") or {}).get("accepted") is False,
    critical_cleanup,
)

missing_test_answer = comparison_answer.rsplit("\n\nThe first test", 1)[0]
missing_test_review_calls = []
missing_test_audit = server.run_generic_reasoning_audit(
    comparison_messages,
    comparison_route,
    missing_test_answer,
    triage_fn=lambda *_args, **_kwargs: {"attempted": False, "passed": False},
    review_fn=lambda *_args, **_kwargs: missing_test_review_calls.append(True)
    or {
        "payload": {},
        "attemptCount": 1,
        "attemptedModels": [server.GENERIC_REASONING_AUDIT_MODEL],
        "error": "synthetic unavailable reviewer",
    },
)
check(
    "incomplete-critical-obligation-cannot-use-a-generic-decision-fast-path",
    len(missing_test_review_calls) == 1
    and missing_test_audit.get("deepReviewSkipped") is not True
    and not missing_test_audit.get("finalAnswer")
    and (missing_test_audit.get("obligationReceipt") or {}).get("status") == "block",
    missing_test_audit,
)


eta_messages, eta_route = route(
    "Why are my slicer and Qidi device-tab completion estimates different?"
)
eta_audit_calls = []


def eta_audit(*_args, **_kwargs):
    eta_audit_calls.append(True)
    return {"finalAnswer": "untrusted", "verdict": "sound"}


eta_answer = server.apply_generic_reasoning_final_gate(
    eta_messages,
    eta_route,
    "The slicer and printer use different estimates, so the printer is definitely four hours late.",
    audit_fn=eta_audit,
)
eta_boundary = eta_route.get("_controllerReasoningBoundaryReceipt") or {}
check(
    "missing-evidence-printer-eta-uses-bound-controller-result-without-review",
    not eta_audit_calls
    and eta_route.get("_supervisionStatus") == "bounded"
    and eta_route.get("_executionReturnCode") == 1
    and eta_boundary.get("status") == "bounded"
    and eta_boundary.get("mayClaimComplete") is False
    and eta_boundary.get("candidateSha256") == server.text_sha256(eta_answer)
    and server.controller_synthesized_registered_reasoning_boundary_candidate(
        eta_messages, eta_route, eta_answer
    )
    and "cannot claim the exact cause or finish time" in eta_answer
    and "slicer estimate is a pre-run prediction" in eta_answer
    and "live printer/device estimate is recalculated" in eta_answer,
    {"answer": eta_answer, "route": eta_route},
)

tampered_eta_route = dict(eta_route)
tampered_eta_route["_controllerReasoningBoundaryReceipt"] = dict(eta_boundary)
tampered_eta_route["_controllerReasoningBoundaryReceipt"]["candidateSha256"] = "0" * 64
check(
    "controller-boundary-request-ledger-candidate-binding-fails-closed",
    not server.controller_synthesized_registered_reasoning_boundary_candidate(
        eta_messages, tampered_eta_route, eta_answer
    )
    and (eta_route.get("_answerObligationReceipt") or {}).get("status") == "block",
    {
        "boundary": tampered_eta_route.get("_controllerReasoningBoundaryReceipt"),
        "obligation": eta_route.get("_answerObligationReceipt"),
    },
)


metric_messages, metric_route = route(
    "Our failed-job count fell, but job lengths and work mix changed. "
    "Design a metric that tells us whether reliability actually improved."
)
metric_answer = (
    "Use failed jobs divided by jobs started as the primary attempt-level failure probability, because the numerator "
    "and denominator describe the same unit at risk. Track failure events per machine-hour separately as exposure "
    "hazard, and track scrap mass, lost machine-hours, or rework cost separately as consequence; those measures "
    "answer different decisions and must not be merged.\n\n"
    "Compare like-for-like machine, material, job-family, and duration cohorts, or standardize both periods to the "
    "same intended work mix before judging improvement. Report a confidence interval or a defined count-rate test, "
    "and do not call the change significant until the sample sizes and comparison window support that uncertainty calculation."
)
metric_review_calls = []


def metric_review(*_args, **_kwargs):
    metric_review_calls.append(True)
    return {"payload": {}, "error": "deep reviewer should not run", "durationMs": 0}


metric_audit = server.run_generic_reasoning_audit(
    metric_messages,
    metric_route,
    metric_answer,
    review_fn=metric_review,
    triage_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("small triage should not run for a controller-proven metric")
    ),
)
check(
    "complete-decision-metric-skips-review-only-after-all-typed-rows-pass",
    not metric_review_calls
    and metric_audit.get("deepReviewSkipped") is True
    and metric_audit.get("controllerGateKind") == "decision-metric"
    and (metric_audit.get("obligationReceipt") or {}).get("status") == "pass"
    and all(
        item.get("controllerValidated") is True
        for item in (metric_audit.get("obligationReceipt") or {}).get("items") or []
    ),
    metric_audit,
)

bad_metric = (
    "Use failures divided by machine-hours as the one reliability score. The lower number proves the process "
    "improved even though product mix changed."
)
check(
    "mixed-unit-or-unsupported-significance-metric-cannot-fast-accept",
    server.decision_metric_candidate_gate(
        metric_messages, metric_route, bad_metric
    ).get("accepted")
    is False,
    server.decision_metric_candidate_gate(metric_messages, metric_route, bad_metric),
)


ordinary_messages, ordinary_route = route("Why does the sky appear blue?")
ordinary_answer = (
    "The sky looks blue because atmospheric molecules scatter shorter visible wavelengths more strongly than longer "
    "ones, redirecting blue light across the sky into your eyes. Violet scatters strongly too, but sunlight contains "
    "less of it and human vision is less sensitive to it. Near sunset, a longer atmospheric path removes more blue "
    "from the direct beam, so reds and oranges dominate."
)
high_risk_cases = (
    ("I have crushing chest pain and trouble breathing. Should I wait until morning?", "Do not wait."),
    ("Is it legal to sign this liability waiver without a lawyer?", "A local lawyer should review it."),
    ("Find the cheapest currently available 2 TB SSD listing today.", "The current price is unknown."),
    ("Prove that the sum of any two odd integers is even.", "Let the integers be odd."),
    ("Write a thread-safe queue with exactly-once delivery guarantees.", "Use a queue."),
    ("Calculate motor current from 11 kW at 48 V.", "Current is power divided by voltage."),
)
high_risk_results = []
for prompt, answer in high_risk_cases:
    messages, candidate_route = route(prompt)
    high_risk_results.append(
        server.low_risk_generic_reasoning_triage_eligible(
            messages, candidate_route, answer, []
        )
    )
check(
    "typed-low-risk-admission-keeps-high-risk-current-formal-code-and-calculation-deep",
    server.low_risk_generic_reasoning_triage_eligible(
        ordinary_messages, ordinary_route, ordinary_answer, []
    )
    and not any(high_risk_results),
    high_risk_results,
)


previous_run_id = server.current_request_run_id()
deadline_run_id = "p192-deadline-contract"
try:
    server.RUN_REQUEST_CONTEXT.run_id = deadline_run_id
    initial = server.register_request_deadline(deadline_run_id, 600, now=100.0)
    tightened = server.tighten_request_deadline(
        deadline_run_id,
        90,
        route_class="conversation-answer",
        now=130.0,
    )
    attempted_extension = server.tighten_request_deadline(
        deadline_run_id,
        120,
        route_class="conversation-answer-full",
        now=140.0,
    )
    receipt = server.request_deadline_receipt(now=191.0)
    check(
        "request-deadline-starts-at-ingress-and-can-only-tighten",
        initial.get("deadlineMonotonic") == 700.0
        and tightened.get("deadlineMonotonic") == 190.0
        and attempted_extension.get("deadlineMonotonic") == 190.0
        and receipt.get("deadlineExhausted") is True
        and receipt.get("effectiveBudgetMs") == 90000
        and receipt.get("tighteningCount") == 2,
        {"initial": initial, "tightened": tightened, "extension": attempted_extension, "receipt": receipt},
    )
finally:
    server.release_request_deadline(deadline_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")


worker_run_id = "p192-worker-deadline"
try:
    server.RUN_REQUEST_CONTEXT.run_id = worker_run_id
    server.register_request_deadline(worker_run_id, 2.0)
    worker_context = server.call_with_request_run_context(
        worker_run_id,
        lambda: {
            "runId": server.current_request_run_id(),
            "remaining": server.remaining_request_budget_seconds(),
        },
    )
    check(
        "worker-thread-context-inherits-the-same-parent-deadline",
        worker_context.get("runId") == worker_run_id
        and 0 < float(worker_context.get("remaining") or 0) <= 2.0,
        worker_context,
    )
finally:
    server.release_request_deadline(worker_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")


blocking_run_id = "p192-blocking-deadline"
release_blocker = threading.Event()
blocking_started = time.monotonic()
blocking_error = ""
try:
    server.RUN_REQUEST_CONTEXT.run_id = blocking_run_id
    server.register_request_deadline(blocking_run_id, 0.06)
    try:
        server.run_cancellable_blocking_call(
            lambda: release_blocker.wait(1.0),
            poll_seconds=0.005,
            stage="synthetic-read-only-io",
        )
    except Exception as exc:  # the exact class is part of the assertion below
        blocking_error = exc.__class__.__name__
    blocking_elapsed = time.monotonic() - blocking_started
    blocking_receipt = server.request_deadline_receipt()
    check(
        "blocking-read-only-io-stops-waiting-at-parent-deadline-and-records-stage",
        blocking_error == "TimeoutError"
        and blocking_elapsed < 0.30
        and blocking_receipt.get("deadlineExhausted") is True
        and any(
            item.get("stage") == "synthetic-read-only-io"
            for item in blocking_receipt.get("skippedStages") or []
        ),
        {"error": blocking_error, "elapsed": blocking_elapsed, "receipt": blocking_receipt},
    )
finally:
    release_blocker.set()
    server.release_request_deadline(blocking_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")

check(
    "request-deadline-contexts-release-without-leak",
    all(
        run_id not in server.REQUEST_DEADLINE_CONTEXTS
        for run_id in (deadline_run_id, worker_run_id, blocking_run_id)
    ),
    list(server.REQUEST_DEADLINE_CONTEXTS),
)

parallel_run_id = "p192-parallel-search-deadline"
release_parallel = threading.Event()
parallel_started = time.monotonic()
try:
    server.RUN_REQUEST_CONTEXT.run_id = parallel_run_id
    server.register_request_deadline(parallel_run_id, 0.06)
    parallel_results = server.parallel_web_search_queries(
        ["one", "two", "three"],
        route={"_liveRunId": parallel_run_id},
        search_fn=lambda _query: release_parallel.wait(1.0) and [],
        max_workers=3,
    )
    parallel_elapsed = time.monotonic() - parallel_started
    parallel_receipt = server.request_deadline_receipt()
    check(
        "parallel-read-only-search-stops-waiting-at-parent-deadline",
        parallel_elapsed < 0.30
        and parallel_results == [("one", []), ("two", []), ("three", [])]
        and parallel_receipt.get("deadlineExhausted") is True
        and any(
            item.get("stage") == "parallel-web-search"
            for item in parallel_receipt.get("skippedStages") or []
        ),
        {"elapsed": parallel_elapsed, "results": parallel_results, "receipt": parallel_receipt},
    )
finally:
    release_parallel.set()
    server.release_request_deadline(parallel_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")

single_search_run_id = "p192-single-search-deadline"
release_single_search = threading.Event()
single_started = time.monotonic()
try:
    server.RUN_REQUEST_CONTEXT.run_id = single_search_run_id
    server.register_request_deadline(single_search_run_id, 0.06)
    single_results = server.parallel_web_search_queries(
        ["only-query"],
        route={"_liveRunId": single_search_run_id},
        search_fn=lambda _query: release_single_search.wait(1.0) and [],
        max_workers=6,
    )
    single_elapsed = time.monotonic() - single_started
    single_receipt = server.request_deadline_receipt()
    check(
        "single-read-only-search-uses-the-same-parent-deadline",
        single_elapsed < 0.30
        and single_results == [("only-query", [])]
        and single_receipt.get("deadlineExhausted") is True
        and any(
            item.get("stage") == "parallel-web-search"
            for item in single_receipt.get("skippedStages") or []
        ),
        {"elapsed": single_elapsed, "results": single_results, "receipt": single_receipt},
    )
finally:
    release_single_search.set()
    server.release_request_deadline(single_search_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")


primary_worker_run_id = "p192-primary-worker-deadline"
primary_worker = None
try:
    server.RUN_REQUEST_CONTEXT.run_id = primary_worker_run_id
    server.register_request_deadline(primary_worker_run_id, 1.0)
    primary_worker = subprocess.Popen(
        ["/bin/sleep", "5"],
        start_new_session=True,
    )
    primary_route = {}
    primary_stopped = server.stop_read_only_primary_worker_for_request_deadline(
        primary_worker,
        route=primary_route,
        reserve_seconds=2.0,
    )
    withheld_partial = server.primary_worker_candidate_after_deadline(
        "Partial worker text that must never reach review or final output.",
        primary_stopped,
        route=primary_route,
    )
    primary_receipt = server.request_deadline_receipt()
    check(
        "stalled-read-only-primary-worker-is-terminated-before-terminal-budget-expires",
        primary_stopped is True
        and primary_worker.poll() is not None
        and withheld_partial == ""
        and (primary_route.get("_requestDeadlinePrimaryWorker") or {}).get("mutationStarted") is False
        and (primary_route.get("_requestDeadlinePrimaryWorker") or {}).get("partialCandidateWithheld") is True
        and primary_receipt.get("deadlineExhausted") is True
        and any(
            item.get("stage") == "primary-worker"
            for item in primary_receipt.get("skippedStages") or []
        ),
        {"route": primary_route, "receipt": primary_receipt},
    )
finally:
    if primary_worker is not None and primary_worker.poll() is None:
        server.terminate_process_group(primary_worker, grace_seconds=0)
    server.release_request_deadline(primary_worker_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")


mutation_gate_run_id = "p192-expired-controller-mutation"
mutation_callbacks = []
try:
    server.RUN_REQUEST_CONTEXT.run_id = mutation_gate_run_id
    server.register_request_deadline(mutation_gate_run_id, 1.0)
    mutation_allowed = server.request_deadline_allows_new_stage(
        "local-action-controller-mutation",
        minimum_remaining_seconds=2.0,
    )
    if mutation_allowed:
        mutation_callbacks.append("applied")
    mutation_receipt = server.request_deadline_receipt()
    check(
        "proposal-inside-terminal-reserve-cannot-start-controller-mutation",
        mutation_allowed is False
        and not mutation_callbacks
        and mutation_receipt.get("deadlineExhausted") is True
        and any(
            item.get("stage") == "local-action-controller-mutation"
            for item in mutation_receipt.get("skippedStages") or []
        ),
        {"callbacks": mutation_callbacks, "receipt": mutation_receipt},
    )
finally:
    server.release_request_deadline(mutation_gate_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")

deadline_classes = {
    "conversation": server.request_deadline_budget_for_route({}, "balanced"),
    "research": server.request_deadline_budget_for_route(
        {"intentFrame": {"evidenceNeed": "current-web-evidence"}}, "balanced"
    ),
    "live": server.request_deadline_budget_for_route(
        {"intentFrame": {"domain": "live_device_action"}}, "balanced"
    ),
    "local": server.request_deadline_budget_for_route(
        {"intentFrame": {"outputContract": {"mode": "local-artifact"}}},
        "balanced",
    ),
    "conversationFull": server.request_deadline_budget_for_route({}, "full"),
}
check(
    "typed-route-classes-tighten-to-distinct-product-budgets",
    deadline_classes
    == {
        "conversation": (90.0, "conversation-answer"),
        "research": (180.0, "research"),
        "live": (60.0, "live-device"),
        "local": (300.0, "local-action-or-artifact"),
        "conversationFull": (120.0, "conversation-answer"),
    },
    deadline_classes,
)

expired_run_id = "p192-expired-before-model"
expired_api_calls = []
try:
    server.RUN_REQUEST_CONTEXT.run_id = expired_run_id
    server.register_request_deadline(
        expired_run_id,
        0.05,
        now=time.monotonic() - 1.0,
    )
    expired_model_result = server.run_ollama_generate(
        "Return one word.",
        timeout=5,
        api_call_fn=lambda *_args, **_kwargs: expired_api_calls.append(True) or {},
    )
    check(
        "expired-parent-budget-prevents-model-or-retry-fanout",
        not expired_api_calls
        and expired_model_result.get("attemptCount") == 0
        and expired_model_result.get("deadlineExhausted") is True
        and "request deadline expired" in str(expired_model_result.get("error") or "").lower(),
        expired_model_result,
    )
finally:
    server.release_model_stage_budget(expired_run_id)
    server.release_request_deadline(expired_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")

cancelled_run_id = "p192-cancel-is-distinct"
cancelled_api_calls = []
try:
    server.RUN_REQUEST_CONTEXT.run_id = cancelled_run_id
    server.register_request_deadline(cancelled_run_id, 5.0)
    server.register_live_run(cancelled_run_id)
    server.cancel_live_run(cancelled_run_id)
    cancelled_model_result = server.run_ollama_generate(
        "Return one word.",
        timeout=5,
        api_call_fn=lambda *_args, **_kwargs: cancelled_api_calls.append(True) or {},
    )
    cancelled_deadline_receipt = server.request_deadline_receipt()
    check(
        "user-cancellation-remains-distinct-from-deadline-exhaustion",
        not cancelled_api_calls
        and cancelled_model_result.get("cancelled") is True
        and cancelled_model_result.get("deadlineExhausted") is False
        and cancelled_deadline_receipt.get("deadlineExhausted") is False
        and not cancelled_deadline_receipt.get("terminalReason"),
        {"model": cancelled_model_result, "deadline": cancelled_deadline_receipt},
    )
finally:
    server.unregister_live_run(cancelled_run_id)
    server.release_model_stage_budget(cancelled_run_id)
    server.release_request_deadline(cancelled_run_id)
    if previous_run_id:
        server.RUN_REQUEST_CONTEXT.run_id = previous_run_id
    elif hasattr(server.RUN_REQUEST_CONTEXT, "run_id"):
        delattr(server.RUN_REQUEST_CONTEXT, "run_id")


failures = [item for item in checks if item["status"] != "pass"]
report = {
    "suite": "p192-typed-reasoning-review-policy",
    "status": "pass" if not failures else "fail",
    "checkCount": len(checks),
    "passed": len(checks) - len(failures),
    "failed": len(failures),
    "failures": failures,
}
print(json.dumps(report, indent=2, ensure_ascii=True))
raise SystemExit(0 if not failures else 1)
