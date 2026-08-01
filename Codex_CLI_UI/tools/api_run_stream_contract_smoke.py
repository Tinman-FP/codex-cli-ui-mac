#!/usr/bin/env python3
"""Verify the /api/run streaming contract and parser behavior."""

import argparse
import json
import time
import urllib.request
from json import JSONDecoder
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://127.0.0.1:8765"


def parse_json_stream_events(text):
    decoder = JSONDecoder()
    events = []
    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        index = 0
        while index < len(line):
            while index < len(line) and line[index].isspace():
                index += 1
            if index >= len(line):
                break
            event, end = decoder.raw_decode(line, index)
            if isinstance(event, dict):
                events.append(event)
            index = end
    return events


def post_run_stream(server, payload, timeout):
    request = urllib.request.Request(
        f"{server.rstrip('/')}/api/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    raw_parts = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            raw_parts.append(chunk.decode("utf-8", errors="replace"))
    raw_text = "".join(raw_parts)
    events = parse_json_stream_events(raw_text)
    return events, raw_text, int((time.time() - started) * 1000)


def summarize_events(events, duration_ms, raw_text=""):
    types = [event.get("type") for event in events]
    status = next((event for event in events if event.get("type") == "status"), {})
    assistant = next((event for event in events if event.get("type") == "assistant"), {})
    done = next((event for event in events if event.get("type") == "done"), {})
    ok = (
        bool(events)
        and "status" in types
        and "assistant" in types
        and "done" in types
        and bool(str(assistant.get("text") or "").strip())
        and int(done.get("returnCode") or 0) == 0
    )
    return {
        "status": "pass" if ok else "fail",
        "eventCount": len(events),
        "eventTypes": types,
        "durationMs": duration_ms,
        "routeProjectId": (status.get("route") or {}).get("projectId"),
        "mode": status.get("mode"),
        "assistantPreview": str(assistant.get("text") or "").replace("\n", " ")[:500],
        "returnCode": done.get("returnCode"),
        "rawBytes": len(raw_text.encode("utf-8")) if raw_text else 0,
    }


def self_check():
    sample = "\n".join(
        [
            '{"type":"status","mode":"sample"}',
            'data: {"type":"thought","text":"ok"}',
            '{"type":"assistant","text":"one"}{"type":"done","returnCode":0}',
            "",
        ]
    )
    events = parse_json_stream_events(sample)
    types = [event.get("type") for event in events]
    ok = types == ["status", "thought", "assistant", "done"]
    return {
        "status": "pass" if ok else "fail",
        "eventCount": len(events),
        "eventTypes": types,
        "checks": [
            {"name": "ndjson-line", "status": "pass" if "status" in types else "fail"},
            {"name": "sse-data-line", "status": "pass" if "thought" in types else "fail"},
            {"name": "concatenated-json", "status": "pass" if types[-2:] == ["assistant", "done"] else "fail"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Verify /api/run streaming NDJSON contract.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--cwd", default=str(Path.home() / "Documents" / "Codex"))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_check:
        result = self_check()
    else:
        payload = {
            "profile": "manager",
            "cwd": args.cwd,
            "accessLevel": "danger-full-access",
            "reasoningLevel": "medium",
            "managerDepth": "fast",
            "friendlinessLevel": "warm",
            "humorLevel": "light",
            "webSearch": "disabled",
            "messages": [
                {
                    "role": "user",
                    "text": "Show me the latest verification receipts for Codex CLI UI testing.",
                }
            ],
        }
        events, raw_text, duration_ms = post_run_stream(args.server, payload, args.timeout)
        result = summarize_events(events, duration_ms, raw_text)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"status: {result.get('status')}")
        print(f"events: {result.get('eventCount')} {result.get('eventTypes')}")
        if result.get("assistantPreview"):
            print(f"assistant: {result.get('assistantPreview')}")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
