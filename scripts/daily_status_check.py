#!/usr/bin/env python3
"""Daily status reconciliation for all active customers.

Re-checks each customer's live site, resolves fixed audit issues, marks live
content published, ticks satisfied todos, and auto-advances status
(→ active/monitoring) when fully live. See:
  specs/active/daily-status-reconciliation.md
  geo_agent/status_checker.py

Run via cron (after the 06:00 GSC pull):
    30 6 * * * docker exec practicerank-dashboard python3 /app/scripts/daily_status_check.py

Flags:
    --dry-run            show what WOULD change; write nothing
    --customer <id>      run a single customer (great with --dry-run)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime  # noqa: E402

from geo_agent import status_checker as sc  # noqa: E402
from geo_agent.db import CustomerDB  # noqa: E402

DB_PATH = os.environ.get("DB_PATH", "/app/data/practicerank.db")


def _print(r: dict):
    tag = "[dry-run] " if r["dry_run"] else ""
    print(f"  {tag}{r['customer_id']} ({r['domain']})")
    if r.get("audit_scores"):
        s = r["audit_scores"]
        print(f"    audit scores: perf={s.get('performance')} seo={s.get('seo')} "
              f"a11y={s.get('accessibility')} bp={s.get('best_practices')}")
    if r["issues_fixed"]:
        print(f"    issues resolved: {len(r['issues_fixed'])} -> " +
              ", ".join(i["title"] or str(i["id"]) for i in r["issues_fixed"][:5]))
    if r["content_published"]:
        print(f"    content marked published: {len(r['content_published'])}")
    if r["todos_ticked"]:
        print(f"    todos ticked: {', '.join(r['todos_ticked'])}")
    if r["transition"]:
        print(f"    STATUS: {r['transition']['from']} -> {r['transition']['to']}")
    elif r.get("advance_blockers"):
        print(f"    not advanced — blockers: {', '.join(r['advance_blockers'])}")
    for a in r["alerts"]:
        print(f"    alert: {a}")
    if not any([r["issues_fixed"], r["content_published"], r["todos_ticked"], r["transition"]]):
        print("    (no changes)")


def main():
    dry_run = "--dry-run" in sys.argv
    customer_id = None
    if "--customer" in sys.argv:
        customer_id = sys.argv[sys.argv.index("--customer") + 1]

    db = CustomerDB(DB_PATH)
    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"[{datetime.now().isoformat()}] Daily status check ({mode})")
    try:
        if customer_id:
            _print(sc.reconcile_customer(db, customer_id, dry_run=dry_run))
        else:
            results = sc.reconcile_all(db, dry_run=dry_run)
            for r in results:
                _print(r)
            advanced = sum(1 for r in results if r["transition"])
            print(f"[{datetime.now().isoformat()}] Done — {len(results)} customers, "
                  f"{advanced} status change(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
