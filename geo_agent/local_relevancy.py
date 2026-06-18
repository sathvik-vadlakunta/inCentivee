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


def local_relevancy_view(db, customer: dict) -> dict | None:
    """Read-only snapshot of the local-relevancy signals — no API calls, no rec
    creation. Used by the weekly report and the VA action tab. None if non-local.
    """
    bt = customer.get("business_type")
    if not is_local(bt):
        return None
    return {
        "breadth": directory_breadth(db, customer["id"], bt),
        "reviews": _module_4_review_recency(db, customer),
        "gbp": _module_5_gbp_completeness(db, customer),
        "nap": canonical_nap(customer),
        "profile": directory_profile(bt) or [],
    }


def _step(title: str, instruction: str, status: str, link: str = "") -> dict:
    # status ∈ done | todo | verify | ongoing
    return {"title": title, "instruction": instruction, "status": status, "link": link}


def va_action_plan(db, customer: dict) -> dict | None:
    """Crystal-clear, per-customer VA steps for the local-relevancy work.

    Translates the engine's signals into explicit, ordered actions across the
    canonical NAP, Google Business Profile / Maps, Apple Maps, Bing, directory
    citations, reviews, and the local content pages. None if non-local.
    """
    from geo_agent.directory_profiles import gbp_primary_category

    view = local_relevancy_view(db, customer)
    if not view:
        return None

    cid = customer["id"]
    bt = customer.get("business_type")
    nap = view["nap"]
    primary_cat = gbp_primary_category(bt)
    place = db.get_google_places(cid)
    claimed = bool(place and place.get("place_id"))
    review_link = view["reviews"].get("review_link", "")
    cities = customer.get("service_areas") or []
    sa_pending = [r for r in (db.get_content_recommendations(cid, status="pending", limit=200) or [])
                  if r.get("category") == "service_area"]
    cit = {(c.get("directory") or "").lower(): c for c in (db.get_citations(cid) or [])}

    groups: list[dict] = []

    groups.append({
        "group": "0 · Use this EXACT business info everywhere",
        "intro": ("Every listing below must match this exactly — name, address, phone, website. "
                  "Inconsistent info is the #1 thing that hurts local ranking and AI trust."),
        "nap": nap,
        "steps": [],
    })

    groups.append({"group": "1 · Google Business Profile + Google Maps", "steps": [
        _step("Claim & verify the Google Business Profile",
              "Go to business.google.com. If it's unclaimed, claim it and complete verification "
              "(postcard, phone, or video). This is the single most important local listing.",
              "done" if claimed else "todo", "https://business.google.com"),
        _step(f"Set the PRIMARY category to '{primary_cat}'",
              "Edit profile → category. The primary category is the strongest Google Maps ranking "
              "signal — make sure it's the most specific accurate match.", "verify"),
        _step("Add 3–4 relevant ADDITIONAL categories",
              "Add secondary categories that match the services offered (don't over-stuff).", "verify"),
        _step("Confirm the map pin is on the exact location",
              "On Google Maps, drag the pin to the real building/entrance so proximity is correct.", "verify"),
        _step("Set the service-area cities",
              ("Add these nearby cities as service areas: " + (", ".join(cities) if cities
               else "(none yet — run the engine or set them on the customer to populate).")),
              "verify" if cities else "todo"),
        _step("Complete services, hours, attributes, and 10+ real photos",
              "Fill every field. Add genuine photos (exterior, interior, team) — these help conversion.", "verify"),
    ]})

    groups.append({"group": "2 · Apple Maps (Apple Business Connect)", "steps": [
        _step("Claim the business at business.apple.com",
              "Sign in with an Apple ID, search for the business, claim it, and verify.",
              "todo", "https://business.apple.com"),
        _step("Match the NAP to the exact business info above",
              "Name, address, and phone must match the canonical info exactly.", "todo"),
        _step(f"Set the category close to '{primary_cat}' and add photos",
              "Pick the closest Apple category and upload the same photos used on Google.", "todo"),
    ]})

    groups.append({"group": "3 · Bing Places", "steps": [
        _step("Claim at bingplaces.com (import from Google to save time)",
              "Use 'Import from Google Business Profile', then verify the NAP matches exactly.",
              "todo", "https://www.bingplaces.com"),
    ]})

    cit_steps = []
    for d in view["profile"]:
        row = cit.get(d["name"].lower())
        if row and row.get("listed") and row.get("nap_match"):
            st, instr = "done", "Listed and NAP matches — no action."
        elif row and row.get("listed"):
            st, instr = "todo", "Listed but the NAP is WRONG — edit it to match the exact business info above."
        else:
            st, instr = "todo", "Not listed — create a listing using the exact business info above."
        step = _step(d["name"], instr, st, row.get("listing_url", "") if row else "")
        step["mark"] = d["name"]  # enables the manual "mark listed" control (Path B)
        cit_steps.append(step)
    groups.append({
        "group": "4 · Directory citations (NAP consistency)",
        "note": ("Once BrightLocal is connected it auto-audits/fixes most of these. Until then, "
                 "do the core directories (top of the list) manually."),
        "steps": cit_steps,
    })

    rv = view["reviews"]
    if rv.get("status") == "no_gbp":
        review_steps = [_step("Match the Google Business Profile first",
                              "Reviews can't be tracked until the GBP is claimed/matched (step 1).", "todo")]
    else:
        review_steps = [_step(
            rv.get("action", "Request fresh Google reviews"),
            ("Text/email this review link to recent happy customers: " + review_link) if review_link
            else "Use the GBP 'Get more reviews' short link.",
            "todo" if rv.get("status") == "below_threshold" else "ongoing", review_link)]
    groups.append({"group": "5 · Reviews", "steps": review_steps})

    groups.append({"group": "6 · Local content pages", "steps": [
        _step(f"Review & publish {len(sa_pending)} pending city/service page(s)",
              "Open the Content tab, review each generated page for accuracy, approve, and publish.",
              "todo" if sa_pending else "done"),
    ]})

    total = sum(len(g["steps"]) for g in groups)
    todo = sum(1 for g in groups for s in g["steps"] if s["status"] in ("todo", "verify"))
    return {"nap": nap, "groups": groups, "total_steps": total, "open_steps": todo,
            "primary_category": primary_cat}


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
