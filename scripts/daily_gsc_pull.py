#!/usr/bin/env python3
"""Daily GSC keyword pull + site audit for all customers with GSC integration.

Run via cron: 0 6 * * * docker exec practicerank-dashboard python3 /app/scripts/daily_gsc_pull.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from geo_agent.db import CustomerDB
from geo_agent.gsc_client import fetch_top_queries
from geo_agent.site_auditor import run_site_audit

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")


def pull_keywords(db, customer_id, site_url):
    """Pull top 50 queries from GSC and save as tracked keywords."""
    end = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    queries = fetch_top_queries(site_url, start, end, limit=50)
    if not queries:
        print(f"  No GSC data for {customer_id}")
        return 0

    for q in queries:
        db.add_tracked_keyword(customer_id, q["query"], source="gsc")
        db.save_keyword_rank(
            customer_id, q["query"], today,
            round(q["position"], 1),
            clicks=q["clicks"],
            impressions=q["impressions"],
            ctr=round(q["ctr"], 4),
        )

    print(f"  {customer_id}: {len(queries)} keywords saved")
    return len(queries)


def run_audit(db, customer_id, domain):
    """Run a site audit and save results."""
    today = datetime.now().strftime("%Y-%m-%d")
    result = run_site_audit(domain)
    scores = result["scores"]
    issues = result["issues"]
    db.save_site_audit(customer_id, today, scores, issues, result.get("raw_data"))
    print(f"  {customer_id}: audit scores perf={scores['performance']} seo={scores['seo']} "
          f"a11y={scores['accessibility']} bp={scores['best_practices']}, {len(issues)} issues")


def main():
    db = CustomerDB(DB_PATH)
    customers = db.list_customers()

    print(f"[{datetime.now().isoformat()}] Daily GSC pull starting for {len(customers)} customers")

    for customer in customers:
        cid = customer["id"]
        domain = customer["domain"]

        # Check for GSC integration
        integ = db.get_integration(cid, "gsc")
        if integ and integ.get("status") == "active":
            site_url = integ.get("config", {}).get("property_url", f"sc-domain:{domain}")
            print(f"Pulling keywords for {cid} ({site_url})...")
            pull_keywords(db, cid, site_url)

        # Run site audit (weekly on Mondays, or if no audit exists yet)
        if datetime.now().weekday() == 0:  # Monday
            print(f"Running audit for {cid} ({domain})...")
            try:
                run_audit(db, cid, domain)
            except Exception as e:
                print(f"  Audit error for {cid}: {e}")

    db.close()
    print(f"[{datetime.now().isoformat()}] Daily GSC pull complete")


if __name__ == "__main__":
    main()
