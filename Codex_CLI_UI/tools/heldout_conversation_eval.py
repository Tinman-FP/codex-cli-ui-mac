#!/usr/bin/env python3
"""Evaluate private, held-out conversation prompts without retaining their text.

The input belongs outside the repository and may be supplied through stdin. Reports
contain scenario labels and aggregate checks only: never prompts, answers, messages,
or source-thread identifiers. This keeps real user history useful as an acceptance
test without turning it into a response lookup table.
"""

import argparse
import hashlib
import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_SERVER = "http://127.0.0.1:8766"
DEFAULT_TIMEOUT = 180
BAD_RESPONSE_TERMS = (
    "load failed",
    "no final message returned",
    "no response",
    "run failed",
)
SCRIPTED_FRAME_TERMS = (
    "this is why:",
    "you should also consider:",
)


def read_cases(path):
    source = sys.stdin if path == "-" else Path(path).expanduser().open(encoding="utf-8")
    try:
        data = json.load(source)
    finally:
        if source is not sys.stdin:
            source.close()
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("private evaluation input needs a non-empty cases array")
    return cases


def post_json_stream(server_url, payload, timeout):
    request = urllib.request.Request(
        server_url.rstrip("/") + "/api/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            if raw.strip():
                yield json.loads(raw.decode("utf-8"))


def normalized_messages(case):
    messages = case.get("messages") if isinstance(case, dict) else None
    if not isinstance(messages, list) or not messages:
        raise ValueError("each private evaluation case needs conversation messages")
    clean = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        text = str(message.get("text") or "").strip()
        if role in {"user", "assistant"} and text:
            clean.append({"role": role, "text": text})
    if not clean or clean[-1]["role"] != "user":
        raise ValueError("each private evaluation case must end with a user message")
    return clean


def case_fingerprint(messages):
    material = json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def required_terms(value):
    return [str(item).strip().lower() for item in value or [] if str(item).strip()]


def evaluate(case, answer, route, return_code, warnings):
    expectation = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    text = str(answer or "").strip()
    lower = text.lower()
    failures = []
    required_all = required_terms(expectation.get("requiredAll"))
    required_any = required_terms(expectation.get("requiredAny"))
    forbidden = required_terms(expectation.get("forbidden"))
    if not text:
        failures.append("missing-answer")
    if return_code not in {0, None}:
        failures.append("nonzero-return")
    if any(term in lower for term in BAD_RESPONSE_TERMS):
        failures.append("runtime-fallback")
    if expectation.get("naturalConversation") and any(term in lower for term in SCRIPTED_FRAME_TERMS):
        failures.append("scripted-frame")
    if expectation.get("noCannedOpening") and lower.startswith(("certainly", "of course", "absolutely", "great question", "happy to help")):
        failures.append("canned-opening")
    if required_all and any(term not in lower for term in required_all):
        failures.append("missing-required-content")
    if required_any and not any(term in lower for term in required_any):
        failures.append("missing-required-alternative")
    if any(term in lower for term in forbidden):
        failures.append("forbidden-content")
    expected_project = str(expectation.get("projectId") or "").strip()
    if expected_project and route.get("projectId") != expected_project:
        failures.append("route-project-mismatch")
    expected_objective = str(expectation.get("objectiveType") or "").strip()
    objective = (route.get("objectivePlan") or {}).get("objectiveType")
    if expected_objective and objective != expected_objective:
        failures.append("route-objective-mismatch")
    if expectation.get("sourceExpected") and not ("http://" in lower or "https://" in lower):
        failures.append("missing-source-boundary")
    if expectation.get("minWords") and len(text.split()) < int(expectation["minWords"]):
        failures.append("too-brief")
    if expectation.get("maxWords") and len(text.split()) > int(expectation["maxWords"]):
        failures.append("too-verbose")
    if warnings:
        failures.append("run-warning")
    return failures


def run_case(server_url, case, timeout):
    messages = normalized_messages(case)
    expectation = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    payload = {
        "profile": expectation.get("profile") or "manager",
        "cwd": expectation.get("cwd") or str(Path(__file__).resolve().parents[1]),
        "accessLevel": "danger-full-access",
        "reasoningLevel": expectation.get("reasoningLevel") or "medium",
        "managerDepth": expectation.get("managerDepth") or "fast",
        "friendlinessLevel": "warm",
        "humorLevel": "light",
        "webSearch": expectation.get("webSearch") or "live",
        "testRun": True,
        "runId": f"heldout-{uuid.uuid4()}",
        "messages": messages,
    }
    answer = ""
    route = {}
    warnings = []
    return_code = None
    started = time.time()
    try:
        for event in post_json_stream(server_url, payload, timeout):
            event_type = event.get("type")
            if event_type == "status":
                route = event.get("route") or route
            elif event_type == "assistant":
                answer = event.get("text") or ""
            elif event_type in {"warning", "error"}:
                warnings.append(str(event.get("text") or event_type))
            elif event_type == "done":
                return_code = event.get("returnCode")
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
        warnings.append(type(exc).__name__)
    failures = evaluate(case, answer, route, return_code, warnings)
    return {
        "scenario": str(case.get("scenario") or "unspecified")[:80],
        "caseFingerprint": case_fingerprint(messages),
        "passed": not failures,
        "failures": failures,
        "durationMs": int((time.time() - started) * 1000),
        "answerWordCount": len(answer.split()),
        "route": {
            "projectId": route.get("projectId") or "",
            "engine": route.get("engine") or "",
            "objectiveType": (route.get("objectivePlan") or {}).get("objectiveType") or "",
        },
        "warningCount": len(warnings),
    }


def main():
    parser = argparse.ArgumentParser(description="Run a non-persistent held-out conversation evaluation.")
    parser.add_argument("--input", default="-", help="Private JSON case input; use - for stdin.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--output", help="Optional report path. The report never includes prompt or answer text.")
    args = parser.parse_args()
    cases = read_cases(args.input)
    results = [run_case(args.server, case, max(1, args.timeout)) for case in cases]
    failed = [result for result in results if not result["passed"]]
    report = {
        "suite": "private-heldout-conversation-eval",
        "privacy": "prompts and answers are processed in memory and omitted from this report",
        "caseCount": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "status": "pass" if not failed else "fail",
        "results": results,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).expanduser().write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
