"""Client-portal Full Reports history + snapshot viewer (Ticket 10).

Covers: /portal/reports lists per-cadence history with empty-tab handling,
/portal/reports/<id> serves the stored HTML with the same headers as the
token-based /r/<token> route, and cross-customer snapshot ids 404 rather
than leaking another practice's report.
"""

from __future__ import annotations

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
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c2", "Other Co", "otherco.example", "Reno", "NV", "active", "practice", "webflow"),
    )
    db.conn.commit()

    result = db.create_client_user("c1", "davidg", "Dr. David Gallup")
    db.complete_client_signup(result["signup_token"], "correct horse battery staple")

    # c1: 3 weekly snapshots, one with real HTML; zero monthly/quarterly.
    db.save_report_snapshot(
        "c1", "weekly", "2026-06-09", "2026-06-15", 78,
        "{}", "<html><body>report c1 week3</body></html>",
    )
    db.save_report_snapshot(
        "c1", "weekly", "2026-06-02", "2026-06-08", 74,
        "{}", "<html><body>report c1 week2</body></html>",
    )
    db.save_report_snapshot(
        "c1", "weekly", "2026-05-26", "2026-06-01", 69,
        "{}", "<html><body>report c1 c1</body></html>",
    )

    # c2: its own snapshot, wholly separate customer.
    db.save_report_snapshot(
        "c2", "weekly", "2026-06-09", "2026-06-15", 55,
        "{}", "<html><body>report c2</body></html>",
    )

    db.close()
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


def _login_c1(client):
    client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
    )


def _snapshot_id(dbp: str, customer_id: str, html_substring: str) -> int:
    db = CustomerDB(db_path=dbp)
    try:
        row = db.conn.execute(
            "SELECT id FROM report_snapshots WHERE customer_id = ? AND html LIKE ?",
            (customer_id, f"%{html_substring}%"),
        ).fetchone()
        return row["id"]
    finally:
        db.close()


def test_portal_reports_requires_login(client):
    resp = client.get("/portal/reports", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/login")


def test_portal_reports_lists_weekly_and_shows_empty_other_cadences(client):
    _login_c1(client)
    resp = client.get("/portal/reports")
    assert resp.status_code == 200
    body = resp.data.decode()

    # All 3 weekly snapshots for c1 listed.
    assert "2026-06-15" in body
    assert "2026-06-08" in body
    assert "2026-06-01" in body
    assert body.count("View Report") == 3

    # c2's snapshot must never appear.
    assert "report c2" not in body

    # Monthly/quarterly cadences render as empty tabs, not errors.
    assert "No monthly reports yet" in body
    assert "No quarterly reports yet" in body


def test_portal_report_snapshot_returns_stored_html_with_headers(client):
    _login_c1(client)
    snap_id = _snapshot_id(app.DB_PATH, "c1", "report c1 week3")

    resp = client.get(f"/portal/reports/{snap_id}")
    assert resp.status_code == 200
    assert resp.data == b"<html><body>report c1 week3</body></html>"
    # Note: the route sets "private, no-store", but the app-wide
    # add_no_cache_headers() after_request hook (dashboard/app.py:70-77)
    # overwrites Cache-Control on every text/html response — including
    # /r/<token>'s, identically. See the byte-identical test below for
    # the header-equality assertion that actually matters here.
    assert resp.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert resp.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_portal_report_snapshot_byte_identical_to_public_token_route(client):
    _login_c1(client)
    snap_id = _snapshot_id(app.DB_PATH, "c1", "report c1 week3")

    db = CustomerDB(db_path=app.DB_PATH)
    try:
        share_token = db.conn.execute(
            "SELECT share_token FROM report_snapshots WHERE id = ?", (snap_id,)
        ).fetchone()["share_token"]
    finally:
        db.close()

    portal_resp = client.get(f"/portal/reports/{snap_id}")
    token_resp = client.get(f"/r/{share_token}")

    assert portal_resp.status_code == token_resp.status_code == 200
    assert portal_resp.data == token_resp.data
    assert portal_resp.headers["Cache-Control"] == token_resp.headers["Cache-Control"]
    assert portal_resp.headers["X-Robots-Tag"] == token_resp.headers["X-Robots-Tag"]


def test_portal_report_snapshot_404s_for_other_customers_snapshot(client):
    _login_c1(client)
    c2_snap_id = _snapshot_id(app.DB_PATH, "c2", "report c2")

    resp = client.get(f"/portal/reports/{c2_snap_id}")
    assert resp.status_code == 404


def test_portal_report_snapshot_404s_for_nonexistent_id(client):
    _login_c1(client)
    resp = client.get("/portal/reports/999999")
    assert resp.status_code == 404
