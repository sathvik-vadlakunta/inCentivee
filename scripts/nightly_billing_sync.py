#!/usr/bin/env python3
"""Nightly Stripe reconciliation — self-heals any webhook events missed during a
deploy or outage by pulling current subscription state from Stripe. Run from cron.

    python3 scripts/nightly_billing_sync.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent import billing

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("practicerank.billing_sync")


def main():
    if not billing.billing_enabled():
        logger.warning("STRIPE_SECRET_KEY not set — skipping nightly billing sync.")
        return
    db = CustomerDB()
    try:
        n = billing.sync_all(db)
        logger.info("Nightly billing sync upserted %d subscription(s).", n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
