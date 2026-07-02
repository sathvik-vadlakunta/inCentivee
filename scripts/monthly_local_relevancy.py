#!/usr/bin/env python3
"""Local Relevancy Engine runner — one customer or all, staggered.

Runs the per-customer local-relevancy modules (citations/NAP, directory breadth,
+ later phases). No-ops cleanly for non-local business types and for customers
without a BrightLocal account configured. Does not email anyone.

    python3 scripts/monthly_local_relevancy.py --customer paradigm-experts
    python3 scripts/monthly_local_relevancy.py --all              # active book, staggered
    python3 scripts/monthly_local_relevancy.py --all --stagger 30
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime  # noqa: E402

from geo_agent.db import CustomerDB  # noqa: E402
from geo_agent.local_relevancy import run_local_relevancy  # noqa: E402

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", help="single customer id")
    ap.add_argument("--all", action="store_true", help="all active/onboarding customers")
    ap.add_argument("--stagger", type=int, default=30, help="seconds between customers (--all)")
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

    print(f"[{datetime.now().isoformat()}] local relevancy — {len(targets)} customer(s)")
    for i, c in enumerate(targets):
        if not c:
            continue
        print(f"  [{i + 1}/{len(targets)}] {c['id']} …", flush=True)
        try:
            r = run_local_relevancy(db, c["id"])
            if r.get("skipped"):
                print(f"      skipped: {r['skipped']}", flush=True)
            else:
                br = r["modules"]["directory_breadth"]
                cit = r["modules"]["citations"]
                print(f"      breadth {br['listed_ok']}/{br['target']} ({br['pct']}%); "
                      f"citations {'configured' if cit.get('configured') else 'not configured'}",
                      flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"      ERROR {e}", flush=True)
        if args.all and i < len(targets) - 1:
            time.sleep(args.stagger)
    db.record_job_run("monthly_local_relevancy")
    db.close()
    print(f"[{datetime.now().isoformat()}] done")


if __name__ == "__main__":
    main()
