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


def test_dominate_due_then_satisfied(db):
    due = fp.due_orders(db, "c1", "Dominate", now=NOW)
    assert due["tier"] == "dominate"
    by_type = {i["type"]: i for i in due["items"]}
    assert by_type["link"]["qty_due"] == 4
    assert by_type["citation"]["qty_due"] == 1
    assert by_type["mention"]["qty_due"] == 1
    assert due["total_due"] == 6

    # Place this month's link drip (qty 4) + onboarding citations.
    db.add_offsite_order("c1", "link", quantity=4, dr_tier=40, cost_usd=864)
    db.add_offsite_order("c1", "citation", quantity=100, cost_usd=120)
    due2 = fp.due_orders(db, "c1", "Dominate", now=NOW)
    by_type2 = {i["type"]: i for i in due2["items"]}
    assert by_type2["link"]["qty_due"] == 0
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


def test_buying_window_severity_escalates(db):
    """Monthly orders are 'ok' early in the window, 'soon' near the deadline,
    'overdue' once past it."""
    sev = lambda day: fp.due_orders(
        db, "c1", "Grow", now=datetime(2026, 6, day, tzinfo=timezone.utc)
    )["severity"]
    # MONTHLY_ORDER_BY_DAY=10. But onboarding citations are due immediately, so the
    # plan severity is driven by the soonest item — check the monthly item directly.
    def link_sev(day):
        d = fp.due_orders(db, "c1", "Grow", now=datetime(2026, 6, day, tzinfo=timezone.utc))
        return next(i["severity"] for i in d["items"] if i["cadence"] == "monthly")
    assert link_sev(2) == "ok"
    assert link_sev(9) == "soon"
    assert link_sev(11) == "overdue"


def test_deadline_is_first_n_days_of_month(db):
    d = fp.due_orders(db, "c1", "Optimize", now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    monthly = next(i for i in d["items"] if i["cadence"] == "monthly")
    assert monthly["deadline"] == f"2026-06-{fp.MONTHLY_ORDER_BY_DAY:02d}"


def test_cancelled_orders_dont_count(db):
    oid = db.add_offsite_order("c1", "link", quantity=2, dr_tier=30, cost_usd=240)
    db.update_offsite_order(oid, status="cancelled")
    due = fp.due_orders(db, "c1", "Grow", now=NOW)
    # Grow needs 2 links/mo; the cancelled order must not reduce the due count.
    assert next(i for i in due["items"] if i["type"] == "link")["qty_due"] == 2
