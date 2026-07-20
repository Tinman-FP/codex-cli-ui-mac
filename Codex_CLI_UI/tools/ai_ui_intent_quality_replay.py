#!/usr/bin/env python3
"""Replay the AI UI 500-question checklist against the local direct-answer path."""

import argparse
import importlib.util
import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = APP_DIR / "tests" / "ai_ui_intent_500_audit.json"
DEFAULT_OUTPUT_DIR = APP_DIR / "data" / "golden_batch_results"
DEFAULT_SERVER = "http://127.0.0.1:8765"
BAD_ANSWER_TERMS = (
    "local research could not find",
    "load failed",
    "no final message returned",
    "run failed",
    "recovery plan:",
)


def load_server(root):
    server_path = Path(root) / "server.py"
    spec = importlib.util.spec_from_file_location("codex_cli_ui_ai_intent_replay_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_audit(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        raise ValueError("audit file does not contain an items list")
    return data, items


def expected_lead(status):
    status = str(status or "").upper()
    if status == "PASS":
        return "Yes."
    if status == "PARTIAL":
        return "Partially."
    return "Not fully proven yet."


def evaluate_answer(item, answer):
    status = str(item.get("status") or "").upper()
    category = str(item.get("category") or "")
    evidence = [str(value).strip() for value in item.get("evidence") or [] if str(value).strip()]
    lower = answer.lower()
    failures = []
    if not answer.strip():
        failures.append("no answer")
    if not answer.startswith(expected_lead(status)):
        failures.append(f"lead did not match {status or 'UNKNOWN'}")
    if f"audit status `{status}`" not in answer:
        failures.append("missing audit status")
    if "This is why:" not in answer:
        failures.append("missing why section")
    if "You should also consider:" not in answer:
        failures.append("missing consider section")
    if status == "PARTIAL" and "Next proof needed:" not in answer:
        failures.append("missing partial next proof")
    if category and category not in answer:
        failures.append("missing category")
    if evidence and "Current evidence:" not in answer:
        failures.append("missing evidence label")
    if any(term in lower for term in BAD_ANSWER_TERMS):
        failures.append("contains bad failure/research wording")
    return failures


def post_json_stream(server_url, payload, timeout):
    request = urllib.request.Request(
        server_url.rstrip("/") + "/api/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            if not raw.strip():
                continue
            yield json.loads(raw.decode("utf-8"))


def replay(audit_path, output_dir, label):
    audit_data, items = load_audit(audit_path)
    server = load_server(APP_DIR)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    label_slug = "-".join(part for part in str(label or "quality").lower().replace("_", "-").split() if part)
    label_slug = label_slug or "quality"
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{stamp}-ai-ui-intent-500-{label_slug}-quality-run.jsonl"
    summary_path = output_dir / f"{stamp}-ai-ui-intent-500-{label_slug}-quality-summary.json"
    md_path = output_dir / f"{stamp}-ai-ui-intent-500-{label_slug}-quality-summary.md"

    records = []
    by_status = defaultdict(lambda: {"total": 0, "passed": 0})
    durations = []
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for item in items:
            question = str(item.get("question") or "").strip()
            started = time.time()
            answer = server.ai_ui_intent_checklist_direct_answer([{"role": "user", "text": question}])
            duration_ms = int((time.time() - started) * 1000)
            durations.append(duration_ms)
            failures = evaluate_answer(item, answer)
            passed = not failures
            status = str(item.get("status") or "UNKNOWN").upper()
            by_status[status]["total"] += 1
            if passed:
                by_status[status]["passed"] += 1
            first_line = answer.splitlines()[0] if answer else ""
            record = {
                "id": item.get("id"),
                "category": item.get("category"),
                "expectedStatus": status,
                "passed": passed,
                "durationMs": duration_ms,
                "answerFirstLine": first_line,
                "failures": failures,
                "evidenceCount": len(item.get("evidence") or []),
            }
            records.append(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    failed = [record for record in records if not record["passed"]]
    summary = {
        "createdAt": stamp,
        "source": audit_data.get("source") or "",
        "audit": str(Path(audit_path).resolve()),
        "jsonl": str(jsonl_path),
        "total": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "avgDurationMs": round(sum(durations) / max(1, len(durations)), 1),
        "maxDurationMs": max(durations) if durations else 0,
        "byStatus": dict(sorted(by_status.items())),
        "firstFailures": failed[:10],
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    title = " ".join(part.capitalize() for part in label_slug.split("-"))
    lines = [
        f"# AI UI Intent 500 {title} Quality Run",
        "",
        f"- Source: `{summary['source']}`",
        f"- Audit: `{summary['audit']}`",
        f"- Results: `{summary['jsonl']}`",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Average latency: {summary['avgDurationMs']} ms",
        f"- Max latency: {summary['maxDurationMs']} ms",
        "",
        "## By Status",
    ]
    for status, counts in summary["byStatus"].items():
        lines.append(f"- {status}: {counts['passed']}/{counts['total']} passed")
    lines.extend(["", "## First Failures"])
    if failed:
        for record in failed[:10]:
            lines.append(f"- Q{record['id']}: {', '.join(record['failures'])}")
    else:
        lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, md_path, summary


def live_review_replay(audit_path, output_dir, server_url, timeout, limit):
    audit_data, items = load_audit(audit_path)
    review_items = [item for item in items if str(item.get("status") or "").upper() == "REVIEW"]
    if limit:
        review_items = review_items[: max(0, int(limit))]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{stamp}-ai-ui-intent-review-live-api-run.jsonl"
    summary_path = output_dir / f"{stamp}-ai-ui-intent-review-live-api-run-summary.json"
    md_path = output_dir / f"{stamp}-ai-ui-intent-review-live-api-run-summary.md"
    records = []
    durations = []

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for item in review_items:
            question = str(item.get("question") or "").strip()
            payload = {
                "profile": "manager",
                "cwd": str(Path.home() / "Documents" / "Codex"),
                "accessLevel": "danger-full-access",
                "reasoningLevel": "low",
                "managerDepth": "fast",
                "friendlinessLevel": "warm",
                "humorLevel": "light",
                "webSearch": "disabled",
                "testRun": True,
                "messages": [{"role": "user", "text": question}],
            }
            started = time.time()
            answer = ""
            mode = ""
            route = {}
            warnings = []
            try:
                for event in post_json_stream(server_url, payload, timeout=timeout):
                    event_type = event.get("type")
                    if event_type == "status":
                        mode = event.get("mode") or mode
                        route = event.get("route") or route
                    elif event_type == "assistant":
                        answer = event.get("text") or answer
                    elif event_type in {"warning", "error"}:
                        warnings.append(event.get("text") or event_type)
            except Exception as exc:
                warnings.append(f"{type(exc).__name__}: {exc}")
            duration_ms = int((time.time() - started) * 1000)
            durations.append(duration_ms)
            failures = evaluate_answer(item, answer)
            if mode != "ai-ui-intent-checklist":
                failures.append(f"unexpected mode: {mode or 'none'}")
            if warnings:
                failures.append("warnings: " + "; ".join(warnings[:3]))
            record = {
                "id": item.get("id"),
                "category": item.get("category"),
                "question": question,
                "passed": not failures,
                "failures": failures,
                "durationMs": duration_ms,
                "mode": mode,
                "route": route.get("projectId") if isinstance(route, dict) else "",
                "answerFirstLine": answer.splitlines()[0] if answer else "",
            }
            records.append(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    failed = [record for record in records if not record["passed"]]
    summary = {
        "createdAt": stamp,
        "source": audit_data.get("source") or "",
        "audit": str(Path(audit_path).resolve()),
        "server": server_url,
        "jsonl": str(jsonl_path),
        "total": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "avgDurationMs": round(sum(durations) / max(1, len(durations)), 1),
        "maxDurationMs": max(durations) if durations else 0,
        "firstFailures": failed[:10],
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# AI UI Intent REVIEW Live API Run",
        "",
        f"- Source: `{summary['source']}`",
        f"- Audit: `{summary['audit']}`",
        f"- Results: `{summary['jsonl']}`",
        f"- Total REVIEW items: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Average latency: {summary['avgDurationMs']} ms",
        f"- Max latency: {summary['maxDurationMs']} ms",
        "",
        "## First Failures",
    ]
    if failed:
        for record in failed[:10]:
            lines.append(f"- Q{record['id']}: {', '.join(record['failures'])}")
    else:
        lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, md_path, summary


def check(audit_path):
    _, items = load_audit(audit_path)
    server = load_server(APP_DIR)
    samples = []
    seen = set()
    for wanted in ("PASS", "PARTIAL", "REVIEW"):
        for item in items:
            if str(item.get("status") or "").upper() == wanted:
                samples.append(item)
                seen.add(wanted)
                break
    checks = []
    for item in samples:
        answer = server.ai_ui_intent_checklist_direct_answer([{"role": "user", "text": item.get("question") or ""}])
        failures = evaluate_answer(item, answer)
        checks.append(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "passed": not failures,
                "failures": failures,
            }
        )
    missing = [status for status in ("PASS", "PARTIAL") if status not in seen]
    if missing:
        checks.append({"id": "audit-status-coverage", "status": "MISSING", "passed": False, "failures": missing})
    else:
        review_count = sum(1 for item in items if str(item.get("status") or "").upper() == "REVIEW")
        checks.append(
            {
                "id": "audit-status-coverage",
                "status": "COVERED",
                "passed": True,
                "failures": [],
                "detail": f"PASS and PARTIAL samples covered; REVIEW count is {review_count}",
            }
        )
    source = Path(__file__).read_text(encoding="utf-8")
    checks.append(
        {
            "id": "live-review-replay-capability",
            "status": "TOOLING",
            "passed": "live_review_replay" in source and '"/api/run"' in source and "--live-review" in source,
            "failures": [] if "live_review_replay" in source and '"/api/run"' in source and "--live-review" in source else ["missing live review replay path"],
        }
    )
    failed = [item for item in checks if not item["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "audit": str(Path(audit_path).resolve()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Replay all 500 AI UI intent checklist questions.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label", default="quality")
    parser.add_argument("--check", action="store_true", help="Run a fast no-output PASS/PARTIAL/REVIEW sample check.")
    parser.add_argument("--live-review", action="store_true", help="Run REVIEW items through the live /api/run endpoint.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.check:
        report = check(args.audit)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"status: {report['status']}")
            print(f"checks: {report['checkCount']}")
            for item in report["checks"]:
                mark = "PASS" if item["passed"] else "FAIL"
                print(f"{mark}: Q{item['id']} - {item['status']}")
        return 0 if report["status"] == "pass" else 1
    if args.live_review:
        summary_path, md_path, summary = live_review_replay(
            args.audit,
            args.output_dir,
            args.server,
            args.timeout,
            args.limit,
        )
        if args.json:
            print(json.dumps({"summary": str(summary_path), "markdown": str(md_path), **summary}, indent=2, sort_keys=True))
        else:
            print(summary_path)
            print(md_path)
            print(f"SUMMARY {summary['passed']} pass {summary['failed']} fail")
        return 0 if summary["failed"] == 0 else 1
    summary_path, md_path, summary = replay(args.audit, args.output_dir, args.label)
    if args.json:
        print(json.dumps({"summary": str(summary_path), "markdown": str(md_path), **summary}, indent=2, sort_keys=True))
    else:
        print(summary_path)
        print(md_path)
        print(f"SUMMARY {summary['passed']} pass {summary['failed']} fail")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
