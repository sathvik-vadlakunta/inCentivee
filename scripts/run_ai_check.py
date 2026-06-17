#!/usr/bin/env python3
"""Systematic AI-mention check runner — one customer or all, staggered.

Engine calls retry with exponential backoff on 429 / 5xx (see
check_ai_mentions._post_json), so a transient rate limit no longer gets recorded
as a missed mention. When running --all we stagger between customers to avoid
bursting the engine APIs.

    python3 scripts/run_ai_check.py --customer paradigm-experts
    python3 scripts/run_ai_check.py --all                 # active book, staggered
    python3 scripts/run_ai_check.py --all --stagger 90
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime  # noqa: E402

from geo_agent.db import CustomerDB  # noqa: E402
from scripts.weekly_ai_check import run_check  # noqa: E402

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", help="single customer id")
    ap.add_argument("--all", action="store_true", help="all active/onboarding customers")
    ap.add_argument("--stagger", type=int, default=45, help="seconds between customers (--all)")
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

    print(f"[{datetime.now().isoformat()}] AI check — {len(targets)} customer(s)")
    for i, c in enumerate(targets):
        if not c:
            continue
        print(f"  [{i + 1}/{len(targets)}] {c['id']} …", flush=True)
        try:
            r = run_check(db, c)
            print(f"      {r.get('mention_count')}/{r.get('total_queries')} "
                  f"({round((r.get('mention_rate') or 0) * 100)}%)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"      ERROR {e}", flush=True)
        if args.all and i < len(targets) - 1:
            time.sleep(args.stagger)
    db.close()
    print(f"[{datetime.now().isoformat()}] done")


if __name__ == "__main__":
    main()
