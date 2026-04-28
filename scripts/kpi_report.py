#!/usr/bin/env python3
"""Generate KPI reports for customers.

Usage:
    python scripts/kpi_report.py --customer hilltop-family-dental
    python scripts/kpi_report.py --all
    python scripts/kpi_report.py --track --customer hilltop-family-dental  # Run tracking first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent.kpi_tracker import generate_kpi_report, track_google_reviews


def main():
    parser = argparse.ArgumentParser(description="KPI reports for PracticeRank customers")
    parser.add_argument("--customer", help="Customer ID")
    parser.add_argument("--all", action="store_true", help="Report for all customers")
    parser.add_argument("--track", action="store_true", help="Run KPI tracking before reporting")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        if args.all:
            customers = db.list_customers()
        elif args.customer:
            customer = db.get_customer(args.customer)
            if not customer:
                print(f"Customer not found: {args.customer}")
                sys.exit(1)
            customers = [customer]
        else:
            print("Specify --customer <id> or --all")
            sys.exit(1)

        for customer in customers:
            cid = customer["id"]

            if args.track:
                print(f"Tracking KPIs for {customer['name']}...")
                track_google_reviews(db, cid)
                print()

            report = generate_kpi_report(db, cid)
            print(report)
            print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
