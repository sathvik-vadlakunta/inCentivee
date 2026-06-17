"""Google Places API (New) integration for business verification.

Verifies customer business data against Google's database:
- Confirms name, address, phone, website
- Gets real Google review count and rating
- Finds nearby competitors (vertical-aware: dental, legal, medical)
- Validates competitors are same-industry via name keywords + website content

Uses the Places API (New) endpoints:
- places:searchText for business lookup
- places:searchNearby for competitor discovery
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Fields we request (controls billing — only request what we need)
PLACE_FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.location",
    "places.businessStatus",
]

COMPETITOR_FIELDS = [
    "places.id",
    "places.displayName",
    "places.rating",
    "places.userRatingCount",
    "places.formattedAddress",
    "places.websiteUri",
    "places.primaryType",
]

# Vertical-aware place types for Google Places searches
# See: https://developers.google.com/maps/documentation/places/web-service/place-types
VERTICAL_PLACE_TYPES: dict[str, list[str]] = {
    "practice": ["dentist"],
    "legal": ["lawyer"],
    "medical": ["doctor", "hospital"],
    "retail": ["store"],
    "restaurant": ["restaurant", "cafe"],
    "service": [],       # too broad — use text search fallback
    "technology": [],    # no good Places type — use text search fallback
    "ecommerce": [],     # no good Places type — use text search fallback
    "finance": ["accounting"],
    "real_estate": ["real_estate_agency"],
    "fitness": ["gym"],
    "salon": ["beauty_salon", "hair_care"],
    "auto": ["car_dealer", "car_repair"],
    "jewelry": ["jewelry_store"],
    "precious_metals_buyer": ["jewelry_store"],  # closest type; refined by text search
    "product": [],       # no good Places type — use text search fallback
}

# Filler words to ignore in name similarity comparison
_NAME_FILLER = {
    "the", "and", "of", "at", "in", "for", "a", "an",
    "law", "firm", "group", "office", "offices", "associates",
    "dental", "medical", "clinic", "practice", "center", "centre",
    "llc", "inc", "pllc", "llp", "pc", "pa",
    "dds", "dmd", "esq", "md", "do",
}

# Per-vertical: name keywords that indicate a wrong-industry competitor
EXCLUDE_KEYWORDS: dict[str, list[str]] = {
    "practice": [
        "veterinar", "vet clinic", "animal hospital",
        "medical center", "hospital",
        "lawyer", "attorney", "law firm", "law office",
    ],
    "legal": [
        "tax relief", "accounting", "cpa", "financial advisor",
        "real estate agent", "realtor", "insurance agent",
        "bail bond", "notary",
        "dental", "dentist", "orthodont",
    ],
    "medical": [
        "veterinar", "vet clinic", "animal hospital",
        "dental", "dentist", "orthodont",
        "lawyer", "attorney", "law firm", "law office",
        "spa", "massage", "acupuncture",
    ],
    "retail": ["dental", "dentist", "doctor", "lawyer", "attorney", "law firm", "law office"],
    "restaurant": ["dental", "dentist", "doctor", "lawyer"],
    "service": ["dental", "dentist", "doctor", "lawyer", "restaurant"],
    "technology": ["dental", "dentist", "doctor", "lawyer", "restaurant"],
    "ecommerce": ["dental", "dentist", "doctor", "lawyer"],
    "finance": ["dental", "dentist", "lawyer", "restaurant"],
    "real_estate": ["dental", "dentist", "doctor", "lawyer"],
    "fitness": ["dental", "dentist", "doctor", "lawyer"],
    "salon": ["dental", "dentist", "doctor", "lawyer"],
    "auto": ["dental", "dentist", "doctor", "lawyer"],
    "jewelry": ["dental", "dentist", "doctor", "lawyer", "restaurant"],
    "precious_metals_buyer": ["dental", "dentist", "doctor", "orthodont", "lawyer", "attorney", "restaurant", "salon", "veterinar"],
    "product": ["dental", "dentist", "doctor", "lawyer", "restaurant"],
}

# Per-vertical: keywords expected on a same-industry website
INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "practice": ["dental", "dentist", "orthodont", "teeth", "oral"],
    "legal": ["law", "attorney", "lawyer", "legal", "litigation", "practice area"],
    "medical": ["medical", "doctor", "physician", "patient", "health", "clinic"],
    "retail": ["shop", "store", "buy", "product", "price", "sale"],
    "restaurant": ["menu", "dining", "reservation", "food", "chef"],
    "service": ["service", "solution", "client", "consultation"],
    "technology": ["software", "platform", "technology", "solution", "saas", "api"],
    "ecommerce": ["shop", "cart", "buy", "product", "shipping", "order"],
    "finance": ["financial", "accounting", "tax", "bookkeeping", "advisory"],
    "real_estate": ["real estate", "property", "listing", "agent", "broker", "home"],
    "fitness": ["fitness", "gym", "workout", "training", "membership", "class"],
    "salon": ["salon", "beauty", "hair", "spa", "stylist", "nail"],
    "auto": ["auto", "car", "vehicle", "dealer", "repair", "service"],
    "jewelry": ["jewelry", "gold", "silver", "diamond", "gem", "ring", "watch", "buy", "sell"],
    # Primary: buying gold & silver; secondary: jewelry store.
    "precious_metals_buyer": ["gold", "silver", "coin", "bullion", "metals", "buy", "sell",
                              "cash for gold", "pawn", "jewelry", "diamond", "watch", "appraisal"],
    "product": ["product", "buy", "shop", "order", "price"],
}


@dataclass
class VerifiedBusinessData:
    """Business data verified via Google Places API."""

    place_id: str
    name: str
    address: str
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    rating: float = 0.0
    review_count: int = 0
    website: str = ""
    lat: float = 0.0
    lng: float = 0.0
    business_status: str = ""
    domain_match: bool = False
    name_match: bool = False
    match_confidence: str = "low"  # "high", "medium", "low"


@dataclass
class CompetitorData:
    """Nearby competitor from Google Places."""

    name: str
    place_id: str
    rating: float = 0.0
    review_count: int = 0
    address: str = ""
    website: str = ""
    primary_type: str = ""


def _normalize_domain(url_or_domain: str) -> str:
    """Extract bare domain from a URL or domain string."""
    if not url_or_domain:
        return ""
    if "://" not in url_or_domain:
        url_or_domain = "https://" + url_or_domain
    parsed = urlparse(url_or_domain)
    domain = parsed.hostname or ""
    return domain.lower().removeprefix("www.")


def _normalize_phone(phone: str) -> str:
    """Strip a phone string to digits only for comparison."""
    return re.sub(r"\D", "", phone or "")


def _name_similarity(a: str, b: str) -> float:
    """Word-level name similarity (0.0 to 1.0), ignoring filler words."""
    if not a or not b:
        return 0.0
    words_a = {w for w in re.sub(r"[^a-z0-9\s]", "", a.lower()).split() if w not in _NAME_FILLER}
    words_b = {w for w in re.sub(r"[^a-z0-9\s]", "", b.lower()).split() if w not in _NAME_FILLER}
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    return overlap / max(len(words_a), len(words_b))


def get_place_types(business_type: str) -> list[str]:
    """Get the Google Places includedTypes for a business type."""
    return VERTICAL_PLACE_TYPES.get(business_type, [])


def _extract_address_component(components: list[dict], component_type: str) -> str:
    """Extract a specific address component from the Places API response."""
    for comp in components:
        if component_type in comp.get("types", []):
            return comp.get("longText", "")
    return ""


def _parse_place(place: dict) -> VerifiedBusinessData:
    """Parse a Places API place object into VerifiedBusinessData."""
    components = place.get("addressComponents", [])
    location = place.get("location", {})

    return VerifiedBusinessData(
        place_id=place.get("id", ""),
        name=place.get("displayName", {}).get("text", ""),
        address=place.get("formattedAddress", ""),
        city=_extract_address_component(components, "locality"),
        state=_extract_address_component(components, "administrative_area_level_1"),
        zip_code=_extract_address_component(components, "postal_code"),
        phone=place.get("nationalPhoneNumber", "") or place.get("internationalPhoneNumber", ""),
        rating=place.get("rating", 0.0),
        review_count=place.get("userRatingCount", 0),
        website=place.get("websiteUri", ""),
        lat=location.get("latitude", 0.0),
        lng=location.get("longitude", 0.0),
        business_status=place.get("businessStatus", ""),
    )


def _score_match(
    place: VerifiedBusinessData,
    name: str,
    domain: str,
    phone: str,
    city: str = "",
) -> tuple[int, VerifiedBusinessData]:
    """Score how well a Places result matches the expected business.

    Returns (score, place_with_match_flags). Higher score = better match.
    City mismatch is an automatic disqualifier (score capped at 0).
    """
    score = 0
    target_domain = _normalize_domain(domain)
    place_domain = _normalize_domain(place.website)

    # City cross-check — if the result is in a different city, reject it
    if city and place.city and city.lower() != place.city.lower():
        place.match_confidence = "none"
        return 0, place

    # Domain match is strongest signal
    if target_domain and place_domain and target_domain == place_domain:
        place.domain_match = True
        score += 100

    # Name match — word-level similarity instead of substring
    sim = _name_similarity(name, place.name) if name and place.name else 0.0
    if sim >= 0.8:
        place.name_match = True
        score += 50
    elif sim >= 0.5:
        place.name_match = True
        score += 40
    elif sim >= 0.3:
        score += 20

    # Phone match
    target_phone = _normalize_phone(phone)
    place_phone = _normalize_phone(place.phone)
    if target_phone and place_phone and target_phone[-10:] == place_phone[-10:]:
        score += 30

    # Set confidence based on score
    if score >= 100:
        place.match_confidence = "high"
    elif score >= 50:
        place.match_confidence = "medium"
    else:
        place.match_confidence = "low"

    return score, place


# Minimum confidence to use verified data in different contexts
# "high" = domain match (strongest), "medium" = name match, "low" = weak, "none" = city mismatch
CONFIDENCE_FOR_REVIEWS = "medium"    # Reviews/rating in llms.txt and schema
CONFIDENCE_FOR_ADDRESS = "high"      # Address/phone override in schema
CONFIDENCE_FOR_COMPETITORS = "medium"  # Competitor data in analyzer prompt


def is_trusted(verified_data: VerifiedBusinessData | None, required: str = "medium") -> bool:
    """Check if verified data meets the required confidence threshold.

    Confidence hierarchy: high > medium > low > none
    """
    if not verified_data:
        return False
    levels = {"none": 0, "low": 1, "medium": 2, "high": 3}
    return levels.get(verified_data.match_confidence, 0) >= levels.get(required, 2)


def fetch_place_data(
    name: str,
    city: str,
    state: str,
    domain: str = "",
    phone: str = "",
    api_key: str = "",
    business_type: str = "practice",
) -> VerifiedBusinessData | None:
    """Look up a business via Google Places text search.

    Tries multiple query variations and picks the best match:
    1. "{name} {type_hint} {city} {state}"
    2. "{name} {city} {state}"
    3. "{domain} {type_hint}"

    Cross-checks city to prevent using another business's data.
    Returns the best-matching result or None on failure.
    """
    if not api_key:
        logger.warning("No Google Places API key — skipping verification")
        return None

    # Add a type hint based on business vertical for search accuracy
    type_hints = {
        "practice": "dentist",
        "legal": "law firm",
        "medical": "doctor",
    }
    type_hint = type_hints.get(business_type, "")
    queries = [
        f"{name} {type_hint} {city} {state}".strip(),
        f"{name} {city} {state}",
    ]
    if domain:
        queries.append(f"{domain} {type_hint}".strip())

    best_score = -1
    best_place: VerifiedBusinessData | None = None

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(PLACE_FIELDS),
        "Content-Type": "application/json",
    }

    for query in queries:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    PLACES_TEXT_SEARCH_URL,
                    headers=headers,
                    json={"textQuery": query, "maxResultCount": 5},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.debug(f"Places text search failed for query '{query}': {e}")
            continue

        for raw_place in data.get("places", []):
            place = _parse_place(raw_place)
            score, place = _score_match(place, name, domain, phone, city=city)
            if score > best_score:
                best_score = score
                best_place = place

    # Final safety check: reject low/none confidence matches entirely
    if best_place and best_place.match_confidence in ("low", "none"):
        logger.warning(
            f"Google Places match rejected — confidence too low: "
            f"'{best_place.name}' (confidence={best_place.match_confidence})"
        )
        return None

    if best_place:
        logger.info(
            f"Google Places match: {best_place.name} "
            f"(confidence={best_place.match_confidence}, "
            f"rating={best_place.rating}, reviews={best_place.review_count})"
        )
    else:
        logger.warning(f"No Google Places match found for '{name}' in {city}, {state}")

    return best_place


def fetch_nearby_competitors(
    lat: float,
    lng: float,
    practice_name: str,
    api_key: str = "",
    radius_meters: float = 8000.0,
    max_results: int = 10,
    place_types: list[str] | None = None,
    text_query: str = "",
) -> list[CompetitorData]:
    """Find nearby competitors via Google Places.

    Uses searchNearby with place type filtering when types are available.
    Falls back to searchText with a free-form query when no good place types
    exist (e.g., for "gold buyer", "SaaS company", etc.).

    Args:
        text_query: Free-form search like "gold buyer Springfield VA".
            Used when place_types is empty. If both are empty, defaults to
            ["dentist"] for backward compat.
    """
    if not api_key:
        return []

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(COMPETITOR_FIELDS),
        "Content-Type": "application/json",
    }

    # Decide search strategy: type-based (nearby) vs text-based
    use_text_search = bool(text_query and not place_types)

    if use_text_search:
        # Text search — better for niche industries without a Google place type
        body = {
            "textQuery": text_query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            },
            "maxResultCount": 20,
        }
        search_url = PLACES_TEXT_SEARCH_URL
        logger.info(f"Competitor text search: '{text_query}' near ({lat},{lng})")
    else:
        # Nearby search with place types
        body = {
            "includedTypes": place_types or ["dentist"],
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            },
            "maxResultCount": 20,
        }
        search_url = PLACES_NEARBY_SEARCH_URL

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(search_url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Competitor search failed: {e}")
        return []

    competitors = []

    for raw_place in data.get("places", []):
        name = raw_place.get("displayName", {}).get("text", "")
        # Filter out self using word-level similarity (threshold 0.5)
        if _name_similarity(name, practice_name) >= 0.5:
            continue

        competitors.append(CompetitorData(
            name=name,
            place_id=raw_place.get("id", ""),
            rating=raw_place.get("rating", 0.0),
            review_count=raw_place.get("userRatingCount", 0),
            address=raw_place.get("formattedAddress", ""),
            website=raw_place.get("websiteUri", ""),
            primary_type=raw_place.get("primaryType", ""),
        ))

    # Sort by review count descending
    competitors.sort(key=lambda c: c.review_count, reverse=True)
    return competitors[:max_results]


def validate_competitors(
    competitors: list[CompetitorData],
    business_type: str = "practice",
) -> list[CompetitorData]:
    """Filter out wrong-industry competitors by name keywords and website content.

    Uses name-based keyword exclusion first (fast), then optionally checks
    the competitor's website for industry-relevant content.
    """
    exclude_keywords = EXCLUDE_KEYWORDS.get(business_type, [])
    industry_keywords = INDUSTRY_KEYWORDS.get(business_type, [])

    validated = []
    with httpx.Client(timeout=5.0, follow_redirects=True, max_redirects=3) as client:
        for comp in competitors:
            name_lower = comp.name.lower()

            # Name-based exclusion (fast, no network)
            excluded = False
            for kw in exclude_keywords:
                if kw in name_lower:
                    logger.debug(f"Excluding competitor '{comp.name}' — name matches exclude keyword '{kw}'")
                    excluded = True
                    break
            if excluded:
                continue

            # Website content check — only fetch public http/https URLs to prevent SSRF
            if comp.website and industry_keywords and comp.website.startswith(("http://", "https://")):
                try:
                    resp = client.get(comp.website)
                    page_text = resp.text[:5000].lower()
                    matches = sum(1 for kw in industry_keywords if kw in page_text)
                    if matches < 2:
                        logger.debug(
                            f"Excluding competitor '{comp.name}' — website has only "
                            f"{matches} industry keyword matches"
                        )
                        continue
                except Exception:
                    # If we can't reach the site, keep the competitor (benefit of the doubt)
                    pass

            validated.append(comp)

    if len(validated) < len(competitors):
        logger.info(
            f"Competitor validation: kept {len(validated)}/{len(competitors)} "
            f"for {business_type} vertical"
        )

    return validated


def verify_customer(
    customer,
    api_key: str = "",
) -> tuple[VerifiedBusinessData | None, list[CompetitorData]]:
    """Convenience wrapper: verify a Customer and find competitors.

    Args:
        customer: A geo_agent.config.Customer instance.
        api_key: Google Places API key.

    Returns:
        (verified_data, competitors) tuple. Either may be None/empty on failure.
    """
    if not api_key:
        api_key_from_secrets = ""
        try:
            from geo_agent.secrets import get_secrets
            api_key_from_secrets = get_secrets().get("GOOGLE_PLACES_API_KEY")
        except Exception:
            pass
        api_key = api_key_from_secrets

    if not api_key:
        logger.info("No GOOGLE_PLACES_API_KEY — skipping business verification")
        return None, []

    business_type = getattr(customer, "business_type", "practice")

    verified = fetch_place_data(
        name=customer.name,
        city=customer.city,
        state=customer.state,
        domain=customer.domain,
        phone=customer.phone,
        api_key=api_key,
        business_type=business_type,
    )

    competitors: list[CompetitorData] = []
    if verified and verified.lat and verified.lng:
        # Use vertical-aware place types for competitor search
        place_types = get_place_types(business_type)

        # Build text query for industries without a Google place type
        text_query = ""
        if not place_types:
            specialties = getattr(customer, "specialties", [])
            city = getattr(customer, "city", "")
            state = getattr(customer, "state", "")
            if specialties:
                # Use first specialty as the search term (most specific)
                text_query = f"{specialties[0]} near {city} {state}".strip()
            elif business_type not in ("practice", ""):
                text_query = f"{business_type} near {city} {state}".strip()

        competitors = fetch_nearby_competitors(
            lat=verified.lat,
            lng=verified.lng,
            practice_name=customer.name,
            api_key=api_key,
            place_types=place_types or None,
            text_query=text_query,
        )
        # Validate competitors — filter wrong-industry results
        competitors = validate_competitors(competitors, business_type)

    return verified, competitors


PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/"


def fetch_place_details(place_id: str, api_key: str = "") -> dict | None:
    """Fetch current rating + review count for a single place by place_id.

    Returns {"rating": float, "review_count": int} or None on failure.
    """
    if not api_key:
        try:
            from geo_agent.secrets import get_secrets
            api_key = get_secrets().get("GOOGLE_PLACES_API_KEY")
        except Exception:
            api_key = ""
    if not api_key or not place_id:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                PLACE_DETAILS_URL + place_id,
                headers={
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "rating,userRatingCount",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug(f"Places details failed for {place_id}: {e}")
        return None
    return {"rating": data.get("rating", 0.0), "review_count": data.get("userRatingCount", 0)}


def refresh_competitor_snapshots(db, customer_id: str) -> int:
    """R2: Refresh each competitor's rating/review_count and record a dated snapshot.

    Updates the live ``competitors`` row and appends to ``competitor_snapshots``
    so the weekly report can show a review-gap *trend*. Returns rows snapshotted.
    """
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    for comp in db.get_competitors(customer_id):
        place_id = comp.get("place_id")
        if not place_id:
            continue
        details = fetch_place_details(place_id)
        if not details:
            continue
        db.conn.execute(
            "UPDATE competitors SET rating = ?, review_count = ? WHERE id = ?",
            (details["rating"], details["review_count"], comp["id"]),
        )
        db.save_competitor_snapshot(
            comp["id"], customer_id, today,
            details["rating"], details["review_count"],
        )
        count += 1
    db.conn.commit()
    logger.info(f"Competitor snapshots refreshed for {customer_id}: {count}")
    return count
