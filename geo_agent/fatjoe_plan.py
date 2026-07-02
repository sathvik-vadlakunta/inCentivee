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
        "content_quota": 2,  # intent-driven content pieces/mo (good-better-best-pricing.html)
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
        "content_quota": 4,  # intent-driven content pieces/mo
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
        "content_quota": 8,  # 6–8 intent-driven content pieces/mo (generate up to 8; Dan approves)
        "onboarding": [
            {"type": "citation", "qty": 100, "dr_tier": None,
             "note": "Initial NAP citation build — match canonical NAP exactly."},
        ],
        "monthly": [
            {"type": "link", "qty": 2, "dr_tier": 40,
             "note": "2 DR40+ editorial links/mo (incl. a “best {service} in {area}” comparison/listicle)."},
            {"type": "link", "qty": 2, "dr_tier": 30,
             "note": "2 DR30+ editorial links/mo to other money/city pages (vary anchors)."},
        ],
        "quarterly": [
            {"type": "mention", "qty": 1, "dr_tier": 40,
             "note": "1 brand mention (DR40–60) for AI visibility."},
        ],
    },
}

# Monthly content target when a customer has no resolvable tier (custom deal /
# pre-Stripe). Conservative floor so we never over-spend on an unpriced account.
DEFAULT_CONTENT_QUOTA = 2

TYPE_LABEL = {"citation": "Local citations", "link": "Editorial link", "mention": "Brand mention"}

# A tier-plan order "type" maps to a catalog product family. Editorial links in
# the tier plans are fresh Blogger Outreach placements.
TYPE_TO_FAMILY = {"citation": "citation", "link": "blogger_outreach", "mention": "mention"}

# Fallback COGS (used only if the catalog has no matching row) — keep the catalog
# (db.fatjoe_catalog) as the real source of truth; these are last-resort defaults.
# Aligned to FATJOE's real USD prices (DR40 $243, brand mention $378, citations $135
# confirmed from FATJOE screenshots 2026-06-30; other DR bands inferred from the GBP
# ladder × the confirmed DR40 conversion — confirm exact USD with Dan).
FALLBACK_LINK_COST = {20: 108, 30: 135, 40: 243, 50: 378, 60: 513}
FALLBACK_CITATION_COST = {50: 90, 100: 135, 300: 288}
FALLBACK_MENTION_COST = 378


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


def monthly_content_quota(plan_name: str | None, override: str | None = None) -> int:
    """How many intent-driven content pieces to queue per month for this tier.
    Falls back to DEFAULT_CONTENT_QUOTA for custom/unresolved tiers."""
    tier = resolve_tier(plan_name, override)
    if not tier:
        return DEFAULT_CONTENT_QUOTA
    return TIER_PLANS[tier].get("content_quota", DEFAULT_CONTENT_QUOTA)


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


def resolve_product(db, spec: dict) -> dict:
    """Resolve a tier-plan spec to its catalog product → unit price, total
    cost-per-period, and the real FATJOE buy URL. Falls back to FALLBACK_* if the
    catalog (db.fatjoe_catalog) has no matching row, so the queue never blanks."""
    family = TYPE_TO_FAMILY.get(spec["type"], spec["type"])
    dr = spec.get("dr_tier")
    item = db.find_catalog_item(family, dr) if hasattr(db, "find_catalog_item") else None
    qty = spec["qty"]
    if item:
        unit = float(item["price_usd"])
        return {
            "unit_price": unit,
            "cost_each_period": round(unit * qty) if spec["type"] != "citation" else round(unit),
            "buy_url": item.get("buy_url", ""),
            "catalog_key": item["product_key"],
            "price_verified": bool(item.get("verified")),
        }
    # Fallback (no catalog row)
    if spec["type"] == "link":
        unit = FALLBACK_LINK_COST.get(dr or 20, 145)
        cost = unit * qty
    elif spec["type"] == "citation":
        unit = FALLBACK_CITATION_COST.get(qty, 120)
        cost = unit
    elif spec["type"] == "mention":
        unit = FALLBACK_MENTION_COST
        cost = unit * qty
    else:
        unit, cost = 0, 0
    return {"unit_price": unit, "cost_each_period": round(cost), "buy_url": "",
            "catalog_key": "", "price_verified": False}


def order_cost(db, spec: dict) -> int:
    """Back-compat: just the cost-per-period for a spec (catalog-resolved)."""
    return resolve_product(db, spec)["cost_each_period"]


def _allocate_link_done(pool_drs: list[int], link_specs: list[dict]) -> dict:
    """Allocate this period's ordered links to the tier's link requirements, where
    a HIGHER-DR order can satisfy a LOWER-DR requirement (but not vice-versa).
    Process the highest-DR requirement first, filling each slot with the smallest
    qualifying order so bigger orders stay available for bigger requirements.
    Returns {id(spec): qty_done}. Example: a tier wants 2×DR40 + 2×DR30 and Dan
    orders 4×DR40 → both rows auto-complete (DR40 ≥ DR30)."""
    pool = sorted(pool_drs)  # ascending → first match is the smallest qualifying
    done: dict = {}
    for spec in sorted(link_specs, key=lambda s: -(s.get("dr_tier") or 0)):
        req = spec.get("dr_tier") or 0
        d = 0
        for _ in range(spec["qty"]):
            idx = next((i for i, v in enumerate(pool) if v >= req), None)
            if idx is None:
                break
            pool.pop(idx)
            d += 1
        done[id(spec)] = d
    return done


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

    # Pre-allocate this month's ordered links across the tier's link rows so a
    # higher-DR order auto-satisfies a lower-DR row (Dan's "order higher DA →
    # mark lower complete"). Links live in the monthly cadence.
    month_link_specs = [s for s in plan.get("monthly", []) if s["type"] == "link"]
    link_done: dict = {}
    if month_link_specs:
        pool: list[int] = []
        for dr, qty in db.link_dr_quantities_in_period(customer_id, month_start).items():
            pool.extend([dr] * qty)
        link_done = _allocate_link_done(pool, month_link_specs)

    for cadence, since in (("onboarding", None), ("monthly", month_start), ("quarterly", quarter_start)):
        for spec in plan.get(cadence, []):
            if spec["type"] == "link" and id(spec) in link_done:
                done = link_done[id(spec)]
            else:
                done = db.count_offsite_orders_in_period(customer_id, spec["type"], since)
            target = 1 if spec["type"] == "citation" else spec["qty"]  # citations: one pack, not 100 orders
            due = max(0, target - done)
            deadline = _deadline_for(cadence, now)
            days_left = (deadline.date() - now.date()).days
            prod = resolve_product(db, spec)
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
                "unit_price": prod["unit_price"],
                "cost_each_period": prod["cost_each_period"],
                "buy_url": prod["buy_url"],
                "catalog_key": prod["catalog_key"],
                "price_verified": prod["price_verified"],
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
