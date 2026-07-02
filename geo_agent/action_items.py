"""Per-customer "needs attention" alarms — computed from current state, not
stored. Aggregates the operational gaps that mean *someone has to do something*
for a customer, so the dashboard can show clear, ranked alarms.

Each item: {key, severity (critical|warning|info), label, detail, url}.
Use worst_severity() for a single per-customer status color.
"""
from __future__ import annotations

from geo_agent import fatjoe_plan

_RANK = {"critical": 3, "warning": 2, "info": 1, None: 0}
PAID_STATUSES = frozenset({"active", "trialing"})


def _ai(key, severity, label, detail="", url=None):
    return {"key": key, "severity": severity, "label": label, "detail": detail, "url": url}


def customer_action_items(db, customer: dict) -> list[dict]:
    """Compute the outstanding action items for one customer. `customer` may
    already carry pending_count / is_staged / is_approved (the dashboard sets
    them); we fall back to querying when absent."""
    cid = customer["id"]
    status = customer.get("status")
    items: list[dict] = []

    # --- Billing: is there a paid plan on file? ---
    sub = db.get_subscription_for_customer(cid)
    paid = bool(sub and sub["status"] in PAID_STATUSES)
    if status in ("active", "onboarding"):
        if not sub:
            items.append(_ai("billing", "warning", "No paid plan linked",
                             "No Stripe subscription — link one on Billing.", "/billing"))
        elif not paid:
            items.append(_ai("billing", "critical",
                             f"Payment {sub['status'].replace('_', ' ')}",
                             "Subscription not in good standing.", "/billing"))

    # --- Access: has the client granted everything we asked for? ---
    pending = customer.get("pending_count")
    if pending is None:
        pending = len(db.get_pending_access(cid))
    if pending:
        sev = "critical" if status == "active" else "warning"
        items.append(_ai("access", sev,
                         f"{pending} access item{'s' if pending != 1 else ''} pending",
                         "Client hasn't granted all access yet."))

    # --- Staged content awaiting our approval ---
    if customer.get("is_staged") and not customer.get("is_approved"):
        items.append(_ai("approval", "warning", "Content awaiting approval",
                         "Review & approve the staged changes."))

    # --- Day-1 quick win: onboarding isn't done until a visible result ships ---
    if status == "onboarding" and not customer.get("quick_win_shipped_at"):
        items.append(_ai("quickwin", "warning", "Ship the Day-1 quick win",
                         "New client — ship a visible first result before onboarding completes.",
                         f"/customer/{cid}#quick-win"))

    # --- FATJOE orders due this period (driven by paid tier) ---
    plan_name = sub["plan_name"] if sub else None
    due = fatjoe_plan.due_orders(db, cid, plan_name)
    if due["tier"] and due["total_due"]:
        n = due["total_due"]
        if due["severity"] == "overdue":
            items.append(_ai("fatjoe", "critical",
                             f"FATJOE overdue by {-due['days_left']}d · {n} to order",
                             "Past the monthly buying window.", "/fatjoe"))
        elif due["severity"] == "soon":
            items.append(_ai("fatjoe", "warning",
                             f"FATJOE due in {due['days_left']}d · {n} to order",
                             "Order before the window closes.", "/fatjoe"))
        else:
            items.append(_ai("fatjoe", "info", f"{n} FATJOE order{'s' if n != 1 else ''} to place",
                             "This period's authority orders.", "/fatjoe"))

    # --- Review velocity: stalled reviews are the top local-pack leak ---
    if status == "active" and paid:
        stats = db.get_review_stats(cid)
        if (stats.get("total") or 0) > 0:  # only when we actually track reviews
            vel = db.review_velocity(cid)
            if not vel["on_track"]:
                deficit = vel["target"] - vel["current"]
                items.append(_ai("reviews", "warning",
                                 f"Reviews behind pace · {vel['current']}/mo vs {vel['target']} target",
                                 f"{deficit} short this month — nudge the review campaign.",
                                 f"/customer/{cid}#reviews"))

    # --- Free-form flagged next step (e.g. "Paid — send access email") ---
    na = (customer.get("next_action") or "").strip()
    if na:
        items.append(_ai("next", "info", na, "Flagged next step."))

    items.sort(key=lambda i: _RANK[i["severity"]], reverse=True)
    return items


def worst_severity(items: list[dict]) -> str | None:
    return max((i["severity"] for i in items), key=lambda s: _RANK[s], default=None)
