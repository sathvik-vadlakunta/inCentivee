#!/usr/bin/env python3
"""Source verbatim-verified expert quotes for a customer and store them.

Usage:
    python scripts/source_quotes.py <customer_id> [--urls URL [URL ...]]
                                    [--max N] [--replace] [--dry-run]

Only quotes verified to appear verbatim in their source are stored into
customers.verified_quotes. Operator-supplied article URLs (--urls) are the most
reliable input — pass specific pages known to contain attributed expert quotes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from geo_agent.db import CustomerDB
from geo_agent import quote_sourcer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("customer_id")
    ap.add_argument("--urls", nargs="*", default=[], help="Specific source article URLs")
    ap.add_argument("--max", type=int, default=6, dest="max_quotes")
    ap.add_argument("--replace", action="store_true", help="Replace existing quotes instead of appending")
    ap.add_argument("--dry-run", action="store_true", help="Source + verify but do NOT persist")
    args = ap.parse_args()

    db = CustomerDB()
    try:
        if args.dry_run:
            # Persist-free path: monkeypatch the writer to a no-op for the run.
            orig = db.update_customer
            db.update_customer = lambda *a, **k: True  # type: ignore[assignment]
            try:
                report = quote_sourcer.source_quotes_for_customer(
                    db, args.customer_id, max_quotes=args.max_quotes,
                    extra_urls=args.urls, replace=args.replace)
            finally:
                db.update_customer = orig  # type: ignore[assignment]
        else:
            report = quote_sourcer.source_quotes_for_customer(
                db, args.customer_id, max_quotes=args.max_quotes,
                extra_urls=args.urls, replace=args.replace)
    finally:
        db.close()

    print(json.dumps(report, indent=2))
    print(f"\n{report['accepted']} verified, {report['rejected']} rejected, "
          f"{report.get('total_on_file', 0)} now on file"
          f"{' (DRY RUN — not saved)' if args.dry_run else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
