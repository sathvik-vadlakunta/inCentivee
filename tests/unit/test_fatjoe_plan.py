"""Tests for the per-tier FATJOE order plan + due-this-period logic."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from geo_agent import fatjoe_plan as fp
from geo_agent.db import CustomerDB


@pytest.fixture()
def db():
    path = tempfile.mktemp(suffix=".db")
    d = CustomerDB(db_path=path)
    d.conn.execute(
        "INSERT INTO customers (id,name,domain,platform,business_type) "
        "VALUES ('c1','Test','x.com','webflow','service')"
    )
    d.conn.commit()
    yield d
    d.close()
    os.remove(path)


NOW = datetime(2026, 6, 22, tzinfo=timezone.utc)


def test_normalize_tier_matches_anywhere():
    assert fp.normalize_tier("Optimize") == "optimize"
    assert fp.normalize_tier("PracticeRank Grow") == "grow"
    assert fp.normalize_tier("Dominate — Founding") == "dominate"
    assert fp.normalize_tier("Enterprise") is None
    assert fp.normalize_tier(None) is None


def test_resolve_tier_override_wins_for_custom_links():
    # custom payment link / discounted deal — product name has no tier keyword
    assert fp.normalize_tier("Samuel Doherty") is None
    assert fp.resolve_tier("Samuel Doherty", "dominate") == "dominate"
    assert fp.resolve_tier("Samuel Doherty", "DOMINATE") == "dominate"  # case-insensitive
    # empty / invalid override falls back to the product-name heuristic
    assert fp.resolve_tier("Samuel Doherty", "") is None
    assert fp.resolve_tier("Samuel Doherty", "bogus") is None
    assert fp.resolve_tier("PracticeRank Grow", None) == "grow"
    # an explicit override beats the heuristic
    assert fp.resolve_tier("PracticeRank Grow", "dominate") == "dominate"


def test_due_orders_honors_tier_override(db):
    # Paradigm-style: no tier in the plan name, override drives the plan
    due = fp.due_orders(db, "c1", "Samuel Doherty", tier_override="dominate")
    assert due["tier"] == "dominate"
    assert due["total_due"] > 0  # dominate has real monthly + onboarding orders


def test_dominate_due_then_satisfied(db):
    due = fp.due_orders(db, "c1", "Dominate", now=NOW)
    assert due["tier"] == "dominate"
    # Dominate monthly is now 2 link rows: 2×DR40 + 2×DR30 (4 links total).
    links = [i for i in due["items"] if i["type"] == "link"]
    assert sum(l["qty_due"] for l in links) == 4
    by_type = {i["type"]: i for i in due["items"] if i["type"] != "link"}
    assert by_type["citation"]["qty_due"] == 1
    assert by_type["mention"]["qty_due"] == 1
    assert due["total_due"] == 6

    # Place this month's drip — must match each DR band — + onboarding citations.
    db.add_offsite_order("c1", "link", quantity=2, dr_tier=40, cost_usd=486)
    db.add_offsite_order("c1", "link", quantity=2, dr_tier=30, cost_usd=270)
    db.add_offsite_order("c1", "citation", quantity=100, cost_usd=135)
    due2 = fp.due_orders(db, "c1", "Dominate", now=NOW)
    links2 = [i for i in due2["items"] if i["type"] == "link"]
    assert sum(l["qty_due"] for l in links2) == 0
    by_type2 = {i["type"]: i for i in due2["items"] if i["type"] != "link"}
    assert by_type2["citation"]["qty_due"] == 0
    # Quarterly mention still outstanding.
    assert by_type2["mention"]["qty_due"] == 1
    assert due2["total_due"] == 1


def test_optimize_has_no_monthly_mention(db):
    due = fp.due_orders(db, "c1", "Optimize", now=NOW)
    types = {i["type"] for i in due["items"]}
    assert "mention" not in types
    assert next(i for i in due["items"] if i["type"] == "link")["qty_due"] == 1


def test_unknown_plan_returns_empty(db):
    due = fp.due_orders(db, "c1", "Some Custom Plan", now=NOW)
    assert due["tier"] is None
    assert due["items"] == []


def test_rolling_window_severity(db):
    """Monthly links are covered for 30 days from the last order, then re-flag."""
    from datetime import timedelta
    now = datetime(2026, 6, 22, tzinfo=timezone.utc)

    def monthly_item(n=now):
        d = fp.due_orders(db, "c1", "Grow", now=n)
        return next(i for i in d["items"] if i["cadence"] == "monthly")

    def _order_ago(days):
        oid = db.add_offsite_order("c1", "link", quantity=2, dr_tier=30, cost_usd=270)
        db.conn.execute("UPDATE offsite_orders SET ordered_at = ? WHERE id = ?",
                        ((now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"), oid))
        db.conn.commit()
        return oid

    # Never ordered → due now, flagged (soon), not overdue.
    it = monthly_item()
    assert it["qty_due"] == 2 and it["severity"] == "soon"

    # Ordered the 2 links 5 days ago → covered; renews in 25 days.
    oid = _order_ago(5)
    it = monthly_item()
    assert it["qty_due"] == 0 and it["severity"] == "done"
    assert it["days_left"] == 25    # 30-day window − 5 days elapsed

    # Push that order to 35 days ago → coverage lapsed → due again, overdue.
    db.conn.execute("UPDATE offsite_orders SET ordered_at = ? WHERE id = ?",
                    ((now - timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%SZ"), oid))
    db.conn.commit()
    it = monthly_item()
    assert it["qty_due"] == 2 and it["severity"] == "overdue"


def test_deadline_is_last_order_plus_window(db):
    """A covered row's deadline is (last order + 30 days), not the calendar 1st."""
    oid = db.add_offsite_order("c1", "link", quantity=1, dr_tier=20, cost_usd=108)
    db.conn.execute("UPDATE offsite_orders SET ordered_at = ? WHERE id = ?",
                    ("2026-06-10T00:00:00Z", oid))
    db.conn.commit()
    d = fp.due_orders(db, "c1", "Optimize", now=datetime(2026, 6, 22, tzinfo=timezone.utc))
    monthly = next(i for i in d["items"] if i["cadence"] == "monthly")
    assert monthly["qty_due"] == 0            # covered by the June 10 order
    assert monthly["deadline"] == "2026-07-10"  # order date + 30-day window


def test_cancelled_orders_dont_count(db):
    oid = db.add_offsite_order("c1", "link", quantity=2, dr_tier=30, cost_usd=240)
    db.update_offsite_order(oid, status="cancelled")
    due = fp.due_orders(db, "c1", "Grow", now=NOW)
    # Grow needs 2 links/mo; the cancelled order must not reduce the due count.
    assert next(i for i in due["items"] if i["type"] == "link")["qty_due"] == 2
