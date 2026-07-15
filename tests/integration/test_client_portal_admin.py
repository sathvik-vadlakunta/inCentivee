"""Ticket 11 — staff-facing 'Client Portal Access' admin panel: create a
username-only client login (no password field anywhere), reset access
(invalidate old signup token, issue a new one), and deactivate (with a
regression check that a deactivated account can no longer authenticate even
with a previously-completed signup + correct password).

Note: `geo_agent.secrets` (a WordPress-integration helper `customer_detail`
imports) is deliberately gitignored (`**/secret*` in .gitignore) and is not
part of this repo checkout — unrelated to this ticket, but it means a full
GET of /customer/<id> 500s in this environment. We stub a minimal fake module
in sys.modules so the page can render for these tests (pre-existing gap,
confirmed via other already-broken tests e.g. test_overview_render.py and
test_config.py that hit the same missing import).
"""

from __future__ import annotations

import sys
import types

import pytest

import dashboard.app as app
from geo_agent.db import CustomerDB


@pytest.fixture(autouse=True)
def _stub_secrets_module(monkeypatch):
    fake_module = types.ModuleType("geo_agent.secrets")

    class _FakeSecretsManager:
        def get_customer_secret(self, customer_id, key):
            return None

    fake_module.get_secrets = lambda: _FakeSecretsManager()
    monkeypatch.setitem(sys.modules, "geo_agent.secrets", fake_module)


@pytest.fixture()
def db_path(tmp_path):
    dbp = str(tmp_path / "t.db")
    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c1", "Test Co", "testco.example", "Reno", "NV", "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.close()
    return dbp


@pytest.fixture()
def client(db_path):
    app.DB_PATH = db_path
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        with c.session_transaction() as s:
            s["logged_in"] = True
            s["username"] = "staff"
            s["display_name"] = "Staff Person"
        yield c


def _db(db_path):
    return CustomerDB(db_path=db_path)


def test_create_client_user_shows_signup_link(client, db_path):
    resp = client.post(
        "/customer/c1/client-users",
        data={"username": "davidg", "display_name": "Dr. David Gallup"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"/portal/signup/" in resp.data

    db = _db(db_path)
    try:
        users = db.list_client_users("c1")
        assert len(users) == 1
        assert users[0]["username"] == "davidg"
        assert users[0]["password_hash"] is None
        token = users[0]["signup_token"]
        assert token
        link = f"/portal/signup/{token}".encode()
        assert link in resp.data
    finally:
        db.close()


def test_duplicate_username_flashes_error_not_500(client, db_path):
    resp1 = client.post(
        "/customer/c1/client-users",
        data={"username": "davidg", "display_name": "Dr. David Gallup"},
        follow_redirects=True,
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/customer/c1/client-users",
        data={"username": "davidg", "display_name": "Someone Else"},
        follow_redirects=True,
    )
    assert resp2.status_code == 200
    assert b"already taken" in resp2.data or b"already exists" in resp2.data

    db = _db(db_path)
    try:
        users = db.list_client_users("c1")
        assert len(users) == 1  # second attempt did not create a duplicate row
    finally:
        db.close()


def test_reset_access_invalidates_old_token_and_issues_new_one(client, db_path):
    db = _db(db_path)
    try:
        result = db.create_client_user("c1", "davidg", "Dr. David Gallup")
        old_token = result["signup_token"]
        user_id = result["id"]
    finally:
        db.close()

    resp = client.post(
        f"/customer/c1/client-users/{user_id}/reset",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"/portal/signup/" in resp.data

    db = _db(db_path)
    try:
        assert db.get_client_user_by_signup_token(old_token) is None
        users = db.list_client_users("c1")
        new_token = users[0]["signup_token"]
        assert new_token != old_token
        assert db.get_client_user_by_signup_token(new_token) is not None
        new_link = f"/portal/signup/{new_token}".encode()
        assert new_link in resp.data
    finally:
        db.close()


def test_deactivate_flips_active_and_blocks_authentication(client, db_path):
    db = _db(db_path)
    try:
        result = db.create_client_user("c1", "davidg", "Dr. David Gallup")
        db.complete_client_signup(result["signup_token"], "correct horse battery staple")
        user_id = result["id"]
        # Sanity: login works before deactivation.
        assert db.authenticate_client_user("davidg", "correct horse battery staple") is not None
    finally:
        db.close()

    resp = client.post(
        f"/customer/c1/client-users/{user_id}/deactivate",
        data={"active": "0"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db = _db(db_path)
    try:
        users = db.list_client_users("c1")
        assert users[0]["active"] == 0
        # Regression check: deactivate button has teeth — correct password no
        # longer authenticates once active=0.
        assert db.authenticate_client_user("davidg", "correct horse battery staple") is None
    finally:
        db.close()


def test_create_client_user_requires_staff_login(db_path):
    app.DB_PATH = db_path
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        resp = c.post(
            "/customer/c1/client-users",
            data={"username": "davidg"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
