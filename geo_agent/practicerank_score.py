"""PracticeRank Score — Composite 0-100 score across 5 pillars.

Pillars and weights:
- AI Visibility  (30%) — mention rate, position quality, engine breadth, trend
- Search Growth  (25%) — click growth, impression growth, keyword momentum
- Technical Health (15%) — Lighthouse, open issues, schema completeness
- Content Velocity (15%) — publish recency, pending ratio, content quality
- Reputation     (15%) — rating, review volume vs competitors, growth
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)

# Pillar weights (must sum to 1.0)
PILLAR_WEIGHTS = {
    "ai_visibility": 0.30,
    "search_growth": 0.25,
    "technical_health": 0.15,
    "content_velocity": 0.15,
    "reputation": 0.15,
}

GRADES = [
    (90, "A", "Excellent", "#16a34a"),
    (75, "B", "Strong", "#65a30d"),
    (60, "C", "Good", "#d97706"),
    (40, "D", "Needs Work", "#ea580c"),
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
    runs = db.get_ai_mention_runs(customer_id, limit=24)
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

def compute_technical_health(db: CustomerDB, customer_id: str) -> dict | None:
    """Compute Technical Health pillar score (0-100)."""
    audit = db.get_latest_audit(customer_id)
    if not audit:
        return None

    # Lighthouse scores
    seo_score = audit.get("seo_score") or 0
    perf_score = audit.get("performance_score") or 0

    # Issues ratio
    issues = db.get_audit_issues(customer_id)
    total_issues = len(issues)
    open_issues = sum(1 for i in issues if i.get("status") == "open")
    critical_open = sum(1 for i in issues if i.get("status") == "open" and i.get("severity") == "critical")

    if total_issues > 0:
        fixed_ratio = (total_issues - open_issues) / total_issues
        issues_score = fixed_ratio * 100
        # Penalize critical issues heavily
        issues_score = max(0, issues_score - critical_open * 15)
    else:
        issues_score = 80.0  # no issues found = good but not perfect (might not have been audited deeply)

    # Schema completeness
    schema_score = 0.0
    ai_readiness = db.get_latest_ai_readiness(customer_id)
    if ai_readiness and ai_readiness.get("breakdown"):
        breakdown = ai_readiness["breakdown"]
        if breakdown.get("local_business_schema") or breakdown.get("organization_schema"):
            schema_score += 25
        if breakdown.get("faq_schema"):
            schema_score += 25
        if breakdown.get("aggregate_rating_schema"):
            schema_score += 25
        if breakdown.get("llms_txt"):
            schema_score += 25
    else:
        # Try to infer from audit data
        raw_data = audit.get("raw_data_json", "{}")
        if isinstance(raw_data, str):
            try:
                raw = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                raw = {}
        else:
            raw = raw_data or {}
        schema_types = raw.get("schema_types", [])
        if any(s in schema_types for s in ("LocalBusiness", "Organization", "Dentist")):
            schema_score += 25
        if "FAQPage" in schema_types:
            schema_score += 25
        if "AggregateRating" in schema_types:
            schema_score += 25
        if raw.get("llms_txt_exists"):
            schema_score += 25

    # Weighted combination
    score = (
        seo_score * 0.30
        + perf_score * 0.20
        + issues_score * 0.30
        + schema_score * 0.20
    )

    return {
        "score": round(score),
        "detail": {
            "lighthouse_seo": seo_score,
            "lighthouse_performance": perf_score,
            "open_issues": open_issues,
            "critical_issues": critical_open,
            "total_issues": total_issues,
            "schema_completeness": round(schema_score),
            "sub_scores": {
                "seo": round(seo_score, 1),
                "performance": round(perf_score, 1),
                "issues": round(issues_score, 1),
                "schema": round(schema_score, 1),
            },
        },
    }


# ---------------------------------------------------------------------------
# Pillar 4: Content Velocity (15%)
# ---------------------------------------------------------------------------

def compute_content_velocity(db: CustomerDB, customer_id: str) -> dict | None:
    """Compute Content Velocity pillar score (0-100)."""
    recs = db.get_content_recommendations(customer_id, limit=100)
    if not recs:
        # No content recs at all — check if there are page scores at least
        page_scores = db.get_page_scores(customer_id)
        if not page_scores:
            return None
        avg_quality = sum(p.get("score", 0) for p in page_scores) / len(page_scores)
        return {
            "score": round(min(avg_quality, 50)),  # cap at 50 without content pipeline
            "detail": {
                "publish_recency_days": None,
                "published_count": 0,
                "approved_count": 0,
                "total_recs": 0,
                "avg_page_quality": round(avg_quality, 1),
                "sub_scores": {
                    "recency": 0,
                    "pending_ratio": 50,
                    "quality": round(avg_quality, 1),
                },
            },
        }

    published = [r for r in recs if r.get("status") == "published"]
    approved = [r for r in recs if r.get("status") == "approved"]

    # Publish recency
    now = datetime.now(timezone.utc)
    recency_score = 0.0
    days_since_publish = None
    if published:
        dates = []
        for r in published:
            pub_date = r.get("published_at")
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    dates.append(dt)
                except (ValueError, TypeError):
                    pass
        if dates:
            latest_publish = max(dates)
            days_since_publish = (now - latest_publish).days
            if days_since_publish <= 7:
                recency_score = 100.0
            elif days_since_publish <= 14:
                recency_score = 80.0
            elif days_since_publish <= 30:
                recency_score = 60.0
            elif days_since_publish <= 60:
                recency_score = 30.0
            else:
                recency_score = 10.0

    # Pending ratio (approved + published vs total)
    total_actionable = len(published) + len(approved)
    if total_actionable > 0:
        publish_ratio = len(published) / total_actionable
        pending_score = publish_ratio * 100
    else:
        pending_score = 50.0  # neutral

    # Content quality from page scores
    page_scores = db.get_page_scores(customer_id)
    if page_scores:
        avg_quality = sum(p.get("score", 0) for p in page_scores) / len(page_scores)
    else:
        avg_quality = 50.0  # neutral

    # Weighted combination
    score = (
        recency_score * 0.40
        + pending_score * 0.30
        + avg_quality * 0.30
    )

    return {
        "score": round(score),
        "detail": {
            "publish_recency_days": days_since_publish,
            "published_count": len(published),
            "approved_count": len(approved),
            "total_recs": len(recs),
            "avg_page_quality": round(avg_quality, 1),
            "sub_scores": {
                "recency": round(recency_score, 1),
                "pending_ratio": round(pending_score, 1),
                "quality": round(avg_quality, 1),
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

    # Review volume vs competitors
    competitors = db.get_competitors(customer_id)
    comp_avg = 0
    if competitors:
        comp_counts = [c.get("review_count", 0) for c in competitors if c.get("review_count")]
        comp_avg = sum(comp_counts) / len(comp_counts) if comp_counts else 0

    if comp_avg > 0:
        ratio = review_count / comp_avg
        if ratio >= 1.5:
            volume_score = 100.0
        elif ratio >= 1.0:
            volume_score = 50 + (ratio - 1.0) / 0.5 * 50
        else:
            volume_score = ratio * 50
    else:
        # Absolute scale
        if review_count >= 100:
            volume_score = 80.0
        elif review_count >= 50:
            volume_score = 60.0
        elif review_count >= 20:
            volume_score = 40.0
        elif review_count >= 10:
            volume_score = 25.0
        else:
            volume_score = max(0, review_count / 10 * 25)

    # Review growth (last 30 days)
    review_kpis = db.get_kpis(customer_id, metric="review_count", limit=2)
    growth_score = 50.0  # neutral default
    if len(review_kpis) >= 2:
        curr_count = review_kpis[0]["value"]
        prev_count = review_kpis[1]["value"]
        new_reviews = curr_count - prev_count
        if new_reviews >= 10:
            growth_score = 100.0
        elif new_reviews >= 5:
            growth_score = 80.0
        elif new_reviews >= 1:
            growth_score = 60.0
        elif new_reviews == 0:
            growth_score = 40.0
        else:
            growth_score = 20.0

    # Sentiment from reviews
    reviews = db.get_reviews(customer_id, limit=50)
    sentiment_score = 50.0  # neutral default
    if reviews:
        positive = sum(1 for r in reviews if r.get("sentiment") == "positive" or (r.get("rating") and r["rating"] >= 4))
        sentiment_score = (positive / len(reviews)) * 100

    # Weighted combination
    score = (
        rating_score * 0.40
        + volume_score * 0.30
        + growth_score * 0.20
        + sentiment_score * 0.10
    )

    return {
        "score": round(score),
        "detail": {
            "rating": rating,
            "review_count": review_count,
            "competitor_avg_reviews": round(comp_avg),
            "sub_scores": {
                "rating": round(rating_score, 1),
                "volume": round(volume_score, 1),
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

    return {
        "score": overall,
        "grade": grade,
        "pillars": pillars_output,
        "available_count": len(available),
        "breakdown_json": json.dumps(pillar_results, default=str),
    }
