#!/usr/bin/env python3
"""Offline, live-shaped regression for eBay marketplace research."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from ebay_marketplace import synthetic_check  # noqa: E402


GOOD_TEXT = (
    "100W JPT MOPA Fiber Laser Engraver | eBay Share 100W JPT MOPA Fiber Laser Engraver "
    "Trusted Machinery (1508) 100% positive US $2,999.00/ea or Best Offer Condition: New New "
    "Quantity: 5 available 1 sold Picture 1 of 24 Shipping: Free FedEx Ground Located in: CA, "
    "United States Delivery: soon Returns: 30 days returns. Seller pays for return shipping. "
    "Payments: card eBay item number: 397341552773 Laser Power 100W Operating Voltage 110V "
    "Software EZCAD2 Marking Speed 8000 Brand Of Fiber Laser Module JPT M7 "
    "Lift Span Of Fiber Laser Module 100000 hours Marking Area 175x175mm Quartz Lens F254 "
    "Rotary Axis Included Yes Enclosure Included No Manufacturer Warranty 1 year UPC none"
)

WRONG_TEXT = (
    "60W generic fiber laser parts only | eBay Share 60W generic fiber laser parts only Parts Seller "
    "(8) 94.0% positive US $799.00 Condition: For parts or not working Quantity: 1 available "
    "Picture 1 of 2 Shipping: US $250.00 Located in: NY Delivery: later Returns: No returns "
    "Payments: card eBay item number: 111111111111 Laser Power 60W Operating Voltage 110V"
)


def main() -> int:
    module_report = synthetic_check()
    messages = [
        {
            "role": "user",
            "content": (
                "Search eBay for three current listings for a new 100W JPT MOPA fiber laser. "
                "Give me the exact model or configuration, total listed price plus shipping, seller feedback, "
                "included lens or work area, enclosure, rotary, software, warranty or returns, and clickable links. "
                "If eBay blocks a field, say exactly which field could not be verified."
            ),
        },
    ]
    route = server.route_manager(messages, cwd=str(ROOT), web_search="disabled")
    original_api = server.ebay_browse_api_candidates
    original_search = server.search_web_free
    original_extract = server.extract_page_evidence

    def fake_api(_subject, limit=12):
        return []

    def fake_search(_query, limit=10):
        return [
            {
                "title": "100W candidate",
                "url": "https://www.ebay.com/itm/397341552773?campaign=tracking",
                "snippet": "search snippet",
            },
            {
                "title": "wrong candidate",
                "url": "https://www.ebay.com/itm/111111111111",
                "snippet": "search snippet",
            },
            {
                "title": "not a listing",
                "url": "https://example.com/top-ten-lasers",
                "snippet": "guide",
            },
        ]

    def fake_extract(item, query=""):
        text = GOOD_TEXT if "397341552773" in item["url"] else WRONG_TEXT
        return {**item, "text": text, "fetched": True}

    try:
        server.ebay_browse_api_candidates = fake_api
        server.search_web_free = fake_search
        server.extract_page_evidence = fake_extract
        result = server.run_local_research(messages, route, web_search="disabled")
    finally:
        server.ebay_browse_api_candidates = original_api
        server.search_web_free = original_search
        server.extract_page_evidence = original_extract

    answer = str(result.get("text") or "")
    marketplace = result.get("marketplace") or {}
    emission_policy = server.research_result_emission_policy(route, result)
    route["_liveRunId"] = "ebay-marketplace-smoke"
    source_receipts = server.response_source_receipts(
        answer,
        route,
        result.get("evidence") or [],
        run_id="ebay-marketplace-smoke",
    )
    source_provenance = server.source_provenance_contract(
        answer,
        source_receipts,
        run_id="ebay-marketplace-smoke",
    )
    checks = {
        "module": module_report.get("status") == "pass",
        "route": (
            route.get("engine") == "local-research"
            and (route.get("capabilityPlan") or {}).get("id") == "ebay-marketplace-research"
            and (route.get("intentFrame") or {}).get("domain") == "marketplace_listing_research"
            and "explicitly requested" in str((route.get("kernelDecision") or {}).get("reason") or "")
        ),
        "executor": result.get("model") == "ebay-marketplace-research",
        "toolOwnsFinalAnswer": (
            emission_policy.get("evidenceOwned") is True
            and emission_policy.get("allowManagerRewrite") is False
            and emission_policy.get("allowSupervisorRewrite") is False
            and emission_policy.get("textLocked") is True
        ),
        "subjectContinuity": marketplace.get("subject") == "100w jpt mopa fiber laser",
        "requestContract": (
            (marketplace.get("requestContract") or {}).get("requestedCount") == 3
            and (marketplace.get("requestContract") or {}).get("condition") == "new"
        ),
        "exactItemOnly": marketplace.get("candidateCount") == 2,
        "fetchedBeforeRanking": marketplace.get("fetchedCount") == 2,
        "wrongPowerRejected": marketplace.get("viableCount") == 1,
        "clickableRecommendation": (
            "[100W JPT MOPA Fiber Laser Engraver](https://www.ebay.com/itm/397341552773)" in answer
        ),
        "noAccessDenial": "can't pull current ebay" not in answer.lower(),
        "unknownsDisclosed": "Still unverified" in answer and "serial number" in answer,
        "requestedFieldsRendered": all(
            label in answer
            for label in (
                "Exact configuration",
                "Listed price",
                "Shipping",
                "Price + shipping",
                "Seller / feedback",
                "Lens / work area",
                "Enclosure",
                "Rotary",
                "Software",
                "Warranty / returns",
            )
        ),
        "unverifiedCellsExplicit": "not verified" in answer,
        "sourceReceiptsBindEveryVisibleItemUrl": (
            len(source_receipts) == 2
            and source_provenance.get("status") == "verified"
            and source_provenance.get("mayClaimGrounded") is True
            and source_provenance.get("unreceiptedAnswerUrls") == []
        ),
    }
    output = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "module": module_report,
        "marketplace": marketplace,
        "sourceProvenance": source_provenance,
    }
    print(json.dumps(output, indent=2))
    return 0 if output["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
