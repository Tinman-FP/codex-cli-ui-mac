"""Deterministic eBay listing inspection and comparison helpers.

Search and HTTP transport stay in ``server.py`` so this module can be tested
without network access.  The module owns the marketplace-specific work:
recovering the product from conversation, parsing item pages, rejecting weak
matches, ranking viable listings, and explaining what remains unverified.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Sequence
from urllib.parse import urlparse


EBAY_ITEM_RE = re.compile(
    r"https?://(?:www\.)?ebay\.(?:com|ca|co\.uk|com\.au|de)/itm/(?:[^/?#]+/)?(\d+)",
    re.IGNORECASE,
)

SUBJECT_STOP_WORDS = {
    "a", "about", "again", "all", "and", "anything", "best", "buy", "can", "check", "checked",
    "checking", "compare", "completely", "condition", "cost", "current", "deal", "direct", "ebay",
    "eight", "exact", "find", "five", "for", "four", "from", "get", "give", "help", "history", "i",
    "in", "included", "listing", "listings", "manufacturer", "me", "model", "models", "new", "nine",
    "of", "on", "one", "open", "or", "please", "prefer", "price", "purchase", "returns",
    "review", "save", "search", "seller", "shipping", "shopping", "still", "the", "things", "this",
    "three", "to", "told", "two", "unverified", "verify", "want", "will", "would", "you", "six",
    "seven", "ten", "configuration", "configurations",
}

GENERIC_PRODUCT_WORDS = {
    "equipment", "item", "kit", "machine", "part", "product", "products", "system",
}

SEARCH_CATEGORY_WORDS = GENERIC_PRODUCT_WORDS | {
    "camera", "controller", "engraver", "fiber", "laser", "motor", "printer", "router", "sensor",
}


def _compact(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def _tokens(value: Any) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:[.+-][a-z0-9]+)*", str(value or "").lower())


def _message_text(message: Dict[str, Any]) -> str:
    """Read both API and internal message shapes without losing user intent."""

    value = message.get("text")
    if value in (None, ""):
        value = message.get("content")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and str(item.get("type") or "") in {"text", "input_text"}:
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in parts if part)
    return str(value or "")


def _latest_user_text(messages: Sequence[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role") or "").lower() == "user":
            return _message_text(message)
    return ""


def is_ebay_item_url(url: Any) -> bool:
    return bool(EBAY_ITEM_RE.search(str(url or "")))


def canonical_ebay_item_url(url: Any) -> str:
    match = EBAY_ITEM_RE.search(str(url or ""))
    return f"https://www.ebay.com/itm/{match.group(1)}" if match else ""


def ebay_item_id(url: Any) -> str:
    match = EBAY_ITEM_RE.search(str(url or ""))
    return match.group(1) if match else ""


def is_ebay_marketplace_request(messages: Sequence[Dict[str, Any]]) -> bool:
    users = [
        _message_text(message).lower()
        for message in messages[-8:]
        if str(message.get("role") or "").lower() == "user"
    ]
    if not users:
        return False
    latest = users[-1]
    marketplace_action = bool(
        re.search(r"\b(?:find|search|compare|check|review|shop|buy|deal|listing|listings)\b", latest)
    )
    explicit_ebay = "ebay" in latest or any(is_ebay_item_url(url) for url in re.findall(r"https?://\S+", latest))
    contextual_ebay = bool(
        marketplace_action
        and any("ebay" in text for text in users[-3:-1])
        and re.search(r"\b(?:those|them|listings|options|results)\b", latest)
    )
    return bool(marketplace_action and (explicit_ebay or contextual_ebay))


def derive_ebay_subject(messages: Sequence[Dict[str, Any]]) -> str:
    """Recover the actual product, including from a short eBay follow-up."""

    candidates = []
    user_messages = [
        _message_text(message)
        for message in messages[-10:]
        if str(message.get("role") or "").lower() == "user"
    ]
    for recency, text in enumerate(reversed(user_messages)):
        clean = re.sub(r"https?://\S+", " ", text)
        clean = re.split(
            r"(?i)[.!?;]\s*(?=(?:give|include|show|list|report|tell|compare|check|verify)\b)",
            clean,
            maxsplit=1,
        )[0]
        clean = re.sub(
            r"(?i)^.*?\bebay\b\s*(?:for\s+)?",
            "",
            clean,
            count=1,
        )
        clean = re.sub(
            r"(?i)^\s*(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+)?"
            r"(?:current\s+)?(?:active\s+)?(?:new\s+|used\s+|refurbished\s+)?"
            r"(?:item\s+pages?|listings?|options?|results?)\s+(?:for\s+|of\s+)?",
            "",
            clean,
            count=1,
        )
        clean = re.sub(r"(?i)^\s*(?:a|an|the)\s+", "", clean, count=1)
        clean = re.split(
            r"(?i)(?:[.!?;]\s*|\s+(?:and|then)\s+)(?=(?:open|check|compare|review|verify|inspect)\b)",
            clean,
            maxsplit=1,
        )[0]
        kept = [token for token in _tokens(clean) if token not in SUBJECT_STOP_WORDS]
        if not kept:
            continue
        meaningful = [token for token in kept if token not in GENERIC_PRODUCT_WORDS]
        spec_tokens = [token for token in kept if any(char.isdigit() for char in token)]
        product_signals = [
            token
            for token in kept
            if token in {
                "laser", "engraver", "printer", "motor", "controller", "cnc", "router",
                "camera", "sensor", "board", "lens", "spindle", "generator", "battery",
            }
        ]
        if len(meaningful) < 2 or not (product_signals or spec_tokens):
            continue
        score = len(meaningful) + 3 * len(spec_tokens) + 2 * len(product_signals) - recency * 0.15
        candidates.append((score, " ".join(kept[:12])))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return _compact(candidates[0][1], 120)


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def derive_marketplace_request_contract(messages: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Separate the product from comparison instructions and requested proof."""

    latest = _latest_user_text(messages)
    lower = latest.lower()
    count = 3
    count_match = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+"
        r"(?:current\s+|active\s+|new\s+|used\s+|refurbished\s+)*"
        r"(?:item\s+pages?|listings?|options?|results?)\b",
        lower,
    )
    if count_match:
        raw_count = count_match.group(1)
        count = int(raw_count) if raw_count.isdigit() else NUMBER_WORDS.get(raw_count, 3)
    count = max(1, min(count, 10))

    condition = ""
    for candidate in ("new", "used", "refurbished", "open box"):
        if re.search(rf"\b{re.escape(candidate)}\b", lower):
            condition = candidate
            break

    requested_fields = [
        "configuration",
        "price",
        "shipping",
        "deliveredPrice",
        "sellerFeedback",
        "condition",
    ]
    field_signals = (
        ("lensOrWorkArea", ("lens", "work area", "working area", "marking area", "marking size")),
        ("enclosure", ("enclosure", "enclosed")),
        ("rotary", ("rotary", "rotation axis")),
        ("software", ("software", "ezcad", "lightburn")),
        ("warrantyOrReturns", ("warranty", "return", "returns")),
    )
    for field, signals in field_signals:
        if any(signal in lower for signal in signals):
            requested_fields.append(field)
    return {
        "requestedCount": count,
        "condition": condition,
        "requestedFields": list(dict.fromkeys(requested_fields)),
        "explicitUnknowns": bool(
            re.search(r"\b(?:blocked?|could not|couldn't|cannot|can't|unverified|not verify|unknown)\b", lower)
        ),
    }


def marketplace_search_queries(subject: str) -> List[str]:
    subject = _compact(subject, 140)
    if not subject:
        return []
    distinctive = [token for token in _tokens(subject) if token not in SEARCH_CATEGORY_WORDS]
    queries = []
    if len(distinctive) >= 2:
        queries.append(f"site:ebay.com/itm {' '.join(distinctive[:7])}")
    queries.extend([
        f"site:ebay.com/itm {subject}",
        f'site:ebay.com/itm "{subject}"',
    ])
    return list(dict.fromkeys(queries))


def _money(value: str) -> float | None:
    try:
        return float(str(value or "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _first(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    return _compact(match.group(1), 160) if match else ""


def _field(text: str, label: str, next_labels: Iterable[str]) -> str:
    stops = "|".join(re.escape(value) for value in next_labels)
    return _first(rf"\b{re.escape(label)}\s+(.{{1,100}}?)(?=\s+(?:{stops})\b|$)", text)


def _first_field(text: str, labels: Iterable[str], next_labels: Iterable[str]) -> str:
    for label in labels:
        value = _field(text, label, next_labels)
        if value:
            return value
    return ""


def _title_claim(title: str, patterns: Iterable[str], value: str) -> str:
    return value if any(re.search(pattern, title, re.I) for pattern in patterns) else ""


def parse_listing(evidence: Dict[str, Any]) -> Dict[str, Any]:
    url = canonical_ebay_item_url(evidence.get("url"))
    text = _compact(evidence.get("text"), 100000)
    fetched = bool(evidence.get("fetched") and text)
    page_title = text.split(" | eBay", 1)[0].strip() if " | eBay" in text else ""
    title = page_title or re.sub(r"\s*[-|]\s*eBay\s*$", "", str(evidence.get("title") or ""), flags=re.I)
    title = _compact(title, 220)

    seller = ""
    feedback_count = None
    feedback_percent = None
    if title:
        seller_match = re.search(
            rf"\bShare\s+{re.escape(title)}\s+(.{{1,90}}?)\s+\(([\d,]+)\)\s+([\d.]+)%\s+positive",
            text,
            re.IGNORECASE,
        )
    else:
        seller_match = None
    if not seller_match:
        seller_match = re.search(r"\b([^()]{2,70}?)\s+\(([\d,]+)\)\s+([\d.]+)%\s+positive", text, re.I)
    if seller_match:
        seller = _compact(seller_match.group(1), 80)
        feedback_count = int(seller_match.group(2).replace(",", ""))
        feedback_percent = float(seller_match.group(3))
        seller_words = _tokens(seller)
        title_words = set(_tokens(title))
        if len(seller_words) > 5 and sum(word in title_words for word in seller_words) >= len(seller_words) // 2:
            seller = seller.split()[-1]

    price_match = re.search(r"\b(?:US\s*)?\$\s*([\d,]+(?:\.\d{2})?)(?:/ea)?", text, re.I)
    price = _money(price_match.group(1)) if price_match else None
    shipping_text = _first(r"\bShipping:\s*(.{1,180}?)(?=\s+(?:Located in:|Delivery:|Returns:|Payments:))", text)
    shipping_free = bool(re.search(r"\bfree\b", shipping_text, re.I))
    shipping_match = re.search(r"(?:US\s*)?\$\s*([\d,]+(?:\.\d{2})?)", shipping_text, re.I)
    shipping_cost = 0.0 if shipping_free else (_money(shipping_match.group(1)) if shipping_match else None)
    delivered_price = price + shipping_cost if price is not None and shipping_cost is not None else None

    returns_text = _first(r"\bReturns:\s*(.{1,160}?)(?=\s+(?:Payments:|Coverage:|About this item))", text)
    condition = _first(r"\bCondition:\s*([A-Za-z][A-Za-z -]{1,45}?)(?=\s+(?:New\b|Used\b|Quantity:|Buy It Now|Time left:))", text)
    if not condition:
        condition = _first(r"\bCondition\s+(New|Used|Open box|Seller refurbished|For parts or not working)\b", text)
    photo_count_raw = _first(r"\bPicture 1 of (\d+)\b", text)
    photo_count = int(photo_count_raw) if photo_count_raw.isdigit() else None
    item_number = _first(r"\beBay item number:\s*(\d+)", text) or ebay_item_id(url)
    available_raw = _first(r"\bQuantity:\s*(\d+)\s+available", text)
    sold_raw = _first(r"\b(\d+)\s+sold\b", text)
    serial_number = _first(r"\bserial(?: number| no\.?| #)?\s*[:#]?\s*([A-Z0-9-]{6,40})\b", text)
    location = _first(r"\bLocated in:\s*(.{1,100}?)(?=\s+Delivery:)", text)

    field_stops = (
        "Operating Voltage", "Software", "Marking Speed", "Windows Versions", "Image Format",
        "Quartz Lens", "Laser frequency", "Center wavelength", "UPC", "Category breadcrumb",
        "Manufacturer Warranty", "Warranty", "Lens", "Focal Length", "Marking size", "Marking Area",
        "Working Area", "Work Area", "Rotary Axis Included", "Enclosure Included", "Enclosure",
    )
    specifics = {
        "laserPower": _field(text, "Laser Power", ("Operating Voltage", "Software", "Marking Speed")),
        "laserModule": _field(text, "Brand Of Fiber Laser Module", ("Lift Span Of Fiber Laser Module", "Light Beam Quality", "Laser Diameter")),
        "software": _field(text, "Software", ("Marking Speed", "Windows Versions", "Image Format")),
        "markingSize": _first_field(text, ("Marking size", "Marking Area", "Working Area", "Work Area"), field_stops),
        "lens": _first_field(text, ("Lens", "Focal Length", "Field Lens"), field_stops),
        "rotaryIncluded": _field(text, "Rotary Axis Included", ("UPC", "Category breadcrumb")),
        "enclosure": _first_field(text, ("Enclosure Included", "Enclosure"), field_stops),
        "warranty": _first_field(text, ("Manufacturer Warranty", "Warranty"), field_stops),
    }
    if not specifics["rotaryIncluded"]:
        specifics["rotaryIncluded"] = _title_claim(
            title,
            (r"\bwith\s+(?:a\s+)?rotary\b", r"\brotary\s+axis\b", r"\brotary\s+included\b"),
            "mentioned in listing title",
        )
    if not specifics["lens"]:
        lens_count = _first(r"\b(\d+\s*(?:pcs?\s*)?lenses?)\b", title)
        specifics["lens"] = lens_count
    if not specifics["enclosure"]:
        specifics["enclosure"] = _title_claim(
            title,
            (r"\bfully\s+enclosed\b", r"\benclosure\s+included\b", r"\bwith\s+enclosure\b"),
            "mentioned in listing title",
        )
    specifics = {key: value for key, value in specifics.items() if value}

    purchase_protection_warning = bool(
        re.search(r"not eligible for eBay purchase protection", text, re.IGNORECASE)
    )
    return {
        "itemId": item_number,
        "url": url,
        "title": title,
        "fetched": fetched,
        "price": price,
        "shipping": shipping_text,
        "shippingCost": shipping_cost,
        "deliveredPrice": delivered_price,
        "condition": condition,
        "seller": seller,
        "feedbackCount": feedback_count,
        "feedbackPercent": feedback_percent,
        "returns": returns_text,
        "photoCount": photo_count,
        "available": int(available_raw) if available_raw.isdigit() else None,
        "sold": int(sold_raw) if sold_raw.isdigit() else None,
        "location": location,
        "serialNumber": serial_number,
        "specifics": specifics,
        "purchaseProtectionWarning": purchase_protection_warning,
        "sourceTextChars": len(text),
        # Keep a bounded excerpt from the trusted fetch boundary so the shared
        # answer envelope can bind visible item URLs to checked source receipts.
        "excerpt": _compact(text, 1800),
    }


def _subject_requirements(subject: str) -> List[str]:
    tokens = [
        token
        for token in _tokens(subject)
        if token not in SUBJECT_STOP_WORDS and token not in GENERIC_PRODUCT_WORDS
    ]
    return list(dict.fromkeys(tokens))


def _subject_match(listing: Dict[str, Any], subject: str) -> Dict[str, Any]:
    requirements = _subject_requirements(subject)
    haystack = " ".join(
        [str(listing.get("title") or "")] + [str(value) for value in (listing.get("specifics") or {}).values()]
    ).lower()
    matched = [token for token in requirements if token in _tokens(haystack) or token in haystack]
    ratio = len(matched) / len(requirements) if requirements else 0.0
    requested_powers = re.findall(r"\b(\d{2,4})\s*w\b", subject.lower())
    listed_powers = re.findall(r"\b(\d{2,4})\s*w\b", haystack)
    wrong_power = bool(requested_powers and listed_powers and requested_powers[0] not in listed_powers)
    missing = [token for token in requirements if token not in matched]
    exact = bool(requirements and ratio >= 0.72 and not wrong_power)
    return {"exact": exact, "ratio": round(ratio, 3), "matched": matched, "missing": missing, "wrongPower": wrong_power}


def compare_listings(
    listings: Sequence[Dict[str, Any]],
    subject: str,
    request_contract: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    contract = request_contract or {}
    requested_condition = str(contract.get("condition") or "").lower()
    prepared = []
    for source in listings:
        listing = dict(source)
        match = _subject_match(listing, subject)
        condition = str(listing.get("condition") or "").lower()
        title = str(listing.get("title") or "").lower()
        reject_reasons = []
        if not listing.get("fetched"):
            reject_reasons.append("item page could not be opened")
        if not match["exact"]:
            reject_reasons.append("does not match the requested product closely enough")
        if match["wrongPower"]:
            reject_reasons.append("listed power conflicts with the requested power")
        if "parts" in condition or "parts only" in title or "not working" in condition:
            reject_reasons.append("parts/not-working condition")
        if requested_condition and requested_condition not in condition:
            reject_reasons.append(f"condition is not verified as {requested_condition}")
        if listing.get("price") is None:
            reject_reasons.append("price was not verified")

        score = 45.0 * match["ratio"]
        if condition == "new":
            score += 5
        feedback_percent = listing.get("feedbackPercent")
        feedback_count = listing.get("feedbackCount")
        if feedback_percent is not None:
            score += max(0.0, min(12.0, (float(feedback_percent) - 94.0) * 2.0))
        if feedback_count is not None:
            score += min(6.0, math.log10(max(1, int(feedback_count))) * 2.0)
        if listing.get("shippingCost") == 0:
            score += 6
        if listing.get("returns"):
            score += 6
        if (listing.get("photoCount") or 0) >= 5:
            score += 4
        if listing.get("specifics"):
            score += min(6, len(listing["specifics"]) * 1.5)
        if listing.get("purchaseProtectionWarning"):
            score -= 12
        if reject_reasons:
            score -= 60
        listing["subjectMatch"] = match
        listing["rejectReasons"] = list(dict.fromkeys(reject_reasons))
        listing["viable"] = not reject_reasons
        listing["score"] = round(score, 2)
        prepared.append(listing)

    viable_prices = [
        float(item["deliveredPrice"])
        for item in prepared
        if item.get("viable") and item.get("deliveredPrice") is not None
    ]
    if viable_prices:
        low, high = min(viable_prices), max(viable_prices)
        for item in prepared:
            delivered = item.get("deliveredPrice")
            if item.get("viable") and delivered is not None:
                value_points = 10.0 if high == low else 20.0 * (high - float(delivered)) / (high - low)
                item["score"] = round(float(item["score"]) + value_points, 2)
    return sorted(
        prepared,
        key=lambda item: (
            bool(item.get("viable")),
            float(item.get("score") or -999),
            -float(item.get("deliveredPrice") or item.get("price") or 10**12),
        ),
        reverse=True,
    )


def _usd(value: Any) -> str:
    return f"${float(value):,.2f}" if value is not None else "not verified"


def _link(listing: Dict[str, Any]) -> str:
    title = str(listing.get("title") or f"eBay item {listing.get('itemId') or ''}").replace("[", "(").replace("]", ")")
    return f"[{title}]({listing.get('url')})"


def _verified_summary(listing: Dict[str, Any]) -> str:
    parts = []
    if listing.get("condition"):
        parts.append(str(listing["condition"]))
    if listing.get("seller"):
        seller = str(listing["seller"])
        if listing.get("feedbackPercent") is not None:
            seller += f" ({listing['feedbackPercent']:g}% positive"
            if listing.get("feedbackCount") is not None:
                seller += f", {listing['feedbackCount']:,} feedback"
            seller += ")"
        parts.append(seller)
    if listing.get("shippingCost") == 0:
        parts.append("free shipping")
    elif listing.get("shipping"):
        parts.append(f"shipping: {listing['shipping']}")
    if listing.get("returns"):
        parts.append(str(listing["returns"]))
    if listing.get("photoCount"):
        parts.append(f"{listing['photoCount']} listing photos")
    return "; ".join(parts)


def _listing_field(listing: Dict[str, Any], field: str) -> str:
    specifics = listing.get("specifics") or {}
    if field == "configuration":
        module = str(specifics.get("laserModule") or "").strip()
        return module or "exact source/configuration not stated"
    if field == "price":
        return _usd(listing.get("price"))
    if field == "shipping":
        if listing.get("shippingCost") == 0:
            return "free"
        if listing.get("shippingCost") is not None:
            return _usd(listing.get("shippingCost"))
        return "not verified"
    if field == "deliveredPrice":
        if listing.get("deliveredPrice") is not None:
            return _usd(listing.get("deliveredPrice")) + " before sales tax"
        return "not verified"
    if field == "sellerFeedback":
        seller = str(listing.get("seller") or "seller not verified")
        if listing.get("feedbackPercent") is not None:
            seller += f"; {listing['feedbackPercent']:g}% positive"
        if listing.get("feedbackCount") is not None:
            seller += f" ({listing['feedbackCount']:,})"
        return seller
    if field == "condition":
        return str(listing.get("condition") or "not verified")
    if field == "lensOrWorkArea":
        values = [
            str(specifics.get("lens") or "").strip(),
            str(specifics.get("markingSize") or "").strip(),
        ]
        return "; ".join(value for value in values if value) or "not verified"
    if field == "enclosure":
        return str(specifics.get("enclosure") or "not verified")
    if field == "rotary":
        return str(specifics.get("rotaryIncluded") or "not verified")
    if field == "software":
        return str(specifics.get("software") or "not verified")
    if field == "warrantyOrReturns":
        values = [
            str(specifics.get("warranty") or "").strip(),
            str(listing.get("returns") or "").strip(),
        ]
        return "; ".join(value for value in values if value) or "not verified"
    return "not verified"


FIELD_LABELS = {
    "configuration": "Exact configuration",
    "price": "Listed price",
    "shipping": "Shipping",
    "deliveredPrice": "Price + shipping",
    "sellerFeedback": "Seller / feedback",
    "condition": "Condition",
    "lensOrWorkArea": "Lens / work area",
    "enclosure": "Enclosure",
    "rotary": "Rotary",
    "software": "Software",
    "warrantyOrReturns": "Warranty / returns",
}


def render_comparison(
    subject: str,
    ranked: Sequence[Dict[str, Any]],
    access_mode: str,
    request_contract: Dict[str, Any] | None = None,
) -> str:
    contract = request_contract or {}
    requested_count = max(1, min(int(contract.get("requestedCount") or 3), 10))
    requested_fields = list(contract.get("requestedFields") or FIELD_LABELS)
    viable = [item for item in ranked if item.get("viable")]
    rejected = [item for item in ranked if not item.get("viable")]
    fetched_count = sum(1 for item in ranked if item.get("fetched"))
    if not viable:
        return (
            f"I searched eBay for **{subject}** and opened {fetched_count} item page(s), but none had enough verified "
            "detail to call a defensible best deal. I would rather leave the ranking blank than rank search snippets, "
            "wrong-power products, parts-only listings, or listings whose price could not be confirmed."
        )

    best = viable[0]
    delivered = best.get("deliveredPrice")
    price_phrase = (
        f"{_usd(delivered)} delivered before sales tax"
        if delivered is not None
        else f"{_usd(best.get('price'))} plus unverified shipping and tax"
    )
    lines = [
        f"I checked {fetched_count} live eBay item page(s) for **{subject}**, not just the search-result titles.",
        "",
        f"**Best deal I could verify:** {_link(best)} — **{price_phrase}**.",
        "",
        f"It won because it matched the requested product and had the strongest combination of price and buyer protection signals. I verified: {_verified_summary(best)}.",
    ]
    specifics = best.get("specifics") or {}
    if specifics:
        readable = {
            "laserPower": "laser power",
            "laserModule": "laser source",
            "software": "software",
            "markingSize": "marking area",
            "rotaryIncluded": "rotary included",
        }
        lines.extend(
            [
                "",
                "The listing itself states "
                + ", ".join(f"{readable.get(key, key)}: {value}" for key, value in specifics.items())
                + ".",
            ]
        )
    unknowns = []
    if not best.get("serialNumber"):
        unknowns.append("the JPT source serial number and manufacturer authentication")
    if best.get("shippingCost") is None:
        unknowns.append("the final shipping charge")
    unknowns.extend(["sales tax", "the exact warranty owner", "every included accessory unless shown in the description/photos"])
    if best.get("purchaseProtectionWarning"):
        unknowns.append("normal eBay purchase-protection eligibility; the page showed a coverage warning")
    lines.extend(
        [
            "",
            "**Still unverified:** " + "; ".join(dict.fromkeys(unknowns)) + ". Those require the seller's documentation or checkout, so I would ask before paying rather than present them as checked facts.",
        ]
    )

    compared = viable[:requested_count]
    if compared:
        lines.extend(["", f"**Checked comparison ({len(compared)} listing{'s' if len(compared) != 1 else ''}):**"])
        headers = ["Listing"] + [FIELD_LABELS.get(field, field) for field in requested_fields]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for item in compared:
            cells = [_link(item)] + [_listing_field(item, field) for field in requested_fields]
            cells = [str(cell).replace("|", "/").replace("\n", " ") for cell in cells]
            lines.append("| " + " | ".join(cells) + " |")

    if len(compared) < requested_count:
        lines.extend(
            [
                "",
                f"I could verify only {len(compared)} of the {requested_count} requested listing(s). "
                "I am leaving the missing slot(s) blank instead of promoting incomplete or mismatched pages.",
            ]
        )

    if rejected:
        lines.extend(["", "**Rejected or not fully checked:**"])
        for item in rejected[:4]:
            reasons = "; ".join(item.get("rejectReasons") or ["insufficient listing evidence"])
            lines.append(f"- {_link(item)} — {reasons}.")

    lines.extend(
        [
            "",
            f"Access used: {access_mode}. Every title above is a clickable exact item page. Prices and availability can change after this check.",
        ]
    )
    return "\n".join(lines)


def synthetic_check() -> Dict[str, Any]:
    messages = [
        {"role": "user", "text": "Find the best deal on a 100W JPT MOPA fiber laser."},
        {"role": "assistant", "text": "I will compare the current options."},
        {"role": "user", "text": "Find me the best deal on eBay and check the listings completely."},
    ]
    subject = derive_ebay_subject(messages)
    detailed_subject = derive_ebay_subject(
        [
            {
                "role": "user",
                "content": (
                    "Search eBay for three current listings for a new 100W JPT MOPA fiber laser. "
                    "Give me the exact configuration, price plus shipping, seller feedback, lens or work area, "
                    "enclosure, rotary, software, warranty or returns, and clickable links."
                ),
            }
        ]
    )
    good_text = (
        "100W JPT MOPA Fiber Laser | eBay Share 100W JPT MOPA Fiber Laser Trusted Tools "
        "(1200) 99.8% positive US $2,999.00/ea Condition: New New Quantity: 2 available "
        "Picture 1 of 12 Shipping: Free FedEx Located in: CA, United States Delivery: soon "
        "Returns: 30 days returns. Seller pays for return shipping. Payments: card "
        "eBay item number: 123456789012 Laser Power 100W Operating Voltage 110V "
        "Brand Of Fiber Laser Module JPT M7 Lift Span Of Fiber Laser Module 100000 hours "
        "Software EZCAD2 Marking Speed 8000 Rotary Axis Included Yes UPC none"
    )
    wrong_text = (
        "60W generic fiber laser parts only | eBay Share 60W generic fiber laser parts only Parts Shop "
        "(12) 95.0% positive US $999.00 Condition: For parts or not working Quantity: 1 available "
        "Shipping: US $250.00 Located in: NY Delivery: later Returns: No returns Payments: card "
        "eBay item number: 999999999999 Laser Power 60W Operating Voltage 110V"
    )
    good = parse_listing({"url": "https://www.ebay.com/itm/123456789012?x=1", "text": good_text, "fetched": True})
    wrong = parse_listing({"url": "https://www.ebay.com/itm/999999999999", "text": wrong_text, "fetched": True})
    ranked = compare_listings([wrong, good], subject)
    contract = derive_marketplace_request_contract(messages)
    live_contract = derive_marketplace_request_contract(
        [
            {
                "role": "user",
                "content": (
                    "Search eBay for three current listings for a new 100W JPT MOPA fiber laser. "
                    "Give me the exact configuration, price plus shipping, seller feedback, lens or work area, "
                    "enclosure, rotary, software, warranty or returns, and clickable links."
                ),
            }
        ]
    )
    rendered = render_comparison(subject, ranked, "free public eBay item pages", contract)
    checks = {
        "followupSubject": "100w" in subject and "jpt" in subject and "mopa" in subject,
        "detailedOneTurnSubject": detailed_subject == "100w jpt mopa fiber laser",
        "canonicalUrl": good.get("url") == "https://www.ebay.com/itm/123456789012",
        "exactWins": ranked[0].get("itemId") == "123456789012" and ranked[0].get("viable"),
        "wrongPowerRejected": not next(item for item in ranked if item.get("itemId") == "999999999999").get("viable"),
        "clickable": "[100W JPT MOPA Fiber Laser](https://www.ebay.com/itm/123456789012)" in rendered,
        "uncertainty": "Still unverified" in rendered and "serial number" in rendered,
        "requestContract": contract.get("requestedCount") == 3 and contract.get("condition") == "",
        "apiMessageShape": (
            detailed_subject == "100w jpt mopa fiber laser"
            and live_contract.get("requestedCount") == 3
            and live_contract.get("condition") == "new"
            and set(live_contract.get("requestedFields") or [])
            >= {"lensOrWorkArea", "enclosure", "rotary", "software", "warrantyOrReturns"}
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "subject": subject,
    }
