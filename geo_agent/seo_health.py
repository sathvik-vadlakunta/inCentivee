"""SEO Health Score — the dashboard donut, as a single source of truth.

The score (0-100) is the average of four DISTINCT, equally-weighted (25%) signals,
so no bucket duplicates another and every point is explainable:

  1. Performance  — Lighthouse performance score (page speed)
  2. Coverage     — % of tracked keywords ranking in the top 20
  3. Traffic      — 30d-vs-prior-30d organic-click trend (neutral 50 = flat)
  4. Technical    — avg of Lighthouse SEO / best-practices / accessibility

Both the dashboard (live render) and the weekly cron (daily persistence) call this,
so the stored history and the on-screen number can never drift apart.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def compute_seo_health(latest_audit, keyword_summary, gsc_daily) -> dict:
    """Return {"score", "buckets": [{key,label,value,weight,detail}, ...]}.

    ``gsc_daily`` must be chronological-ascending (oldest first); pass a stable
    ~60-day window so the score doesn't move with any UI date-range toggle.
    """
    # 1) Performance (25%) — page speed only
    perf = 0.0
    perf_detail = "No audit yet"
    if latest_audit:
        perf = float(latest_audit.get("performance_score", 0) or 0)
        perf_detail = f"Lighthouse performance {round(perf)}/100"

    # 2) Keyword coverage (25%) — % of tracked keywords in top 20
    kw_pct = 0.0
    kw_detail = "No tracked keywords"
    if keyword_summary:
        in_top_20 = sum(1 for k in keyword_summary
                        if k.get("current_position") and k["current_position"] <= 20)
        kw_pct = in_top_20 / len(keyword_summary) * 100
        kw_detail = f"{in_top_20}/{len(keyword_summary)} keywords in top 20"

    # 3) Traffic trend (25%) — 30d vs prior 30d (halves a short window). Fixed
    # window so the score is stable regardless of any page date-range toggle.
    traffic_score = 50.0  # neutral = flat
    traffic_detail = "Not enough history yet (neutral)"
    if gsc_daily and len(gsc_daily) >= 14:
        win = 30 if len(gsc_daily) >= 60 else len(gsc_daily) // 2
        recent = sum(d.get("clicks", 0) for d in gsc_daily[-win:])
        prior = sum(d.get("clicks", 0) for d in gsc_daily[-2 * win:-win])
        if prior > 0:
            growth = (recent - prior) / prior
            traffic_score = min(100, max(0, 50 + growth * 200))
            sign = "+" if growth >= 0 else ""
            traffic_detail = f"{recent} vs {prior} clicks ({sign}{round(growth * 100)}%, {win}d)"
        elif recent > 0:
            traffic_score = 75.0
            traffic_detail = f"{recent} clicks (new traffic, {win}d)"

    # 4) Technical (25%) — on-page technical health, distinct from raw speed
    tech_score = 0.0
    tech_detail = "No audit yet"
    if latest_audit:
        parts = [
            latest_audit.get("seo_score", 0) or 0,
            latest_audit.get("best_practices_score", 0) or 0,
            latest_audit.get("accessibility_score", 0) or 0,
        ]
        tech_score = sum(parts) / 3
        tech_detail = (f"SEO {round(parts[0])} · best-practices {round(parts[1])} "
                       f"· a11y {round(parts[2])}")

    buckets = [
        {"key": "pagespeed", "label": "Performance", "value": round(perf),
         "weight": 25, "detail": perf_detail},
        {"key": "keyword_coverage", "label": "Keyword coverage", "value": round(kw_pct),
         "weight": 25, "detail": kw_detail},
        {"key": "traffic_trend", "label": "Traffic trend", "value": round(traffic_score),
         "weight": 25, "detail": traffic_detail},
        {"key": "technical", "label": "Technical SEO", "value": round(tech_score),
         "weight": 25, "detail": tech_detail},
    ]
    score = round(perf * 0.25 + kw_pct * 0.25 + traffic_score * 0.25 + tech_score * 0.25)
    return {"score": score, "buckets": buckets}


def persist_seo_health(db, customer_id: str, date: str | None = None) -> dict | None:
    """Compute today's SEO health for a customer and upsert it into history.

    Returns the computed result, or None if the customer has no usable data.
    """
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    latest_audit = db.get_latest_audit(customer_id)
    keyword_summary = db.get_keyword_summary(customer_id)
    gsc_daily = list(reversed(db.get_gsc_daily(customer_id, limit=60)))
    if not latest_audit and not keyword_summary and not gsc_daily:
        return None
    result = compute_seo_health(latest_audit, keyword_summary, gsc_daily)
    b = result["buckets"]
    db.save_seo_health(
        customer_id, date, result["score"],
        pagespeed=b[0]["value"], keyword_coverage=b[1]["value"],
        traffic_trend=b[2]["value"], technical=b[3]["value"],
        breakdown_json=json.dumps(b),
    )
    return result
