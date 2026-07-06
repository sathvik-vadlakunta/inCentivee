"""Per-customer / per-tier COGS attribution from the expense ledger.

Model (as directed by ops — "average out all the expenses spread over each customer,
then the ones that are customer-specific"):

  * SHARED expenses — every ``expense_entries`` row (platform subscriptions, AI/LLM
    APIs, infra, SEO, Google) serves the whole book, so the monthly pool is spread
    EVENLY across the customers we're actively serving.
  * CUSTOMER-SPECIFIC expenses — FATJOE off-site orders carry a ``customer_id``, so
    they're attributed DIRECTLY to that customer (and roll up by that customer's tier).

Both are averaged over the most recent N months that have ledger data, so a one-off
(e.g. an onboarding citation burst) doesn't distort the run-rate cost-to-serve.
"""

from __future__ import annotations

import datetime as _dt

from geo_agent import fatjoe_plan

SERVED_STATUSES = ("active", "onboarding")
_TIER_ORDER = {"optimize": 0, "grow": 1, "dominate": 2, "unassigned": 9}


def _served_customers(db) -> list[dict]:
    return [c for c in db.list_customers() if c.get("status") in SERVED_STATUSES]


def _tier_for(db, cust: dict) -> str:
    sub = db.get_subscription_for_customer(cust["id"])
    plan_name = sub["plan_name"] if sub else None
    return fatjoe_plan.resolve_tier(plan_name, cust.get("tier_override") or "") or "unassigned"


def compute(db, n_months: int = 3, today: str | None = None) -> dict:
    """Return per-customer and per-tier average monthly COGS.

    Shared platform costs are split evenly across served customers; FATJOE spend is
    direct. Everything is the mean over the most recent ``n_months`` of *complete*
    ledger data — the in-progress current month is excluded so a partial month doesn't
    drag the run-rate down (unless it's the only data we have).
    """
    cur = today or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")
    all_months = sorted(db.expense_months() or [], reverse=True)
    past = [m for m in all_months if m < cur]
    months = (past or all_months)[:n_months]
    served = _served_customers(db)
    n_served = len(served)
    n_m = len(months)

    # Shared pool per month = sum of ALL expense_entries (FATJOE is NOT in here — it's
    # derived from offsite_orders — so there's no double-count).
    shared_by_month = {
        m: round(sum(e["amount_usd"] for e in db.list_expense_entries(m)), 2) for m in months
    }
    shared_pool_avg = round(sum(shared_by_month.values()) / n_m, 2) if n_m else 0.0
    shared_per_customer = round(shared_pool_avg / n_served, 2) if n_served else 0.0

    # Direct FATJOE per customer, averaged over the same months.
    direct_by_month = {m: db.offsite_spend_by_customer(m) for m in months}
    per_customer: list[dict] = []
    for c in served:
        cid = c["id"]
        direct_vals = [direct_by_month[m].get(cid, (0.0, 0))[0] for m in months]
        direct_avg = round(sum(direct_vals) / n_m, 2) if n_m else 0.0
        per_customer.append({
            "id": cid,
            "name": c.get("name") or cid,
            "tier": _tier_for(db, c),
            "shared_avg": shared_per_customer,
            "direct_avg": direct_avg,
            "total_avg": round(shared_per_customer + direct_avg, 2),
        })
    per_customer.sort(key=lambda r: r["total_avg"], reverse=True)

    # Per-tier rollup: avg cost-to-serve per customer + the tier's total monthly COGS.
    buckets: dict[str, dict] = {}
    for r in per_customer:
        b = buckets.setdefault(r["tier"], {"tier": r["tier"], "count": 0,
                                           "direct_sum": 0.0, "total_sum": 0.0})
        b["count"] += 1
        b["direct_sum"] += r["direct_avg"]
        b["total_sum"] += r["total_avg"]
    per_tier: list[dict] = []
    for b in buckets.values():
        cnt = b["count"] or 1
        per_tier.append({
            "tier": b["tier"],
            "count": b["count"],
            "shared_avg": shared_per_customer,
            "direct_avg": round(b["direct_sum"] / cnt, 2),
            "total_avg": round(b["total_sum"] / cnt, 2),   # per customer in this tier
            "total_month": round(b["total_sum"], 2),        # whole tier's monthly COGS
        })
    per_tier.sort(key=lambda r: _TIER_ORDER.get(r["tier"], 5))

    return {
        "months": months,
        "n_months": n_m,
        "n_served": n_served,
        "shared_pool_avg": shared_pool_avg,
        "shared_per_customer": shared_per_customer,
        "per_customer": per_customer,
        "per_tier": per_tier,
        "grand_total_month": round(sum(r["total_avg"] for r in per_customer), 2),
    }
