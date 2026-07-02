"""Churn-risk radar — sort Dan's book by who's about to leave, not who's loud.

The accounts that cancel are usually the quiet ones: results drifting sideways, no
recent touchpoint, reviews stalled. This rolls the signals we already compute into a
single 0–100 *risk* score (higher = more likely to churn) with a plain-language
top reason, so the dashboard can surface at-risk clients before the cancel email.

Signals are additive and capped at 100. Each carries a weight and, when it fires, a
human reason string. We read the same helpers the report/dashboard use
(seo_score_and_delta, review_velocity, share_of_voice, outcomes) so the score never
diverges from what a client sees.
"""

from __future__ import annotations

from datetime import datetime, timezone

PAID_STATUSES = frozenset({"active", "trialing"})


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00").split("T")[0])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def churn_risk(db, customer: dict) -> dict:
    """Return {score, level, reasons, top_reason} for one customer.

    Only meaningful for active accounts; onboarding/paused/churned return a low,
    inert score so they sort below live at-risk clients.
    """
    cid = customer["id"]
    status = customer.get("status")
    if status != "active":
        return {"score": 0, "level": "none", "reasons": [], "top_reason": ""}

    score = 0
    reasons: list[tuple[int, str]] = []  # (weight, reason) — sorted for top_reason

    def hit(weight: int, reason: str):
        nonlocal score
        score += weight
        reasons.append((weight, reason))

    # 1) Payment not in good standing — the loudest churn signal there is.
    sub = db.get_subscription_for_customer(cid)
    if not sub:
        hit(25, "No paid plan linked")
    elif sub["status"] not in PAID_STATUSES:
        hit(40, f"Payment {sub['status'].replace('_', ' ')}")

    # 2) Results trend — flat or negative PracticeRank/SEO score is why clients leave.
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    seo_score, seo_delta = db.seo_score_and_delta(cid, cutoff)
    if seo_delta is not None:
        if seo_delta < 0:
            hit(20, f"Results slipping (score {seo_delta:+d} in 30d)")
        elif seo_delta == 0:
            hit(12, "Results flat for 30d")

    # 3) AI Share-of-Voice going the wrong way (our moat metric).
    try:
        from geo_agent import share_of_voice as _sov
        _, sov_delta = _sov.sov_score(db, cid)
        if sov_delta is not None and sov_delta < 0:
            hit(10, f"AI share-of-voice down {abs(sov_delta)} pts")
    except Exception:
        pass

    # 4) Review velocity stalled (only when we actually track reviews).
    try:
        if (db.get_review_stats(cid).get("total") or 0) > 0:
            vel = db.review_velocity(cid)
            if not vel["on_track"]:
                hit(12, f"Reviews behind pace ({vel['current']}/mo vs {vel['target']})")
    except Exception:
        pass

    # 5) No new-patient inquiries in 30d (nothing to show for the spend).
    try:
        from geo_agent import outcomes as _oc
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        # Only counts as a signal when tracking is live (conversions exist historically).
        if db.get_conversions(cid, "2000-01-01", end, channel="organic"):
            if _oc.inquiries_in_window(db, cid, start, end) == 0:
                hit(10, "No new-patient inquiries in 30d")
    except Exception:
        pass

    # 6) Touchpoint recency — a client who hasn't gotten a report in weeks feels ignored.
    snaps = db.get_report_snapshots(cid, limit=1)
    last_report = snaps[0].get("emailed_at") or snaps[0].get("created_at") if snaps else None
    days = _days_since(last_report)
    if days is None:
        hit(15, "No report ever sent")
    elif days > 45:
        hit(15, f"No report in {days}d")
    elif days > 30:
        hit(8, f"Last report {days}d ago")

    # 7) Onboarding friction lingering on a live account.
    pending = customer.get("pending_count")
    if pending is None:
        try:
            pending = len(db.get_pending_access(cid))
        except Exception:
            pending = 0
    if pending:
        hit(10, f"{pending} access item(s) still pending")

    score = min(score, 100)
    level = "high" if score >= 50 else "medium" if score >= 25 else "low"
    reasons.sort(key=lambda r: -r[0])
    reason_strs = [r[1] for r in reasons]
    return {
        "score": score,
        "level": level,
        "reasons": reason_strs,
        "top_reason": " · ".join(reason_strs[:2]),
    }
