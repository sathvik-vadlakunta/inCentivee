"""Tests for per-customer / per-tier COGS attribution (geo_agent.cost_allocation)."""

from __future__ import annotations

import os
import tempfile

import pytest

from geo_agent import cost_allocation
from geo_agent.db import CustomerDB


@pytest.fixture
def db():
    path = os.path.join(tempfile.mkdtemp(), "cogs.db")
    d = CustomerDB(db_path=path)
    yield d
    d.close()


def _date_order(db, customer_id, cost, ordered_at, status="ordered"):
    oid = db.add_offsite_order(customer_id, "link", cost_usd=cost, status=status)
    db.conn.execute("UPDATE offsite_orders SET ordered_at = ? WHERE id = ?", (ordered_at, oid))
    db.conn.commit()
    return oid


def test_even_split_plus_direct_averaged(db):
    # Two served customers (archived is excluded from the denominator).
    db.add_customer("c1", name="Alpha", domain="a.com")   # default status = onboarding (served)
    db.add_customer("c2", name="Beta", domain="b.com")
    db.add_customer("c3", name="Gone", domain="g.com")
    db.update_customer("c1", status="active", tier_override="grow")
    db.update_customer("c2", tier_override="dominate")     # stays onboarding
    db.update_customer("c3", status="archived", tier_override="optimize")

    # Shared platform costs across two ledger months.
    db.add_expense_entry(month="2026-05", name="Claude", amount_usd=80.0, category="AI / LLM APIs")
    db.add_expense_entry(month="2026-06", name="Claude", amount_usd=100.0, category="AI / LLM APIs")
    db.add_expense_entry(month="2026-06", name="DigitalOcean", amount_usd=20.0, category="Infrastructure")

    # Direct FATJOE — June only; cancelled order must be excluded.
    _date_order(db, "c1", 41.0, "2026-06-10T00:00:00Z")
    _date_order(db, "c2", 135.0, "2026-06-05T00:00:00Z")
    _date_order(db, "c1", 99.0, "2026-06-05T00:00:00Z", status="cancelled")

    out = cost_allocation.compute(db, n_months=3)

    assert out["n_served"] == 2                        # archived excluded
    assert set(out["months"]) == {"2026-05", "2026-06"}
    assert out["n_months"] == 2
    # Shared pool avg = (80 + 120) / 2 = 100 ; even split over 2 customers = 50.
    assert out["shared_pool_avg"] == 100.0
    assert out["shared_per_customer"] == 50.0

    per = {r["id"]: r for r in out["per_customer"]}
    # c1 direct = 41 (June only) averaged over 2 months = 20.5 (cancelled excluded).
    assert per["c1"]["direct_avg"] == 20.5
    assert per["c1"]["total_avg"] == 70.5
    assert per["c1"]["tier"] == "grow"
    # c2 direct = 135 / 2 = 67.5.
    assert per["c2"]["direct_avg"] == 67.5
    assert per["c2"]["total_avg"] == 117.5

    tiers = {t["tier"]: t for t in out["per_tier"]}
    assert tiers["grow"]["count"] == 1
    assert tiers["dominate"]["total_avg"] == 117.5
    assert out["grand_total_month"] == round(70.5 + 117.5, 2)


def test_no_served_customers_is_safe(db):
    db.add_expense_entry(month="2026-06", name="Claude", amount_usd=100.0)
    out = cost_allocation.compute(db)
    assert out["n_served"] == 0
    assert out["shared_per_customer"] == 0.0
    assert out["per_customer"] == []
    assert out["per_tier"] == []


def test_unassigned_tier_bucket(db):
    db.add_customer("c1", name="Solo", domain="s.com")     # onboarding, no tier/override
    db.add_expense_entry(month="2026-06", name="Moz", amount_usd=20.0)
    out = cost_allocation.compute(db)
    assert out["per_customer"][0]["tier"] == "unassigned"
    assert out["per_tier"][0]["tier"] == "unassigned"
    assert out["shared_per_customer"] == 20.0
