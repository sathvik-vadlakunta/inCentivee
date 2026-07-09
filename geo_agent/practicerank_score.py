"""PracticeRank Score — Composite 0-100 score (v2).

Designed to show real progress within 4-6 weeks: weighted toward the work we
control and that moves fast (GEO Foundation + Content + AI), and robust to
missing/flaky data (no zeros on absent signals; Search omitted when no GSC).
See specs/active/practicerank-score-v2.html.

Pillars (DB keys kept stable to avoid a migration; labels updated):
- ai_visibility    (30%) — mention rate, position, engine breadth, trend
- technical_health (30%) — GEO FOUNDATION: completion of schema/llms.txt/robots/
                           FAQ/sitemap deliverables (not PageSpeed; PageSpeed
                           flakiness no longer tanks the score)
- content_velocity (20%) — CONTENT & COVERAGE: publish cadence + breadth +
                           service-area page coverage + freshness
- reputation       (10%) — rating + review-growth trend (volume de-emphasised)
- search_growth    (10%) — SEARCH PERFORMANCE: organic trend; omitted (weight
                           redistributed) when GSC isn't connected
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)

# Pillar weights (must sum to 1.0). Keys are the stable DB columns.
PILLAR_WEIGHTS = {
    "ai_visibility": 0.30,
    "technical_health": 0.30,   # GEO Foundation
    "content_velocity": 0.20,   # Content & Coverage
    "reputation": 0.10,
    "search_growth": 0.10,      # Search Performance
}

# Human labels for the pillar keys (used by the report).
PILLAR_LABELS = {
    "ai_visibility": "AI Visibility",
    "technical_health": "GEO Foundation",
    "content_velocity": "Content & Coverage",
    "reputation": "Reputation",
    "search_growth": "Search Performance",
}

# Recalibrated so a fully-executed early account (foundation done, content
# shipped, AI building) lands at a strong B (~80).
GRADES = [
    (88, "A", "Excellent", "#16a34a"),
    (72, "B", "Strong", "#65a30d"),
    (55, "C", "Good", "#d97706"),
    (38, "D", "Needs Work", "#ea580c"),
    (0, "F", "Critical", "#dc2626"),
]


def grade_from_score(score: int) -> dict:
    """Return grade letter, label, and color for a 0-100 score."""
    for threshold, letter, label, color in GRADES:
        if score >= threshold:
            return {"letter": letter, "label": label, "color": color}
    return {"letter": "F", "label": "Critical", "color": "#dc2626"}


# ---------------------------------------------------------------------------
# Pillar 1: AI Visibility (30%)
# ---------------------------------------------------------------------------

def _score_mention_rate(rate: float) -> float:
    """Score based on mention rate (0.0-1.0). Returns 0-100.

    Thresholds are stricter — 60%+ for perfect, 40% for 80.
    Most practices start at 10-30% mention rate pre-optimization.
    """
    pct = rate * 100
    if pct >= 60:
        return 100.0
    if pct >= 50:
        return 85 + (pct - 50) / 10 * 15
    if pct >= 40:
        return 70 + (pct - 40) / 10 * 15
    if pct >= 30:
        return 50 + (pct - 30) / 10 * 20
    if pct >= 20:
        return 30 + (pct - 20) / 10 * 20
    if pct >= 10:
        return 15 + (pct - 10) / 10 * 15
    if pct >= 1:
        return 5 + (pct - 1) / 9 * 10
    return 0.0


def _score_position_quality(avg_position: float) -> float:
    """Score based on average position in AI responses. Returns 0-100."""
    if avg_position <= 0:
        return 0.0
    if avg_position <= 1.5:
        return 100.0
    if avg_position <= 2.5:
        return 80.0
    if avg_position <= 3.5:
        return 60.0
    if avg_position <= 5.0:
        return 40.0
    return 20.0


def _score_engine_breadth(engines_with_mentions: int, total_engines: int = 0) -> float:
    """Score based on how many AI engines mention the business. Returns 0-100.

    Requires meaningful presence (2+ mentions per engine counted upstream).
    """
    if engines_with_mentions >= 5:
        return 100.0
    if engines_with_mentions >= 4:
        return 80.0
    if engines_with_mentions == 3:
        return 60.0
    if engines_with_mentions == 2:
        return 40.0
    if engines_with_mentions == 1:
        return 20.0
    return 0.0


def _score_ai_trend(current_rate: float, prev_rate: float | None) -> float:
    """Score based on mention rate trend. Returns 0-100.

    Proportional to magnitude of improvement, not binary.
    """
    if prev_rate is None:
        return 40.0  # slightly below neutral when no history (haven't proven growth)
    delta = current_rate - prev_rate
    if delta >= 0.20:
        return 100.0
    if delta >= 0.10:
        return 80 + (delta - 0.10) / 0.10 * 20
    if delta >= 0.05:
        return 65 + (delta - 0.05) / 0.05 * 15
    if delta >= 0:
        return 50 + delta / 0.05 * 15
    if delta >= -0.05:
        return 35 + (delta + 0.05) / 0.05 * 15
    if delta >= -0.10:
        return 20 + (delta + 0.10) / 0.05 * 15
    return max(0, 20 + delta * 100)


def compute_ai_visibility(db: CustomerDB, customer_id: str) -> dict | None:
    """Compute AI Visibility pillar score (0-100)."""
    # Only count runs that actually measured something — an empty/failed run
    # (0 queries) must NOT tank the score (omit it like any missing signal).
    runs = [r for r in db.get_ai_mention_runs(customer_id, limit=24) if r.get("total_queries")]
    if not runs:
        return None

    latest = runs[0]
    mention_rate = latest.get("mention_rate", 0) or 0
    avg_position = latest.get("avg_position", 0) or 0

    # Engine breadth from latest run
    engines_json = latest.get("engines_json", "{}")
    if isinstance(engines_json, str):
        try:
            engines_data = json.loads(engines_json)
        except (json.JSONDecodeError, TypeError):
            engines_data = {}
    else:
        engines_data = engines_json or {}

    engines_with_mentions = sum(
        1 for e in engines_data.values()
        if isinstance(e, dict) and e.get("mentions", 0) >= 2
    )

    # Trend from previous runs
    current_window = runs[:4]
    prev_window = runs[4:8]
    current_avg = sum(r.get("mention_rate", 0) or 0 for r in current_window) / len(current_window)
    prev_avg = None
    if prev_window:
        prev_avg = sum(r.get("mention_rate", 0) or 0 for r in prev_window) / len(prev_window)

    # Sub-scores
    rate_score = _score_mention_rate(mention_rate)
    position_score = _score_position_quality(avg_position)
    breadth_score = _score_engine_breadth(engines_with_mentions)
    trend_score = _score_ai_trend(current_avg, prev_avg)

    # Weighted combination — mention rate is the primary outcome metric
    score = (
        rate_score * 0.55
        + position_score * 0.20
        + breadth_score * 0.15
        + trend_score * 0.10
    )

    return {
        "score": round(score),
        "detail": {
            "mention_rate": round(mention_rate, 4),
            "avg_position": round(avg_position, 2),
            "engines_with_mentions": engines_with_mentions,
            "trend": "up" if prev_avg and current_avg > prev_avg + 0.02 else
                     "down" if prev_avg and current_avg < prev_avg - 0.02 else "stable",
            "sub_scores": {
                "rate": round(rate_score, 1),
                "position": round(position_score, 1),
                "breadth": round(breadth_score, 1),
                "trend": round(trend_score, 1),
            },
        },
    }


# ---------------------------------------------------------------------------
# Pillar 2: Search Growth (25%)
# ---------------------------------------------------------------------------

def compute_search_growth(db: CustomerDB, customer_id: str) -> dict | None:
    """Compute Search Growth pillar score (0-100)."""
    daily = db.get_gsc_daily(customer_id, limit=60)
    if len(daily) < 7:
        return None

    # Split into current vs previous period
    this_period = daily[:30]
    prev_period = daily[30:60]

    tp_clicks = sum(d.get("clicks", 0) for d in this_period)
    tp_impressions = sum(d.get("impressions", 0) for d in this_period)
    pp_clicks = sum(d.get("clicks", 0) for d in prev_period) if prev_period else 0
    pp_impressions = sum(d.get("impressions", 0) for d in prev_period) if prev_period else 0

    # Click growth score
    if pp_clicks > 0:
        click_growth = (tp_clicks - pp_clicks) / pp_clicks
    elif tp_clicks > 0:
        click_growth = 0.20  # some clicks from nothing = good
    else:
        click_growth = 0.0

    if click_growth >= 0.30:
        click_score = 100.0
    elif click_growth >= 0.15:
        click_score = 80 + (click_growth - 0.15) / 0.15 * 20
    elif click_growth >= 0.05:
        click_score = 60 + (click_growth - 0.05) / 0.10 * 20
    elif click_growth >= 0:
        click_score = 50 + click_growth / 0.05 * 10
    elif click_growth >= -0.10:
        click_score = 30 + (click_growth + 0.10) / 0.10 * 20
    elif click_growth >= -0.30:
        click_score = 10 + (click_growth + 0.30) / 0.20 * 20
    else:
        click_score = 0.0

    # Impression growth score
    if pp_impressions > 0:
        imp_growth = (tp_impressions - pp_impressions) / pp_impressions
    elif tp_impressions > 0:
        imp_growth = 0.20
    else:
        imp_growth = 0.0

    imp_score = min(100, max(0, 50 + imp_growth * 100))

    # Position improvement
    tp_positions = [d.get("position", 0) for d in this_period if d.get("position")]
    pp_positions = [d.get("position", 0) for d in prev_period if d.get("position")]
    tp_avg_pos = sum(tp_positions) / len(tp_positions) if tp_positions else 0
    pp_avg_pos = sum(pp_positions) / len(pp_positions) if pp_positions else 0

    if pp_avg_pos > 0 and tp_avg_pos > 0:
        pos_improvement = pp_avg_pos - tp_avg_pos  # positive = improved
        if pos_improvement >= 5:
            pos_score = 100.0
        elif pos_improvement >= 2:
            pos_score = 70 + (pos_improvement - 2) / 3 * 30
        elif pos_improvement >= 0:
            pos_score = 50 + pos_improvement / 2 * 20
        elif pos_improvement >= -3:
            pos_score = 30 + (pos_improvement + 3) / 3 * 20
        else:
            pos_score = max(0, 30 + pos_improvement * 5)
    else:
        pos_score = 50.0  # neutral

    # Keyword momentum
    kw_summary = db.get_keyword_summary(customer_id)
    improving_kw = 0
    declining_kw = 0
    if kw_summary:
        for kw in kw_summary:
            curr = kw.get("current_position") or kw.get("position")
            prev = kw.get("prev_position")
            if curr and prev:
                if curr < prev:
                    improving_kw += 1
                elif curr > prev:
                    declining_kw += 1
    total_kw = improving_kw + declining_kw
    if total_kw > 0:
        kw_ratio = improving_kw / total_kw
        kw_score = kw_ratio * 100
    else:
        kw_score = 50.0  # neutral

    # Weighted combination
    score = (
        click_score * 0.40
        + imp_score * 0.20
        + pos_score * 0.25
        + kw_score * 0.15
    )

    return {
        "score": round(score),
        "detail": {
            "click_growth": round(click_growth, 3),
            "clicks_current": tp_clicks,
            "clicks_previous": pp_clicks,
            "impression_growth": round(imp_growth, 3),
            "position_current": round(tp_avg_pos, 1),
            "position_previous": round(pp_avg_pos, 1),
            "keywords_improving": improving_kw,
            "keywords_declining": declining_kw,
            "sub_scores": {
                "clicks": round(click_score, 1),
                "impressions": round(imp_score, 1),
                "position": round(pos_score, 1),
                "keywords": round(kw_score, 1),
            },
        },
    }


# ---------------------------------------------------------------------------
# Pillar 3: Technical Health (15%)
# ---------------------------------------------------------------------------

# GEO Foundation deliverables → points (sum to 100). Driven by the persisted
# checklist (the daily reconciler ticks these from live detection), so it's
# DB-only and robust — a PageSpeed timeout can never tank it.
_FOUNDATION_ITEMS = [
    (("seo_schema_localbusiness", "seo_schema_org", "seo_schema_legalservice"), 20),  # core schema (any)
    (("seo_schema_faq",), 15),                                                         # FAQ schema
    (("seo_llms_txt",), 15),                                                           # llms.txt live
    (("seo_robots_txt",), 15),                                                         # robots AI rules
    (("seo_llms_full",), 10),                                                          # llms-full.txt
    (("seo_xml_sitemap",), 10),                                                        # sitemap
    (("seo_schema_review", "seo_schema_person", "seo_schema_service"), 10),            # supporting schema (any)
    (("seo_structured_headings",), 5),                                                 # heading hierarchy
]


def compute_technical_health(db: CustomerDB, customer_id: str) -> dict | None:
    """GEO FOUNDATION (key kept as technical_health). Completion of the GEO
    deliverables we ship — robust, no PageSpeed dependency."""
    checklist = db.get_checklist(customer_id) or {}
    # A brand-new customer has an empty checklist → foundation ~0 (the baseline).
    earned = 0
    done = {}
    for keys, pts in _FOUNDATION_ITEMS:
        hit = any(checklist.get(k) for k in keys)
        done[keys[0]] = hit
        if hit:
            earned += pts

    # Open critical audit issues subtract (a real, fixable regression — not a
    # PageSpeed timeout). PageSpeed performance is an optional small bonus.
    issues = db.get_audit_issues(customer_id, status="open")
    critical_open = sum(1 for i in issues if i.get("severity") == "critical")
    score = max(0.0, earned - critical_open * 10)

    audit = db.get_latest_audit(customer_id) or {}
    perf = audit.get("performance_score") or 0
    if perf:  # tiny bonus when we have a real (non-zero) perf score; never a penalty
        score = min(100.0, score + min(5.0, perf / 20.0))

    # Citation / NAP consistency (Local Relevancy Engine, Module 1). Gated on
    # having audited citations — dormant until BrightLocal is configured, so no
    # current scores move. Bonus-only (up to +8), never a penalty.
    nap_pct = None
    citations = db.get_citations(customer_id)
    tracked = [c for c in (citations or []) if c.get("listed")]
    if tracked:
        nap_pct = sum(1 for c in tracked if c.get("nap_match")) / len(tracked)
        score = min(100.0, score + nap_pct * 8.0)

    return {
        "score": round(score),
        "detail": {
            "deliverables_done": sum(1 for v in done.values() if v),
            "deliverables_total": len(_FOUNDATION_ITEMS),
            "critical_issues": critical_open,
            "lighthouse_performance": perf,
            "nap_consistency": round(nap_pct * 100) if nap_pct is not None else None,
            "sub_scores": {PILLAR_LABELS["technical_health"]: round(score, 1)},
            "items": {k: bool(v) for k, v in done.items()},
        },
    }


# ---------------------------------------------------------------------------
# Pillar 4: Content Velocity (15%)
# ---------------------------------------------------------------------------

# Target content categories (breadth) — having each type published is a signal.
_CONTENT_CATEGORIES = {
    "blog_post": "blog", "faq_update": "faq", "new_page": "pages",
    "expert_quote": "depth", "stat_injection": "depth", "freshness_update": "fresh",
}


def compute_content_velocity(db: CustomerDB, customer_id: str) -> dict | None:
    """CONTENT & COVERAGE (key kept). Publish cadence + breadth + service-area
    page coverage + freshness — all work we control, so it climbs in weeks 1-6."""
    recs = db.get_content_recommendations(customer_id, limit=300)
    if not recs:
        return None
    published = [r for r in recs if r.get("status") == "published"]

    # Breadth — distinct content categories we've actually published.
    cats = {_CONTENT_CATEGORIES.get(r.get("rec_type")) for r in published}
    cats.discard(None)
    breadth_score = min(len(cats), 4) / 4 * 100

    # Volume — published count (8+ = full marks).
    volume_score = min(len(published), 8) / 8 * 100

    # Service-area coverage — cities with a published location page ÷ cities served.
    customer = db.get_customer(customer_id) or {}
    areas = customer.get("service_areas") or []
    if areas:
        page_titles = " || ".join((r.get("title") or "").lower()
                                  for r in published if r.get("rec_type") == "new_page")
        # A city counts as covered if WE published a location page for it OR the
        # reconciler detected a live page for it on the site (dev-built pages).
        live_areas = {a for a in (customer.get("live_area_pages") or [])}
        covered = sum(1 for a in areas
                      if a.split(",")[0].strip().lower() in page_titles or a in live_areas)
        coverage_score = covered / len(areas) * 100
    else:
        covered = 0
        coverage_score = 60.0  # neutral when no service area is defined

    # Freshness — a freshness_update published in the last 90 days.
    cutoff = (datetime.now(timezone.utc).timestamp() - 90 * 86400)
    fresh = False
    for r in published:
        if r.get("rec_type") == "freshness_update" and r.get("published_at"):
            try:
                if datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")).timestamp() >= cutoff:
                    fresh = True
                    break
            except (ValueError, TypeError):
                pass
    freshness_score = 100.0 if fresh else 50.0

    score = (breadth_score * 0.35 + volume_score * 0.30
             + coverage_score * 0.20 + freshness_score * 0.15)

    return {
        "score": round(score),
        "detail": {
            "published_count": len(published),
            "categories": sorted(cats),
            "service_areas": len(areas),
            "areas_covered": covered,
            "sub_scores": {
                "breadth": round(breadth_score, 1),
                "volume": round(volume_score, 1),
                "coverage": round(coverage_score, 1),
                "freshness": round(freshness_score, 1),
            },
        },
    }


# ---------------------------------------------------------------------------
# Pillar 5: Reputation (15%)
# ---------------------------------------------------------------------------

def compute_reputation(db: CustomerDB, customer_id: str) -> dict | None:
    """Compute Reputation pillar score (0-100)."""
    places = db.get_google_places(customer_id)
    if not places:
        return None

    rating = places.get("rating") or 0
    review_count = places.get("review_count") or 0

    # Rating score (benchmark: 4.5)
    if rating >= 4.8:
        rating_score = 100.0
    elif rating >= 4.5:
        rating_score = 80 + (rating - 4.5) / 0.3 * 20
    elif rating >= 4.0:
        rating_score = 50 + (rating - 4.0) / 0.5 * 30
    elif rating >= 3.5:
        rating_score = 25 + (rating - 3.5) / 0.5 * 25
    elif rating > 0:
        rating_score = rating / 3.5 * 25
    else:
        rating_score = 0.0

    # Review growth (vs last recorded count). Volume-vs-competitors is dropped —
    # it depended on the (often wrong-industry) competitors table and is a slow,
    # external signal we shouldn't over-weight.
    review_kpis = db.get_kpis(customer_id, metric="review_count", limit=2)
    growth_score = 50.0  # neutral default
    if len(review_kpis) >= 2:
        new_reviews = review_kpis[0]["value"] - review_kpis[1]["value"]
        if new_reviews >= 10:
            growth_score = 100.0
        elif new_reviews >= 5:
            growth_score = 85.0
        elif new_reviews >= 1:
            growth_score = 70.0
        elif new_reviews == 0:
            growth_score = 50.0
        else:
            growth_score = 30.0

    # Sentiment from reviews
    reviews = db.get_reviews(customer_id, limit=50)
    sentiment_score = 60.0  # neutral-positive default
    if reviews:
        positive = sum(1 for r in reviews if r.get("sentiment") == "positive" or (r.get("rating") and r["rating"] >= 4))
        sentiment_score = (positive / len(reviews)) * 100

    score = rating_score * 0.6 + growth_score * 0.3 + sentiment_score * 0.1

    return {
        "score": round(score),
        "detail": {
            "rating": rating,
            "review_count": review_count,
            "sub_scores": {
                "rating": round(rating_score, 1),
                "growth": round(growth_score, 1),
                "sentiment": round(sentiment_score, 1),
            },
        },
    }


# ---------------------------------------------------------------------------
# Composite Score
# ---------------------------------------------------------------------------

def compute_practicerank_score(db: CustomerDB, customer_id: str) -> dict:
    """Compute the composite PracticeRank Score (0-100).

    Returns a dict with overall score, grade, per-pillar scores, and breakdown.
    Missing pillars have their weight redistributed to available ones.
    """
    pillar_results = {
        "ai_visibility": compute_ai_visibility(db, customer_id),
        "search_growth": compute_search_growth(db, customer_id),
        "technical_health": compute_technical_health(db, customer_id),
        "content_velocity": compute_content_velocity(db, customer_id),
        "reputation": compute_reputation(db, customer_id),
    }

    # Separate available from unavailable
    available = {}
    unavailable = []
    for pillar, result in pillar_results.items():
        if result is not None:
            available[pillar] = result
        else:
            unavailable.append(pillar)

    # Need at least 2 pillars for a meaningful score
    if len(available) < 2:
        return {
            "score": None,
            "grade": grade_from_score(0),
            "label": "Insufficient Data",
            "pillars": {k: {"score": None, "available": False} for k in PILLAR_WEIGHTS},
            "available_count": len(available),
            "breakdown_json": json.dumps(pillar_results, default=str),
        }

    # Redistribute weights from unavailable pillars
    total_available_weight = sum(PILLAR_WEIGHTS[p] for p in available)
    if total_available_weight > 0:
        scale = 1.0 / total_available_weight
    else:
        scale = 1.0

    # Compute weighted score
    weighted_sum = 0.0
    pillars_output = {}
    for pillar, result in pillar_results.items():
        if result is not None:
            effective_weight = PILLAR_WEIGHTS[pillar] * scale
            weighted_sum += result["score"] * effective_weight
            pillars_output[pillar] = {
                "score": result["score"],
                "weight": round(effective_weight, 3),
                "available": True,
                "detail": result.get("detail", {}),
            }
        else:
            pillars_output[pillar] = {
                "score": None,
                "weight": 0,
                "available": False,
                "detail": {},
            }

    overall = round(max(0, min(100, weighted_sum)))
    grade = grade_from_score(overall)

    # Data-readiness warnings — surface "we're missing valuable context" so the
    # score isn't trusted blindly. Order-of-operations: Google + competitors first.
    warnings = []
    if not db.get_google_places(customer_id):
        warnings.append({"key": "google_places", "severity": "error",
                         "message": "Google Business Profile not verified — connect it first (Reputation & local context missing)."})
    if not db.get_competitors(customer_id):
        warnings.append({"key": "competitors", "severity": "warning",
                         "message": "No competitors identified — run competitor discovery for competitive context."})
    if len(db.get_gsc_daily(customer_id, limit=7)) < 7:
        warnings.append({"key": "gsc", "severity": "warning",
                         "message": "Search Console not connected — Search Performance is excluded from the score."})
    if not db.get_ai_mention_runs(customer_id, limit=1):
        warnings.append({"key": "ai_mentions", "severity": "warning",
                         "message": "No AI-mention data yet — AI Visibility not measured."})

    # Week-0 baseline: lock the first score (pre-work) so we can show progress.
    customer = db.get_customer(customer_id) or {}
    baseline = customer.get("baseline_score")
    if baseline is None:
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            db.update_customer(customer_id, baseline_score=overall, baseline_date=today)
            baseline = overall
        except Exception:
            logger.warning("could not set baseline for %s", customer_id)

    return {
        "score": overall,
        "grade": grade,
        "pillars": pillars_output,
        "available_count": len(available),
        "baseline": baseline,
        "delta_from_baseline": (overall - baseline) if baseline is not None else 0,
        "warnings": warnings,
        "breakdown_json": json.dumps(pillar_results, default=str),
    }
