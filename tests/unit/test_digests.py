"""Tests for the operational digest builders (no network — build only)."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from geo_agent import digests
from geo_agent.db import CustomerDB

NOW = datetime(2026, 6, 18, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    path = tempfile.mktemp(suffix=".db")
    d = CustomerDB(db_path=path)
    yield d
    d.close()
    os.remove(path)


def _add_paid(db, cid, name, domain, plan):
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,platform,business_type,status,email) "
        "VALUES (?,?,?,?,?,?,?)",
        (cid, name, domain, "webflow", "service", "active", f"office@{domain}"),
    )
    db.conn.commit()
    db.upsert_subscription({
        "stripe_subscription_id": f"sub_{cid}", "stripe_customer_id": "cus",
        "stripe_customer_email": f"office@{domain}", "plan_name": plan, "price_id": "p",
        "amount_cents": 250000, "currency": "usd", "billing_interval": "month",
        "status": "active", "latest_invoice_status": "paid",
        "last_payment_at": "2026-06-01T00:00:00Z", "current_period_end": None,
        "cancel_at_period_end": False, "raw": {},
    })


def test_monthly_fatjoe_lists_due_orders(db):
    _add_paid(db, "c1", "Paradigm", "paradigm.com", "Dominate")
    subject, html, count = digests.build_monthly_fatjoe(db, NOW)
    assert count == 6  # Dominate: 100 citations + 4 links + 1 mention
    assert "Paradigm" in html and "to place" in subject


def test_monthly_fatjoe_all_clear_when_logged(db):
    _add_paid(db, "c1", "Paradigm", "paradigm.com", "Dominate")
    db.add_offsite_order("c1", "citation", quantity=100)
    db.add_offsite_order("c1", "link", quantity=2, dr_tier=40)
    db.add_offsite_order("c1", "link", quantity=2, dr_tier=30)
    db.add_offsite_order("c1", "mention", quantity=1, dr_tier=40)
    subject, html, count = digests.build_monthly_fatjoe(db, NOW)
    assert count == 0
    assert "all clear" in subject


def test_daily_attention_flags_unmatched_paid_sub(db):
    # A paid sub whose email matches nothing -> unmatched, should be flagged.
    db.upsert_subscription({
        "stripe_subscription_id": "sub_x", "stripe_customer_id": "cus",
        "stripe_customer_email": "nobody@unknown-co.com", "plan_name": "Grow", "price_id": "p",
        "amount_cents": 250000, "currency": "usd", "billing_interval": "month",
        "status": "active", "latest_invoice_status": "paid", "last_payment_at": "2026-06-01T00:00:00Z",
        "current_period_end": None, "cancel_at_period_end": False, "raw": {},
    })
    subject, html, urgent = digests.build_daily_attention(db, NOW)
    assert urgent >= 1
    assert "not linked to a client" in html


def test_daily_attention_empty_when_clean(db):
    subject, html, urgent = digests.build_daily_attention(db, NOW)
    assert urgent == 0 and subject == ""
