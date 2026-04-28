#!/usr/bin/env python3
"""Show monthly status for all customers.

Usage:
    python scripts/monthly_status.py
    python scripts/monthly_status.py --db path/to/db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent.staging import StagingManager


def main():
    parser = argparse.ArgumentParser(description="Monthly status overview")
    parser.add_argument("--db", default=None, help="Database file path")
    parser.add_argument("--data-dir", default=None, help="Data directory")
    args = parser.parse_args()

    data_dir = args.data_dir or str(Path(__file__).resolve().parent.parent / "data")
    db = CustomerDB(db_path=args.db)
    staging = StagingManager(data_dir=data_dir)

    try:
        customers = db.list_customers()

        if not customers:
            print("No customers in database.")
            print("Run: python scripts/onboard.py --import-json")
            return

        print(f"PracticeRank Monthly Status ({len(customers)} customers)")
        print("=" * 60)

        for c in customers:
            cid = c["id"]
            status_icon = {
                "onboarding": "[ONBOARDING]",
                "active": "[ACTIVE]    ",
                "paused": "[PAUSED]    ",
                "churned": "[CHURNED]   ",
            }.get(c["status"], "[???]       ")

            print(f"\n{status_icon} {c['name']} ({c['domain']})")

            # Platform access status
            pending = db.get_pending_access(cid)
            if pending:
                platforms = ", ".join(p["platform"].upper() for p in pending)
                print(f"  Pending access: {platforms}")

            # Latest run
            run = db.get_latest_run(cid)
            if run:
                run_status = run["status"]
                if run_status == "staged" and not run["approved"]:
                    print(f"  Staged changes awaiting approval (since {run['run_date'][:10]})")
                elif run_status == "approved":
                    print(f"  Approved, ready to publish (approved {run.get('approved_at', '')[:10]})")
                elif run_status == "published":
                    print(f"  Last published: {run.get('published_at', '')[:10]}")
                elif run_status == "failed":
                    errors = run.get("errors", [])
                    print(f"  Last run FAILED: {errors[0] if errors else 'unknown'}")
            else:
                print("  No runs yet")

            # Staging status
            if staging.is_staged(cid):
                if staging.is_approved(cid):
                    print("  Staging: APPROVED (ready to publish)")
                else:
                    print("  Staging: PENDING APPROVAL")

            # Latest KPIs
            places = db.get_google_places(cid)
            if places:
                print(f"  Reviews: {places['rating']} stars ({places['review_count']} reviews)")

        print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
