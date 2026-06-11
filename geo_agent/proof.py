"""Proof-of-improvement report assembler.

Pulls the before/after story for a customer out of the existing tracking tables:
AI-visibility (baseline vs latest), the AI trend series, Google Search Console
growth, share-of-voice, the source domains now citing the practice, the
PracticeRank Score delta, and an attribution timeline of what we shipped.

Everything is read-only and defensive — any missing signal is simply omitted so
the report degrades gracefully for customers without (e.g.) GSC access.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _pct(x: float) -> float:
    return round(x * 100, 1)


def _delta(now: float | None, base: float | None) -> float | None:
    if now is None or base is None:
        return None
    return round(now - base, 1)


def build_proof_report(db, customer_id: str) -> dict:
    """Assemble the proof-of-improvement payload for a customer."""
    customer = db.get_customer(customer_id) or {}
    report: dict = {
        "customer_id": customer_id,
        "customer_name": customer.get("name", customer_id),
        "city": customer.get("city", ""),
        "state": customer.get("state", ""),
    }

    # --- AI visibility: baseline vs latest -------------------------------
    # Lock the baseline FIRST so the freshly-set is_baseline flag is reflected in
    # the runs we then fetch for the trend series.
    baseline = None
    try:
        baseline = db.ensure_baseline_run(customer_id)
    except Exception as e:
        logger.warning(f"proof: baseline failed: {e}")

    try:
        runs = db.get_ai_mention_runs(customer_id, limit=52)  # newest first
    except Exception as e:
        logger.warning(f"proof: ai runs failed: {e}")
        runs = []

    latest = runs[0] if runs else None
    if baseline and latest and baseline["id"] != latest["id"]:
        report["ai_visibility"] = {
            "baseline_date": baseline.get("run_date"),
            "latest_date": latest.get("run_date"),
            "baseline_mention_rate": _pct(baseline.get("mention_rate", 0) or 0),
            "latest_mention_rate": _pct(latest.get("mention_rate", 0) or 0),
            "mention_rate_delta": _delta(
                _pct(latest.get("mention_rate", 0) or 0),
                _pct(baseline.get("mention_rate", 0) or 0),
            ),
            "baseline_avg_position": baseline.get("avg_position"),
            "latest_avg_position": latest.get("avg_position"),
            "engines": list((latest.get("engines_json") and __import__("json").loads(latest["engines_json"]) or {}).keys()),
        }
    elif latest:
        report["ai_visibility"] = {
            "latest_date": latest.get("run_date"),
            "latest_mention_rate": _pct(latest.get("mention_rate", 0) or 0),
            "latest_avg_position": latest.get("avg_position"),
            "note": "Baseline will lock after the first scheduled run.",
        }

    # Trend series (oldest -> newest) for charting
    report["ai_trend"] = [
        {
            "date": r.get("run_date"),
            "mention_rate": _pct(r.get("mention_rate", 0) or 0),
            "avg_position": r.get("avg_position"),
            "is_baseline": bool(r.get("is_baseline")),
        }
        for r in reversed(runs)
    ]

    # --- Citations: who is now citing the practice -----------------------
    try:
        report["citation_domains"] = db.get_citation_domains(customer_id, last_n_runs=4)
    except Exception as e:
        logger.warning(f"proof: citations failed: {e}")
        report["citation_domains"] = []

    # --- Share of voice vs competitors -----------------------------------
    try:
        sov = db.get_share_of_voice(customer_id, last_n_runs=4)
        report["share_of_voice"] = {
            "customer_share": _pct(sov.get("customer_share", 0) or 0),
            "rank": sov.get("customer_rank"),
            "competitors": (sov.get("competitors") or [])[:8],
        }
    except Exception as e:
        logger.warning(f"proof: sov failed: {e}")

    # --- Google Search Console growth (real organic) ---------------------
    try:
        weeks = db.get_gsc_weekly_summary(customer_id, weeks=12)
        if weeks and len(weeks) >= 2:
            first, last = weeks[0], weeks[-1]
            report["gsc"] = {
                "first_week": first.get("week_start") or first.get("week"),
                "last_week": last.get("week_start") or last.get("week"),
                "clicks_first": first.get("clicks", 0),
                "clicks_last": last.get("clicks", 0),
                "impressions_first": first.get("impressions", 0),
                "impressions_last": last.get("impressions", 0),
                "series": weeks,
            }
    except Exception as e:
        logger.warning(f"proof: gsc failed: {e}")

    # --- PracticeRank Score delta ----------------------------------------
    try:
        scores = db.get_practicerank_scores(customer_id, limit=90)  # newest first
        if scores:
            newest, oldest = scores[0], scores[-1]
            report["score"] = {
                "baseline": oldest.get("overall"),
                "latest": newest.get("overall"),
                "delta": _delta(newest.get("overall"), oldest.get("overall")),
                "baseline_date": oldest.get("date"),
                "latest_date": newest.get("date"),
            }
    except Exception as e:
        logger.warning(f"proof: score failed: {e}")

    # --- Attribution timeline: what we shipped ---------------------------
    try:
        report["published"] = db.get_published_content_events(customer_id, limit=50)
    except Exception as e:
        logger.warning(f"proof: published events failed: {e}")
        report["published"] = []

    return report
