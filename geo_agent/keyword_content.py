"""Turn Google Search Console query data into monthly content recommendations.

This is the engine behind the "search-data-driven content" promise: instead of
guessing blog topics, we mine the queries a site *already* gets impressions for
and recommend the content/pages that will capture that existing demand. Four
opportunity types, each mapped to a content recommendation:

- **striking_distance** — ranks #8–20 with real impressions → a dedicated,
  optimized page can push it onto page 1. (highest priority)
- **high_impressions_low_ctr** — ranks well but few clicks → the page exists but
  underperforms; refresh title/intent or build a focused page.
- **question** — who/what/why/how/cost/price/"near me" intent → FAQ / answer
  content engineered to rank AND be cited by AI.
- **untapped** — lots of impressions but ranks > 20 → no good page yet; create one.

Pure + deterministic (no network) so it's testable and free; the classifier and
title-building are plain Python. See specs/content-system.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_QUESTION_RE = re.compile(
    r"^\s*(how|what|why|when|where|who|which|can|do|does|is|are|should|will)\b|"
    r"\b(cost|price|pricing|near me|vs|reviews?)\b", re.I)


def _classify(q: dict) -> str | None:
    """Map one aggregated query to an opportunity type (or None to skip)."""
    pos = q.get("position") or 99
    impr = q.get("impressions") or 0
    clicks = q.get("clicks") or 0
    ctr = q.get("ctr") or 0
    text = (q.get("query") or "").strip()
    if not text or impr < 10:
        return None
    if _QUESTION_RE.search(text):
        return "question"
    if 8 <= pos <= 20 and impr >= 20:
        return "striking_distance"
    if pos <= 7 and impr >= 50 and ctr < 0.02 and clicks <= 1:
        return "high_impressions_low_ctr"
    if pos > 20 and impr >= 30:
        return "untapped"
    return None


_TYPE_META = {
    # opportunity → (rec_type, category, base_priority, build title/desc/reason)
    "striking_distance": ("new_page", "search_opportunity", 1),
    "untapped": ("new_page", "search_opportunity", 2),
    "high_impressions_low_ctr": ("freshness_update", "search_opportunity", 2),
    "question": ("faq_update", "search_opportunity", 2),
}


def _titleize(query: str) -> str:
    small = {"a", "an", "the", "and", "or", "for", "to", "in", "of", "near", "me", "vs"}
    words = query.split()
    return " ".join(w if (w.lower() in small and i) else w.capitalize()
                    for i, w in enumerate(words))


def _build(opportunity: str, q: dict) -> dict:
    """Build the (title, description, ai_impact_reason) for a recommendation."""
    query = q["query"].strip()
    pos = round(q.get("position") or 0)
    impr = int(q.get("impressions") or 0)
    clicks = int(q.get("clicks") or 0)
    t = _titleize(query)

    if opportunity == "question":
        title = f'Answer: "{t}"'
        desc = (f'People search "{query}" — {impr} impressions in the last 4 weeks. '
                f'Publish a concise FAQ/answer section so you rank and get cited by AI assistants.')
        reason = "Question-intent + FAQ schema is the content most likely to be quoted by ChatGPT/Perplexity/Google AI."
    elif opportunity == "striking_distance":
        title = f'Page for "{t}" (ranks #{pos} — striking distance)'
        desc = (f'You already rank #{pos} for "{query}" with {impr} impressions but only {clicks} click(s). '
                f'A dedicated, optimized page can push this onto page 1 and capture demand you\'re already showing up for.')
        reason = "Striking-distance terms (8–20) are the fastest, cheapest ranking wins — the demand is already proven."
    elif opportunity == "high_impressions_low_ctr":
        title = f'Fix click-through for "{t}"'
        desc = (f'"{query}" gets {impr} impressions at ~#{pos} but almost no clicks. '
                f'Refresh the ranking page\'s title/meta and intent match, or build a focused page for it.')
        reason = "High impressions + low CTR is leaking demand — a title/intent fix converts existing visibility into clicks."
    else:  # untapped
        title = f'New page targeting "{t}"'
        desc = (f'"{query}" shows {impr} impressions but you rank #{pos}+ — there\'s no strong page for it yet. '
                f'Create dedicated, locally-relevant content to claim it.')
        reason = "Proven local demand with no page to capture it — a clear content gap."

    return {"title": title, "description": desc, "ai_impact_reason": reason}


def recommend_from_search_data(db, customer_id: str, *, lookback_days: int = 28,
                               max_recs: int = 8, today: str | None = None) -> list[dict]:
    """Generate + persist content recommendations from GSC query data.

    Idempotent-ish: skips opportunities whose query already has a pending
    recommendation. Returns the recommendations created (dicts).
    """
    end = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    queries = db.get_query_aggregates(customer_id, start, end, min_impressions=10, limit=300)
    if not queries:
        return []

    # Don't re-recommend a query we already have a pending rec for.
    existing = db.get_content_recommendations(customer_id, status="pending", limit=200) or []
    seen = {(r.get("target_page") or "").strip().lower() for r in existing}

    scored = []
    for q in queries:
        opp = _classify(q)
        if not opp:
            continue
        key = (q["query"] or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rec_type, category, base_pri = _TYPE_META[opp]
        built = _build(opp, q)
        # Score by impressions, lightly boosted for striking distance.
        boost = 1.4 if opp == "striking_distance" else 1.0
        scored.append({"opp": opp, "q": q, "rec_type": rec_type, "category": category,
                       "priority": base_pri, "score": (q.get("impressions") or 0) * boost,
                       **built})

    scored.sort(key=lambda r: r["score"], reverse=True)
    created = []
    for r in scored[:max_recs]:
        rid = "kw_" + hashlib.sha1(
            f"{customer_id}:{r['q']['query']}".encode()).hexdigest()[:16]
        rec = {
            "id": rid, "customer_id": customer_id, "rec_type": r["rec_type"],
            "target_page": r["q"]["query"].strip(), "title": r["title"],
            "description": r["description"], "priority": r["priority"],
            "category": r["category"], "status": "pending",
            "ai_impact_reason": r["ai_impact_reason"],
        }
        db.add_content_recommendation(rec)
        created.append(rec)
    if created:
        logger.info("keyword_content: %d recs for %s", len(created), customer_id)
    return created
