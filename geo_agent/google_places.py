"""Google Places API (New) integration for business verification.

Verifies customer business data against Google's database:
- Confirms name, address, phone, website
- Gets real Google review count and rating
- Finds nearby competitor dental practices

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
]


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
    """Nearby competitor dental practice from Google Places."""

    name: str
    place_id: str
    rating: float = 0.0
    review_count: int = 0
    address: str = ""


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

    # Name match (case-insensitive substring)
    if name and place.name and name.lower() in place.name.lower():
        place.name_match = True
        score += 50
    elif name and place.name and place.name.lower() in name.lower():
        place.name_match = True
        score += 40

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

    # Add a type hint for dental practices to improve search accuracy
    type_hint = "dentist" if business_type == "practice" else ""
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
) -> list[CompetitorData]:
    """Find nearby competitors via Google Places.

    Searches within radius_meters of the given lat/lng,
    filters out the business itself, and returns up to max_results
    sorted by review count (descending).
    """
    if not api_key:
        return []

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(COMPETITOR_FIELDS),
        "Content-Type": "application/json",
    }

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

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                PLACES_NEARBY_SEARCH_URL,
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Nearby competitor search failed: {e}")
        return []

    competitors = []
    practice_name_lower = practice_name.lower()

    for raw_place in data.get("places", []):
        name = raw_place.get("displayName", {}).get("text", "")
        # Filter out self
        if name.lower() in practice_name_lower or practice_name_lower in name.lower():
            continue

        competitors.append(CompetitorData(
            name=name,
            place_id=raw_place.get("id", ""),
            rating=raw_place.get("rating", 0.0),
            review_count=raw_place.get("userRatingCount", 0),
            address=raw_place.get("formattedAddress", ""),
        ))

    # Sort by review count descending
    competitors.sort(key=lambda c: c.review_count, reverse=True)
    return competitors[:max_results]


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
        # Use appropriate place types for competitor search
        place_types = ["dentist"] if business_type == "practice" else None
        competitors = fetch_nearby_competitors(
            lat=verified.lat,
            lng=verified.lng,
            practice_name=customer.name,
            api_key=api_key,
            place_types=place_types,
        )

    return verified, competitors
