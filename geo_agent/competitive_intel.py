"""Competitive intelligence monitoring for businesses (dental, legal, medical, etc).

Tracks competitor review counts, ratings, and schema markup changes.
Generates alerts when competitors make significant moves.
Uses vertical-aware place types and competitor validation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import httpx

from geo_agent.db import CustomerDB
from geo_agent.google_places import fetch_place_data, fetch_nearby_competitors, get_place_types, validate_competitors

logger = logging.getLogger(__name__)


@dataclass
class CompetitorAlert:
    """An alert about a competitor's activity."""
    customer_id: str
    competitor_name: str
    alert_type: str  # review_surge, rating_change, new_schema, new_content
    severity: str  # info, warning, critical
    message: str
    details: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def check_competitor_reviews(
    db: CustomerDB,
    customer_id: str,
    api_key: str | None = None,
) -> list[CompetitorAlert]:
    """Check all competitors for review count and rating changes.

    Compares current Google Places data against stored data.
    Generates alerts for:
    - Review surges (>5 new reviews since last check)
    - Rating changes (up or down by 0.2+)
    - Competitors overtaking the practice in review count
    """
    api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        logger.info("GOOGLE_PLACES_API_KEY not set — skipping competitor check")
        return []

    customer = db.get_customer(customer_id)
    if not customer:
        return []

    places = db.get_google_places(customer_id)
    if not places or not places.get("lat") or not places.get("lng"):
        logger.info(f"No Places data for {customer_id} — skipping competitor check")
        return []

    our_reviews = places.get("review_count", 0)
    our_rating = places.get("rating", 0.0)

    # Fetch current competitor data from Google using vertical-aware place types
    business_type = customer.get("business_type", "practice")
    place_types = get_place_types(business_type) or None
    try:
        current_competitors = fetch_nearby_competitors(
            places["lat"], places["lng"],
            customer["name"], api_key,
            place_types=place_types,
        )
        current_competitors = validate_competitors(current_competitors, business_type)
    except Exception as e:
        logger.warning(f"Failed to fetch competitors: {e}")
        return []

    # Get stored competitor data
    stored_competitors = db.get_competitors(customer_id)
    stored_map = {c["name"].lower(): c for c in stored_competitors}

    alerts = []
    updated_competitors = []

    for comp in current_competitors:
        comp_key = comp.name.lower()
        stored = stored_map.get(comp_key)

        comp_dict = {
            "name": comp.name,
            "rating": comp.rating,
            "review_count": comp.review_count,
            "address": comp.address,
            "place_id": comp.place_id,
        }
        updated_competitors.append(comp_dict)

        if not stored:
            # New competitor appeared
            if comp.review_count > 50:
                alerts.append(CompetitorAlert(
                    customer_id=customer_id,
                    competitor_name=comp.name,
                    alert_type="new_competitor",
                    severity="info",
                    message=f"New competitor detected: {comp.name} ({comp.rating} stars, {comp.review_count} reviews)",
                    details=comp_dict,
                ))
            continue

        old_reviews = stored.get("review_count", 0)
        old_rating = stored.get("rating", 0.0)
        review_delta = comp.review_count - old_reviews
        rating_delta = comp.rating - old_rating

        # Review surge detection
        if review_delta >= 10:
            severity = "critical" if review_delta >= 20 else "warning"
            alerts.append(CompetitorAlert(
                customer_id=customer_id,
                competitor_name=comp.name,
                alert_type="review_surge",
                severity=severity,
                message=(
                    f"{comp.name} gained {review_delta} reviews "
                    f"({old_reviews} → {comp.review_count}). "
                    f"They may be running a review campaign."
                ),
                details={
                    "old_reviews": old_reviews,
                    "new_reviews": comp.review_count,
                    "delta": review_delta,
                },
            ))
        elif review_delta >= 5:
            alerts.append(CompetitorAlert(
                customer_id=customer_id,
                competitor_name=comp.name,
                alert_type="review_surge",
                severity="info",
                message=f"{comp.name} gained {review_delta} reviews ({old_reviews} → {comp.review_count})",
                details={"old_reviews": old_reviews, "new_reviews": comp.review_count, "delta": review_delta},
            ))

        # Rating change detection
        if abs(rating_delta) >= 0.2:
            direction = "up" if rating_delta > 0 else "down"
            alerts.append(CompetitorAlert(
                customer_id=customer_id,
                competitor_name=comp.name,
                alert_type="rating_change",
                severity="info",
                message=f"{comp.name} rating moved {direction}: {old_rating} → {comp.rating}",
                details={"old_rating": old_rating, "new_rating": comp.rating, "delta": round(rating_delta, 1)},
            ))

        # Competitor overtaking alert
        if comp.review_count > our_reviews and old_reviews <= our_reviews:
            alerts.append(CompetitorAlert(
                customer_id=customer_id,
                competitor_name=comp.name,
                alert_type="overtake",
                severity="warning",
                message=(
                    f"{comp.name} now has more reviews than you "
                    f"({comp.review_count} vs your {our_reviews})"
                ),
                details={"their_reviews": comp.review_count, "your_reviews": our_reviews},
            ))

    # Update stored competitors
    if updated_competitors:
        db.replace_competitors(customer_id, updated_competitors)

    if alerts:
        logger.info(f"Generated {len(alerts)} competitor alerts for {customer_id}")
    else:
        logger.info(f"No competitor alerts for {customer_id}")

    return alerts


def check_competitor_schema(
    competitor_domains: list[str],
    customer_id: str,
) -> list[CompetitorAlert]:
    """Check if competitors have added schema markup to their sites.

    Scrapes competitor sites and checks for JSON-LD schema presence.
    """
    alerts = []

    for domain in competitor_domains[:5]:  # Limit to top 5
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(f"https://{domain}")
                html = resp.text.lower()

                has_schema = "application/ld+json" in html
                has_faq = "faqpage" in html
                has_dentist = '"dentist"' in html or '"localbusiness"' in html
                has_llms_txt = False

                # Check for llms.txt
                try:
                    llms_resp = client.get(f"https://{domain}/llms.txt")
                    has_llms_txt = llms_resp.status_code == 200 and len(llms_resp.text) > 50
                except Exception:
                    pass

                if has_schema and has_faq:
                    alerts.append(CompetitorAlert(
                        customer_id=customer_id,
                        competitor_name=domain,
                        alert_type="new_schema",
                        severity="warning",
                        message=f"{domain} has FAQ schema markup — they may have hired an SEO",
                        details={"has_schema": True, "has_faq": True, "has_dentist": has_dentist},
                    ))

                if has_llms_txt:
                    alerts.append(CompetitorAlert(
                        customer_id=customer_id,
                        competitor_name=domain,
                        alert_type="new_schema",
                        severity="critical",
                        message=f"{domain} has an llms.txt file — they're doing AI search optimization",
                        details={"has_llms_txt": True},
                    ))

        except Exception as e:
            logger.debug(f"Failed to check schema for {domain}: {e}")

    return alerts


def generate_competitor_report(
    db: CustomerDB,
    customer_id: str,
) -> str:
    """Generate a text competitor intelligence report."""
    customer = db.get_customer(customer_id)
    if not customer:
        return f"Customer not found: {customer_id}"

    places = db.get_google_places(customer_id)
    competitors = db.get_competitors(customer_id)

    lines = [
        f"Competitor Intelligence Report: {customer['name']}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 55,
        "",
    ]

    if places:
        lines.append(f"Your Practice: {places['rating']} stars, {places['review_count']} reviews")
        lines.append("")

    if competitors:
        lines.append("Competitor Landscape:")
        lines.append(f"{'Name':<30} {'Rating':>6} {'Reviews':>8} {'Gap':>6}")
        lines.append("-" * 55)
        our_reviews = places["review_count"] if places else 0
        for c in competitors:
            gap = c["review_count"] - our_reviews
            gap_str = f"{gap:+d}"
            lines.append(f"{c['name'][:29]:<30} {c['rating']:>6.1f} {c['review_count']:>8} {gap_str:>6}")
        lines.append("")

        # Summary stats
        avg_reviews = sum(c["review_count"] for c in competitors) / len(competitors)
        avg_rating = sum(c["rating"] for c in competitors) / len(competitors)
        lines.append(f"Market Average: {avg_rating:.1f} stars, {avg_reviews:.0f} reviews")
        if places:
            if our_reviews > avg_reviews:
                lines.append(f"You are ABOVE the market average by {our_reviews - avg_reviews:.0f} reviews")
            else:
                lines.append(f"You are BELOW the market average by {avg_reviews - our_reviews:.0f} reviews")
    else:
        lines.append("No competitors tracked yet.")

    return "\n".join(lines)
