#!/usr/bin/env python3
import argparse
import json
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULT_DIR = DATA_DIR / "golden_batch_results"
DEFAULT_SERVER = "http://127.0.0.1:8765"

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


def post_json_stream(url, payload, timeout=240):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
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
        "webSearch": test.get("webSearch") or "disabled",
        "testRun": True,
        "messages": test_messages(test),
    }
    started = time.time()
    run = {
        "route": {},
        "answer": "",
        "analyticalCore": {},
        "returnCode": None,
        "thoughts": [],
        "warnings": [],
        "durationMs": 0,
    }
    for event in post_json_stream(f"{server}/api/run", payload, timeout=args.timeout):
        event_type = event.get("type")
        if event_type == "status":
            run["route"] = event.get("route") or run["route"]
        elif event_type == "assistant":
            run["answer"] = event.get("text") or ""
            run["analyticalCore"] = event.get("analyticalCore") or {}
        elif event_type == "thought":
            run["thoughts"].append(event.get("text") or "")
        elif event_type in {"warning", "error"}:
            run["warnings"].append(event.get("text") or event_type)
        elif event_type == "done":
            run["returnCode"] = event.get("returnCode")
    run["durationMs"] = int((time.time() - started) * 1000)
    return run


def evaluate_test(test, run):
    answer = str(run.get("answer") or "").strip()
    lower = answer.lower()
    route = run.get("route") or {}
    checks = []

    def add(label, passed, detail=""):
        checks.append({"label": label, "passed": bool(passed), "detail": detail})

    add(
        "answered",
        bool(answer) and not re.search(r"no final message returned|returned no answer|run failed", lower),
        "final text returned" if answer else "no final text",
    )
    if test.get("expectedProjectId"):
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
        add("context", bool(matched), "matched: " + ", ".join(matched) if matched else "no anyTerms matched")
    if test.get("forbiddenTerms"):
        found = [term for term in test["forbiddenTerms"] if term.lower() in lower]
        add("grounded", not found, "found: " + ", ".join(found) if found else "no forbidden terms found")
    if test.get("requiresSource"):
        add("source", "http://" in lower or "https://" in lower or "sources checked" in lower, "source expected")
    if test.get("minAnalyticalScore"):
        score = float((run.get("analyticalCore") or {}).get("score") or 0)
        add("analytical", score >= float(test["minAnalyticalScore"]), f"score {score}")
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

    bench = load_json_url(f"{args.server}/api/test-bench")
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
