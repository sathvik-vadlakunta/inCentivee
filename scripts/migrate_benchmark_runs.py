#!/usr/bin/env python3
"""One-time migration: create benchmark shadow runs from historical comprehensive runs.

For each existing comprehensive run, filters results to only prompts that match
the benchmark prompt set, recomputes stats, and creates a new "benchmark" run.
This makes historical data comparable with new benchmark runs for rolling averages.

Usage:
    python scripts/migrate_benchmark_runs.py              # preview changes
    python scripts/migrate_benchmark_runs.py --apply       # apply changes
    python scripts/migrate_benchmark_runs.py --db /path    # custom DB path
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB
from scripts.check_ai_mentions import build_benchmark_prompts


def get_benchmark_prompt_set(db: CustomerDB, customer_id: str) -> set[str]:
    """Build the benchmark prompt set for a customer and return lowercase prompts."""
    customer = db.get_customer(customer_id)
    if not customer:
        return set()

    competitors_list = customer.get("competitors", [])
    if isinstance(competitors_list, str):
        competitors_list = json.loads(competitors_list)
    competitor_names = [c["name"] if isinstance(c, dict) else str(c) for c in competitors_list]

    services_list = db.get_services(customer_id)
    service_names = [s["name"] for s in services_list]

    prompts = build_benchmark_prompts(
        customer["name"],
        customer.get("city", ""),
        customer.get("state", ""),
        customer.get("specialties", []),
        business_type=customer.get("business_type", "practice"),
        competitors=competitor_names,
        services=service_names,
    )
    return {p["prompt"].lower().strip() for p in prompts}


def migrate_run(db: CustomerDB, run: dict, benchmark_prompts: set[str], apply: bool) -> dict | None:
    """Create a benchmark shadow run from a comprehensive run.

    Returns summary dict or None if no matching results found.
    """
    run_id = run["id"]
    customer_id = run["customer_id"]

    # Get all results for this run
    results = db.get_ai_mention_results(run_id)
    if not results:
        return None

    # Filter to benchmark-matching prompts
    matching = [r for r in results if r["prompt"].lower().strip() in benchmark_prompts]
    if not matching:
        return None

    # Recompute stats from matching results only
    mention_count = sum(1 for r in matching if r["mentioned"])
    total_queries = len(matching)
    mention_rate = mention_count / total_queries if total_queries > 0 else 0.0
    positions = [r["position"] for r in matching if r["mentioned"] and r["position"]]
    avg_position = sum(positions) / len(positions) if positions else None

    # Engine breakdown
    engines = {}
    for r in matching:
        eng = r["engine"]
        if eng not in engines:
            engines[eng] = {"status": "active", "mentions": 0, "total": 0}
        engines[eng]["total"] += 1
        if r["mentioned"]:
            engines[eng]["mentions"] += 1

    new_run_id = f"bm-{run_id[:36]}"  # prefix to identify migrated runs

    summary = {
        "original_run_id": run_id,
        "new_run_id": new_run_id,
        "customer_id": customer_id,
        "run_date": run["run_date"],
        "original_queries": len(results),
        "benchmark_queries": total_queries,
        "original_mentions": run["total_mentions"],
        "benchmark_mentions": mention_count,
        "original_rate": run["mention_rate"],
        "benchmark_rate": mention_rate,
    }

    if apply:
        # Create the benchmark shadow run
        db.save_ai_mention_run({
            "id": new_run_id,
            "customer_id": customer_id,
            "run_date": run["run_date"],
            "total_mentions": mention_count,
            "total_queries": total_queries,
            "mention_rate": mention_rate,
            "avg_position": avg_position,
            "engines": engines,
            "prompt_set": "benchmark",
        })

        # Copy matching results to the new run
        for r in matching:
            db.save_ai_mention_result({
                "run_id": new_run_id,
                "customer_id": customer_id,
                "engine": r["engine"],
                "prompt": r["prompt"],
                "prompt_category": r.get("prompt_category", "general"),
                "mentioned": r["mentioned"],
                "position": r.get("position"),
                "quality_score": r.get("quality_score", 0),
                "context": r.get("context", ""),
                "full_response": r.get("full_response", ""),
                "is_disclaimer": r.get("is_disclaimer", False),
            })

    return summary


def main():
    parser = argparse.ArgumentParser(description="Migrate historical runs to benchmark format")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: preview only)")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        # Get all comprehensive runs (those without prompt_set or with 'comprehensive')
        runs = db.conn.execute(
            """SELECT * FROM ai_mention_runs
               WHERE prompt_set = 'comprehensive' OR prompt_set IS NULL
               ORDER BY customer_id, run_date"""
        ).fetchall()
        runs = [dict(r) for r in runs]

        if not runs:
            print("No comprehensive runs to migrate.")
            return

        print(f"Found {len(runs)} comprehensive runs to migrate")
        print(f"Mode: {'APPLY' if args.apply else 'PREVIEW (use --apply to write changes)'}")
        print()

        # Cache benchmark prompts per customer
        prompt_cache: dict[str, set[str]] = {}
        migrated = 0

        for run in runs:
            cid = run["customer_id"]
            if cid not in prompt_cache:
                prompt_cache[cid] = get_benchmark_prompt_set(db, cid)
                print(f"Customer {cid}: {len(prompt_cache[cid])} benchmark prompts")

            if not prompt_cache[cid]:
                print(f"  SKIP {run['id']}: no benchmark prompts (customer not found?)")
                continue

            summary = migrate_run(db, run, prompt_cache[cid], apply=args.apply)
            if summary:
                migrated += 1
                action = "MIGRATED" if args.apply else "WOULD MIGRATE"
                print(
                    f"  {action} {run['run_date']}: "
                    f"{summary['benchmark_queries']}/{summary['original_queries']} queries, "
                    f"{summary['benchmark_mentions']}/{summary['original_mentions']} mentions, "
                    f"rate {summary['original_rate']:.1%} -> {summary['benchmark_rate']:.1%}"
                )
            else:
                print(f"  SKIP {run['id']}: no matching benchmark prompts in results")

        print(f"\n{'Migrated' if args.apply else 'Would migrate'}: {migrated}/{len(runs)} runs")
        if not args.apply and migrated > 0:
            print("Run with --apply to write changes.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
