#!/usr/bin/env python3
"""Daily PracticeRank Score computation.

Run after daily_gsc_pull.py to compute and store scores for all customers.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent.practicerank_score import compute_practicerank_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    db = CustomerDB()
    try:
        customers = db.list_customers()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        computed = 0
        skipped = 0

        for customer in customers:
            cid = customer["id"]
            name = customer.get("name", cid)

            try:
                result = compute_practicerank_score(db, cid)
                overall = result.get("score")

                if overall is None:
                    logger.info(f"  {name}: insufficient data, skipping")
                    skipped += 1
                    continue

                pillars = result.get("pillars", {})
                db.save_practicerank_score(
                    customer_id=cid,
                    date=today,
                    overall=overall,
                    ai_visibility=pillars.get("ai_visibility", {}).get("score"),
                    search_growth=pillars.get("search_growth", {}).get("score"),
                    technical_health=pillars.get("technical_health", {}).get("score"),
                    content_velocity=pillars.get("content_velocity", {}).get("score"),
                    reputation=pillars.get("reputation", {}).get("score"),
                    breakdown_json=result.get("breakdown_json", "{}"),
                )
                grade = result.get("grade", {}).get("letter", "?")
                logger.info(f"  {name}: {overall}/100 ({grade}) — {result.get('available_count', 0)} pillars")
                computed += 1

            except Exception:
                logger.exception(f"  {name}: error computing score")

        logger.info(f"Done: {computed} scored, {skipped} skipped (insufficient data)")
        db.record_job_run("daily_score", detail=f"{computed} scored, {skipped} skipped")
    finally:
        db.close()


if __name__ == "__main__":
    main()
