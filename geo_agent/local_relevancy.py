"""Local Relevancy Engine — per-customer orchestrator.

Runs the verified, automatable local levers for one customer, tailored to its
domain + business type. Phase 1 wires Modules 1 (citations/NAP) and 2 (directory
breadth); Modules 3–5 are stubs filled in later phases.

See specs/active/local-relevancy-engine.html.

    from geo_agent.local_relevancy import run_local_relevancy
    run_local_relevancy(db, "paradigm-experts")
"""

from __future__ import annotations

import logging
import re

from geo_agent import brightlocal_client
from geo_agent.directory_profiles import (
    canonical_nap,
    content_schema,
    default_service_terms,
    directory_profile,
    is_local,
    profile_target_count,
)
from geo_agent.nearby_cities import ensure_service_areas

logger = logging.getLogger(__name__)

# Cap service-area pages created per run so we don't flood the review queue.
MAX_SERVICE_AREA_PAGES = 12


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def directory_breadth(db, customer_id: str, business_type: str | None) -> dict:
    """Module 2 — how broadly + correctly the business is listed.

    Aggregates the ``citations`` table against the business type's target
    directory profile. ``pct`` is the share of targeted directories that are
    listed with a correct NAP — the "broad third-party presence" signal AI uses
    for local queries.
    """
    target = profile_target_count(business_type)
    profile = directory_profile(business_type) or []
    target_keys = {e["name"].lower(): e for e in profile}

    rows = db.get_citations(customer_id) or []
    listed_ok = 0
    present = set()
    for c in rows:
        present.add((c.get("directory") or "").lower())
        if c.get("listed") and c.get("nap_match"):
            listed_ok += 1

    missing = [e["name"] for e in profile if e["name"].lower() not in present]
    pct = round(100 * listed_ok / target, 1) if target else 0.0
    return {
        "listed_ok": listed_ok,
        "target": target,
        "pct": pct,
        "missing": missing[:20],
        "tracked": len(rows),
    }


def _module_3_service_area_pages(db, customer):
    """Module 3 — plan {service} in {city} pages and queue them for review.

    Discovers/uses the customer's service-area cities (nearby towns within
    ~25 min), pairs them with the customer's services (or vertical defaults),
    and creates pending ``new_page`` recommendations with the right vertical
    schema. HTML is filled by the existing content-generation/publish flow.
    Idempotent: stable rec ids + title de-dupe avoid duplicates across runs.
    """
    cid = customer["id"]
    cities = ensure_service_areas(db, cid)
    if not cities:
        return {"status": "no_service_areas", "module": "service_area_pages",
                "note": "no city/service_areas and GEONAMES_USERNAME unset"}

    try:
        services = [s.get("name") for s in (db.get_services(cid) or []) if s.get("name")]
    except Exception:  # noqa: BLE001
        services = []
    if not services:
        services = default_service_terms(customer.get("business_type"))

    schema = content_schema(customer.get("business_type"))
    nap = canonical_nap(customer)
    existing = {(r.get("title") or "").lower()
                for r in (db.get_content_recommendations(cid, limit=500) or [])}

    pairs = [(s, c) for s in services for c in cities][:MAX_SERVICE_AREA_PAGES]
    created = 0
    for service, city in pairs:
        title = f"{service} in {city}"
        if title.lower() in existing:
            continue
        slug = _slugify(f"{service}-in-{city}")
        db.add_content_recommendation({
            "id": f"sa-{cid}-{slug}",
            "customer_id": cid,
            "rec_type": "new_page",
            "target_page": f"/{slug}",
            "title": title,
            "category": "service_area",
            "priority": 2,
            "status": "pending",
            "description": (
                f"Create a localized service page for '{service}' targeting {city}. "
                f"Use {schema} + FAQPage schema, lead with a direct answer, and include the "
                f"business NAP ({nap['name']}, {nap['phone']}), local neighborhoods/landmarks, "
                f"directions, and a {city}-specific FAQ. Each city page must have UNIQUE local "
                f"context — no templated boilerplate."
            ),
            "ai_impact_reason": (
                f"Captures local '{service} near me / in {city}' intent. The business website is the "
                f"#1 AI citation source for local queries; a unique {city} page supplies the "
                f"service-area + proximity relevance AI uses to recommend local businesses."
            ),
        })
        created += 1

    return {"status": "ok", "module": "service_area_pages",
            "cities": cities, "services": services[:5],
            "planned": len(pairs), "created": created}


REVIEW_THRESHOLD = 10  # verified: 9->10 gives a noticeable local bump; diminishing after


def _module_4_review_recency(db, customer):
    """Module 4 — drive reviews to ~10+ with text, then keep a recent drip.

    Uses the matched Google Place (rating + review_count) to produce a concrete
    review-generation action + the GBP write-review link. (Last-review-date isn't
    persisted yet — recency is handled by the recurring request action.)
    """
    place = db.get_google_places(customer["id"])
    if not place:
        return {"status": "no_gbp", "module": "review_recency",
                "note": "Google Business Profile not matched yet — can't drive reviews"}
    rating = place.get("rating") or 0
    count = place.get("review_count") or 0
    place_id = place.get("place_id") or ""
    review_link = (f"https://search.google.com/local/writereview?placeid={place_id}"
                   if place_id else "")
    gap = max(0, REVIEW_THRESHOLD - count)
    if count < REVIEW_THRESHOLD:
        status, action = "below_threshold", (
            f"Request {gap} more Google review(s) to reach the {REVIEW_THRESHOLD}-review "
            f"threshold (the verified local-ranking step-up).")
    else:
        status, action = "maintain", (
            "Keep a steady monthly drip of fresh reviews with text — recency is a top "
            "local AI-recommendation signal.")
    return {"status": status, "module": "review_recency", "rating": rating,
            "review_count": count, "gap_to_threshold": gap,
            "review_link": review_link, "action": action}


def _module_5_gbp_completeness(db, customer):
    """Module 5 — GBP completeness checklist, with vertical-correct category hints.

    Field-level GBP data (categories/hours/photos) isn't persisted, so unknown
    items are surfaced as 'needs verification' rather than guessed.
    """
    from geo_agent.directory_profiles import gbp_primary_category

    place = db.get_google_places(customer["id"])
    claimed = bool(place and place.get("place_id"))
    primary = gbp_primary_category(customer.get("business_type"))
    checklist = [
        {"item": "GBP claimed & verified", "ok": claimed},
        {"item": f"Primary category set (suggested: {primary})", "ok": None},
        {"item": "3-4 relevant additional categories", "ok": None},
        {"item": "Services / products listed", "ok": None},
        {"item": "Hours + attributes complete", "ok": None},
        {"item": "Service-area cities set", "ok": bool(customer.get("service_areas"))},
        {"item": "Photos uploaded", "ok": None},
    ]
    return {
        "status": "ok" if claimed else "no_gbp",
        "module": "gbp_completeness",
        "suggested_primary_category": primary,
        "checklist": checklist,
        "missing": [c["item"] for c in checklist if c["ok"] is False],
        "needs_verification": [c["item"] for c in checklist if c["ok"] is None],
    }


def run_local_relevancy(db, customer_id: str, recompute: bool = True) -> dict:
    """Run all available local-relevancy modules for one customer.

    Returns a per-module summary. No-ops (with a reason) for non-local
    business types. Does not email anyone.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        return {"customer_id": customer_id, "skipped": "customer not found"}

    business_type = customer.get("business_type")
    if not is_local(business_type):
        logger.info("local_relevancy: %s is non-local (%s) — skipping", customer_id, business_type)
        return {"customer_id": customer_id, "skipped": f"non-local business_type: {business_type}"}

    nap = canonical_nap(customer)
    summary: dict = {
        "customer_id": customer_id,
        "business_type": business_type,
        "canonical_nap": nap,
        "modules": {},
    }

    # Module 1 — citations / NAP (BrightLocal). No-op until an account +
    # location_id are configured; returns None and the rest still runs.
    try:
        written = brightlocal_client.track_citations(db, customer_id)
        summary["modules"]["citations"] = {
            "written": written,
            "configured": written is not None,
        }
    except Exception as exc:  # never let one module abort the run
        logger.warning("local_relevancy: citations failed for %s: %s", customer_id, exc)
        summary["modules"]["citations"] = {"error": str(exc)}

    # Module 2 — directory breadth (aggregation over citations).
    summary["modules"]["directory_breadth"] = directory_breadth(db, customer_id, business_type)

    # Modules 3–5 — stubs until their phases.
    summary["modules"]["service_area_pages"] = _module_3_service_area_pages(db, customer)
    summary["modules"]["review_recency"] = _module_4_review_recency(db, customer)
    summary["modules"]["gbp_completeness"] = _module_5_gbp_completeness(db, customer)

    if recompute:
        try:
            from geo_agent.practicerank_score import compute_practicerank_score
            compute_practicerank_score(db, customer_id)
        except Exception as exc:
            logger.debug("local_relevancy: score recompute skipped for %s: %s", customer_id, exc)

    return summary
