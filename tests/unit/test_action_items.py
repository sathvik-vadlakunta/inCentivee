"""Tests for the per-customer 'needs attention' alarm aggregator."""

from __future__ import annotations

import os
import tempfile

import pytest

from geo_agent import action_items as ai
from geo_agent.db import CustomerDB


@pytest.fixture()
def db():
    path = tempfile.mktemp(suffix=".db")
    d = CustomerDB(db_path=path)
    yield d
    d.close()
    os.remove(path)


def _add(db, cid, status="active", next_action=""):
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,platform,business_type,status,next_action) "
        "VALUES (?,?,?,?,?,?,?)",
        (cid, cid.title(), f"{cid}.com", "webflow", "service", status, next_action),
    )
    db.conn.commit()


def test_active_customer_without_plan_warns(db):
    _add(db, "c1", status="active")
    items = ai.customer_action_items(db, {"id": "c1", "status": "active"})
    keys = {i["key"] for i in items}
    assert "billing" in keys
    assert ai.worst_severity(items) == "warning"


def test_next_action_surfaces_as_info(db):
    _add(db, "c2", status="active", next_action="Send access email")
    items = ai.customer_action_items(db, {"id": "c2", "status": "active", "next_action": "Send access email"})
    assert any(i["key"] == "next" and i["severity"] == "info" for i in items)


def test_all_clear_when_nothing_outstanding(db):
    # A paused customer with no plan requirement and no pending access -> no items.
    _add(db, "c3", status="paused")
    items = ai.customer_action_items(db, {"id": "c3", "status": "paused", "pending_count": 0})
    assert items == []
    assert ai.worst_severity(items) is None


def test_items_sorted_critical_first(db):
    items = [
        {"key": "a", "severity": "info", "label": "i"},
        {"key": "b", "severity": "critical", "label": "c"},
        {"key": "c", "severity": "warning", "label": "w"},
    ]
    items.sort(key=lambda i: ai._RANK[i["severity"]], reverse=True)
    assert [i["severity"] for i in items] == ["critical", "warning", "info"]
