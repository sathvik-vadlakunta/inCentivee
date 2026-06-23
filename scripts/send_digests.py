#!/usr/bin/env python3
"""Send operational digests (Dan + CC Kody). Run from cron.

    python3 scripts/send_digests.py --monthly-fatjoe   # day 1 of the month
    python3 scripts/send_digests.py --daily-attention   # every morning
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent import digests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("practicerank.digests")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--monthly-fatjoe", action="store_true", help="Send the monthly FATJOE order digest")
    ap.add_argument("--daily-attention", action="store_true", help="Send the daily needs-attention digest")
    args = ap.parse_args()

    db = CustomerDB()
    try:
        if args.monthly_fatjoe:
            sent = digests.monthly_fatjoe_digest(db)
            logger.info("Monthly FATJOE digest %s", "sent" if sent else "not sent")
        if args.daily_attention:
            sent = digests.daily_attention_digest(db)
            logger.info("Daily attention digest %s", "sent" if sent else "skipped (nothing urgent)")
        if not (args.monthly_fatjoe or args.daily_attention):
            ap.error("choose --monthly-fatjoe and/or --daily-attention")
    finally:
        db.close()


if __name__ == "__main__":
    main()
