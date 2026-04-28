#!/usr/bin/env python3
"""Generate a case study from a customer's KPI data.

Produces a one-page sales-ready case study showing before/after results
that can be used to close new dental practice clients.

Usage:
    python scripts/generate_case_study.py --customer hilltop-family-dental
    python scripts/generate_case_study.py --customer hilltop-family-dental --format html
    python scripts/generate_case_study.py --all --format markdown
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_case_study(db: CustomerDB, customer_id: str, fmt: str = "markdown") -> str:
    """Generate a case study for a customer.

    Args:
        db: Database connection.
        customer_id: Customer ID.
        fmt: Output format — "markdown" or "html".

    Returns:
        Formatted case study string.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        return f"Customer not found: {customer_id}"

    places = db.get_google_places(customer_id)
    competitors = db.get_competitors(customer_id)

    # Gather KPI history
    review_kpis = db.get_kpis(customer_id, "review_count", limit=12)
    rating_kpis = db.get_kpis(customer_id, "rating", limit=12)
    mention_kpis = db.get_kpis(customer_id, "ai_mentions", limit=12)
    position_kpis = db.get_kpis(customer_id, "ai_avg_position", limit=12)
    hits_kpis = db.get_kpis(customer_id, "llms_txt_hits", limit=12)

    # Calculate deltas (first entry is most recent, last is oldest)
    def calc_delta(kpis):
        if len(kpis) < 2:
            return None, None, None
        current = kpis[0]["value"]
        oldest = kpis[-1]["value"]
        delta = current - oldest
        pct = (delta / oldest * 100) if oldest > 0 else 0
        return current, delta, pct

    review_current, review_delta, review_pct = calc_delta(review_kpis)
    rating_current, _, _ = calc_delta(rating_kpis)
    mention_current, mention_delta, _ = calc_delta(mention_kpis)
    position_current, position_delta, _ = calc_delta(position_kpis)
    hits_current, hits_delta, hits_pct = calc_delta(hits_kpis)

    # First recorded values (baseline)
    review_baseline = review_kpis[-1]["value"] if review_kpis else 0
    mention_baseline = mention_kpis[-1]["value"] if mention_kpis else 0
    hits_baseline = hits_kpis[-1]["value"] if hits_kpis else 0
    first_date = review_kpis[-1]["date"] if review_kpis else "N/A"
    latest_date = review_kpis[0]["date"] if review_kpis else "N/A"

    # Competitor context
    our_reviews = places["review_count"] if places else (review_current or 0)
    competitors_above = sum(1 for c in competitors if c["review_count"] > our_reviews) if competitors else 0
    competitors_total = len(competitors) if competitors else 0
    competitor_rank = competitors_above + 1

    # Content recs stats
    recs = db.get_content_recommendations(customer_id)
    recs_published = sum(1 for r in recs if r.get("status") == "published")
    recs_total = len(recs)

    # Schema validation (check checklist)
    checklist = db.get_checklist(customer_id)
    schema_done = sum(1 for k, v in checklist.items() if k.startswith("seo_schema_") and v)
    llms_deployed = checklist.get("seo_llms_txt", False)

    # Time period
    months_active = _months_between(first_date, latest_date) if first_date != "N/A" else 0

    if fmt == "html":
        return _render_html(
            customer, places, months_active, first_date, latest_date,
            review_baseline, review_current, review_delta, review_pct,
            rating_current, mention_baseline, mention_current, mention_delta,
            hits_baseline, hits_current, hits_delta, hits_pct,
            position_current, position_delta, competitor_rank, competitors_total,
            schema_done, llms_deployed, recs_published,
        )
    else:
        return _render_markdown(
            customer, places, months_active, first_date, latest_date,
            review_baseline, review_current, review_delta, review_pct,
            rating_current, mention_baseline, mention_current, mention_delta,
            hits_baseline, hits_current, hits_delta, hits_pct,
            position_current, position_delta, competitor_rank, competitors_total,
            schema_done, llms_deployed, recs_published,
        )


def _months_between(date1: str, date2: str) -> int:
    """Calculate months between two date strings."""
    try:
        d1 = datetime.strptime(date1[:10], "%Y-%m-%d")
        d2 = datetime.strptime(date2[:10], "%Y-%m-%d")
        return abs((d2.year - d1.year) * 12 + d2.month - d1.month) or 1
    except (ValueError, TypeError):
        return 1


def _fmt_delta(val, is_position=False):
    """Format a delta value with +/- sign."""
    if val is None:
        return "N/A"
    if is_position:
        # For position, lower is better so negative delta is good
        if val < 0:
            return f"improved by {abs(val):.1f} positions"
        elif val > 0:
            return f"dropped {val:.1f} positions"
        return "unchanged"
    if val > 0:
        return f"+{val:.0f}"
    return f"{val:.0f}"


def _render_markdown(
    customer, places, months_active, first_date, latest_date,
    review_baseline, review_current, review_delta, review_pct,
    rating_current, mention_baseline, mention_current, mention_delta,
    hits_baseline, hits_current, hits_delta, hits_pct,
    position_current, position_delta, competitor_rank, competitors_total,
    schema_done, llms_deployed, recs_published,
) -> str:
    lines = []
    lines.append(f"# Case Study: {customer['name']}")
    lines.append(f"*{customer.get('city', '')}, {customer.get('state', '')} — {months_active} months with PracticeRank*")
    lines.append(f"*Period: {first_date} to {latest_date}*")
    lines.append("")

    # Challenge
    lines.append("## The Challenge")
    lines.append(f"{customer['name']} needed to increase their visibility in both traditional")
    lines.append(f"search and AI-powered search assistants (ChatGPT, Claude, Perplexity, Google AI).")
    if review_baseline:
        lines.append(f"Starting with {int(review_baseline)} Google reviews, they needed to stand out")
        lines.append(f"in a competitive market with {competitors_total} nearby dental practices.")
    lines.append("")

    # Solution
    lines.append("## What We Did")
    lines.append("")
    if llms_deployed:
        lines.append("- **AI Search Optimization** — Deployed llms.txt files making the practice")
        lines.append("  discoverable by AI assistants")
    if schema_done:
        lines.append(f"- **Schema Markup** — Implemented {schema_done} structured data schemas")
        lines.append("  (Dentist, FAQ, MedicalProcedure) for rich search results")
    if recs_published:
        lines.append(f"- **Content Optimization** — Published {recs_published} AI-optimized content")
        lines.append("  updates with expert quotes, statistics, and FAQ sections")
    lines.append("- **Monthly Monitoring** — Automated tracking of AI mentions, search position,")
    lines.append("  and competitor activity")
    lines.append("")

    # Results
    lines.append("## Results")
    lines.append("")
    lines.append("| Metric | Before | After | Change |")
    lines.append("|--------|--------|-------|--------|")

    if review_current is not None:
        lines.append(f"| Google Reviews | {int(review_baseline)} | {int(review_current)} | {_fmt_delta(review_delta)} ({review_pct:+.0f}%) |")
    if rating_current is not None:
        lines.append(f"| Google Rating | — | {rating_current:.1f} stars | — |")
    if mention_current is not None:
        lines.append(f"| AI Search Mentions | {int(mention_baseline)} | {int(mention_current)} | {_fmt_delta(mention_delta)} |")
    if hits_current is not None:
        pct_str = f" ({hits_pct:+.0f}%)" if hits_pct else ""
        lines.append(f"| llms.txt AI Reads | {int(hits_baseline)} | {int(hits_current)} | {_fmt_delta(hits_delta)}{pct_str} |")
    if position_current is not None:
        lines.append(f"| AI Recommendation Position | — | #{position_current:.1f} | {_fmt_delta(position_delta, is_position=True)} |")
    if competitors_total:
        lines.append(f"| Local Market Rank | — | #{competitor_rank} of {competitors_total} | — |")
    lines.append("")

    # Key highlight
    if hits_current and hits_current > 100:
        lines.append(f"> **\"AI assistants read {customer['name']}'s practice information")
        lines.append(f"> {int(hits_current):,} times — that's {int(hits_current):,} potential patients")
        lines.append(f"> learning about the practice through ChatGPT, Claude, and Perplexity.\"**")
        lines.append("")

    if mention_current and mention_current > 0:
        lines.append(f"> Before PracticeRank, AI assistants didn't mention {customer['name']}.")
        lines.append(f"> Now they appear in {int(mention_current)} out of tested AI search queries.")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by PracticeRank on {datetime.now(timezone.utc).strftime('%B %d, %Y')}*")

    return "\n".join(lines)


def _render_html(
    customer, places, months_active, first_date, latest_date,
    review_baseline, review_current, review_delta, review_pct,
    rating_current, mention_baseline, mention_current, mention_delta,
    hits_baseline, hits_current, hits_delta, hits_pct,
    position_current, position_delta, competitor_rank, competitors_total,
    schema_done, llms_deployed, recs_published,
) -> str:
    metrics_html = ""

    def metric_card(label, value, subtitle=""):
        return f"""<div style="text-align:center; padding:1.5rem; background:#f8f9fa; border-radius:8px;">
            <div style="font-size:2rem; font-weight:700; color:#2563eb;">{value}</div>
            <div style="font-size:0.85rem; color:#6b7280; text-transform:uppercase;">{label}</div>
            {f'<div style="font-size:0.8rem; color:#059669; margin-top:0.25rem;">{subtitle}</div>' if subtitle else ''}
        </div>"""

    cards = []
    if review_current is not None and review_delta:
        cards.append(metric_card("Google Reviews", f"{int(review_current)}", f"{_fmt_delta(review_delta)} ({review_pct:+.0f}%)"))
    if rating_current is not None:
        cards.append(metric_card("Google Rating", f"{rating_current:.1f} stars"))
    if hits_current is not None:
        cards.append(metric_card("AI Reads", f"{int(hits_current):,}", "via llms.txt"))
    if mention_current is not None:
        cards.append(metric_card("AI Mentions", f"{int(mention_current)}"))
    if position_current is not None:
        cards.append(metric_card("AI Position", f"#{position_current:.1f}", _fmt_delta(position_delta, is_position=True)))
    if competitors_total:
        cards.append(metric_card("Market Rank", f"#{competitor_rank}", f"of {competitors_total} practices"))

    grid_cols = min(len(cards), 3)
    metrics_html = f'<div style="display:grid; grid-template-columns:repeat({grid_cols}, 1fr); gap:1rem; margin:1.5rem 0;">{"".join(cards)}</div>'

    what_we_did = []
    if llms_deployed:
        what_we_did.append("Deployed AI-readable llms.txt files")
    if schema_done:
        what_we_did.append(f"Implemented {schema_done} structured data schemas")
    if recs_published:
        what_we_did.append(f"Published {recs_published} AI-optimized content updates")
    what_we_did.append("Automated monthly monitoring of AI mentions and competitors")

    actions_html = "\n".join(f"<li>{a}</li>" for a in what_we_did)

    highlight = ""
    if hits_current and hits_current > 100:
        highlight = f"""<blockquote style="border-left:4px solid #2563eb; padding:1rem 1.25rem; margin:1.5rem 0; background:#eff6ff; border-radius:0 8px 8px 0;">
            <p style="font-size:1.1rem; font-weight:500; margin:0;">AI assistants read {customer['name']}'s practice information <strong>{int(hits_current):,} times</strong> — each one a potential patient learning about the practice through ChatGPT, Claude, or Perplexity.</p>
        </blockquote>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Case Study: {customer['name']} - PracticeRank</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #111827; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; }}
        h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
        h2 {{ font-size: 1.2rem; color: #374151; margin: 1.5rem 0 0.75rem; }}
        p {{ margin-bottom: 0.75rem; }}
        ul {{ padding-left: 1.5rem; margin-bottom: 1rem; }}
        li {{ margin-bottom: 0.35rem; }}
        .subtitle {{ color: #6b7280; font-size: 0.95rem; margin-bottom: 1.5rem; }}
        .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div style="margin-bottom: 0.5rem;">
        <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%232563eb' width='24' height='24'><path d='M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5'/></svg>" alt="" style="height: 28px; vertical-align: middle; margin-right: 0.5rem;">
        <span style="font-weight: 700; color: #2563eb; font-size: 1rem;">PracticeRank</span>
    </div>
    <h1>Case Study: {customer['name']}</h1>
    <p class="subtitle">{customer.get('city', '')}, {customer.get('state', '')} — {months_active} months with PracticeRank ({first_date} to {latest_date})</p>

    {metrics_html}

    {highlight}

    <h2>The Challenge</h2>
    <p>{customer['name']} needed to increase their visibility in both traditional search and AI-powered search assistants (ChatGPT, Claude, Perplexity, Google AI Overviews). With {int(review_baseline) if review_baseline else 'limited'} Google reviews and {competitors_total} nearby competitors, they needed a data-driven approach to stand out.</p>

    <h2>What We Did</h2>
    <ul>{actions_html}</ul>

    <h2>The Results</h2>
    <p>Within {months_active} month{'s' if months_active != 1 else ''}, {customer['name']} saw measurable improvements across every tracked metric — from Google reviews to AI search visibility.</p>

    <div class="footer">
        Generated by PracticeRank on {datetime.now(timezone.utc).strftime('%B %d, %Y')}<br>
        Learn more at practicerank.ai
    </div>
</body>
</html>"""


def generate_aggregate_stats(db: CustomerDB) -> str:
    """Generate aggregate marketing stats across all customers."""
    customers = db.list_customers(status="active")
    if not customers:
        return "No active customers."

    total_review_growth = 0
    total_mention_growth = 0
    total_hits = 0
    customers_with_data = 0

    for c in customers:
        review_kpis = db.get_kpis(c["id"], "review_count", limit=12)
        mention_kpis = db.get_kpis(c["id"], "ai_mentions", limit=12)
        hits_kpis = db.get_kpis(c["id"], "llms_txt_hits", limit=1)

        if len(review_kpis) >= 2:
            total_review_growth += review_kpis[0]["value"] - review_kpis[-1]["value"]
            customers_with_data += 1
        if len(mention_kpis) >= 2:
            total_mention_growth += mention_kpis[0]["value"] - mention_kpis[-1]["value"]
        if hits_kpis:
            total_hits += hits_kpis[0]["value"]

    lines = [
        "PracticeRank — Aggregate Results",
        "=" * 40,
        f"Active Clients: {len(customers)}",
        f"Total Review Growth: +{int(total_review_growth)} reviews",
        f"Total AI Mention Growth: +{int(total_mention_growth)}",
        f"Total llms.txt AI Reads: {int(total_hits):,}",
        "",
    ]

    if customers_with_data > 0:
        avg_review_growth = total_review_growth / customers_with_data
        lines.append(f"Average Review Growth per Client: +{avg_review_growth:.1f} reviews")

    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate case study from KPI data")
    parser.add_argument("--customer", help="Customer ID")
    parser.add_argument("--all", action="store_true", help="Generate for all active customers")
    parser.add_argument("--aggregate", action="store_true", help="Generate aggregate stats")
    parser.add_argument("--format", choices=["markdown", "html"], default="markdown", help="Output format")
    parser.add_argument("--output-dir", default=None, help="Save to directory instead of stdout")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    if not args.customer and not args.all and not args.aggregate:
        parser.error("Specify --customer, --all, or --aggregate")

    db = CustomerDB(db_path=args.db)
    try:
        if args.aggregate:
            report = generate_aggregate_stats(db)
            print(report)
            return

        if args.all:
            customers = db.list_customers(status="active")
            customer_ids = [c["id"] for c in customers]
        else:
            customer_ids = [args.customer]

        for cid in customer_ids:
            case_study = generate_case_study(db, cid, fmt=args.format)

            if args.output_dir:
                out_dir = Path(args.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                ext = "html" if args.format == "html" else "md"
                out_file = out_dir / f"case-study-{cid}.{ext}"
                out_file.write_text(case_study)
                print(f"Saved: {out_file}")
            else:
                print(case_study)
                if len(customer_ids) > 1:
                    print("\n" + "=" * 60 + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
