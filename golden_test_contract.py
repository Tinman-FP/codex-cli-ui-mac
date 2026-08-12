"""Presentation-neutral golden-test schema helpers.

This module intentionally has no server/runtime dependencies so producers,
batch runners, migration tools, and package-health checks share one contract.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


PRESENTATION_ONLY_POSITIVE_TERMS = frozenset(
    {
        "this is why",
        "you should also consider",
    }
)


def normalized_term(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).rstrip(":").strip()


def is_presentation_only_required_term(value: Any) -> bool:
    return normalized_term(value) in PRESENTATION_ONLY_POSITIVE_TERMS


def semantic_required_terms(terms: Iterable[Any] | None, limit: int = 8) -> list[str]:
    """Normalize required answer terms without spending slots on visible labels."""

    clean: list[str] = []
    for term in terms or ():
        value = re.sub(r"\s+", " ", str(term or "").strip().lower())[:80].strip()
        if not value or is_presentation_only_required_term(value) or value in clean:
            continue
        clean.append(value)
        if len(clean) >= max(0, int(limit)):
            break
    return clean


def semantic_answer_coverage(test: dict[str, Any] | None) -> dict[str, Any]:
    row = test if isinstance(test, dict) else {}
    answer_basis = []
    for key in ("requiredTerms", "directTerms", "anyTerms"):
        values = row.get(key)
        if isinstance(values, list) and any(str(value or "").strip() for value in values):
            answer_basis.append(key)
    contract_basis = []
    values = row.get("requiredContractProof")
    if isinstance(values, list) and any(str(value or "").strip() for value in values):
        contract_basis.append("requiredContractProof")
    return {
        "answerCovered": bool(answer_basis),
        "contractCovered": bool(contract_basis),
        "answerBasis": answer_basis,
        "contractBasis": contract_basis,
    }


def normalize_golden_test_presentation(
    test: dict[str, Any] | None,
    *,
    legacy: bool = False,
    enforce_direct_answer_coverage: bool = False,
) -> dict[str, Any]:
    """Remove presentation-only requirements and explicitly classify coverage.

    A test that loses its only positive answer expectation is kept as a truthful
    route/forbidden/contract guard. It no longer claims to verify a direct answer.
    """

    row = dict(test) if isinstance(test, dict) else {}
    removed_by_field: dict[str, int] = {}
    for key in ("requiredTerms", "directTerms", "anyTerms"):
        original = row.get(key) if isinstance(row.get(key), list) else []
        removed_by_field[key] = sum(1 for value in original if is_presentation_only_required_term(value))
        if original or key in row:
            row[key] = semantic_required_terms(original, limit=max(8, len(original)))
    removed = sum(removed_by_field.values())

    coverage = semantic_answer_coverage(row)
    prior = row.get("semanticCoverage") if isinstance(row.get("semanticCoverage"), dict) else {}
    if coverage["answerCovered"]:
        status = "semantic-answer"
    elif coverage["contractCovered"]:
        status = "contract-only"
    elif removed or (enforce_direct_answer_coverage and row.get("directAnswer")):
        status = "route-only-legacy" if legacy or prior.get("status") == "route-only-legacy" else "route-only-insufficient"
    else:
        status = str(prior.get("status") or "unclassified")

    if removed or prior or (enforce_direct_answer_coverage and row.get("directAnswer")):
        row["semanticCoverage"] = {
            "status": status,
            "answerBasis": coverage["answerBasis"],
            "contractBasis": coverage["contractBasis"],
            "presentationTermsRemoved": int(prior.get("presentationTermsRemoved") or removed),
            "presentationTermsRemovedByField": (
                prior.get("presentationTermsRemovedByField")
                if isinstance(prior.get("presentationTermsRemovedByField"), dict)
                else removed_by_field
            ),
        }
    if (removed or enforce_direct_answer_coverage) and not coverage["answerCovered"] and row.get("directAnswer"):
        row["legacyDirectAnswerClaim"] = True
        row["directAnswer"] = False
    return row


def golden_test_presentation_inventory(tests: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [row for row in tests or () if isinstance(row, dict)]
    affected = []
    removed_count = 0
    removed_by_field = {"requiredTerms": 0, "directTerms": 0, "anyTerms": 0}
    route_only = []
    semantic_answer = []
    contract_only = []
    for row in rows:
        counts = {}
        for key in removed_by_field:
            values = row.get(key) if isinstance(row.get(key), list) else []
            counts[key] = sum(1 for value in values if is_presentation_only_required_term(value))
            removed_by_field[key] += counts[key]
        count = sum(counts.values())
        if not count:
            continue
        affected.append(row)
        removed_count += count
        normalized = normalize_golden_test_presentation(row, legacy=True)
        coverage = semantic_answer_coverage(normalized)
        if coverage["answerCovered"]:
            semantic_answer.append(row)
        elif coverage["contractCovered"]:
            contract_only.append(row)
        else:
            route_only.append(row)
    return {
        "totalCount": len(rows),
        "presentationBoundCount": len(affected),
        "presentationTermCount": removed_count,
        "presentationTermCountByField": removed_by_field,
        "semanticAnswerAfterRemovalCount": len(semantic_answer),
        "contractOnlyAfterRemovalCount": len(contract_only),
        "contractOnlyIds": [str(row.get("id") or "") for row in contract_only],
        "contractOnlyDirectClaimCount": sum(bool(row.get("directAnswer")) for row in contract_only),
        "routeOnlyLegacyCount": len(route_only),
        "routeOnlyLegacyIds": [str(row.get("id") or "") for row in route_only],
        "routeOnlyDirectClaimCount": sum(bool(row.get("directAnswer")) for row in route_only),
    }
