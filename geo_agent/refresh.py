"""Scheduled data refresh — keep each active customer's GSC cache, keyword ranks, and site
audit fresh so the dashboard is accurate ON LOAD instead of stale-until-someone-clicks.

Before this, nothing populated gsc_daily_metrics (the cache the Overview falls back to) or
re-ran audits on a cadence — data only moved when a human clicked a button. Run daily via cron
inside the dashboard container:

    docker exec practicerank-dashboard python -m geo_agent.refresh

Everything is fail-safe per customer + per source: one slow/broken customer never blocks the rest.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)


def refresh_customer(db, customer_id: str) -> dict:
    """Refresh one customer's GSC metrics + keyword ranks + site audit. Fail-safe per source."""
    out = {"customer_id": customer_id, "gsc_metrics": False, "gsc_queries": False, "audit": False}
    cust = db.get_customer(customer_id)
    if not cust or not cust.get("domain"):
        return out

    # GSC daily metrics — populates gsc_daily_metrics, the cache the Overview reads/falls back to.
    try:
        from geo_agent.gsc_client import track_gsc_metrics, track_gsc_queries
        if track_gsc_metrics(db, customer_id):
            out["gsc_metrics"] = True
        if track_gsc_queries(db, customer_id):
            out["gsc_queries"] = True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"refresh: GSC pull failed for {customer_id}: {e}")

    # Site audit — refreshes scores + auto-closes fixed issues (PSI score preserved on failure).
    try:
        from geo_agent.site_auditor import run_site_audit
        res = run_site_audit(cust["domain"], cust.get("platform", ""))
        db.save_site_audit(customer_id, res["audit_date"], res["scores"], res["issues"], res.get("raw_data"))
        out["audit"] = True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"refresh: audit failed for {customer_id}: {e}")

    # Surface a 'last refreshed' marker for the UI.
    try:
        db.record_kpi(customer_id, "data_last_refreshed", 1,
                      datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    except Exception:  # noqa: BLE001
        pass
    return out


def refresh_all_active(stagger_seconds: float = 2.0) -> list[dict]:
    """Refresh every active/onboarding customer with a domain. Staggered to be polite to APIs."""
    db = CustomerDB()
    try:
        custs = [c for c in db.list_customers()
                 if c.get("status") in ("active", "onboarding") and c.get("domain")]
        logger.info(f"refresh: {len(custs)} customers to refresh")
        results = []
        for i, c in enumerate(custs):
            results.append(refresh_customer(db, c["id"]))
            if i < len(custs) - 1:
                time.sleep(stagger_seconds)
        return results
    finally:
        db.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = refresh_all_active()
    ok = sum(1 for r in results if r["gsc_metrics"] or r["audit"])
    logger.info(f"refresh complete: {ok}/{len(results)} customers updated")
    print(f"refreshed {ok}/{len(results)} customers")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
