#!/usr/bin/env python3
"""Approve staged changes for a customer.

Usage:
    python scripts/approve.py --customer downtown-dental
    python scripts/approve.py --customer downtown-dental --auto  # Skip confirmation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent.staging import StagingManager


def main():
    parser = argparse.ArgumentParser(description="Approve staged changes")
    parser.add_argument("--customer", required=True, help="Customer ID")
    parser.add_argument("--auto", action="store_true", help="Auto-approve without confirmation")
    parser.add_argument("--db", default=None, help="Database file path")
    parser.add_argument("--data-dir", default=None, help="Data directory path")
    args = parser.parse_args()

    data_dir = args.data_dir or str(Path(__file__).resolve().parent.parent / "data")
    staging = StagingManager(data_dir=data_dir)
    db = CustomerDB(db_path=args.db)

    try:
        if not staging.is_staged(args.customer):
            print(f"No staged changes for {args.customer}")
            sys.exit(1)

        if staging.is_approved(args.customer):
            print(f"Changes for {args.customer} are already approved.")
            if input("Publish now? (y/n): ").strip().lower() in ("y", "yes"):
                published = staging.publish_staged(args.customer)
                print(f"Published {len(published)} files.")
            return

        # Show diff
        diff_report = staging.generate_diff_report(args.customer)
        print(diff_report)
        print()

        if args.auto:
            approved = True
        else:
            choice = input("Approve these changes? (y/n): ").strip().lower()
            approved = choice in ("y", "yes")

        if approved:
            staging.approve_changes(args.customer)

            # Update run in DB
            latest_run = db.get_latest_run(args.customer)
            if latest_run and latest_run["status"] == "staged":
                db.approve_run(latest_run["id"])

            print(f"Changes approved for {args.customer}.")
            print("Run with --publish flag or wait for the monthly publish cron.")
        else:
            print("Changes not approved.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
