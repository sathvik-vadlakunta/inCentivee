#!/usr/bin/env python3
"""One-time backfill: extract business entities from all existing AI mention responses.

Parses full_response in ai_mention_results to populate ai_response_entities
for competitive share-of-voice analysis.

Usage:
    python scripts/backfill_entities.py                    # preview
    python scripts/backfill_entities.py --apply            # run backfill
    python scripts/backfill_entities.py --customer sojo    # single customer
    python scripts/backfill_entities.py --db /path/to/db   # custom DB path
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from geo_agent.entity_extractor import extract_entities_from_response


def backfill(db: CustomerDB, customer_id: str | None = None, apply: bool = False):
    """Extract entities from all historical AI mention results."""
    # Get all runs
    query = "SELECT id, customer_id, run_date FROM ai_mention_runs WHERE total_queries > 0"
    params: list = []
    if customer_id:
        query += " AND customer_id = ?"
        params.append(customer_id)
    query += " ORDER BY run_date ASC"

    runs = [dict(r) for r in db.conn.execute(query, params).fetchall()]
    print(f"Found {len(runs)} runs to process")

    # Get customer names for entity matching
    customers: dict[str, str] = {}
    for row in db.conn.execute("SELECT id, name FROM customers").fetchall():
        customers[row["id"]] = row["name"]

    total_entities = 0
    total_runs_processed = 0
    total_runs_skipped = 0

    for run in runs:
        run_id = run["id"]
        cid = run["customer_id"]
        run_date = run["run_date"]
        customer_name = customers.get(cid, "")

        if not customer_name:
            print(f"  SKIP {run_id}: customer {cid} not found")
            continue

        # Check if already backfilled
        if db.has_entities_for_run(run_id):
            total_runs_skipped += 1
            continue

        # Get all results for this run
        results = db.conn.execute(
            "SELECT id, engine, prompt, prompt_category, full_response FROM ai_mention_results WHERE run_id = ? AND full_response != ''",
            (run_id,),
        ).fetchall()

        run_entities = []
        for r in results:
            entities = extract_entities_from_response(r["full_response"], customer_name)
            for ent in entities:
                run_entities.append({
                    "result_id": r["id"],
                    "run_id": run_id,
                    "customer_id": cid,
                    "entity_name": ent["name"],
                    "entity_name_normalized": ent["normalized_name"],
                    "is_customer": ent["is_customer"],
                    "position": ent["position"],
                    "engine": r["engine"],
                    "prompt": r["prompt"],
                    "prompt_category": r["prompt_category"],
                    "run_date": run_date,
                })

        if run_entities:
            if apply:
                db.save_ai_response_entities_batch(run_entities)
            total_entities += len(run_entities)
            total_runs_processed += 1
            customer_count = sum(1 for e in run_entities if e["is_customer"])
            competitor_count = len(run_entities) - customer_count
            print(f"  {run_id[:8]}.. {cid} {run_date}: {len(run_entities)} entities ({customer_count} customer, {competitor_count} competitors) from {len(results)} responses")

    print(f"\nSummary:")
    print(f"  Runs processed: {total_runs_processed}")
    print(f"  Runs skipped (already done): {total_runs_skipped}")
    print(f"  Total entities extracted: {total_entities}")
    if not apply:
        print(f"\n  DRY RUN — rerun with --apply to save to database")

    # Auto-discover competitors
    if apply and total_entities > 0:
        print(f"\nAuto-discovering competitors...")
        for cid in set(r["customer_id"] for r in runs):
            added = db.auto_discover_competitors_from_entities(cid, min_mentions=3)
            if added:
                print(f"  {cid}: added {len(added)} competitors: {', '.join(added)}")


def main():
    parser = argparse.ArgumentParser(description="Backfill AI response entities from historical data")
    parser.add_argument("--apply", action="store_true", help="Actually write to database (default: dry run)")
    parser.add_argument("--customer", default=None, help="Process single customer ID")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        backfill(db, customer_id=args.customer, apply=args.apply)
    finally:
        db.close()


if __name__ == "__main__":
    main()
