#!/usr/bin/env python3
"""Live /api/run malformed-payload smoke tests for Codex CLI UI."""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://127.0.0.1:8765"


def expected_partial_count():
    try:
        data = json.loads((APP_DIR / "tests" / "ai_ui_intent_500_audit.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return 0
    return sum(1 for item in items if str(item.get("status") or "").upper() == "PARTIAL")


def post_json(server_url, payload, timeout=60):
    req = urllib.request.Request(
        server_url.rstrip("/") + "/api/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_ndjson(raw):
    objects = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            objects.append({"type": "unparsed", "text": line})
    return objects


def run_case(server_url, name, cwd_value):
    partial_count = expected_partial_count()
    payload = {
        "messages": [{"role": "user", "text": "What still needs human QA in the AI UI intent audit?"}],
        "profile": "manager",
        "managerDepth": "fast",
        "webSearch": "disabled",
        "cwd": cwd_value,
        "testRun": True,
    }
    started = time.time()
    try:
        raw = post_json(server_url, payload)
        objects = parse_ndjson(raw)
        text = "".join(str(item.get("text") or item.get("answer") or "") for item in objects)
        modes = [item.get("mode") for item in objects if item.get("mode")]
        ok = (
            bool(objects)
            and "server-crash-recovery" not in raw
            and "Traceback" not in raw
            and f"{partial_count} PARTIAL" in text
            and "This is why:" in text
        )
        return {
            "name": name,
            "ok": ok,
            "durationMs": round((time.time() - started) * 1000, 1),
            "objectCount": len(objects),
            "modes": modes[:4],
            "textPreview": text[:260],
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "name": name,
            "ok": False,
            "durationMs": round((time.time() - started) * 1000, 1),
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def build_cases(root):
    root = str(Path(root).resolve())
    return [
        ("cwd-list", [root]),
        ("cwd-dict", {"cwd": root}),
        ("cwd-path-dict", {"path": root}),
        ("cwd-number", 42),
        ("cwd-nested-list", {"cwd": ["", None, root]}),
        ("cwd-nested-dict-list", {"value": {"cwd": [root]}}),
    ]


def main():
    parser = argparse.ArgumentParser(description="Run live /api/run malformed cwd payload smoke tests.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cases = [run_case(args.server, name, cwd_value) for name, cwd_value in build_cases(args.root)]
    failed = [case for case in cases if not case.get("ok")]
    report = {
        "status": "pass" if not failed else "fail",
        "server": args.server,
        "caseCount": len(cases),
        "failedCount": len(failed),
        "cases": cases,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"cases: {report['caseCount']}")
        for case in cases:
            mark = "PASS" if case.get("ok") else "FAIL"
            print(f"{mark}: {case['name']} ({case.get('durationMs')} ms)")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
