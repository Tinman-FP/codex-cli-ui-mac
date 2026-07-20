#!/usr/bin/env python3
"""Cleanup-safe live rehearsal for interaction-feedback regression promotion."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


SIDE_EFFECT_FILES = [
    "data/quality_feedback.jsonl",
    "data/interaction_feedback_ledger.jsonl",
    "data/improvement_lab.json",
    "data/golden_tests.json",
    "data/golden_test_results.json",
    "data/self_healing_journal.jsonl",
    "data/self_patch_queue.json",
    "data/response_examples.json",
]

EXPECTED_OBJECTIVE_TYPE = "local-ui-status-surface"
EXPECTED_RESPONSE_KIND = "local-app-status-fix"
EXPECTED_PROJECT_ID = "codex-cli-ui-local-agent"


def read_json_response(url: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = None
    headers = {}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body or "{}")


def snapshot_files(root: Path) -> dict[str, bytes | None]:
    snapshot: dict[str, bytes | None] = {}
    for relative in SIDE_EFFECT_FILES:
        path = root / relative
        snapshot[relative] = path.read_bytes() if path.exists() else None
    return snapshot


def restore_files(root: Path, snapshot: dict[str, bytes | None]) -> None:
    for relative, content in snapshot.items():
        path = root / relative
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            os.replace(tmp_name, path)
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass


def snapshot_matches(root: Path, snapshot: dict[str, bytes | None]) -> bool:
    for relative, content in snapshot.items():
        path = root / relative
        current = path.read_bytes() if path.exists() else None
        if current != content:
            return False
    return True


def rehearsal_route() -> dict:
    objective_plan = {
        "version": 1,
        "objectiveType": EXPECTED_OBJECTIVE_TYPE,
        "responseKind": EXPECTED_RESPONSE_KIND,
        "target": "Codex CLI UI Model Health row for Bambu H2D",
        "action": "fix or extend the local status panel rather than asking for CAD geometry",
        "evidenceNeed": "live-or-configured-status-source",
        "missingInputs": ["Bambu H2D progress/ETA telemetry source or manual override values"],
        "forbiddenAnswerFamilies": ["cad-missing-geometry", "fusion-ready-cad", "generic-printer-profile"],
        "routeCandidates": [EXPECTED_PROJECT_ID],
        "confidence": 0.96,
    }
    return {
        "engine": "local",
        "confidence": "high",
        "projectId": EXPECTED_PROJECT_ID,
        "project": "Codex CLI UI & Local Agent",
        "specialist": "Local Agent Builder",
        "objectivePlan": objective_plan,
    }


def feedback_payload(index: int) -> dict:
    prompt = (
        "The Bambu H2D is printing; show percent complete and time remaining in Model Health."
        if index == 1
        else "In Model Health for the Bambu H2D, show print progress percent and ETA instead of only printing/offline."
    )
    answer = (
        "I can design the part, but I do not have enough geometry to create a Fusion-ready CAD file yet."
    )
    note = (
        "The answer misunderstood a local UI status request and returned canned CAD missing-geometry text."
    )
    route = rehearsal_route()
    return {
        "rating": "fix",
        "note": note,
        "prompt": prompt,
        "answer": answer,
        "messages": [{"role": "user", "text": prompt}, {"role": "assistant", "text": answer}],
        "cwd": str(Path.cwd()),
        "webSearch": "disabled",
        "route": route,
        "objectivePlan": route["objectivePlan"],
        "compositionStyle": {"mode": "conversational", "tone": "direct", "structure": "answer-first"},
        "projectId": EXPECTED_PROJECT_ID,
    }


def find_test(test_bench: dict, test_id: str) -> dict | None:
    for item in test_bench.get("tests") or []:
        if isinstance(item, dict) and item.get("id") == test_id:
            return item
    return None


def validate_regression(test: dict | None) -> list[str]:
    errors: list[str] = []
    if not test:
        return ["interaction regression test was not found in /api/test-bench"]
    if test.get("group") != "Interaction Learning":
        errors.append(f"group={test.get('group')!r}")
    if test.get("source") != "interaction-feedback-ledger":
        errors.append(f"source={test.get('source')!r}")
    if test.get("expectedProjectId") != EXPECTED_PROJECT_ID:
        errors.append(f"expectedProjectId={test.get('expectedProjectId')!r}")
    if test.get("expectedObjectiveType") != EXPECTED_OBJECTIVE_TYPE:
        errors.append(f"expectedObjectiveType={test.get('expectedObjectiveType')!r}")
    if test.get("expectedObjectiveResponseKind") != EXPECTED_RESPONSE_KIND:
        errors.append(f"expectedObjectiveResponseKind={test.get('expectedObjectiveResponseKind')!r}")
    forbidden = set(test.get("forbiddenTerms") or [])
    if "not enough geometry" not in forbidden and "fusion-ready cad" not in forbidden:
        errors.append("forbiddenTerms missing CAD misroute guard")
    if int(test.get("interactionPatternCount") or 0) < 2:
        errors.append(f"interactionPatternCount={test.get('interactionPatternCount')!r}")
    return errors


def run_live_rehearsal(root: Path, server: str, timeout: float = 20.0, keep: bool = False) -> dict:
    server = server.rstrip("/")
    snapshot = snapshot_files(root)
    started = time.time()
    result: dict = {
        "status": "fail",
        "server": server,
        "restored": False,
        "createdRegression": None,
        "errors": [],
    }
    regression_id = ""
    try:
        first = read_json_response(f"{server}/api/feedback", feedback_payload(1), timeout=timeout)
        second = read_json_response(f"{server}/api/feedback", feedback_payload(2), timeout=timeout)
        if not first.get("ok"):
            result["errors"].append(f"first feedback failed: {first.get('error') or first}")
        if not second.get("ok"):
            result["errors"].append(f"second feedback failed: {second.get('error') or second}")
        regression = second.get("interactionRegression") or first.get("interactionRegression") or {}
        regression_id = str(regression.get("id") or "")
        result["createdRegression"] = regression
        if not regression_id:
            result["errors"].append("feedback responses did not include interactionRegression")
        test = None
        if regression_id:
            test_bench = read_json_response(f"{server}/api/test-bench", timeout=timeout)
            test = find_test(test_bench, regression_id)
            result["testBenchFound"] = bool(test)
            result["testBenchRegression"] = test
            result["errors"].extend(validate_regression(test))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        result["errors"].append(f"{exc.__class__.__name__}: {exc}")
    finally:
        if not keep:
            restore_files(root, snapshot)
            result["restored"] = snapshot_matches(root, snapshot)
            if regression_id:
                try:
                    after = read_json_response(f"{server}/api/test-bench", timeout=timeout)
                    result["testRemovedAfterRestore"] = find_test(after, regression_id) is None
                    if not result["testRemovedAfterRestore"]:
                        result["errors"].append("interaction regression still visible after restore")
                except Exception as exc:  # best-effort post-restore cache check
                    result["errors"].append(f"post-restore check failed: {exc.__class__.__name__}: {exc}")
            if not result["restored"]:
                result["errors"].append("side-effect files were not restored to their original bytes")
        else:
            result["restored"] = False
    result["durationMs"] = int((time.time() - started) * 1000)
    result["status"] = "pass" if not result["errors"] else "fail"
    return result


def run_self_check(root: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="interaction-feedback-rehearsal-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for relative in SIDE_EFFECT_FILES:
            path = tmp_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {relative}\n", encoding="utf-8")
        snapshot = snapshot_files(tmp_root)
        (tmp_root / SIDE_EFFECT_FILES[0]).write_text("changed\n", encoding="utf-8")
        restore_files(tmp_root, snapshot)
        entry = {
            "id": "self-check",
            "group": "Interaction Learning",
            "source": "interaction-feedback-ledger",
            "expectedProjectId": EXPECTED_PROJECT_ID,
            "expectedObjectiveType": EXPECTED_OBJECTIVE_TYPE,
            "expectedObjectiveResponseKind": EXPECTED_RESPONSE_KIND,
            "forbiddenTerms": ["not enough geometry"],
            "interactionPatternCount": 2,
        }
        errors = []
        if not snapshot_matches(tmp_root, snapshot):
            errors.append("snapshot restore failed")
        errors.extend(validate_regression(entry))
    script_text = Path(__file__).read_text(encoding="utf-8")
    required = [
        "/api/feedback",
        "/api/test-bench",
        "restore_files(root, snapshot)",
        "testRemovedAfterRestore",
        "expectedObjectiveType",
        "expectedObjectiveResponseKind",
    ]
    missing = [token for token in required if token not in script_text]
    if missing:
        errors.append(f"script contract missing: {', '.join(missing)}")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "sideEffectFiles": SIDE_EFFECT_FILES,
        "root": str(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--server", default=os.environ.get("CODEX_CLI_UI_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--keep", action="store_true", help="Do not restore side-effect files after the live rehearsal.")
    parser.add_argument("--self-check", action="store_true", help="Check rehearsal mechanics without calling the live server.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.self_check:
        result = run_self_check(root)
    else:
        result = run_live_rehearsal(root, args.server, timeout=args.timeout, keep=args.keep)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result.get('status', 'fail')} interaction feedback rehearsal")
        for error in result.get("errors") or []:
            print(f"- {error}")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
