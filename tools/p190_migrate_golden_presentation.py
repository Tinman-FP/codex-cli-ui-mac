#!/usr/bin/env python3
"""Atomically migrate saved golden tests away from visible answer scaffolds."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from golden_test_contract import (  # noqa: E402
    golden_test_presentation_inventory,
    is_presentation_only_required_term,
    normalize_golden_test_presentation,
    semantic_answer_coverage,
)


SOURCE = APP_DIR / "data" / "golden_tests.json"
RECEIPT = APP_DIR / "data" / "golden_test_migrations" / "p190-natural-presentation.json"
VERIFICATION = APP_DIR / "data" / "golden_test_migrations" / "p190-natural-presentation-latest-verification.json"
MIGRATION_ID = "p190-natural-presentation-v1"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def migrate(data: dict) -> tuple[dict, dict]:
    rows = data.get("tests") if isinstance(data.get("tests"), list) else []
    before = golden_test_presentation_inventory(rows)
    migrated = []
    for row in rows:
        normalized = normalize_golden_test_presentation(
            row,
            legacy=True,
            enforce_direct_answer_coverage=True,
        )
        migrated.append(normalized)
    after = golden_test_presentation_inventory(migrated)
    status_counts: dict[str, int] = {}
    for row in migrated:
        status = str((row.get("semanticCoverage") or {}).get("status") or "unclassified")
        status_counts[status] = status_counts.get(status, 0) + 1

    output = dict(data)
    output["version"] = max(2, int(output.get("version") or 1))
    output["schema"] = "presentation-neutral-golden-test-v2"
    output["tests"] = migrated
    output["migration"] = {
        "id": MIGRATION_ID,
        "presentationOnlyTermsAllowed": False,
        "semanticCoverageStatusRequiredForMigratedRows": True,
    }
    receipt = {
        "migrationId": MIGRATION_ID,
        "before": before,
        "after": {
            **after,
            "presentationBoundCount": sum(
                any(
                    is_presentation_only_required_term(value)
                    for key in ("requiredTerms", "directTerms", "anyTerms")
                    for value in row.get(key) or []
                )
                for row in migrated
            ),
            "coverageStatusCounts": status_counts,
        },
        "backfilledCount": 0,
        "archivedCount": 0,
        "historicalSemanticSlotsLostToPriorLimits": "unknown-and-not-claimed-restored",
        "routeOnlyLegacyCount": before["routeOnlyLegacyCount"],
        "contractOnlyCount": before["contractOnlyAfterRemovalCount"],
        "semanticAnswerCount": before["semanticAnswerAfterRemovalCount"],
        "directAnswerClaimsDemoted": sum(
            bool(old.get("directAnswer")) and not bool(new.get("directAnswer"))
            for old, new in zip(rows, migrated)
        ),
        "uncoveredDirectAnswerClaimsAfter": sum(
            bool(row.get("directAnswer")) and not semantic_answer_coverage(row)["answerCovered"]
            for row in migrated
        ),
    }
    return output, receipt


def current_verification(data: dict, source_bytes: bytes) -> dict:
    rows = data.get("tests") if isinstance(data.get("tests"), list) else []
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str((row.get("semanticCoverage") or {}).get("status") or "unclassified")
        status_counts[status] = status_counts.get(status, 0) + 1
    inventory = golden_test_presentation_inventory(rows)
    uncovered = [
        str(row.get("id") or "")
        for row in rows
        if row.get("directAnswer") and not semantic_answer_coverage(row)["answerCovered"]
    ]
    demoted_ids = sorted(
        str(row.get("id") or "") for row in rows if row.get("legacyDirectAnswerClaim")
    )
    return {
        "migrationId": MIGRATION_ID,
        "status": "pass" if inventory["presentationBoundCount"] == 0 and not uncovered else "fail",
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "sourceSha256": sha256_bytes(source_bytes),
        "testCount": len(rows),
        "presentationBoundCount": inventory["presentationBoundCount"],
        "presentationTermCountByField": inventory["presentationTermCountByField"],
        "coverageStatusCounts": status_counts,
        "uncoveredDirectAnswerClaimIds": uncovered,
        "directAnswerClaimsDemotedTotal": len(demoted_ids),
        "directAnswerClaimDemotedIdsSha256": sha256_bytes("\n".join(demoted_ids).encode("utf-8")),
    }


def immutable_event_from_evidence(evidence: dict) -> dict:
    before = evidence.get("initialBefore") or evidence.get("before") or {}
    return {
        "status": "applied",
        "appliedAt": evidence.get("appliedAt"),
        "sourceSha256Before": evidence.get("sourceSha256Before"),
        "sourceSha256After": evidence.get("sourceSha256After"),
        "before": before,
        "presentationBoundCount": before.get("presentationBoundCount"),
        "presentationTermCount": before.get("presentationTermCount"),
        "presentationTermCountByField": before.get("presentationTermCountByField"),
        "semanticAnswerCount": evidence.get("semanticAnswerCount")
        if evidence.get("semanticAnswerCount") is not None
        else before.get("semanticAnswerAfterRemovalCount"),
        "contractOnlyCount": evidence.get("contractOnlyCount")
        if evidence.get("contractOnlyCount") is not None
        else before.get("contractOnlyAfterRemovalCount"),
        "routeOnlyLegacyCount": evidence.get("routeOnlyLegacyCount")
        if evidence.get("routeOnlyLegacyCount") is not None
        else before.get("routeOnlyLegacyCount"),
        "directAnswerClaimsDemoted": evidence.get("directAnswerClaimsDemoted"),
        "backfilledCount": 0,
        "archivedCount": 0,
        "historicalSemanticSlotsLostToPriorLimits": "unknown-and-not-claimed-restored",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--event-evidence", default="")
    args = parser.parse_args()
    original_bytes = SOURCE.read_bytes()
    data = json.loads(original_bytes)
    previous_receipt = {}
    if RECEIPT.exists():
        try:
            previous_receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_receipt = {}
    already_applied = (data.get("migration") or {}).get("id") == MIGRATION_ID
    if args.apply and already_applied:
        evidence = {}
        if args.event_evidence:
            evidence = json.loads(Path(args.event_evidence).read_text(encoding="utf-8"))
        prior_event = previous_receipt.get("event") if isinstance(previous_receipt.get("event"), dict) else {}
        event = prior_event or immutable_event_from_evidence(evidence or previous_receipt)
        verification = current_verification(data, original_bytes)
        initial_demotions = int(event.get("directAnswerClaimsDemoted") or 0)
        payload = {
            "migrationId": MIGRATION_ID,
            "status": "pass" if event.get("presentationBoundCount") and verification["status"] == "pass" else "fail",
            "immutableEvent": True,
            "event": event,
            "reconciliation": {
                "additionalPreexistingDirectClaimsDemoted": max(
                    0, verification["directAnswerClaimsDemotedTotal"] - initial_demotions
                ),
                "directAnswerClaimsDemotedTotal": verification["directAnswerClaimsDemotedTotal"],
                "backfilledCount": 0,
                "archivedCount": 0,
            },
            "latestVerificationPath": str(VERIFICATION),
        }
        if not prior_event:
            atomic_json_write(RECEIPT, payload)
        atomic_json_write(VERIFICATION, verification)
        print(json.dumps({**payload, "verification": verification}, sort_keys=True))
        return 0 if payload["status"] == "pass" else 1

    output, receipt = migrate(data)
    output_bytes = (json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    receipt.update({"status": "pass", "source": str(SOURCE), "sourceSha256Before": sha256_bytes(original_bytes), "sourceSha256After": sha256_bytes(output_bytes), "applied": bool(args.apply)})
    if args.apply:
        applied_at = datetime.now(timezone.utc).isoformat()
        output["migration"]["appliedAt"] = applied_at
        output["updatedAt"] = applied_at
        atomic_json_write(SOURCE, output)
        final_bytes = SOURCE.read_bytes()
        receipt["sourceSha256After"] = sha256_bytes(final_bytes)
        receipt["appliedAt"] = applied_at
        event = immutable_event_from_evidence(receipt)
        verification = current_verification(output, final_bytes)
        atomic_json_write(
            RECEIPT,
            {
                "migrationId": MIGRATION_ID,
                "status": "pass",
                "immutableEvent": True,
                "event": event,
                "reconciliation": {
                    "additionalPreexistingDirectClaimsDemoted": 0,
                    "directAnswerClaimsDemotedTotal": verification["directAnswerClaimsDemotedTotal"],
                    "backfilledCount": 0,
                    "archivedCount": 0,
                },
                "latestVerificationPath": str(VERIFICATION),
            },
        )
        atomic_json_write(VERIFICATION, verification)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
