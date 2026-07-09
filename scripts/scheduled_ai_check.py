#!/usr/bin/env python3
"""Scheduled AI mention check — run via cron 3x/week.

Checks all active customers' AI search visibility across ChatGPT, Claude,
Perplexity, Gemini, and Grok. Stores results for rolling average computation.

Usage:
    python scripts/scheduled_ai_check.py              # all active customers
    python scripts/scheduled_ai_check.py --customer hilltop-family-dental  # single customer
    python scripts/scheduled_ai_check.py --dry-run    # show what would run

Cron (Mon/Wed/Fri 6am ET):
    0 10 * * 1,3,5 cd /app && python scripts/scheduled_ai_check.py >> /app/data/logs/ai-check.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_ai_mentions import (
    build_benchmark_prompts,
    check_mention,
    query_claude,
    query_gemini,
    query_grok,
    query_openai,
    query_perplexity,
    run_engine_samples,
)

# Samples per prompt×engine — averages out LLM non-determinism. Each extra sample
# multiplies grounded API cost, so it's env-tunable; 2 is a solid robustness/cost
# balance on top of the cross-run rolling average.
SAMPLES = max(1, int(os.environ.get("AI_CHECK_SAMPLES", "2")))

from geo_agent.db import CustomerDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ENGINES = [
    ("Claude", query_claude),
    ("ChatGPT", query_openai),
    ("Perplexity", query_perplexity),
    ("Gemini", query_gemini),
    ("Grok", query_grok),
]


def get_active_customers(db: CustomerDB) -> list[dict]:
    """Cut-over customers only — the recurring 3x/week check runs solely for the
    book of customers whose sites are live with our changes. Not-yet-started
    customers get a one-time baseline via `--customer <id>`, not this bulk run.
    See specs/active/paying-only-recurring-work.md."""
    return db.list_recurring_customers()


def run_check_for_customer(db: CustomerDB, customer: dict) -> dict:
    """Run a full AI mention check for one customer. Returns a summary dict."""
    customer_id = customer["id"]
    run_id = f"{customer_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Starting check for {customer['name']} ({customer_id})")

    # Build prompts from customer data
    competitors_list = customer.get("competitors", [])
    if isinstance(competitors_list, str):
        competitors_list = json.loads(competitors_list)
    competitor_names = [c["name"] if isinstance(c, dict) else str(c) for c in competitors_list]

    # Get services from DB
    services_list = db.get_services(customer_id)
    service_names = [s["name"] for s in services_list]

    # Curated buyer/action-intent keywords — used as discovery prompts (esp. for
    # product/B2B, where "how to reduce shot pain" beats "best {product}").
    keyword_list = [k["keyword"] for k in (db.get_tracked_keywords(customer_id) or [])]

    prompt_defs = build_benchmark_prompts(
        customer["name"],
        customer.get("city", ""),
        customer.get("state", ""),
        customer.get("specialties", []),
        business_type=customer.get("business_type", "practice"),
        competitors=competitor_names,
        services=service_names,
        service_areas=customer.get("service_areas", []),
        keywords=keyword_list,
    )

    # Create initial run record (needed for FK constraint on results)
    db.save_ai_mention_run({
        "id": run_id,
        "customer_id": customer_id,
        "run_date": today,
        "total_mentions": 0,
        "total_queries": 0,
        "mention_rate": 0.0,
        "avg_position": None,
        "engines": {},
        "prompt_set": "benchmark",
    })

    results = []
    mention_count = 0
    total_samples = 0
    total_samples_mentioned = 0
    engines_checked = {}

    # Query the 5 engines CONCURRENTLY per prompt (each a different provider, so
    # one concurrent call each — no single-provider rate pressure). HTTP runs in the
    # worker threads; DB writes stay on this main thread via as_completed.
    from scripts.weekly_ai_check import _recompute_and_save_run
    with ThreadPoolExecutor(max_workers=len(ENGINES)) as executor:
        for prompt_idx, pdef in enumerate(prompt_defs):
            prompt = pdef["prompt"]
            category = pdef["category"]
            futures = {
                executor.submit(run_engine_samples, query_fn, prompt, customer["name"], SAMPLES): ai_name
                for ai_name, query_fn in ENGINES
            }
            for fut in as_completed(futures):
                ai_name = futures[fut]
                try:
                    agg = fut.result()
                except Exception as e:
                    engines_checked[ai_name] = "error"
                    logger.warning(f"  {ai_name} thread error: {e}")
                    continue
                if agg is None:
                    engines_checked.setdefault(ai_name, "no_api_key")
                    continue
                if agg.get("error"):
                    engines_checked[ai_name] = "error"
                    logger.warning(f"  {ai_name} error: {agg['error']}")
                    continue

                engines_checked[ai_name] = "active"
                is_mentioned = agg["mentioned"]
                if is_mentioned:
                    mention_count += 1
                total_samples += agg["valid"]
                total_samples_mentioned += agg["samples_mentioned"]

                db.save_ai_mention_result({
                    "run_id": run_id,
                    "customer_id": customer_id,
                    "engine": ai_name,
                    "prompt": prompt,
                    "prompt_category": category,
                    "mentioned": is_mentioned,
                    "position": agg["position"],
                    "quality_score": agg["quality_score"],
                    "context": (agg.get("context") or "")[:500],
                    "full_response": (agg.get("response") or "")[:2000],
                    "is_disclaimer": agg["is_disclaimer"],
                    "model": agg["model"],
                    "citations": agg["citations"],
                    "samples": agg["valid"],
                    "samples_mentioned": agg["samples_mentioned"],
                })

                results.append({
                    "ai": ai_name,
                    "prompt": prompt,
                    "category": category,
                    "mentioned": is_mentioned,
                    "position": agg["position"],
                    "quality_score": agg["quality_score"],
                })

            # Persist incrementally so an interruption (deploy/kill) never leaves
            # the run at 0/0 — it always reflects the results saved so far.
            if (prompt_idx + 1) % 4 == 0:
                _recompute_and_save_run(db, run_id, customer_id, today, "benchmark")

    # Compute final stats. The rate is the AVERAGED fraction across all samples
    # (rock-solid), not a binary per-cell count.
    total_queries = len(results)
    mention_rate = (total_samples_mentioned / total_samples) if total_samples > 0 else 0.0
    positions = [r["position"] for r in results if r["mentioned"] and r["position"]]
    avg_position = sum(positions) / len(positions) if positions else None

    # Engine summary
    engine_summary = {}
    for ai_name, status in engines_checked.items():
        if status in ("no_api_key", "error"):
            engine_summary[ai_name] = {"status": status, "mentions": 0, "total": 0}
        else:
            ai_results = [r for r in results if r["ai"] == ai_name]
            ai_mentions = sum(1 for r in ai_results if r["mentioned"])
            engine_summary[ai_name] = {"status": "active", "mentions": ai_mentions, "total": len(ai_results)}

    # Update run record with final stats
    db.save_ai_mention_run({
        "id": run_id,
        "customer_id": customer_id,
        "run_date": today,
        "total_mentions": mention_count,
        "total_queries": total_queries,
        "mention_rate": mention_rate,
        "avg_position": avg_position,
        "engines": engine_summary,
        "prompt_set": "benchmark",
    })

    # Record KPIs
    db.record_kpi(customer_id, "ai_mentions", mention_count, today)
    if avg_position is not None:
        db.record_kpi(customer_id, "ai_avg_position", avg_position, today)

    # Extract competitor entities from responses
    try:
        from geo_agent.entity_extractor import extract_and_store
        entity_count = extract_and_store(db, run_id, customer_id, customer["name"])
        logger.info(f"  Extracted {entity_count} entities from responses")
        # Auto-discover competitors from frequently-mentioned entities
        added = db.auto_discover_competitors_from_entities(customer_id, min_mentions=3)
        if added:
            logger.info(f"  Auto-discovered {len(added)} new competitors: {', '.join(added)}")
    except Exception as e:
        logger.warning(f"  Entity extraction failed (non-fatal): {e}")

    summary = {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "run_id": run_id,
        "total_mentions": mention_count,
        "total_queries": total_queries,
        "mention_rate": round(mention_rate * 100, 1),
        "avg_position": round(avg_position, 1) if avg_position else None,
        "engines": engine_summary,
    }

    logger.info(
        f"  Done: {mention_count}/{total_queries} mentions "
        f"({summary['mention_rate']}%), "
        f"avg position: {summary['avg_position'] or 'N/A'}"
    )

    return summary


def main():
    parser = argparse.ArgumentParser(description="Scheduled AI mention check for all active customers")
    parser.add_argument("--customer", default=None, help="Run for a single customer ID")
    parser.add_argument("--dry-run", action="store_true", help="Show which customers would be checked")
    parser.add_argument("--delay", type=int, default=300, help="Seconds between customers (default: 300)")
    parser.add_argument("--db", default=None, help="Database file path (auto-detects if omitted)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"AI mention check started at {datetime.now(timezone.utc).isoformat()}")

    # Verify at least one API key is configured
    has_any_key = any(
        os.environ.get(k)
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY")
    )
    if not has_any_key and not args.dry_run:
        logger.error("No AI API keys found in environment. Set at least one of: "
                      "ANTHROPIC_API_KEY, OPENAI_API_KEY, PERPLEXITY_API_KEY, GEMINI_API_KEY, XAI_API_KEY")
        sys.exit(1)

    db = CustomerDB(db_path=args.db)
    try:
        # Determine which customers to check
        if args.customer:
            customer = db.get_customer(args.customer)
            if not customer:
                logger.error(f"Customer not found: {args.customer}")
                sys.exit(1)
            customers = [customer]
        else:
            customers = get_active_customers(db)

        if not customers:
            logger.warning("No active customers found.")
            sys.exit(0)

        logger.info(f"Customers to check: {len(customers)}")
        for c in customers:
            logger.info(f"  - {c['name']} ({c['id']}) [{c.get('status', 'unknown')}]")

        if args.dry_run:
            logger.info("Dry run complete. No checks executed.")
            sys.exit(0)

        # Run checks
        summaries = []
        failures = []

        for i, customer in enumerate(customers):
            try:
                summary = run_check_for_customer(db, customer)
                summaries.append(summary)
            except Exception as e:
                logger.exception(f"Failed to check {customer['name']} ({customer['id']}): {e}")
                failures.append({"customer_id": customer["id"], "customer_name": customer["name"], "error": str(e)})

            # Stagger between customers (skip delay after last one)
            if i < len(customers) - 1 and args.delay > 0:
                logger.info(f"Waiting {args.delay}s before next customer...")
                time.sleep(args.delay)

        # Print summary
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info(f"  Customers checked: {len(summaries)}")
        total_mentions = sum(s["total_mentions"] for s in summaries)
        total_queries = sum(s["total_queries"] for s in summaries)
        logger.info(f"  Total mentions found: {total_mentions}/{total_queries}")
        if failures:
            logger.warning(f"  Failures: {len(failures)}")
            for f in failures:
                logger.warning(f"    - {f['customer_name']}: {f['error']}")

        for s in summaries:
            logger.info(
                f"  {s['customer_name']}: {s['total_mentions']}/{s['total_queries']} "
                f"({s['mention_rate']}%), avg pos: {s['avg_position'] or 'N/A'}"
            )

        logger.info(f"Completed at {datetime.now(timezone.utc).isoformat()}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
