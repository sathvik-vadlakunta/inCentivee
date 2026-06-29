#!/usr/bin/env python3
"""Bi-weekly content cadence — turn each active customer's Google Search Console
queries into fresh content recommendations (the #5 search-data engine).

Runs every 2 weeks so each client gets a steady pipeline of intent-driven content
ideas (striking-distance, low-CTR, question, and untapped queries) rather than
relying on someone clicking "From Search Data" by hand. Idempotent: skips queries
that already have a pending recommendation.

    python3 scripts/biweekly_content.py --all
    python3 scripts/biweekly_content.py --customer paradigm-experts
    python3 scripts/biweekly_content.py --all --dry-run

Cron (Monday 07:00 — idempotent top-up; dedupes so weekly cadence is safe):
    0 7 * * 1 docker exec practicerank-dashboard
      python3 /app/scripts/biweekly_content.py --all
      >> /home/kody/dental-marketing/logs/biweekly_content.log 2>&1
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime  # noqa: E402

from geo_agent import fatjoe_plan  # noqa: E402
from geo_agent.db import CustomerDB  # noqa: E402
from geo_agent.keyword_content import recommend_from_search_data  # noqa: E402

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", help="single customer id")
    ap.add_argument("--all", action="store_true", help="all active/onboarding customers")
    ap.add_argument("--max", type=int, default=None,
                    help="override max recs per customer (default: tier-driven content quota)")
    ap.add_argument("--dry-run", action="store_true", help="don't persist (counts only)")
    args = ap.parse_args()

    db = CustomerDB(DB_PATH)
    if args.customer:
        c = db.get_customer(args.customer)
        targets = [c] if c else []
    elif args.all:
        targets = [c for c in db.list_customers() if c.get("status") in ("onboarding", "active")]
    else:
        ap.error("pass --customer <id> or --all")
        return

    print(f"[{datetime.now().isoformat()}] biweekly content — {len(targets)} customer(s)")
    total = 0
    for i, c in enumerate(targets):
        if not c:
            continue
        cid = c["id"]
        try:
            if args.dry_run:
                # Classify without persisting: reuse the recommender on a throwaway
                # in-memory view is overkill — just report query volume.
                from datetime import timedelta
                end = datetime.utcnow().strftime("%Y-%m-%d")
                start = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
                q = db.get_query_aggregates(cid, start, end, min_impressions=10, limit=300)
                print(f"  [{i+1}/{len(targets)}] {cid}: {len(q)} candidate queries (dry-run)")
                continue
            # Tier dictates how many content pieces we queue this month, unless
            # --max explicitly overrides. Optimize=2, Grow=4, Dominate=8.
            if args.max is not None:
                quota = args.max
            else:
                sub = db.get_subscription_for_customer(cid)
                plan_name = sub["plan_name"] if sub else None
                quota = fatjoe_plan.monthly_content_quota(plan_name, c.get("tier_override"))
            created = recommend_from_search_data(db, cid, max_recs=quota)
            total += len(created)
            # Monthly GBP Q&A (idempotent per month — skips if this month's rec exists).
            gbp = None
            try:
                from geo_agent.gbp_qa import generate_gbp_qa
                gbp = generate_gbp_qa(db, cid)
            except Exception as qe:  # noqa: BLE001
                print(f"  [{i+1}/{len(targets)}] {cid}: GBP Q&A error {qe}")
            total += 1 if gbp else 0
            print(f"  [{i+1}/{len(targets)}] {cid}: +{len(created)} content rec(s)"
                  f"{' +GBP Q&A' if gbp else ''}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(targets)}] {cid}: ERROR {e}")

    db.close()
    print(f"[{datetime.now().isoformat()}] biweekly content complete — {total} recs created")


if __name__ == "__main__":
    main()
