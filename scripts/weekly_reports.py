#!/usr/bin/env python3
"""Weekly customer report job (R0) — ingest fresh data, then snapshot reports.

Run via cron (Mondays 08:00):
    0 8 * * 1 docker exec practicerank-dashboard python3 /app/scripts/weekly_reports.py

For each active customer (onboarding_step in live/content/monitoring) it:
  1. R1 — pulls GSC query-level data         → gsc_query_daily
  2. R2 — refreshes competitor ratings        → competitor_snapshots
  3. R3 — pulls GA4 conversions (if config)   → conversions_daily
  4. R4 — pulls BrightLocal citations (if config) → citations
  5. R0 — generates + persists the weekly report snapshot

IMPORTANT: This job does NOT email customers. Reports are generated and stored
only; view them in the dashboard. Customer email delivery is intentionally
deferred until we're ready to turn it on.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime  # noqa: E402

from geo_agent import weekly_report as wr  # noqa: E402
from geo_agent.brightlocal_client import track_citations  # noqa: E402
from geo_agent.db import CustomerDB  # noqa: E402
from geo_agent.ga4_client import track_conversions  # noqa: E402
from geo_agent.google_places import refresh_competitor_snapshots  # noqa: E402
from geo_agent.moz_client import track_competitor_da, track_domain_authority  # noqa: E402
from geo_agent.gsc_client import track_gsc_queries  # noqa: E402

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")
EMAIL_CUSTOMERS = False  # ← keep False until we're ready to send to customers


def _safe(label, fn, *args):
    """Run an ingest step, swallowing/loggng failures so one bad source can't
    block the rest of the job."""
    try:
        result = fn(*args)
        print(f"    {label}: {result}")
    except Exception as exc:  # noqa: BLE001
        print(f"    {label}: ERROR {exc}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate customer reports (weekly/monthly/quarterly).")
    ap.add_argument("--period", type=int, default=7,
                    help="report window in days: 7 weekly (default), 30 monthly, 90 quarterly")
    args = ap.parse_args()
    period = args.period
    # Only the weekly run refreshes data sources; monthly/quarterly just re-generate
    # the report over a longer window from the data the weekly run already pulled.
    refresh = period == 7
    label = wr._REPORT_TYPE_BY_DAYS.get(period, f"{period}d")

    db = CustomerDB(DB_PATH)
    customers = [c for c in db.list_customers()
                 if c.get("onboarding_step") in wr.ACTIVE_STEPS]
    print(f"[{datetime.now().isoformat()}] {label} reports: {len(customers)} active customers")

    for c in customers:
        cid = c["id"]
        print(f"  {cid} ({c.get('name')})")
        if refresh:
            _safe("R1 gsc_queries", track_gsc_queries, db, cid)
            _safe("R2 competitors", refresh_competitor_snapshots, db, cid)
            _safe("R3 ga4_conversions", track_conversions, db, cid)
            _safe("R4 citations", track_citations, db, cid)
            # Weekly DA refresh so the report's week-over-week DA deltas populate.
            _safe("R5 domain_authority", track_domain_authority, db, cid)
            _safe("R5 competitor_da", track_competitor_da, db, cid)
        try:
            res = wr.generate_and_store(db, cid, period_days=period)
            print(f"    R0 {res['report_type']} report: score {res['score']} (ending {res['period_end']})")
            if EMAIL_CUSTOMERS:
                # Intentionally disabled — see module docstring.
                pass
        except Exception as exc:  # noqa: BLE001
            print(f"    R0 report: ERROR {exc}")

    db.close()
    print(f"[{datetime.now().isoformat()}] Weekly reports complete (emails disabled)")


if __name__ == "__main__":
    main()
