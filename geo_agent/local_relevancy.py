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


def _module_4_review_recency(db, customer):  # TODO Phase 4
    return {"status": "not_built", "module": "review_recency"}


def _module_5_gbp_completeness(db, customer):  # TODO Phase 4
    return {"status": "not_built", "module": "gbp_completeness"}


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
