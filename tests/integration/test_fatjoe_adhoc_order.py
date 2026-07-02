"""The ad-hoc 'Add / upgrade a backlink' route resolves a catalog product and
records both COGS (cost_usd) and retail (sell_usd) on a logged offsite order."""

from __future__ import annotations

import pytest

import dashboard.app as app
from geo_agent.db import CustomerDB


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "t.db")
    db = CustomerDB(db_path=dbp)
    db.add_customer("c1", "Test Co", "testco.example")
    db.close()
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        with c.session_transaction() as s:
            s["logged_in"] = True
        yield c


def test_adhoc_order_records_cogs_and_sell(client):
    resp = client.post(
        "/fatjoe/c1/adhoc-order",
        data={"product_key": "blogger_outreach_dr40", "quantity": "2",
              "target_url": "https://testco.example/page", "anchor_text": "dentist reno",
              "vendor_order_id": "FJ-123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302  # redirects back to the queue

    db = CustomerDB(db_path=app.DB_PATH)
    try:
        orders = db.get_offsite_orders("c1")
        assert len(orders) == 1
        o = orders[0]
        # blogger_outreach → link; DR40 COGS $243 ×2, retail $499 ×2
        assert o["order_type"] == "link"
        assert o["dr_tier"] == 40
        assert o["quantity"] == 2
        assert o["cost_usd"] == 486.0
        assert o["sell_usd"] == 998.0
        assert o["vendor_order_id"] == "FJ-123"
        assert o["target_url"] == "https://testco.example/page"
        # economics helpers agree
        assert db.offsite_spend("c1") == 486.0
        assert db.offsite_revenue("c1") == 998.0
    finally:
        db.close()


def test_adhoc_order_rejects_unknown_product(client):
    resp = client.post("/fatjoe/c1/adhoc-order", data={"product_key": "nope"},
                       follow_redirects=False)
    assert resp.status_code == 302
    db = CustomerDB(db_path=app.DB_PATH)
    try:
        assert db.get_offsite_orders("c1") == []
    finally:
        db.close()


def test_adhoc_citation_maps_to_citation_type(client):
    client.post("/fatjoe/c1/adhoc-order",
                data={"product_key": "citation_100", "quantity": "1"})
    db = CustomerDB(db_path=app.DB_PATH)
    try:
        o = db.get_offsite_orders("c1")[0]
        assert o["order_type"] == "citation"
        assert o["cost_usd"] == 135.0
        assert o["sell_usd"] == 299.0
    finally:
        db.close()
