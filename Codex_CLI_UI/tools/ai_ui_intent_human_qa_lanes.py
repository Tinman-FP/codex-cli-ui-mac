#!/usr/bin/env python3
"""Group AI UI intent PARTIAL items into human-review lanes."""

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = APP_DIR / "tests" / "ai_ui_intent_500_audit.json"
DEFAULT_OUTPUT_DIR = APP_DIR / "data" / "golden_batch_results"

STRONG_PREFIXES = (
    "api:",
    "ui:",
    "tools:",
    "analysis:",
    "python:",
)

LANE_BY_CATEGORY_TERM = (
    ("safety", "safety-adversarial-review"),
    ("privacy", "privacy-ux-review"),
    ("sensitive", "privacy-ux-review"),
    ("prompt guidance", "prompt-guidance-ux-review"),
    ("personalization", "personalization-preference-review"),
    ("accessibility", "accessibility-assistive-tech-review"),
    ("latency", "latency-live-ux-review"),
    ("high-stakes", "high-stakes-qualified-review"),
    ("localization", "localization-cultural-review"),
    ("production readiness", "production-release-review"),
)

LANE_LABELS = {
    "safety-adversarial-review": "Safety adversarial review",
    "privacy-ux-review": "Privacy and sensitive-data UX review",
    "prompt-guidance-ux-review": "Prompt guidance UX review",
    "personalization-preference-review": "Personalization and preference review",
    "accessibility-assistive-tech-review": "Accessibility and assistive-tech review",
    "latency-live-ux-review": "Latency and live-progress UX review",
    "high-stakes-qualified-review": "High-stakes qualified-domain review",
    "localization-cultural-review": "Localization and cultural review",
    "production-release-review": "Production release-readiness review",
}

REVIEW_ORDER = (
    "safety-adversarial-review",
    "privacy-ux-review",
    "high-stakes-qualified-review",
    "accessibility-assistive-tech-review",
    "production-release-review",
    "localization-cultural-review",
    "latency-live-ux-review",
    "prompt-guidance-ux-review",
    "personalization-preference-review",
)


def load_items(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("audit file does not contain an items list")
    return data, items


def lane_for_category(category):
    lower = str(category or "").lower()
    for term, lane in LANE_BY_CATEGORY_TERM:
        if term in lower:
            return lane
    return "general-human-review"


def strong_evidence_count(evidence):
    return sum(1 for value in evidence or [] if str(value or "").strip().startswith(STRONG_PREFIXES))


def proof_level(strong_count):
    if strong_count >= 3:
        return "strong-automated-proof"
    if strong_count >= 1:
        return "basic-automated-proof"
    return "review-only-proof"


def lane_action(lane):
    return {
        "safety-adversarial-review": "Run adversarial refusal, redirect, and over-refusal review before PASS.",
        "privacy-ux-review": "Review visible privacy wording, sensitive-data behavior, generated links, and shared-install assumptions before PASS.",
        "prompt-guidance-ux-review": "Review real first-run prompt suggestions and whether users understand how to steer/edit tasks before PASS.",
        "personalization-preference-review": "Verify preference handling with real accessibility and persistence behavior before PASS.",
        "accessibility-assistive-tech-review": "Run keyboard-only, screen-reader, focus-order, reduced-motion, and contrast checks before PASS.",
        "latency-live-ux-review": "Run live slow-task observation for progress, steerability, cancellation, and timeout behavior before PASS.",
        "high-stakes-qualified-review": "Review medical, legal, financial, aviation, electrical, and safety-critical answers with qualified-domain expectations before PASS.",
        "localization-cultural-review": "Run locale, culture, units, dates, currency, names, and mixed-language review before PASS.",
        "production-release-review": "Confirm installer, rollback, incident, support, privacy, public-claims, and release-owner gates before PASS.",
    }.get(lane, "Assign a human owner and define concrete PASS criteria.")


def build_report(audit_path):
    data, items = load_items(audit_path)
    partials = [item for item in items if str(item.get("status") or "").upper() == "PARTIAL"]
    lane_items = []
    for item in partials:
        evidence = [str(value).strip() for value in item.get("evidence") or [] if str(value).strip()]
        lane = lane_for_category(item.get("category"))
        strong_count = strong_evidence_count(evidence)
        lane_items.append(
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "question": item.get("question"),
                "lane": lane,
                "laneLabel": LANE_LABELS.get(lane, "General human review"),
                "proofLevel": proof_level(strong_count),
                "strongEvidenceCount": strong_count,
                "evidenceCount": len(evidence),
                "note": item.get("note") or "",
                "reviewAction": lane_action(lane),
            }
        )
    lane_counts = Counter(item["lane"] for item in lane_items)
    proof_counts = Counter(item["proofLevel"] for item in lane_items)
    by_lane = defaultdict(list)
    for item in lane_items:
        by_lane[item["lane"]].append(item)
    ordered_lanes = [lane for lane in REVIEW_ORDER if lane in by_lane]
    ordered_lanes.extend(sorted(lane for lane in by_lane if lane not in ordered_lanes))
    return {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceAudit": str(audit_path),
        "auditSummary": data.get("summary") if isinstance(data.get("summary"), dict) else {},
        "partialCount": len(partials),
        "laneCounts": dict(sorted(lane_counts.items())),
        "proofCounts": dict(sorted(proof_counts.items())),
        "reviewOrder": [
            {
                "lane": lane,
                "label": LANE_LABELS.get(lane, "General human review"),
                "count": lane_counts[lane],
                "action": lane_action(lane),
            }
            for lane in ordered_lanes
        ],
        "samplesByLane": {
            lane: sorted(items, key=lambda item: item.get("id") or 0)[:8]
            for lane, items in sorted(by_lane.items())
        },
    }


def write_outputs(report, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    json_path = output_dir / f"{stamp}-ai-ui-intent-human-qa-lanes.json"
    md_path = output_dir / f"{stamp}-ai-ui-intent-human-qa-lanes.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# AI UI Intent Human QA Lanes",
        "",
        f"- Source audit: `{report['sourceAudit']}`",
        f"- PARTIAL items: {report['partialCount']}",
        f"- Lane counts: `{json.dumps(report['laneCounts'], sort_keys=True)}`",
        f"- Proof counts: `{json.dumps(report['proofCounts'], sort_keys=True)}`",
        "",
        "## Recommended Review Order",
    ]
    for lane in report["reviewOrder"]:
        lines.append(f"- {lane['label']}: {lane['count']} items. {lane['action']}")
    lines.append("")
    lines.append("## Lane Samples")
    for lane in report["reviewOrder"]:
        lane_id = lane["lane"]
        lines.append("")
        lines.append(f"### {lane['label']}")
        for item in report["samplesByLane"].get(lane_id, []):
            lines.append(f"- Q{item['id']}: {item['question']} ({item['proofLevel']})")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def report_ok(report):
    lane_total = sum(report["laneCounts"].values())
    present_lanes = set(report["laneCounts"])
    known_lanes = set(REVIEW_ORDER)
    return (
        report["partialCount"] > 0
        and lane_total == report["partialCount"]
        and present_lanes
        and present_lanes.issubset(known_lanes)
        and report["proofCounts"].get("review-only-proof", 0) == 0
    )


def main():
    parser = argparse.ArgumentParser(description="Group PARTIAL AI UI audit items into human-review lanes.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    audit_path = Path(args.audit).expanduser().resolve()
    report = build_report(audit_path)
    ok = report_ok(report)
    if args.check:
        result = {
            "ok": ok,
            "partialCount": report["partialCount"],
            "laneCounts": report["laneCounts"],
            "proofCounts": report["proofCounts"],
            "reviewLaneCount": len(report["laneCounts"]),
        }
        print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
        return 0 if ok else 1
    json_path, md_path = write_outputs(report, Path(args.output_dir).expanduser().resolve())
    if args.json:
        print(json.dumps({"json": str(json_path), "markdown": str(md_path), **report}, indent=2, sort_keys=True))
    else:
        print(json_path)
        print(md_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
