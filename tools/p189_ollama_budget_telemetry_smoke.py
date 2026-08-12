#!/usr/bin/env python3
"""Focused P189 monotonic local-model budget and metadata-only timing contract."""

from __future__ import annotations

import json
import math
import sys
import time
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


def response(text="ok", reason="stop", *, thinking="", scale=1):
    return {
        "response": text,
        "thinking": thinking,
        "done_reason": reason,
        "eval_count": 7 * scale,
        "prompt_eval_count": 11 * scale,
        "total_duration": 13_000_000 * scale,
        "load_duration": 2_000_000 * scale,
        "prompt_eval_duration": 3_000_000 * scale,
        "eval_duration": 5_000_000 * scale,
    }


clean_calls = []


def clean_call(_payload, timeout=180):
    clean_calls.append(timeout)
    return response()


clean = server.run_ollama_generate(
    "P189_SENTINEL_PROMPT",
    model="synthetic-local",
    timeout=3,
    api_call_fn=clean_call,
    allow_final_retry=False,
)
check(
    "clean-first-pass-is-one-attempt-with-normalized-ollama-timing",
    clean.get("text") == "ok"
    and clean.get("attemptCount") == 1
    and clean.get("deadlineExhausted") is False
    and clean.get("doneReason") == "stop"
    and clean.get("ollamaTotalDurationMs") == 13
    and clean.get("ollamaLoadDurationMs") == 2
    and clean.get("ollamaPromptEvalDurationMs") == 3
    and clean.get("ollamaEvalDurationMs") == 5
    and clean.get("evalCount") == 7
    and clean.get("promptEvalCount") == 11
    and len(clean_calls) == 1
    and 2.9 <= clean_calls[0] <= 3.0,
    clean,
)


hidden_calls = []


def hidden_call(_payload, timeout=180):
    hidden_calls.append(timeout)
    if len(hidden_calls) == 1:
        return response("", "length", thinking="P189_HIDDEN_SENTINEL")
    return response("visible answer", "stop", scale=2)


hidden = server.run_ollama_generate(
    "hidden-only test",
    model="synthetic-local",
    timeout=3,
    api_call_fn=hidden_call,
    allow_final_retry=True,
)
check(
    "hidden-only-retry-shares-one-deadline-and-keeps-distinct-attempt-rows",
    hidden.get("text") == "visible answer"
    and hidden.get("attemptCount") == 2
    and hidden.get("finalRetryReason") == "hidden-only"
    and [item.get("kind") for item in hidden.get("attemptReceipts") or []]
    == ["initial", "final-only-retry"]
    and sum(hidden_calls) <= 3.005
    and max(hidden_calls) < 3,
    {"timeouts": hidden_calls, "receipt": hidden},
)


three_calls = []


def three_call(_payload, timeout=180):
    three_calls.append(timeout)
    if len(three_calls) == 1:
        return response("", "length", thinking="hidden")
    if len(three_calls) == 2:
        return response("partial", "length")
    return response("complete", "stop")


three = server.run_ollama_generate(
    "three attempt test",
    model="synthetic-local",
    timeout=3,
    api_call_fn=three_call,
    allow_final_retry=True,
)
check(
    "hidden-then-truncated-retry-never-authorizes-more-than-requested-budget",
    three.get("text") == "complete"
    and three.get("attemptCount") == 3
    and three.get("budgetFullyAllocated") is True
    and three.get("deadlineExhausted") is False
    and math.isclose(sum(three_calls), 3.0, abs_tol=0.005),
    {"timeouts": three_calls, "receipt": three},
)


visible_calls = []


def visible_call(_payload, timeout=180):
    visible_calls.append(timeout)
    return response("cut" if len(visible_calls) == 1 else "complete visible", "length" if len(visible_calls) == 1 else "stop")


visible = server.run_ollama_generate(
    "visible truncation test",
    timeout=3,
    api_call_fn=visible_call,
    allow_final_retry=True,
)
check(
    "visible-truncation-retry-uses-only-the-residual-allocation",
    visible.get("text") == "complete visible"
    and visible.get("attemptCount") == 2
    and visible.get("finalRetryReason") == "truncated-visible"
    and math.isclose(sum(visible_calls), 3.0, abs_tol=0.005),
    {"timeouts": visible_calls, "receipt": visible},
)


bad_counts = server.run_ollama_generate(
    "bad count metadata",
    timeout=1,
    api_call_fn=lambda _payload, timeout=1: {
        "response": "bounded",
        "done_reason": "stop",
        "eval_count": "bad",
        "prompt_eval_count": object(),
        "total_duration": "bad",
    },
)
malformed = server.run_ollama_generate(
    "malformed response",
    timeout=1,
    api_call_fn=lambda _payload, timeout=1: ["not", "an", "object"],
)
check(
    "malformed-response-and-numeric-metadata-fail-closed-without-crashing",
    bad_counts.get("text") == "bounded"
    and bad_counts.get("evalCount") == 0
    and bad_counts.get("promptEvalCount") == 0
    and bad_counts.get("ollamaTotalDurationMs") == 0
    and malformed.get("attemptCount") == 1
    and "not a JSON object" in str(malformed.get("error") or "")
    and (malformed.get("attemptReceipts") or [{}])[0].get("errorClass")
    == "JSONDecodeError",
    {"badCounts": bad_counts, "malformed": malformed},
)


timed_out = server.run_ollama_generate(
    "api timeout",
    timeout=1,
    api_call_fn=lambda _payload, timeout=1: (_ for _ in ()).throw(TimeoutError("synthetic deadline")),
    allow_final_retry=True,
)
check(
    "api-timeout-does-not-start-a-retry-fanout",
    timed_out.get("attemptCount") == 1
    and "synthetic deadline" in str(timed_out.get("error") or "")
    and (timed_out.get("attemptReceipts") or [{}])[0].get("errorClass")
    == "TimeoutError",
    timed_out,
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


expired_clock = FakeClock()
expired_calls = []


def expired_call(_payload, timeout=180):
    expired_calls.append(timeout)
    expired_clock.value = 3.1
    return response("", "length", thinking="hidden")


expired = server.run_ollama_generate(
    "expire before retry",
    timeout=3,
    api_call_fn=expired_call,
    allow_final_retry=True,
    clock_fn=expired_clock,
)
check(
    "expired-before-retry-preserves-first-attempt-metadata-without-clean-stop",
    len(expired_calls) == 1
    and expired.get("attemptCount") == 1
    and expired.get("deadlineExhausted") is True
    and expired.get("doneReason") == "length"
    and not expired.get("text")
    and "budget was exhausted" in str(expired.get("error") or ""),
    expired,
)


original_cancel = server.live_run_cancelled
cancel_checks = {"count": 0}


def cancel_after_call(_run_id):
    cancel_checks["count"] += 1
    return cancel_checks["count"] >= 2


try:
    server.live_run_cancelled = cancel_after_call
    cancelled = server.run_ollama_generate(
        "cancel test",
        timeout=2,
        api_call_fn=lambda _payload, timeout=2: response("do not publish", "stop"),
    )
finally:
    server.live_run_cancelled = original_cancel
check(
    "cancellation-is-distinct-from-deadline-exhaustion",
    cancelled.get("cancelled") is True
    and cancelled.get("deadlineExhausted") is False
    and (cancelled.get("attemptReceipts") or [{}])[0].get("errorClass")
    == "cancelled",
    cancelled,
)


run_a = "p189-context-a"
server.RUN_REQUEST_CONTEXT.run_id = run_a
server.establish_model_stage_budget(run_a, 10)
context_a = server.current_model_stage_context()
missing_context = server.call_with_request_run_context(
    "p189-context-missing-b",
    server.current_model_stage_context,
)
restored_context = server.current_model_stage_context()
propagated_context = server.call_with_request_run_context(
    run_a,
    server.current_model_stage_context,
)
server.release_model_stage_budget(run_a)
server.RUN_REQUEST_CONTEXT.run_id = ""
outside_context = server.current_model_stage_context()
check(
    "worker-context-propagates-matching-deadline-without-cross-run-or-stale-leak",
    bool(context_a)
    and propagated_context.get("deadlineMonotonic") == context_a.get("deadlineMonotonic")
    and missing_context == {}
    and restored_context.get("deadlineMonotonic") == context_a.get("deadlineMonotonic")
    and outside_context == {},
    {
        "contextA": context_a,
        "propagated": propagated_context,
        "missing": missing_context,
        "outside": outside_context,
    },
)


ordinary_messages = [{"role": "user", "text": "Explain why checksums catch accidental corruption."}]
ordinary_route = server.route_manager(
    ordinary_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
ordinary_decision = server.manager_auto_deep_review_decision(
    ordinary_messages,
    ordinary_route,
    "balanced",
    "manager",
)
ordinary_depth = ordinary_decision.get("effectiveDepth") or "balanced"
ordinary_run = "p189-ordinary-budget"
server.RUN_REQUEST_CONTEXT.run_id = ordinary_run
server.register_model_stage_budget(ordinary_run, 180)
server.update_model_stage_budget(
    ordinary_run,
    server.model_stage_budget_seconds_for_request("manager", ordinary_depth),
)
ordinary_budget = server.current_model_stage_context()
server.release_model_stage_budget(ordinary_run)

deep_messages = [
    {
        "role": "user",
        "text": (
            "Go deep and compare a single-writer append-only journal with periodic full-state snapshots "
            "for crash recovery, recommend one, and explain when you would reverse the choice."
        ),
    }
]
deep_route = server.route_manager(
    deep_messages,
    cwd=str(ROOT),
    requested_profile="manager",
    web_search="disabled",
)
deep_decision = server.manager_auto_deep_review_decision(
    deep_messages,
    deep_route,
    "balanced",
    "manager",
)
deep_depth = deep_decision.get("effectiveDepth") or "balanced"
deep_run = "p189-auto-deep-budget"
server.RUN_REQUEST_CONTEXT.run_id = deep_run
server.register_model_stage_budget(deep_run, 180)
server.update_model_stage_budget(
    deep_run,
    server.model_stage_budget_seconds_for_request("manager", deep_depth),
)
deep_budget = server.current_model_stage_context()
server.release_model_stage_budget(deep_run)
missing_run = "p189-missing-context-update"
server.RUN_REQUEST_CONTEXT.run_id = missing_run
missing_updated = server.update_model_stage_budget(missing_run, 180)
missing_context = server.current_model_stage_context()
server.release_model_stage_budget(missing_run)
server.RUN_REQUEST_CONTEXT.run_id = ""
check(
    "effective-auto-deep-depth-selects-budget-before-first-model-without-consuming-routing-time",
    ordinary_decision.get("escalated") is not True
    and ordinary_budget.get("requestedBudgetSeconds") == 180
    and ordinary_budget.get("activated") is False
    and deep_decision.get("escalated") is True
    and deep_depth == "full"
    and deep_budget.get("requestedBudgetSeconds") == 240
    and deep_budget.get("activated") is False
    and missing_updated.get("requestedBudgetSeconds") == 180
    and missing_context.get("activated") is False,
    {
        "ordinaryDecision": ordinary_decision,
        "ordinaryBudget": ordinary_budget,
        "deepDecision": deep_decision,
        "deepBudget": deep_budget,
        "missingContext": missing_context,
    },
)


fanout_run = "p189-parent-fanout"
server.RUN_REQUEST_CONTEXT.run_id = fanout_run
server.establish_model_stage_budget(fanout_run, 10)
stage_calls = []
original_review = server.run_local_review
original_polish = server.run_manager_polish
original_coach = server.run_quality_coach


def synthetic_review(*_args, **_kwargs):
    stage_calls.append("review")
    server.RUN_REQUEST_CONTEXT.model_stage_deadline_monotonic = time.monotonic() - 0.01
    with server.MODEL_STAGE_CONTEXTS_LOCK:
        server.MODEL_STAGE_CONTEXTS[fanout_run]["deadlineMonotonic"] = time.monotonic() - 0.01
    return {"text": "review note"}


def should_not_polish(*_args, **_kwargs):
    stage_calls.append("polish")
    return {"text": "wrong replacement"}


def should_not_coach(*_args, **_kwargs):
    stage_calls.append("coach")
    return {"text": "wrong replacement", "coached": True}


try:
    server.run_local_review = synthetic_review
    server.run_manager_polish = should_not_polish
    server.run_quality_coach = should_not_coach
    fanout = server.run_manager_review_and_polish(
        [{"role": "user", "text": "Compare two stable designs."}],
        {"capabilityPlan": {"registered": False}},
        "Best verified primary candidate.",
        manager_depth="balanced",
    )
finally:
    server.run_local_review = original_review
    server.run_manager_polish = original_polish
    server.run_quality_coach = original_coach
    server.release_model_stage_budget(fanout_run)
    server.RUN_REQUEST_CONTEXT.run_id = ""
check(
    "expired-parent-budget-stops-polish-and-coach-and-retains-best-prior-candidate",
    stage_calls == ["review"]
    and fanout.get("text") == "Best verified primary candidate."
    and fanout.get("budgetExhausted") is True,
    {"calls": stage_calls, "result": fanout},
)


telemetry_run = "p189-two-call-telemetry"
server.RUN_REQUEST_CONTEXT.run_id = telemetry_run
server.establish_model_stage_budget(telemetry_run, 10)
failed_primary = server.run_ollama_generate(
    "FAILED_PRIMARY_CONTENT_SENTINEL",
    model="synthetic-primary",
    timeout=2,
    api_call_fn=lambda _payload, timeout=2: (_ for _ in ()).throw(
        TimeoutError("primary unavailable")
    ),
    allow_final_retry=False,
)
residency_calls = []


def synthetic_residency(model, timeout=0.25):
    residency_calls.append((model, timeout))
    loaded = len(residency_calls) >= 2
    return {
        "observed": True,
        "selectedModelLoaded": loaded,
        "selectedModelDigest": "sha256:fallback-digest" if loaded else "",
        "loadedModels": [model] if loaded else [],
    }


successful_fallback = server.run_ollama_generate(
    "SUCCESSFUL_FALLBACK_CONTENT_SENTINEL",
    model="synthetic-fallback",
    timeout=2,
    api_call_fn=lambda _payload, timeout=2: response("fallback answer", "stop"),
    residency_fn=synthetic_residency,
    allow_final_retry=False,
)
stage_telemetry = server.model_stage_budget_receipt()
server.release_model_stage_budget(telemetry_run)
server.RUN_REQUEST_CONTEXT.run_id = ""
stage_rows = stage_telemetry.get("generationReceipts") or []
check(
    "failed-primary-and-successful-fallback-both-remain-visible-in-run-telemetry",
    failed_primary.get("attemptCount") == 1
    and successful_fallback.get("text") == "fallback answer"
    and stage_telemetry.get("generationCount") == 2
    and stage_telemetry.get("attemptCount") == 2
    and stage_telemetry.get("models") == ["synthetic-primary", "synthetic-fallback"]
    and len(stage_rows) == 2
    and (stage_rows[0].get("attempts") or [{}])[0].get("errorClass")
    == "TimeoutError"
    and stage_rows[1].get("doneReason") == "stop"
    and all(row.get("contentsRecorded") is False for row in stage_rows),
    stage_telemetry,
)
check(
    "residency-before-after-digest-and-duration-telemetry-propagates",
    len(residency_calls) == 2
    and (stage_rows[1].get("residencyBefore") or {}).get("selectedModelLoaded")
    is False
    and (stage_rows[1].get("residencyAfter") or {}).get("selectedModelLoaded")
    is True
    and (stage_rows[1].get("residencyAfter") or {}).get("selectedModelDigest")
    == "sha256:fallback-digest"
    and stage_telemetry.get("ollamaTotalDurationMs") == 13
    and stage_telemetry.get("ollamaLoadDurationMs") == 2,
    stage_telemetry,
)


server_source = (ROOT / "server.py").read_text(encoding="utf-8")
review_surface = server_source.split(
    "if effective_profile in LOCAL_REVIEW_PROFILES:", 1
)[1].split("if effective_profile in LOCAL_RESEARCH_PROFILES:", 1)[0]
research_surface = server_source.split(
    "if effective_profile in LOCAL_RESEARCH_PROFILES:", 1
)[1].split("if effective_profile in RESEARCH_APPLY_PROFILES:", 1)[0]
apply_surface = server_source.split(
    "if effective_profile in RESEARCH_APPLY_PROFILES:", 1
)[1].split("if effective_profile in CLOUD_PROFILES:", 1)[0]
exception_surface = server_source.split("except Exception as exc:\n            try:", 1)[-1]
check(
    "all-model-backed-early-terminal-surfaces-emit-the-shared-timing-receipt",
    review_surface.count("model_done_timing_fields(") >= 2
    and "review_worker_duration_ms" in review_surface
    and research_surface.count("model_done_timing_fields(") >= 2
    and "research_worker_duration_ms" in research_surface
    and apply_surface.count("model_done_timing_fields(") >= 2
    and "research_apply_worker_duration_ms" in apply_surface
    and exception_surface.count("model_done_timing_fields(") >= 3,
    {
        "review": review_surface.count("model_done_timing_fields("),
        "research": research_surface.count("model_done_timing_fields("),
        "researchApply": apply_surface.count("model_done_timing_fields("),
        "exception": exception_surface.count("model_done_timing_fields("),
    },
)


timing = server.model_path_timing_receipt(
    50,
    2,
    20,
    route={
        "_primaryGenerationReceipt": {
            "model": "synthetic-local",
            "attemptCount": clean.get("attemptCount"),
            "requestedBudgetMs": clean.get("requestedBudgetMs"),
            "effectiveBudgetMs": clean.get("effectiveBudgetMs"),
            "elapsedMs": clean.get("elapsedMs"),
            "doneReason": clean.get("doneReason"),
            "ollamaTotalDurationMs": clean.get("ollamaTotalDurationMs"),
            "ollamaLoadDurationMs": clean.get("ollamaLoadDurationMs"),
            "ollamaPromptEvalDurationMs": clean.get("ollamaPromptEvalDurationMs"),
            "ollamaEvalDurationMs": clean.get("ollamaEvalDurationMs"),
        }
    },
)
serialized_receipts = json.dumps(
    {
        "cleanAttempts": clean.get("attemptReceipts") or [],
        "hiddenAttempts": hidden.get("attemptReceipts") or [],
        "threeAttempts": three.get("attemptReceipts") or [],
        "timing": timing,
        "stage": stage_telemetry,
    },
    default=str,
)
check(
    "timing-provenance-surfaces-all-phases-without-prompt-response-or-thinking-content",
    (timing.get("primaryGeneration") or {}).get("attemptCount") == 1
    and (timing.get("primaryGeneration") or {}).get("ollamaLoadDurationMs") == 2
    and (timing.get("primaryGeneration") or {}).get("ollamaPromptEvalDurationMs") == 3
    and (timing.get("primaryGeneration") or {}).get("ollamaEvalDurationMs") == 5
    and "P189_SENTINEL_PROMPT" not in serialized_receipts
    and "P189_HIDDEN_SENTINEL" not in serialized_receipts
    and "visible answer" not in serialized_receipts
    and "FAILED_PRIMARY_CONTENT_SENTINEL" not in serialized_receipts
    and "SUCCESSFUL_FALLBACK_CONTENT_SENTINEL" not in serialized_receipts
    and "fallback answer" not in serialized_receipts,
    timing,
)


report = {
    "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
    "checkCount": len(checks),
    "passed": sum(item["status"] == "pass" for item in checks),
    "failed": sum(item["status"] == "fail" for item in checks),
    "checks": checks,
}
print(json.dumps(report, indent=2, default=str))
raise SystemExit(0 if report["status"] == "pass" else 1)
