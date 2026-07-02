"""AI Share-of-Voice — the flagship moat metric.

Every agency does backlinks. Almost none can say "we get you named by ChatGPT,
Perplexity, and Google AI Overviews more than your competitors." This module turns
the existing entity-mention data (``db.get_share_of_voice`` /
``get_share_of_voice_history``) into a single 0–100 score with a trend, so the
report, the dashboard, and the sales deck all read one number from one place.

Score definition (kept honest and explainable):
    AI Share-of-Voice = share of AI brand-mentions, among *real businesses*, that
    name this practice — i.e. customer_mentions / all_business_mentions, ×100.

It answers "when AI engines list businesses for your buyer queries, how often are
YOU one of them, vs everyone else." Rank (1 = most-named) is carried alongside for
context, since a #1 practice in a crowded market can still have a modest raw share.
"""

from __future__ import annotations


def _score_from_share(share: float | None) -> int:
    return int(round((share or 0) * 100))


def sov_summary(db, customer_id: str) -> dict | None:
    """Flagship SoV summary, or None when there's no AI-mention data yet.

    Returns:
        score        0–100 AI Share-of-Voice (current pooled value)
        rank         1-based rank among named businesses (or None)
        competitors  [{name, share_pct, ...}] top rivals by share
        delta        score change vs the first point in history (or None)
        history      [{date, sov_pct, rank}] chronological, for the sparkline
        leads        True when the practice is the #1-named business
    """
    sov = db.get_share_of_voice(customer_id)
    if not sov or not sov.get("total_entity_mentions"):
        return None

    score = _score_from_share(sov.get("customer_share"))
    history = db.get_share_of_voice_history(customer_id) or []

    delta = None
    if len(history) >= 2:
        first = history[0].get("sov_pct")
        if first is not None:
            delta = round(score - first)

    competitors = [
        {"name": c["name"], "share_pct": round((c.get("share", 0) or 0) * 100)}
        for c in sov.get("competitors", [])[:5]
    ]

    return {
        "score": score,
        "rank": sov.get("customer_rank"),
        "total_named": (sov.get("total_unique_entities") or 0),
        "competitors": competitors,
        "delta": delta,
        "history": history,
        "leads": sov.get("customer_rank") == 1,
        "runs_analyzed": sov.get("runs_analyzed", 0),
    }


def sov_score(db, customer_id: str) -> tuple[int | None, int | None]:
    """(score, delta) for the dashboard tile — cheap wrapper. (None, None) if no data."""
    s = sov_summary(db, customer_id)
    if not s:
        return None, None
    return s["score"], s["delta"]
