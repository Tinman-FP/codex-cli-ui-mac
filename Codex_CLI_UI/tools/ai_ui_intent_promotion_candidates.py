#!/usr/bin/env python3
"""Find AI UI intent PARTIAL items that may be ready for stronger proof or PASS promotion."""

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
    "tools:live-feedback",
    "tools:app-ui-browser-smoke",
    "tools:accessibility-static-audit",
    "tools:localization-static-audit",
    "tools:privacy-static-audit",
    "tools:privacy-runtime-audit",
    "tools:privacy-live-storage-audit",
    "tools:safety-legal-static-audit",
    "tools:production-readiness-audit",
    "tools:ai-ui-intent-quality-replay",
    "analysis:",
    "python:",
)

HUMAN_QA_TERMS = (
    "human",
    "manual",
    "manual qa",
    "human ux",
    "human cultural",
    "qualified",
    "signs off",
    "signoff",
    "manual accessibility",
    "manual localization",
    "governance",
    "kept partial until",
    "still needs",
    "before pass",
    "until ",
    "needs real",
    "needs final",
    "needs public",
    "needs broader",
    "tested manually",
    "dry run",
    "drill",
    "confirmation before pass",
)

HIGH_RISK_CATEGORY_TERMS = (
    "safety",
    "privacy",
    "sensitive",
    "high-stakes",
    "production readiness",
    "accessibility",
    "localization",
)


def load_audit(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("audit file does not contain an items list")
    return data, items


def strong_evidence(evidence):
    strong = []
    for value in evidence or []:
        text = str(value or "").strip()
        if text.startswith(STRONG_PREFIXES):
            strong.append(text)
    return strong


def classify_item(item):
    category = str(item.get("category") or "")
    note = str(item.get("note") or "")
    evidence = [str(value).strip() for value in item.get("evidence") or [] if str(value).strip()]
    strong = strong_evidence(evidence)
    category_lower = category.lower()
    note_lower = note.lower()
    human_hold = any(term in note_lower for term in HUMAN_QA_TERMS)
    high_risk = any(term in category_lower for term in HIGH_RISK_CATEGORY_TERMS)
    if item.get("status") != "PARTIAL":
        bucket = "not-partial"
    elif human_hold:
        bucket = "human-qa-hold"
    elif len(strong) >= 3 and not high_risk:
        bucket = "promotion-candidate"
    elif len(strong) >= 3:
        bucket = "strong-evidence-needs-review"
    else:
        bucket = "needs-stronger-proof"
    return {
        "id": item.get("id"),
        "category": category,
        "question": item.get("question"),
        "bucket": bucket,
        "strongEvidenceCount": len(strong),
        "strongEvidence": strong[:8],
        "evidenceCount": len(evidence),
        "humanQaHold": human_hold,
        "highRiskCategory": high_risk,
        "note": note,
    }


def build_report(audit_path):
    data, items = load_audit(audit_path)
    partials = [item for item in items if str(item.get("status") or "").upper() == "PARTIAL"]
    classified = [classify_item(item) for item in partials]
    buckets = Counter(item["bucket"] for item in classified)
    by_category = defaultdict(Counter)
    for item in classified:
        by_category[item["category"]][item["bucket"]] += 1
    candidates = [item for item in classified if item["bucket"] == "promotion-candidate"]
    candidates.sort(key=lambda item: (-item["strongEvidenceCount"], item["category"], item["id"] or 0))
    strong_needs_review = [item for item in classified if item["bucket"] == "strong-evidence-needs-review"]
    strong_needs_review.sort(key=lambda item: (-item["strongEvidenceCount"], item["category"], item["id"] or 0))
    human_holds = [item for item in classified if item["bucket"] == "human-qa-hold"]
    human_holds.sort(key=lambda item: (item["category"], item["id"] or 0))
    needs_proof = [item for item in classified if item["bucket"] == "needs-stronger-proof"]
    needs_proof.sort(key=lambda item: (item["category"], item["id"] or 0))
    return {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceAudit": str(audit_path),
        "auditSummary": data.get("summary") if isinstance(data.get("summary"), dict) else {},
        "partialCount": len(partials),
        "bucketCounts": dict(sorted(buckets.items())),
        "byCategory": {category: dict(counter) for category, counter in sorted(by_category.items())},
        "promotionCandidates": candidates[:40],
        "strongEvidenceNeedsReview": strong_needs_review[:40],
        "humanQaHolds": human_holds[:40],
        "needsStrongerProof": needs_proof[:40],
    }


def write_outputs(report, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    json_path = output_dir / f"{stamp}-ai-ui-intent-promotion-candidates.json"
    md_path = output_dir / f"{stamp}-ai-ui-intent-promotion-candidates.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# AI UI Intent Promotion Candidates",
        "",
        f"- Source audit: `{report['sourceAudit']}`",
        f"- Partial items: {report['partialCount']}",
        f"- Buckets: `{json.dumps(report['bucketCounts'], sort_keys=True)}`",
        "",
        "## Promotion Candidates",
    ]
    for item in report["promotionCandidates"][:20]:
        lines.append(f"- Q{item['id']} ({item['category']}): {item['question']} [{item['strongEvidenceCount']} strong evidence receipts]")
    if not report["promotionCandidates"]:
        lines.append("- None")
    lines.extend(["", "## Strong Evidence, Still Needs Review"])
    for item in report["strongEvidenceNeedsReview"][:20]:
        lines.append(f"- Q{item['id']} ({item['category']}): {item['question']} [{item['strongEvidenceCount']} strong evidence receipts]")
    if not report["strongEvidenceNeedsReview"]:
        lines.append("- None")
    lines.extend(["", "## Human QA Holds"])
    for item in report["humanQaHolds"][:20]:
        lines.append(f"- Q{item['id']} ({item['category']}): {item['question']}")
    if not report["humanQaHolds"]:
        lines.append("- None")
    lines.extend(["", "## Needs Stronger Proof"])
    for item in report["needsStrongerProof"][:20]:
        lines.append(f"- Q{item['id']} ({item['category']}): {item['question']}")
    if not report["needsStrongerProof"]:
        lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Identify PARTIAL AI UI audit items that may be candidates for promotion.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--check", action="store_true", help="Validate that candidate classification works without writing files.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    audit_path = Path(args.audit).expanduser().resolve()
    report = build_report(audit_path)
    classified_total = sum(report["bucketCounts"].values())
    ok = (
        report["partialCount"] > 0
        and classified_total == report["partialCount"]
        and report["bucketCounts"].get("not-partial", 0) == 0
        and (
            report["bucketCounts"].get("promotion-candidate", 0) > 0
            or report["bucketCounts"].get("strong-evidence-needs-review", 0) > 0
            or report["bucketCounts"].get("human-qa-hold", 0) > 0
            or report["bucketCounts"].get("needs-stronger-proof", 0) > 0
        )
    )
    if args.check:
        result = {
            "ok": ok,
            "partialCount": report["partialCount"],
            "bucketCounts": report["bucketCounts"],
            "autoPromoteSafe": report["bucketCounts"].get("promotion-candidate", 0) > 0,
            "topCandidateIds": [item["id"] for item in report["promotionCandidates"][:10]],
            "topStrongEvidenceReviewIds": [item["id"] for item in report["strongEvidenceNeedsReview"][:10]],
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, sort_keys=True))
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
