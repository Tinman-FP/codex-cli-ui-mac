#!/usr/bin/env python3
"""Build an actionable backlog from the AI UI 500-question audit."""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = APP_DIR / "tests" / "ai_ui_intent_500_audit.json"
DEFAULT_OUTPUT_DIR = APP_DIR / "data" / "golden_batch_results"


ACTION_RULES = (
    (
        "Accessibility",
        "Add keyboard-only flows, focus-order checks, ARIA/label checks, semantic answer checks, and a screen-reader smoke test.",
    ),
    (
        "Localization",
        "Add locale/date/unit/currency checks, spelling-variant tests, mixed-language prompts, and culture-safe wording checks.",
    ),
    (
        "Production Readiness",
        "Add release owner, rollback, incident response, monitoring, public feedback, support, and launch-approval gates.",
    ),
    (
        "Privacy",
        "Add sensitive-data warnings, redaction tests, memory-use boundaries, and export/package privacy checks.",
    ),
    (
        "Safety",
        "Add adversarial rephrase tests, safety-critical refusal/redirect checks, and tool-action confirmation gates.",
    ),
    (
        "High-Stakes",
        "Add medical/legal/financial/engineering intent detection, source requirements, and conservative escalation wording.",
    ),
    (
        "Latency",
        "Add latency budgets, progress-state checks, cancellation/steering checks, and slow-tool fallback tests.",
    ),
    (
        "Prompt Guidance",
        "Add unobtrusive guidance tests that ensure suggestions help without hijacking the user's actual task.",
    ),
    (
        "Personalization",
        "Add preference-boundary tests so personality and memory help without exposing private or stale context.",
    ),
)


def action_for_category(category):
    for key, action in ACTION_RULES:
        if key.lower() in category.lower():
            return action
    return "Add focused regression prompts and human-review notes for this category."


def priority_for(category, status_counts):
    review = status_counts.get("REVIEW", 0)
    partial = status_counts.get("PARTIAL", 0)
    if review >= 10:
        return "P0"
    if review or partial >= 15:
        return "P1"
    if partial:
        return "P2"
    return "P3"


def load_audit(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("audit file does not contain an items list")
    return data, items


def build_backlog(audit_path):
    data, items = load_audit(audit_path)
    by_category = defaultdict(lambda: {"total": 0, "PASS": 0, "PARTIAL": 0, "REVIEW": 0, "items": []})
    for item in items:
        category = str(item.get("category") or "Uncategorized")
        status = str(item.get("status") or "UNKNOWN").upper()
        bucket = by_category[category]
        bucket["total"] += 1
        bucket[status] = bucket.get(status, 0) + 1
        if status in {"PARTIAL", "REVIEW"}:
            bucket["items"].append(item)

    categories = []
    for category, bucket in by_category.items():
        status_counts = {key: bucket.get(key, 0) for key in ("PASS", "PARTIAL", "REVIEW")}
        if not bucket["items"]:
            continue
        categories.append(
            {
                "category": category,
                "priority": priority_for(category, status_counts),
                "statusCounts": status_counts,
                "gapCount": len(bucket["items"]),
                "action": action_for_category(category),
                "exampleQuestions": [
                    {
                        "id": item.get("id"),
                        "status": item.get("status"),
                        "question": item.get("question"),
                    }
                    for item in bucket["items"][:5]
                ],
            }
        )
    categories.sort(key=lambda row: (row["priority"], -row["statusCounts"].get("REVIEW", 0), -row["gapCount"], row["category"]))
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceAudit": str(audit_path),
        "summary": summary,
        "gapTotals": {
            "categories": len(categories),
            "questions": sum(row["gapCount"] for row in categories),
            "partial": sum(row["statusCounts"].get("PARTIAL", 0) for row in categories),
            "review": sum(row["statusCounts"].get("REVIEW", 0) for row in categories),
        },
        "categories": categories,
    }


def write_outputs(backlog, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    json_path = output_dir / f"{stamp}-ai-ui-intent-gap-backlog.json"
    md_path = output_dir / f"{stamp}-ai-ui-intent-gap-backlog.md"
    json_path.write_text(json.dumps(backlog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# AI UI Intent Gap Backlog",
        "",
        f"- Source audit: `{backlog['sourceAudit']}`",
        f"- Gap categories: {backlog['gapTotals']['categories']}",
        f"- Gap questions: {backlog['gapTotals']['questions']}",
        f"- Partial: {backlog['gapTotals']['partial']}",
        f"- Review: {backlog['gapTotals']['review']}",
        "",
        "## Priority Categories",
    ]
    for row in backlog["categories"]:
        counts = row["statusCounts"]
        lines.extend(
            [
                "",
                f"### {row['priority']} - {row['category']}",
                "",
                f"- Status: PASS {counts.get('PASS', 0)}, PARTIAL {counts.get('PARTIAL', 0)}, REVIEW {counts.get('REVIEW', 0)}",
                f"- Action: {row['action']}",
            ]
        )
        for example in row["exampleQuestions"]:
            lines.append(f"- Q{example['id']} ({example['status']}): {example['question']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Summarize AI UI intent audit gaps into an actionable backlog.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--check", action="store_true", help="Validate that the audit produces a useful backlog without writing files.")
    args = parser.parse_args()

    audit_path = Path(args.audit).expanduser().resolve()
    backlog = build_backlog(audit_path)
    if args.check:
        totals = backlog["gapTotals"]
        if totals["questions"] <= 0 or totals["categories"] <= 0:
            raise SystemExit("no gaps found; expected a backlog from this audit")
        if totals["questions"] != totals["partial"] + totals["review"]:
            raise SystemExit("gap question totals do not match PARTIAL + REVIEW counts")
        rows = backlog["categories"]
        for index, row in enumerate(rows):
            counts = row.get("statusCounts") or {}
            gaps = int(row.get("gapCount") or 0)
            if not row.get("category") or not row.get("priority") or not row.get("action"):
                raise SystemExit(f"backlog row {index} is missing category, priority, or action")
            if gaps <= 0 or gaps != int(counts.get("PARTIAL") or 0) + int(counts.get("REVIEW") or 0):
                raise SystemExit(f"backlog row {index} has inconsistent gap counts")
            if not row.get("exampleQuestions"):
                raise SystemExit(f"backlog row {index} has no example questions")
        first = rows[0]
        print(
            json.dumps(
                {
                    "ok": True,
                    "gapTotals": totals,
                    "firstCategory": first.get("category"),
                    "firstPriority": first.get("priority"),
                },
                sort_keys=True,
            )
        )
        return
    json_path, md_path = write_outputs(backlog, Path(args.output_dir).expanduser().resolve())
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
