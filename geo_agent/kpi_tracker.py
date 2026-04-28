"""KPI tracking for customer practices.

Tracks Google reviews, AI search mentions, llms.txt hits, and schema validation.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from geo_agent.db import CustomerDB
from geo_agent.google_places import fetch_place_data

logger = logging.getLogger(__name__)


def track_google_reviews(db: CustomerDB, customer_id: str) -> dict | None:
    """Fetch current Google Places data and record review KPIs."""
    customer = db.get_customer(customer_id)
    if not customer:
        logger.warning(f"Customer not found: {customer_id}")
        return None

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        logger.warning("GOOGLE_PLACES_API_KEY not set — skipping review tracking")
        return None

    verified = fetch_place_data(
        name=customer["name"],
        city=customer["city"],
        state=customer["state"],
        domain=customer["domain"],
        phone=customer.get("phone", ""),
        api_key=api_key,
    )

    if not verified:
        logger.warning(f"No Google Places match for {customer_id}")
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Record KPIs
    db.record_kpi(customer_id, "review_count", verified.review_count, today)
    db.record_kpi(customer_id, "rating", verified.rating, today)

    # Update stored Places data
    db.upsert_google_places(
        customer_id=customer_id,
        place_id=verified.place_id,
        rating=verified.rating,
        review_count=verified.review_count,
        match_confidence=verified.match_confidence,
        lat=verified.lat,
        lng=verified.lng,
    )

    # Calculate delta from last month
    prev_reviews = db.get_kpis(customer_id, "review_count", limit=2)
    delta = 0
    if len(prev_reviews) >= 2:
        delta = int(prev_reviews[0]["value"] - prev_reviews[1]["value"])

    result = {
        "review_count": verified.review_count,
        "rating": verified.rating,
        "review_delta": delta,
        "match_confidence": verified.match_confidence,
    }

    logger.info(
        f"KPI tracked for {customer_id}: "
        f"{verified.rating} stars, {verified.review_count} reviews (delta: {delta:+d})"
    )
    return result


def track_llms_txt_hits(
    db: CustomerDB, customer_id: str,
    cf_api_token: str = "", cf_account_id: str = "",
) -> dict | None:
    """Pull Cloudflare Worker analytics for llms.txt request counts.

    Queries the /stats/{domain} endpoint on the Cloudflare Worker.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        return None

    cf_api_token = cf_api_token or os.environ.get("CF_API_TOKEN", "")
    if not cf_api_token:
        logger.info("CF_API_TOKEN not set — skipping llms.txt hit tracking")
        return None

    # Try to fetch stats from the worker
    domain = customer["domain"]
    worker_url = os.environ.get("WORKER_STATS_URL", "")
    if not worker_url:
        logger.info("WORKER_STATS_URL not set — skipping llms.txt hit tracking")
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{worker_url}/stats/{domain}",
                headers={"Authorization": f"Bearer {cf_api_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch llms.txt stats: {e}")
        return None

    hits = data.get("total_hits", 0)
    today_hits = data.get("today_hits", 0)
    by_agent = data.get("by_agent", {})
    daily_history = data.get("daily_history", [])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db.record_kpi(customer_id, "llms_txt_hits", hits, today)

    # Record per-agent hits as separate KPIs
    for agent_name, agent_data in by_agent.items():
        agent_total = agent_data.get("total", 0)
        if agent_total > 0:
            db.record_kpi(customer_id, f"llms_hits_{agent_name}", agent_total, today)

    logger.info(
        f"KPI tracked for {customer_id}: {hits} llms.txt hits "
        f"(today: {today_hits}, agents: {list(by_agent.keys())})"
    )
    return {
        "llms_txt_hits": hits,
        "today_hits": today_hits,
        "by_agent": by_agent,
        "daily_history": daily_history,
    }


def generate_kpi_report(db: CustomerDB, customer_id: str) -> str:
    """Generate a text-based KPI report for a customer."""
    customer = db.get_customer(customer_id)
    if not customer:
        return f"Customer not found: {customer_id}"

    lines = [
        f"KPI Report: {customer['name']}",
        f"Domain: {customer['domain']}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 50,
        "",
    ]

    metrics = [
        ("review_count", "Google Reviews"),
        ("rating", "Google Rating"),
        ("ai_mentions", "AI Search Mentions"),
        ("ai_avg_position", "AI Search Position (lower is better)"),
        ("llms_txt_hits", "llms.txt Hits"),
    ]

    for metric_key, metric_name in metrics:
        kpis = db.get_kpis(customer_id, metric_key, limit=3)
        if kpis:
            current = kpis[0]["value"]
            lines.append(f"{metric_name}: {current}")
            if len(kpis) >= 2:
                prev = kpis[1]["value"]
                delta = current - prev
                direction = "+" if delta > 0 else ""
                lines.append(f"  Change: {direction}{delta}")
            lines.append(f"  Last recorded: {kpis[0]['date']}")
        else:
            lines.append(f"{metric_name}: No data yet")
        lines.append("")

    # Competitor comparison
    competitors = db.get_competitors(customer_id)
    if competitors:
        lines.append("Competitors:")
        places = db.get_google_places(customer_id)
        our_reviews = places["review_count"] if places else 0
        for c in competitors[:5]:
            gap = c["review_count"] - our_reviews
            gap_str = f"({gap:+d} vs you)" if our_reviews else ""
            lines.append(f"  {c['name']}: {c['rating']} stars, {c['review_count']} reviews {gap_str}")
        lines.append("")

    # AI search position trend
    position_kpis = db.get_kpis(customer_id, "ai_avg_position", limit=6)
    if position_kpis:
        lines.append("AI Search Position Trend:")
        for k in position_kpis:
            lines.append(f"  {k['date']}: #{k['value']:.1f}")
        lines.append("")

    # Per-agent llms.txt breakdown
    agent_names = ["chatgpt", "claude", "perplexity", "google", "bing", "apple"]
    agent_data = []
    for agent in agent_names:
        kpi = db.get_latest_kpi(customer_id, f"llms_hits_{agent}")
        if kpi and kpi["value"] > 0:
            agent_data.append((agent.title(), int(kpi["value"])))
    if agent_data:
        lines.append("llms.txt Hits by AI Agent:")
        for name, count in sorted(agent_data, key=lambda x: -x[1]):
            lines.append(f"  {name}: {count:,}")
        lines.append("")

    return "\n".join(lines)
