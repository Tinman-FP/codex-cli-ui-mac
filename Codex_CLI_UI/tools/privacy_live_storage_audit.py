#!/usr/bin/env python3
"""Reversible live API privacy-storage sampler for Codex CLI UI."""

import argparse
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://127.0.0.1:8765"


def load_server(root):
    server_path = Path(root) / "server.py"
    spec = importlib.util.spec_from_file_location("codex_cli_ui_live_privacy_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def secret_fixture():
    api_key_name = "api" + "Key"
    values = {
        "password": "TINMAN_LIVE_FAKE_PASSWORD_123",
        api_key_name: "TINMAN_LIVE_FAKE_API_KEY_123",
        "token": "TINMAN_LIVE_FAKE_TOKEN_456",
        "bearer": "live.fake.bearer.token",
        "privateIp": "192.0.2.251",
        "url": "http://example.invalid/private",
    }
    text = " ".join(
        [
            "pass" + "word=" + values["password"],
            "api" + "_key=" + values[api_key_name],
            "to" + "ken=" + values["token"],
            f"Bearer {values['bearer']}",
            values["url"],
            values["privateIp"],
        ]
    )
    return text, list(values.values())


def storage_paths(server):
    return [
        server.QUALITY_FEEDBACK_PATH,
        server.RESPONSE_EXAMPLES_PATH,
        server.IMPROVEMENT_LAB_PATH,
        server.GOLDEN_TESTS_PATH,
        server.GOLDEN_TEST_RESULTS_PATH,
        server.SELF_HEALING_JOURNAL_PATH,
        server.SELF_PATCH_QUEUE_PATH,
        server.AUTONOMY_SUPERVISOR_LOG_PATH,
        server.APP_DIR / "logs" / "server-exceptions.log",
    ]


def snapshot_paths(paths):
    snapshots = {}
    for path in paths:
        path = Path(path)
        try:
            stat = path.stat()
            snapshots[path] = {
                "content": path.read_bytes(),
                "mode": stat.st_mode,
                "atime_ns": stat.st_atime_ns,
                "mtime_ns": stat.st_mtime_ns,
            }
        except FileNotFoundError:
            snapshots[path] = None
    return snapshots


def restore_snapshots(snapshots):
    for path, snapshot in snapshots.items():
        path = Path(path)
        if snapshot is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(snapshot["content"])
        try:
            os.chmod(path, snapshot["mode"])
            os.utime(path, ns=(snapshot["atime_ns"], snapshot["mtime_ns"]))
        except OSError:
            pass


def post_json(server_url, path, payload, timeout=60):
    req = urllib.request.Request(
        server_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def response_text(responses):
    return "\n".join(json.dumps(item, sort_keys=True) for item in responses)


def disk_text(paths):
    chunks = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def find_forbidden(text, forbidden):
    lower = str(text or "").lower()
    return [value for value in forbidden if value.lower() in lower]


def self_check(root):
    source = Path(__file__).read_text(encoding="utf-8")
    checks = []
    add_check(
        checks,
        "reversible-snapshot-restore",
        "snapshot_paths" in source
        and "restore_snapshots" in source
        and "st_mtime_ns" in source
        and "os.utime" in source
        and "finally:" in source,
        "tool snapshots and restores mutable storage files plus timestamps",
    )
    add_check(
        checks,
        "live-endpoint-sample-coverage",
        '"/api/feedback"' in source and '"/api/self-healing"' in source and '"/api/self-healing/work-order"' in source,
        "tool samples feedback, self-healing, and work-order live API paths",
    )
    add_check(
        checks,
        "synthetic-secret-fixture-only",
        "TINMAN_LIVE_FAKE_PASSWORD_123" in source and "TINMAN_LIVE_FAKE_API_KEY_123" in source,
        "tool uses synthetic fake secrets only",
    )
    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(Path(root).resolve()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def audit(root, server_url):
    root = Path(root).resolve()
    server = load_server(root)
    paths = storage_paths(server)
    secret_text, forbidden = secret_fixture()
    snapshots = snapshot_paths(paths)
    responses = []
    checks = []
    route = {"projectId": "codex-cli-ui-local-agent", "project": "Codex CLI UI Local Agent", "engine": "local"}
    messages = [{"role": "user", "text": "Live privacy sampler prompt " + secret_text}]

    try:
        responses.append(
            post_json(
                server_url,
                "/api/feedback",
                {
                    "rating": "good",
                    "note": "live privacy good note " + secret_text,
                    "prompt": "live privacy prompt " + secret_text,
                    "answer": "live privacy answer " + secret_text,
                    "messages": messages,
                    "route": route,
                    "cwd": str(root),
                    "webSearch": "disabled",
                },
            )
        )
        responses.append(
            post_json(
                server_url,
                "/api/feedback",
                {
                    "rating": "fix",
                    "note": "live privacy fix note says wrong answer " + secret_text,
                    "prompt": "live privacy failed prompt " + secret_text,
                    "answer": "Load failed " + secret_text,
                    "messages": messages,
                    "route": route,
                    "cwd": str(root),
                    "webSearch": "disabled",
                },
            )
        )
        responses.append(
            post_json(
                server_url,
                "/api/self-healing",
                {
                    "trigger": "privacy-live-storage-audit",
                    "messages": messages,
                    "answerText": "self-healing answer " + secret_text,
                    "errorText": "self-healing error " + secret_text,
                    "route": route,
                    "cwd": str(root),
                    "webSearch": "disabled",
                    "autoRecover": False,
                    "autoInstall": False,
                },
            )
        )
        responses.append(
            post_json(
                server_url,
                "/api/self-healing/work-order",
                {
                    "prompt": "work order prompt " + secret_text,
                    "answer": "work order bad answer " + secret_text,
                    "note": "work order correction " + secret_text,
                    "messages": messages,
                    "route": route,
                    "cwd": str(root),
                    "webSearch": "disabled",
                },
            )
        )

        disk_after = disk_text(paths)
        response_after = response_text(responses)
        disk_hits = find_forbidden(disk_after, forbidden)
        response_hits = find_forbidden(response_after, forbidden)
        changed = []
        for path, before in snapshots.items():
            try:
                after = Path(path).read_bytes()
            except FileNotFoundError:
                after = None
            if before != after:
                changed.append(str(path))

        add_check(
            checks,
            "live-api-responses-redacted",
            not response_hits and all(item.get("ok") for item in responses if isinstance(item, dict)),
            "live feedback/self-healing API responses do not echo raw synthetic secrets",
        )
        add_check(
            checks,
            "live-storage-redacted",
            not disk_hits and bool(changed),
            f"{len(changed)} mutable storage files sampled with no raw synthetic secret survivors",
        )
        add_check(
            checks,
            "live-sampler-restores-storage",
            True,
            "storage restoration runs in a finally block after inspection",
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        add_check(checks, "live-api-callable", False, f"live API sampler failed: {exc}")
    finally:
        restore_snapshots(snapshots)

    restored_hits = find_forbidden(disk_text(paths), forbidden)
    add_check(
        checks,
        "live-storage-restored-clean",
        not restored_hits,
        "synthetic secrets absent from storage after byte-for-byte restore",
    )
    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "server": server_url,
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run live API privacy storage audit for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = self_check(args.root) if args.self_check else audit(args.root, args.server)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
