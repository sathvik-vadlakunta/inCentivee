"""Composite AI Visibility Score.

Combines multiple signals into a 0-100 score that reliably shows improvement
over time, smoothing out LLM non-determinism in individual AI mention checks.

Signals (with fallback weights when some are unavailable):
- Rolling AI mention rate (25%) — 4-week average of mention checks
- GSC organic clicks growth (30%) — month-over-month change
- llms.txt hits (25%) — AI agents reading the content
- Review growth (20%) — Google review count trend
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)

# Default signal weights (must sum to 1.0)
_WEIGHTS: dict[str, float] = {
    "ai_mentions": 0.25,
    "gsc_clicks": 0.30,
    "llms_hits": 0.25,
    "reviews": 0.20,
}


def _grade_from_score(score: int) -> str:
    """Map a 0-100 score to a letter grade."""
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Rolling mention rate
# ---------------------------------------------------------------------------


def compute_rolling_mention_rate(
    db: CustomerDB,
    customer_id: str,
    window_runs: int = 12,
) -> dict | None:
    """Compute rolling AI mention rate over the last *window_runs* runs.

    Returns ``None`` when fewer than 3 runs are available (not enough data to
    be meaningful).
    """
    # Fetch current + previous window so we can compute trend
    runs = db.get_ai_mention_runs(customer_id, limit=window_runs * 2)
    if len(runs) < 3:
        return None

    current_runs = runs[:window_runs]
    prev_runs = runs[window_runs : window_runs * 2]

    current_rates = [r["mention_rate"] for r in current_runs]
    current_rate = sum(current_rates) / len(current_rates)

    prev_rate: float | None = None
    trend = "flat"
    if prev_runs:
        prev_rates = [r["mention_rate"] for r in prev_runs]
        prev_rate = sum(prev_rates) / len(prev_rates)
        delta = current_rate - prev_rate
        if delta > 0.02:
            trend = "up"
        elif delta < -0.02:
            trend = "down"

    return {
        "current_rate": round(current_rate, 4),
        "prev_rate": round(prev_rate, 4) if prev_rate is not None else None,
        "trend": trend,
        "run_count": len(current_runs),
        "rates": [round(r, 4) for r in current_rates],
    }


# ---------------------------------------------------------------------------
# Individual signal scorers (each returns 0-100)
# ---------------------------------------------------------------------------


def _score_ai_mentions(mention_rate: float) -> tuple[float, str]:
    """Score based on rolling mention rate (0.0-1.0 scale).

    >40% rate  -> 100
    20-40%     -> linear 50-100
    5-20%      -> linear 25-50
    <5%        -> linear 0-25
    """
    rate_pct = mention_rate * 100  # convert to percentage

    if rate_pct >= 40:
        score = 100.0
    elif rate_pct >= 20:
        score = 50 + (rate_pct - 20) / 20 * 50
    elif rate_pct >= 5:
        score = 25 + (rate_pct - 5) / 15 * 25
    else:
        score = rate_pct / 5 * 25

    detail = f"{rate_pct:.1f}% mention rate"
    return round(score, 1), detail


def _score_gsc_clicks(db: CustomerDB, customer_id: str) -> tuple[float, str] | None:
    """Score based on month-over-month organic click growth.

    >20% growth -> 100
    0% (flat)   -> 50
    declining   -> 0-40
    """
    kpis = db.get_kpis(customer_id, metric="organic_clicks", limit=2)
    if len(kpis) < 2:
        return None

    current = kpis[0]["value"]
    previous = kpis[1]["value"]

    if previous == 0:
        # Can't compute growth from zero baseline
        if current > 0:
            return 60.0, f"{int(current)} clicks (no prior baseline)"
        return 0.0, "No click data"

    growth = (current - previous) / previous

    if growth >= 0.20:
        score = 100.0
    elif growth >= 0:
        # 0% -> 50, 20% -> 100
        score = 50 + growth / 0.20 * 50
    elif growth >= -0.50:
        # -50% -> 0, 0% -> 40 (declining range is 0-40 to penalise drops)
        score = 40 + growth / 0.50 * 40
    else:
        score = 0.0

    detail = f"{growth:+.0%} MoM ({int(previous)} -> {int(current)} clicks)"
    return round(max(score, 0), 1), detail


def _score_llms_hits(db: CustomerDB, customer_id: str) -> tuple[float, str] | None:
    """Score based on weekly llms.txt hit volume.

    >100/week -> 100
    50-100    -> 75
    10-50     -> 50
    1-10      -> 25
    0         -> 0
    """
    kpi = db.get_latest_kpi(customer_id, "llms_txt_hits")
    if kpi is None:
        return None

    hits = kpi["value"]

    if hits > 100:
        score = 100.0
    elif hits >= 50:
        score = 75.0
    elif hits >= 10:
        score = 50.0
    elif hits >= 1:
        score = 25.0
    else:
        score = 0.0

    detail = f"{int(hits)} hits/week"
    return score, detail


def _score_reviews(db: CustomerDB, customer_id: str) -> tuple[float, str] | None:
    """Score based on review count relative to competitor average, plus growth bonus.

    Above avg -> 80-100
    At avg    -> 50
    Below avg -> 0-50
    +10 bonus for positive review growth trend.
    """
    places = db.get_google_places(customer_id)
    if places is None:
        return None

    review_count = places.get("review_count", 0)
    competitors = db.get_competitors(customer_id)

    if not competitors:
        # No competitor data — score purely on absolute count
        if review_count >= 100:
            score = 80.0
        elif review_count >= 50:
            score = 60.0
        elif review_count >= 20:
            score = 40.0
        else:
            score = max(review_count, 0) / 20 * 40
        detail = f"{review_count} reviews (no competitor data)"
        return round(score, 1), detail

    comp_counts = [c.get("review_count", 0) for c in competitors]
    avg_count = sum(comp_counts) / len(comp_counts) if comp_counts else 0

    if avg_count == 0:
        ratio = 2.0 if review_count > 0 else 0.0
    else:
        ratio = review_count / avg_count

    if ratio >= 1.5:
        score = 100.0
    elif ratio >= 1.0:
        # At avg (1.0) -> 50, 1.5x -> 100
        score = 50 + (ratio - 1.0) / 0.5 * 50
    else:
        # 0 -> 0, at avg (1.0) -> 50
        score = ratio * 50

    # Growth bonus: check if review count increased recently
    review_kpis = db.get_kpis(customer_id, metric="review_count", limit=2)
    growth_bonus = 0.0
    if len(review_kpis) >= 2:
        if review_kpis[0]["value"] > review_kpis[1]["value"]:
            growth_bonus = 10.0

    score = min(score + growth_bonus, 100.0)
    detail = f"{review_count} reviews (avg competitor: {int(avg_count)})"
    return round(score, 1), detail


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def compute_visibility_score(db: CustomerDB, customer_id: str) -> dict:
    """Compute the composite AI Visibility Score (0-100).

    Fetches all available signals, redistributes weight from unavailable signals
    proportionally to available ones, and returns the weighted composite score
    with grade, trend, and per-signal detail.
    """
    # --- Gather signals ---
    signals: dict[str, dict] = {}

    # AI mentions
    mention_data = compute_rolling_mention_rate(db, customer_id)
    if mention_data is not None:
        value, detail = _score_ai_mentions(mention_data["current_rate"])
        signals["ai_mentions"] = {
            "value": value,
            "weight": _WEIGHTS["ai_mentions"],
            "available": True,
            "detail": detail,
        }
    else:
        signals["ai_mentions"] = {
            "value": 0.0,
            "weight": _WEIGHTS["ai_mentions"],
            "available": False,
            "detail": "Not enough runs (<3)",
        }

    # GSC clicks
    gsc_result = _score_gsc_clicks(db, customer_id)
    if gsc_result is not None:
        value, detail = gsc_result
        signals["gsc_clicks"] = {
            "value": value,
            "weight": _WEIGHTS["gsc_clicks"],
            "available": True,
            "detail": detail,
        }
    else:
        signals["gsc_clicks"] = {
            "value": 0.0,
            "weight": _WEIGHTS["gsc_clicks"],
            "available": False,
            "detail": "No organic click data",
        }

    # llms.txt hits
    llms_result = _score_llms_hits(db, customer_id)
    if llms_result is not None:
        value, detail = llms_result
        signals["llms_hits"] = {
            "value": value,
            "weight": _WEIGHTS["llms_hits"],
            "available": True,
            "detail": detail,
        }
    else:
        signals["llms_hits"] = {
            "value": 0.0,
            "weight": _WEIGHTS["llms_hits"],
            "available": False,
            "detail": "No llms.txt hit data",
        }

    # Reviews
    review_result = _score_reviews(db, customer_id)
    if review_result is not None:
        value, detail = review_result
        signals["reviews"] = {
            "value": value,
            "weight": _WEIGHTS["reviews"],
            "available": True,
            "detail": detail,
        }
    else:
        signals["reviews"] = {
            "value": 0.0,
            "weight": _WEIGHTS["reviews"],
            "available": False,
            "detail": "No Google Places data",
        }

    # --- Redistribute weights for unavailable signals ---
    available = {k: v for k, v in signals.items() if v["available"]}
    total_available_weight = sum(v["weight"] for v in available.values())

    if total_available_weight > 0 and total_available_weight < 1.0:
        # Scale up available weights proportionally
        scale = 1.0 / total_available_weight
        for sig in available.values():
            sig["weight"] = round(sig["weight"] * scale, 4)

    # --- Compute weighted score ---
    if not available:
        score = 0
    else:
        score = round(
            sum(sig["value"] * sig["weight"] for sig in available.values())
        )
        score = max(0, min(100, score))

    # --- Compute trend from previous mention data ---
    trend = "stable"
    prev_score: int | None = None
    if mention_data is not None and mention_data.get("prev_rate") is not None:
        prev_mention_value, _ = _score_ai_mentions(mention_data["prev_rate"])
        # Rough previous score estimate using mention signal change as proxy
        current_mention_value = signals["ai_mentions"]["value"]
        delta = current_mention_value - prev_mention_value
        if delta > 5:
            trend = "improving"
        elif delta < -5:
            trend = "declining"

        # Estimate previous composite by shifting mention contribution
        if available:
            mention_weight = signals["ai_mentions"].get("weight", 0)
            prev_score = max(
                0,
                min(100, round(score - delta * mention_weight)),
            )

    return {
        "score": score,
        "grade": _grade_from_score(score),
        "signals": signals,
        "trend": trend,
        "prev_score": prev_score,
    }
