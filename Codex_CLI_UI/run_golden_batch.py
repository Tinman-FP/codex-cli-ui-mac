#!/usr/bin/env python3
import argparse
import json
import random
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULT_DIR = DATA_DIR / "golden_batch_results"
DEFAULT_SERVER = "http://127.0.0.1:8765"
SERVER_STDOUT_LOG = APP_DIR / "logs" / "golden-batch-server.out.log"
SERVER_STDERR_LOG = APP_DIR / "logs" / "golden-batch-server.err.log"

WEB_TEST_TERMS = (
    "amazon.com",
    "http://",
    "https://",
    "web",
    "website",
    "search",
    "look up",
    "lookup",
    "find online",
    "latest",
    "current",
    "today",
    "price",
    "pricing",
    "availability",
    "available",
    "in stock",
    "source",
    "manual",
    "datasheet",
)


def raise_timeout(signum, frame):
    raise TimeoutError("golden test exceeded wall-clock timeout")

SAFE_SKIP_TERMS = (
    "api key",
    "apple id",
    "attached",
    "authenticator",
    "credential",
    "delete",
    "deploy",
    "download",
    "ebb",
    "github",
    "humidity",
    "image",
    "install",
    "ip address",
    "iphone",
    "log into",
    "moonraker",
    "nozzle temp",
    "password",
    "photo",
    "pic",
    "production",
    "qidi",
    "restart",
    "see photo",
    "see photos",
    "ssh",
    "sudo",
    "tailscale",
    "token",
    "upload",
    "vpn",
)

SAFE_SKIP_PROJECTS = {
    "flightops-tracker",
    "printer-klipper-ops",
    "mac-system-accounts",
}


def load_json_url(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def can_autostart_server(server):
    return server.rstrip("/") in {
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    }


def ensure_local_server(server, startup_timeout=20):
    try:
        return load_json_url(f"{server}/api/test-bench", timeout=3)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        if not can_autostart_server(server):
            raise

    SERVER_STDOUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    stdout = SERVER_STDOUT_LOG.open("ab")
    stderr = SERVER_STDERR_LOG.open("ab")
    subprocess.Popen(
        [sys.executable, str(APP_DIR / "server.py")],
        cwd=str(APP_DIR),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    deadline = time.time() + startup_timeout
    last_error = None
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            return load_json_url(f"{server}/api/test-bench", timeout=3)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
    raise RuntimeError(f"local Codex CLI UI server did not start within {startup_timeout}s: {last_error}")


def post_json_stream(url, payload, timeout=240):
    deadline = time.time() + max(1, timeout)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            if time.time() > deadline:
                raise TimeoutError(f"/api/run exceeded {timeout}s wall-clock timeout")
            if not raw.strip():
                continue
            yield json.loads(raw.decode("utf-8"))


def test_messages(test):
    messages = test.get("messages")
    if isinstance(messages, list) and messages:
        return messages
    return [{"role": "user", "text": test.get("prompt", "")}]


def prompt_text(test):
    return "\n".join(str(message.get("text", "")) for message in test_messages(test)).lower()


def text_has_any(text, terms):
    return any(term in text for term in terms)


CONTEXT_RECOVERY_TERMS = (
    "context",
    "more detail",
    "specific",
    "which",
    "what task",
    "earlier",
    "not sure",
    "project",
    "active project",
    "last run",
    "last result",
    "target",
    "board",
    "connector",
    "pin numbers",
    "exact pins",
    "refers to",
    "previous plan",
    "previous result",
    "warning text",
    "source of truth",
)


def test_web_search_mode(test):
    explicit = test.get("webSearch")
    text = prompt_text(test)
    if explicit and explicit != "disabled":
        return explicit
    if explicit == "disabled":
        return explicit
    return "live" if text_has_any(text, WEB_TEST_TERMS) else "disabled"


def is_slicer_plate_prompt(text):
    stripped = str(text or "").lstrip()
    if stripped.startswith("{") and "klippy_connected" in stripped and "moonraker" in stripped:
        return False
    if text_has_any(text, ("endplate", "endplates", "end plates", "buckets", "bucket")) and text_has_any(
        text,
        ("airflow", "aero", "aerodynamic", "turbine"),
    ):
        return False
    return (
        text_has_any(text, ("plate", "plates", "build plate", "add a plate", "add plate", "plate to plate", "p0", "p1"))
        and text_has_any(text, ("print", "printing", "arrange", "move", "model", "models", "file", "files", "tabs"))
    )


def answer_has_wrong_cpap_template(prompt, answer):
    if text_has_any(prompt, ("cpap", "cooling duct", "part cooling", "toolhead", "hotend", "nozzle")):
        return False
    if text_has_any(prompt, ("fusion", "fusion 360")) and text_has_any(prompt, ("script", "python")):
        return text_has_any(
            answer,
            (
                "first-pass cpap",
                "cpap cooling duct",
                "cpap part-cooling",
                "18 mm cpap inlet",
                "nozzle target",
                "toolhead envelope",
            ),
        )
    return text_has_any(
        answer,
        (
            "first-pass cpap",
            "cpap cooling duct",
            "cpap part-cooling",
            "18 mm cpap inlet",
            "openscad model",
            "fusion 360 script",
            "nozzle target",
            "toolhead envelope",
        ),
    )


def answer_has_wrong_structural_template(prompt, answer):
    if text_has_any(prompt, ("fea", "fem", "finite element", "stress", "strain", "deflection", "structural", "cad", "stl", "step", "geometry")):
        return False
    return text_has_any(
        answer,
        (
            "structural fea",
            "mechanical/structural preflight",
            "calculix",
            "seed fallback",
            "real calculix deck",
            "real mesh",
            "fea report",
            "structural_fea",
        ),
    )


def terse_answer_requested(prompt):
    return text_has_any(
        prompt,
        (
            "one short sentence",
            "in one sentence",
            "single sentence",
            "just answer",
            "answer only",
            "no explanation",
            "short answer",
        ),
    )


def is_safe_test(test, include_live=False):
    if include_live:
        return True, ""
    if test.get("webSearch") == "live" or test.get("requiresSource"):
        return False, "live web/source test"
    project = str(test.get("expectedProjectId") or "")
    if project in SAFE_SKIP_PROJECTS:
        return False, f"skipped project {project}"
    text = prompt_text(test)
    for term in SAFE_SKIP_TERMS:
        if term in text:
            return False, f"skip term {term}"
    return True, ""


def select_tests(tests, args):
    if args.ids:
        wanted = [item.strip() for item in args.ids.split(",") if item.strip()]
        by_id = {item.get("id"): item for item in tests}
        selected = [by_id[item_id] for item_id in wanted if item_id in by_id]
        missing = [item_id for item_id in wanted if item_id not in by_id]
        if missing:
            print("Missing test ids: " + ", ".join(missing), file=sys.stderr)
        return selected

    candidates = []
    skipped = []
    for test in tests:
        if args.group and test.get("group") != args.group:
            continue
        if args.source and test.get("source") != args.source:
            continue
        ok, reason = is_safe_test(test, include_live=args.include_live)
        if not ok:
            skipped.append({"id": test.get("id"), "reason": reason})
            continue
        candidates.append(test)
    if args.shuffle:
        random.Random(args.seed).shuffle(candidates)
    if args.offset:
        candidates = candidates[args.offset :]
    if args.limit:
        candidates = candidates[: args.limit]
    return candidates


def run_test(server, test, args):
    payload = {
        "profile": test.get("profile") or "manager",
        "cwd": args.cwd,
        "accessLevel": "danger-full-access",
        "reasoningLevel": test.get("reasoningLevel") or "medium",
        "managerDepth": test.get("managerDepth") or "fast",
        "friendlinessLevel": args.friendliness,
        "humorLevel": args.humor,
        "webSearch": test_web_search_mode(test),
        "testRun": True,
        "messages": test_messages(test),
    }
    started = time.time()
    run = {
        "route": {},
        "answer": "",
        "analyticalCore": {},
        "taskContract": {},
        "contractGate": {},
        "scorecard": {},
        "returnCode": None,
        "thoughts": [],
        "warnings": [],
        "durationMs": 0,
    }
    previous_alarm_handler = None
    alarm_active = False
    try:
        if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
            previous_alarm_handler = signal.signal(signal.SIGALRM, raise_timeout)
            signal.setitimer(signal.ITIMER_REAL, max(1, args.timeout))
            alarm_active = True
        for event in post_json_stream(f"{server}/api/run", payload, timeout=args.timeout):
            event_type = event.get("type")
            if event_type == "status":
                run["route"] = event.get("route") or run["route"]
            elif event_type == "assistant":
                run["answer"] = event.get("text") or ""
                run["analyticalCore"] = event.get("analyticalCore") or {}
                run["taskContract"] = event.get("taskContract") or {}
                run["contractGate"] = event.get("contractGate") or {}
                run["scorecard"] = event.get("scorecard") or {}
            elif event_type == "thought":
                run["thoughts"].append(event.get("text") or "")
            elif event_type in {"warning", "error"}:
                run["warnings"].append(event.get("text") or event_type)
            elif event_type == "done":
                run["returnCode"] = event.get("returnCode")
    except Exception as exc:
        run["warnings"].append(f"run interrupted: {type(exc).__name__}: {exc}")
    finally:
        if alarm_active:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if previous_alarm_handler is not None:
                signal.signal(signal.SIGALRM, previous_alarm_handler)
    run["durationMs"] = int((time.time() - started) * 1000)
    return run


def evaluate_test(test, run):
    answer = str(run.get("answer") or "").strip()
    lower = answer.lower()
    prompt_lower = prompt_text(test)
    route = run.get("route") or {}
    task_contract = run.get("taskContract") or {}
    contract_gate = run.get("contractGate") or {}
    scorecard = run.get("scorecard") or {}
    checks = []

    def add(label, passed, detail=""):
        checks.append({"label": label, "passed": bool(passed), "detail": detail})

    add(
        "answered",
        bool(answer) and not re.search(r"no final message returned|returned no answer|run failed", lower),
        "final text returned" if answer else "no final text",
    )
    if test.get("maxDurationMs"):
        duration = int(run.get("durationMs") or 0)
        limit = int(test.get("maxDurationMs") or 0)
        add(
            "duration",
            duration <= limit,
            f"expected <= {limit}ms; got {duration}ms",
        )
    if test.get("contextDependent"):
        expected_context_terms = [term.lower() for term in (test.get("anyTerms") or [])]
        matched_expected_context = any(term in lower for term in expected_context_terms)
        add(
            "context",
            matched_expected_context
            or text_has_any(lower, CONTEXT_RECOVERY_TERMS),
            "context-only follow-up should ask for or recover missing context, or satisfy its explicit expected context terms",
        )
    if is_slicer_plate_prompt(prompt_lower):
        add(
            "slicer-plate",
            route.get("projectId") in {"tinmanx-slicer-research", "orcaslicer-codex", "codex-cli-ui-local-agent"},
            f"plate workflow route got {route.get('projectId') or 'none'}",
        )
        add(
            "no-wrong-template",
            not answer_has_wrong_cpap_template(prompt_lower, lower),
            "slicer plate workflow must not return CPAP/CAD artifact template",
        )
    else:
        add(
            "no-wrong-template",
            not answer_has_wrong_cpap_template(prompt_lower, lower) and not answer_has_wrong_structural_template(prompt_lower, lower),
            "prompt must not return an unrelated CPAP/CAD/FEA artifact template",
        )
    if terse_answer_requested(prompt_lower):
        sentence_count = len(re.findall(r"[.!?](?:\s|$)", answer))
        add(
            "terse",
            sentence_count <= 1 and len(answer.split()) <= 24,
            f"expected one short sentence; got {sentence_count} sentence markers and {len(answer.split())} words",
        )
    context_safe_route = bool(test.get("contextDependent")) and route.get("projectId") == "general"
    if test.get("expectedProjectId") and not context_safe_route:
        add(
            "route",
            route.get("projectId") == test["expectedProjectId"],
            f"expected {test['expectedProjectId']}; got {route.get('projectId') or 'none'}",
        )
    if test.get("expectedEngine"):
        add(
            "engine",
            route.get("engine") == test["expectedEngine"],
            f"expected {test['expectedEngine']}; got {route.get('engine') or 'none'}",
        )
    if test.get("directAnswer"):
        first = lower[:280]
        terms = test.get("directTerms") or []
        add(
            "direct",
            any(term.lower() in first for term in terms) if terms else bool(first),
            "direct-first language",
        )
    if test.get("requiredTerms"):
        missing = [term for term in test["requiredTerms"] if term.lower() not in lower]
        add("required", not missing, "missing: " + ", ".join(missing) if missing else "required terms found")
    if test.get("anyTerms"):
        matched = [term for term in test["anyTerms"] if term.lower() in lower]
        fallback_context = bool(test.get("contextDependent")) and text_has_any(lower, CONTEXT_RECOVERY_TERMS)
        add(
            "context",
            bool(matched) or fallback_context,
            "matched: " + ", ".join(matched)
            if matched
            else ("matched context recovery wording" if fallback_context else "no anyTerms matched"),
        )
    if test.get("forbiddenTerms"):
        found = [term for term in test["forbiddenTerms"] if term.lower() in lower]
        add("grounded", not found, "found: " + ", ".join(found) if found else "no forbidden terms found")
    if test.get("requiresSource"):
        required_proof = task_contract.get("requiredProof") or []
        source_contract = task_contract.get("kind") == "Research" or any("source" in str(item).lower() for item in required_proof)
        has_source = "http://" in lower or "https://" in lower or "sources checked" in lower
        add("source", has_source or not source_contract, "source expected" if source_contract else "source waived by non-research contract")
    if test.get("minAnalyticalScore"):
        score = float((run.get("analyticalCore") or {}).get("score") or 0)
        add("analytical", score >= float(test["minAnalyticalScore"]), f"score {score}")
    expected_contract_kind = test.get("expectedContractKind") or test.get("taskContractKind")
    if expected_contract_kind:
        add(
            "contract-kind",
            task_contract.get("kind") == expected_contract_kind,
            f"expected {expected_contract_kind}; got {task_contract.get('kind') or 'none'}",
        )
    if test.get("expectedContractGate"):
        add(
            "contract-gate",
            contract_gate.get("status") == test["expectedContractGate"],
            f"expected {test['expectedContractGate']}; got {contract_gate.get('status') or 'none'}",
        )
    internal_gate_status = (
        contract_gate.get("status")
        or task_contract.get("gateStatus")
        or ((scorecard.get("contractGate") or {}).get("status") if isinstance(scorecard.get("contractGate"), dict) else "")
    )
    if internal_gate_status:
        expected_gate = test.get("expectedContractGate")
        add(
            "internal-contract-gate",
            internal_gate_status == "pass" or (expected_gate and internal_gate_status == expected_gate),
            f"contract gate {internal_gate_status}",
        )
    scorecard_status = scorecard.get("status")
    if scorecard_status:
        expected_gate = test.get("expectedContractGate")
        add(
            "scorecard-status",
            scorecard_status == "pass" or (expected_gate == "block" and scorecard_status in {"review", "block"}),
            f"scorecard {scorecard_status}",
        )
    scorecard_checks = scorecard.get("checks") if isinstance(scorecard, dict) else None
    if isinstance(scorecard_checks, list) and scorecard_checks:
        failed_scorecard = [
            str(item.get("label") or "unnamed")
            for item in scorecard_checks
            if isinstance(item, dict) and not item.get("passed")
        ]
        if test.get("expectedContractGate") == "block":
            failed_scorecard = [
                label
                for label in failed_scorecard
                if label != "Analytical fit" and not label.startswith("Contract:")
            ]
        add(
            "scorecard-checks",
            not failed_scorecard,
            "failed: " + ", ".join(failed_scorecard[:5]) if failed_scorecard else "all scorecard checks passed",
        )
    if test.get("requiredContractProof"):
        proof_text = " ".join(str(item) for item in (task_contract.get("requiredProof") or [])).lower()
        missing = [term for term in test["requiredContractProof"] if term.lower() not in proof_text]
        add("contract-proof", not missing, "missing: " + ", ".join(missing) if missing else "contract proof terms found")
    if test.get("minScorecard"):
        score = float(scorecard.get("score") or 0)
        add("scorecard", score >= float(test["minScorecard"]), f"score {score}")
    return checks


def main():
    parser = argparse.ArgumentParser(description="Run Codex CLI UI golden tests through /api/run.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--offset", type=int, default=0, help="Skip this many matching safe tests before applying --limit.")
    parser.add_argument("--group", default="Slow")
    parser.add_argument("--source", default="history-harvest")
    parser.add_argument("--ids", default="")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle matching safe tests before applying --offset/--limit.")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic shuffle seed.")
    parser.add_argument("--include-live", action="store_true", help="Allow live web/source and risky project tests.")
    parser.add_argument("--cwd", default=str(Path.home() / "Documents/Codex"))
    parser.add_argument("--friendliness", default="warm")
    parser.add_argument("--humor", default="light")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--no-fail-exit", action="store_true")
    args = parser.parse_args()

    bench = ensure_local_server(args.server)
    tests = bench.get("tests") or []
    selected = select_tests(tests, args)
    started = time.time()
    results = []

    for index, test in enumerate(selected, 1):
        run = run_test(args.server, test, args)
        checks = evaluate_test(test, run)
        status = "pass" if all(check["passed"] for check in checks) else "fail"
        record = {
            "id": test.get("id"),
            "name": test.get("name"),
            "group": test.get("group"),
            "source": test.get("source"),
            "status": status,
            "checks": checks,
            "durationMs": run.get("durationMs"),
            "route": run.get("route"),
            "analyticalCore": run.get("analyticalCore"),
            "taskContract": run.get("taskContract"),
            "contractGate": run.get("contractGate"),
            "scorecard": run.get("scorecard"),
            "answerPreview": str(run.get("answer") or "")[:1200],
            "warnings": run.get("warnings"),
        }
        results.append(record)
        print(
            f"{index:02d}/{len(selected):02d} {status.upper()} {record['id']} "
            f"{record['durationMs']}ms route={(record['route'] or {}).get('projectId')} "
            f"score={(record['analyticalCore'] or {}).get('score')}",
            flush=True,
        )

    failed = [item for item in results if item["status"] != "pass"]
    summary = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "server": args.server,
        "selectedCount": len(selected),
        "passCount": len(results) - len(failed),
        "failCount": len(failed),
        "durationMs": int((time.time() - started) * 1000),
        "filters": {
            "group": args.group,
            "source": args.source,
            "ids": args.ids,
            "includeLive": args.include_live,
            "limit": args.limit,
            "offset": args.offset,
            "shuffle": args.shuffle,
            "seed": args.seed,
        },
        "results": results,
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULT_DIR / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-golden-batch.json")
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"SUMMARY {summary['passCount']} pass {summary['failCount']} fail", flush=True)
    print(f"RESULT {output_path}", flush=True)
    if failed and not args.no_fail_exit:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
