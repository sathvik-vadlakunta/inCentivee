"""P3 integration test: the customer Overview must render REAL data ON LOAD from the cached
gsc_daily_metrics table even when there is no active GSC integration (the live path is gated
off) — proving the P2 #1 cache-fallback fix. This is the 'accurate on load' guarantee.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import dashboard.app as app
from geo_agent.db import CustomerDB


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "t.db")
    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c1", "Test Co", "testco.example", "Reno", "NV", "active", "practice", "webflow"),
    )
    # Cached GSC daily metrics present; NO gsc integration row → live path is skipped.
    for d, clicks in [("2026-06-01", 10), ("2026-06-02", 10), ("2026-06-03", 10)]:
        db.conn.execute(
            "INSERT INTO gsc_daily_metrics (customer_id,date,clicks,impressions,ctr,position) "
            "VALUES (?,?,?,?,?,?)",
            ("c1", d, clicks, 100, 0.1, 5.0),
        )
    db.conn.commit()
    db.close()
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        with c.session_transaction() as s:
            s["logged_in"] = True
        yield c


def test_overview_renders_cached_gsc_with_no_active_integration(client):
    # Stub the (network) auto-detect so the render is hermetic; the GSC fallback is the SUT.
    with patch.object(app, "_auto_detect_seo_status", return_value={}):
        resp = client.get("/customer/c1")
    assert resp.status_code == 200
    body = resp.data.decode()
    # The cache fallback must have fired: the empty-state must NOT show, and the 30 cached
    # clicks total must be rendered.
    assert "No search data available" not in body
    assert "30" in body  # total clicks from the 3 cached days (10+10+10)
