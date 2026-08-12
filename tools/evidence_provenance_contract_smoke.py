#!/usr/bin/env python3
"""Focused adversarial regression for source-receipt evidence calibration."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from answer_envelope import (
    AnswerEnvelope,
    build_source_receipt,
    synthetic_envelope_check,
    text_sha256,
)


def envelope(text, run_id, evidence):
    return (
        AnswerEnvelope.from_text(text, objective="Check the evidence claim", run_id=run_id)
        .with_evidence(evidence)
        .finalize("complete")
    )


def main() -> int:
    invented_text = "The manufacturer confirms it: https://invented.invalid/datasheet"
    invented = envelope(
        invented_text,
        "run-invented",
        [
            {
                "title": "Manufacturer datasheet",
                "url": "https://invented.invalid/datasheet",
                "snippet": "Model-generated source text without retrieval.",
            }
        ],
    )

    web_text = "The checked source is https://example.test/datasheet"
    web_receipt = build_source_receipt(
        receipt_id="web-1",
        run_id="run-web",
        claim_text=web_text,
        source_type="web",
        locator="https://example.test/datasheet",
        content_sha256=text_sha256("retrieved web content"),
        observed_at="2026-08-06T06:20:00Z",
    )
    checked_web = envelope(web_text, "run-web", [web_receipt])

    local_text = "The checked local report records a passing result."
    local_receipt = build_source_receipt(
        receipt_id="local-1",
        run_id="run-local",
        claim_text=local_text,
        source_type="local-file",
        locator="/workspace/report.md",
        content_sha256=text_sha256("local report content"),
        observed_at="2026-08-06T06:20:01Z",
    )
    checked_local = envelope(local_text, "run-local", [local_receipt])

    vault_text = "The checked source-vault manual records the configured limit."
    vault_receipt = build_source_receipt(
        receipt_id="vault-1",
        run_id="run-vault",
        claim_text=vault_text,
        source_type="source-vault",
        locator="source-vault://3d-printing/manual-1",
        source_id="manual-1",
        content_sha256=text_sha256("cached source-vault content"),
        observed_at="2026-08-06T06:20:02Z",
    )
    checked_vault = envelope(vault_text, "run-vault", [vault_receipt])

    wrong_run = envelope(web_text, "run-other", [web_receipt])
    stale_claim = (
        AnswerEnvelope.from_text(web_text, objective="Check the evidence claim", run_id="run-web")
        .with_evidence([web_receipt])
        .revise(
            "A changed claim cites https://example.test/datasheet",
            "post-source-rewrite",
        )
        .finalize("complete")
    )
    mixed_url_text = (
        "The checked source is https://example.test/datasheet, while "
        "https://invented.invalid/extra was not retrieved."
    )
    mixed_url_receipt = build_source_receipt(
        receipt_id="web-2",
        run_id="run-mixed",
        claim_text=mixed_url_text,
        source_type="web",
        locator="https://example.test/datasheet",
        content_sha256=text_sha256("retrieved mixed web content"),
        observed_at="2026-08-06T06:20:03Z",
    )
    mixed_urls = envelope(mixed_url_text, "run-mixed", [mixed_url_receipt])
    unchecked_receipt = {
        **build_source_receipt(
            receipt_id="web-3",
            run_id="run-unchecked",
            claim_text=web_text,
            source_type="web",
            locator="https://example.test/datasheet",
            content_sha256=text_sha256("unreviewed content"),
            observed_at="2026-08-06T06:20:04Z",
        ),
        "state": "suggested",
    }
    unchecked = envelope(web_text, "run-unchecked", [unchecked_receipt])
    health = synthetic_envelope_check()

    checks = {
        "inventedUrlTextDoesNotGround": bool(
            invented.evidence_provenance.get("status") == "unverified"
            and not invented.evidence_provenance.get("mayClaimGrounded")
            and not invented.evidence_provenance.get("mayClaimCited")
            and "url-text-without-source-receipt"
            in (invented.evidence_provenance.get("issues") or [])
        ),
        "checkedWebReceiptGroundsMatchingUrl": bool(
            checked_web.evidence_provenance.get("status") == "verified"
            and checked_web.evidence_provenance.get("sourceTypes") == ["web"]
            and checked_web.evidence_provenance.get("mayClaimVerified")
        ),
        "typedLocalFileReceiptGrounds": bool(
            checked_local.evidence_provenance.get("status") == "verified"
            and checked_local.evidence_provenance.get("sourceTypes") == ["local-file"]
        ),
        "typedSourceVaultReceiptGrounds": bool(
            checked_vault.evidence_provenance.get("status") == "verified"
            and checked_vault.evidence_provenance.get("sourceTypes") == ["source-vault"]
        ),
        "wrongRunReceiptRejected": bool(
            wrong_run.evidence_provenance.get("status") == "unverified"
            and "source-receipt-run-mismatch"
            in (wrong_run.evidence_provenance.get("issues") or [])
        ),
        "staleClaimReceiptRejectedAfterRewrite": bool(
            stale_claim.evidence_provenance.get("status") == "unverified"
            and "source-receipt-claim-mismatch"
            in (stale_claim.evidence_provenance.get("issues") or [])
        ),
        "unreceiptedExtraUrlPreventsCitedStatus": bool(
            mixed_urls.evidence_provenance.get("status") == "partially-grounded"
            and not mixed_urls.evidence_provenance.get("mayClaimCited")
            and mixed_urls.evidence_provenance.get("unreceiptedAnswerUrls")
            == ["https://invented.invalid/extra"]
        ),
        "uncheckedReceiptRejected": bool(
            unchecked.evidence_provenance.get("status") == "unverified"
            and "source-not-checked" in (unchecked.evidence_provenance.get("issues") or [])
        ),
        "packageHealthEnvelopeInvariantPasses": health.get("status") == "pass",
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "samples": {
            "inventedUrl": invented.evidence_provenance,
            "checkedWeb": checked_web.evidence_provenance,
            "checkedLocal": checked_local.evidence_provenance,
            "checkedSourceVault": checked_vault.evidence_provenance,
            "wrongRun": wrong_run.evidence_provenance,
            "staleClaim": stale_claim.evidence_provenance,
            "mixedUrls": mixed_urls.evidence_provenance,
        },
        "envelopeHealth": health,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
