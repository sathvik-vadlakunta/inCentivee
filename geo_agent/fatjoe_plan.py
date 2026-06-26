"""Per-tier FATJOE order plan — turns a customer's paid tier into the exact
orders Dan must place this period, and compares that to what's already been
ordered so the dashboard can show only what's *outstanding*.

Source of truth for cadence: specs/active/link-building-pricing.html (the
"anti-10/month" table) + the sales-deck tier features. We deliberately start
light and relevant — citation burst at onboarding, a small monthly link drip,
a quarterly brand mention — and scale only on the Dominate tier.

The tier name comes from the Stripe product (subscription.plan_name), normalized
to its first word: "Optimize" / "Grow" / "Dominate".
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone

# Each month's link/citation orders should be placed within the first N days of
# the month. After that the row goes "overdue" (red). Quarterly mentions get the
# whole quarter. Tune here — it's the single knob for the buying SLA.
MONTHLY_ORDER_BY_DAY = 10
DUE_SOON_DAYS = 3  # amber when this many days or fewer remain

# anchor_type / dr_tier guidance lives here so Dan never has to guess.
TIER_PLANS: dict[str, dict] = {
    "optimize": {
        "label": "Optimize",
        "onboarding": [
            {"type": "citation", "qty": 100, "dr_tier": None,
             "note": "Initial NAP citation build — match canonical NAP exactly."},
        ],
        "monthly": [
            {"type": "link", "qty": 1, "dr_tier": 20,
             "note": "1 DR20–30 editorial link to a money/city page (rotate target; vary anchor)."},
        ],
        "quarterly": [],
    },
    "grow": {
        "label": "Grow",
        "onboarding": [
            {"type": "citation", "qty": 100, "dr_tier": None,
             "note": "Initial NAP citation build — match canonical NAP exactly."},
        ],
        "monthly": [
            {"type": "link", "qty": 2, "dr_tier": 30,
             "note": "2 DR20–30 editorial links across different target pages; keep exact-match anchors ≤5%."},
        ],
        "quarterly": [
            {"type": "mention", "qty": 1, "dr_tier": 30,
             "note": "1 brand mention (DR30–60) for AI visibility — listicle/roundup naming the city."},
        ],
    },
    "dominate": {
        "label": "Dominate",
        "onboarding": [
            {"type": "citation", "qty": 100, "dr_tier": None,
             "note": "Initial NAP citation build — match canonical NAP exactly."},
        ],
        "monthly": [
            {"type": "link", "qty": 4, "dr_tier": 40,
             "note": "4 links/mo, mix DR30–40. Include a “best {service} in {area}” comparison/listicle placement."},
        ],
        "quarterly": [
            {"type": "mention", "qty": 1, "dr_tier": 40,
             "note": "1 brand mention (DR40–60) for AI visibility."},
        ],
    },
}

TYPE_LABEL = {"citation": "Local citations", "link": "Editorial link", "mention": "Brand mention"}

# FATJOE wholesale cost (our COGS) per the pricing spec — for Dan's reference.
LINK_COST = {10: 72, 20: 96, 30: 120, 40: 216, 50: 336, 60: 456}
CITATION_COST = {50: 90, 100: 120, 300: 288}
MENTION_COST = 336


def normalize_tier(plan_name: str | None) -> str | None:
    """Map a Stripe product name to a tier key. 'Optimize', 'PracticeRank Grow',
    'Dominate — Founding' all resolve correctly."""
    if not plan_name:
        return None
    # Match a tier keyword anywhere in the product name ("PracticeRank Grow",
    # "Dominate — Founding", "Optimize plan" all resolve).
    words = plan_name.strip().lower().replace("—", " ").split()
    for w in words:
        if w in TIER_PLANS:
            return w
    return None


def resolve_tier(plan_name: str | None, override: str | None = None) -> str | None:
    """Resolve a customer's tier. A per-customer `override` wins — for custom payment
    links / discounted deals whose Stripe product name ("Samuel Doherty") doesn't contain
    a tier keyword. Otherwise fall back to the product-name heuristic."""
    if override:
        ov = override.strip().lower()
        if ov in TIER_PLANS:
            return ov
    return normalize_tier(plan_name)


def _period_starts(now: datetime) -> tuple[str, str]:
    """ISO start-of-month and start-of-quarter for 'ordered this period' checks."""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q_first_month = ((now.month - 1) // 3) * 3 + 1
    quarter_start = now.replace(month=q_first_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start.strftime("%Y-%m-%dT%H:%M:%SZ"), quarter_start.strftime("%Y-%m-%dT%H:%M:%SZ")


def _deadline_for(cadence: str, now: datetime) -> datetime:
    """End-of-day deadline by which an order of this cadence should be placed."""
    if cadence == "monthly":
        d = now.replace(day=1) + timedelta(days=MONTHLY_ORDER_BY_DAY - 1)
    elif cadence == "quarterly":
        q_last_month = ((now.month - 1) // 3) * 3 + 3
        last_day = monthrange(now.year, q_last_month)[1]
        d = now.replace(month=q_last_month, day=last_day)
    else:  # onboarding — due immediately
        d = now
    return d.replace(hour=23, minute=59, second=59, microsecond=0)


def _severity(qty_due: int, days_left: int) -> str:
    if qty_due == 0:
        return "done"
    if days_left < 0:
        return "overdue"
    if days_left <= DUE_SOON_DAYS:
        return "soon"
    return "ok"


def order_cost(spec: dict) -> int:
    if spec["type"] == "link":
        return LINK_COST.get(spec.get("dr_tier") or 20, 96) * spec["qty"]
    if spec["type"] == "citation":
        return CITATION_COST.get(spec["qty"], 120)
    if spec["type"] == "mention":
        return MENTION_COST * spec["qty"]
    return 0


def due_orders(db, customer_id: str, plan_name: str | None, now: datetime | None = None,
               tier_override: str | None = None) -> dict:
    """What Dan still needs to order. Returns:
        {tier, label, items: [{cadence, type, type_label, qty_target, qty_done,
                               qty_due, dr_tier, note, cost_each_period}], total_due}
    qty_done counts matching orders already placed in the relevant period
    (onboarding = ever; monthly = this calendar month; quarterly = this quarter)."""
    now = now or datetime.now(timezone.utc)
    tier = resolve_tier(plan_name, tier_override)
    if not tier:
        return {"tier": None, "label": plan_name or "—", "items": [], "total_due": 0}

    month_start, quarter_start = _period_starts(now)
    plan = TIER_PLANS[tier]
    items: list[dict] = []

    for cadence, since in (("onboarding", None), ("monthly", month_start), ("quarterly", quarter_start)):
        for spec in plan.get(cadence, []):
            done = db.count_offsite_orders_in_period(customer_id, spec["type"], since)
            target = 1 if spec["type"] == "citation" else spec["qty"]  # citations: one pack, not 100 orders
            due = max(0, target - done)
            deadline = _deadline_for(cadence, now)
            days_left = (deadline.date() - now.date()).days
            items.append({
                "cadence": cadence,
                "type": spec["type"],
                "type_label": TYPE_LABEL[spec["type"]],
                "qty_target": spec["qty"],
                "orders_target": target,
                "qty_done": done,
                "qty_due": due,
                "dr_tier": spec.get("dr_tier"),
                "note": spec["note"],
                "cost_each_period": order_cost(spec),
                "deadline": deadline.strftime("%Y-%m-%d"),
                "days_left": days_left,
                "severity": _severity(due, days_left),
            })

    due_items = [i for i in items if i["qty_due"]]
    # Worst severity across outstanding items drives the customer's alarm color.
    rank = {"overdue": 3, "soon": 2, "ok": 1, "done": 0}
    worst = max((i["severity"] for i in due_items), key=lambda s: rank[s], default="done")
    soonest = min((i["days_left"] for i in due_items), default=None)
    return {
        "tier": tier,
        "label": plan["label"],
        "items": items,
        "total_due": sum(i["qty_due"] for i in items),
        "severity": worst,
        "days_left": soonest,
        "deadline": min((i["deadline"] for i in due_items), default=None),
    }
