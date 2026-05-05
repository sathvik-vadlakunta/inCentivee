#!/usr/bin/env python3
"""Weekly AI mention check for all customers.

Run via cron: 0 9 * * 1  (every Monday at 9am)

Usage:
    python scripts/weekly_ai_check.py
    python scripts/weekly_ai_check.py --customer smileshape
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from geo_agent.db import CustomerDB
from scripts.check_ai_mentions import (
    build_prompts, query_claude, query_openai, query_perplexity,
    query_gemini, query_grok, check_mention,
)

ENGINES = [
    ("Claude", query_claude),
    ("ChatGPT", query_openai),
    ("Perplexity", query_perplexity),
    ("Gemini", query_gemini),
    ("Grok", query_grok),
]


def run_check(db: CustomerDB, customer: dict) -> dict:
    """Run AI mention check for a single customer. Returns summary dict."""
    customer_id = customer["id"]
    prompts = build_prompts(
        customer["name"], customer.get("city", ""), customer.get("state", ""),
        customer.get("specialties", []),
        business_type=customer.get("business_type", "practice"),
    )

    results = []
    mention_count = 0
    engine_stats = {}

    for prompt in prompts:
        for ai_name, query_fn in ENGINES:
            response = query_fn(prompt)
            if response is None:
                engine_stats.setdefault(ai_name, {"status": "no_key", "mentions": 0, "total": 0})
                continue
            engine_stats.setdefault(ai_name, {"status": "active", "mentions": 0, "total": 0})
            engine_stats[ai_name]["total"] += 1

            result = check_mention(response, customer["name"])
            if result["mentioned"]:
                mention_count += 1
                engine_stats[ai_name]["mentions"] += 1

            results.append({
                "prompt": prompt,
                "ai": ai_name,
                "mentioned": result["mentioned"],
                "position": result["position"],
                "context": result["context"][:150] if result["context"] else "",
            })

    # Record KPIs
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.record_kpi(customer_id, "ai_mentions", mention_count, today)

    # Per-engine mention counts
    for ai_name, stats in engine_stats.items():
        if stats["status"] == "active":
            db.record_kpi(customer_id, f"ai_mentions_{ai_name.lower()}", stats["mentions"], today)

    # Average position
    positions = [r["position"] for r in results if r["mentioned"] and r["position"]]
    if positions:
        avg_pos = sum(positions) / len(positions)
        db.record_kpi(customer_id, "ai_avg_position", avg_pos, today)

    # Total queries with active engines
    total_queries = sum(s["total"] for s in engine_stats.values())

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "date": today,
        "mention_count": mention_count,
        "total_queries": total_queries,
        "engines": engine_stats,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Weekly AI mention check")
    parser.add_argument("--customer", default=None, help="Run for specific customer only")
    parser.add_argument("--db", default=None, help="Database path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        if args.customer:
            customers = [db.get_customer(args.customer)]
            if not customers[0]:
                print(f"Customer not found: {args.customer}")
                sys.exit(1)
        else:
            customers = db.get_customers()

        print(f"Running AI mention check for {len(customers)} customer(s)...")
        print(f"Active engines: {', '.join(n for n, fn in ENGINES if fn('_test_') is not None or os.environ.get({'Claude': 'ANTHROPIC_API_KEY', 'ChatGPT': 'OPENAI_API_KEY', 'Perplexity': 'PERPLEXITY_API_KEY', 'Gemini': 'GEMINI_API_KEY', 'Grok': 'XAI_API_KEY'}.get(n, ''), ''))}")
        print()

        all_results = []
        for customer in customers:
            print(f"Checking: {customer['name']}...")
            summary = run_check(db, customer)
            all_results.append(summary)

            active = {k: v for k, v in summary["engines"].items() if v["status"] == "active"}
            print(f"  Mentions: {summary['mention_count']}/{summary['total_queries']}")
            for eng, stats in active.items():
                print(f"    {eng}: {stats['mentions']}/{stats['total']}")
            print()

        # Save weekly report
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        reports_dir = Path(__file__).resolve().parent.parent / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"ai-mentions-{today}.json"
        report_path.write_text(json.dumps(all_results, indent=2))
        print(f"Report saved: {report_path}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
