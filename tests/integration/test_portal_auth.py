"""Client-portal auth: session exclusivity between admin and client logins,
and that client_login_required / login_required actually gate their routes.
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
    db.conn.commit()
    result = db.create_client_user("c1", "davidg", "Dr. David Gallup")
    db.complete_client_signup(result["signup_token"], "correct horse battery staple")
    db.close()
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


def test_portal_login_success(client):
    resp = client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/")
    with client.session_transaction() as s:
        assert s["client_logged_in"] is True
        assert s["client_customer_id"] == "c1"
        assert s["client_display_name"] == "Dr. David Gallup"


def test_portal_login_failure_shows_generic_error(client):
    resp = client.post(
        "/portal/login",
        data={"username": "davidg", "password": "wrong"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_client_login_clears_admin_session(client):
    with client.session_transaction() as s:
        s["logged_in"] = True
        s["username"] = "staff"
        s["display_name"] = "Staff Person"

    client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
    )

    with client.session_transaction() as s:
        assert "logged_in" not in s
        assert "username" not in s
        assert "display_name" not in s
        assert s["client_logged_in"] is True


def test_admin_login_clears_client_session(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    monkeypatch.setenv("DASHBOARD_PASS", "adminpass")

    with client.session_transaction() as s:
        s["client_logged_in"] = True
        s["client_user_id"] = 1
        s["client_customer_id"] = "c1"
        s["client_display_name"] = "Dr. David Gallup"

    client.post("/login", data={"username": "admin", "password": "adminpass"})

    with client.session_transaction() as s:
        assert "client_logged_in" not in s
        assert "client_user_id" not in s
        assert "client_customer_id" not in s
        assert "client_display_name" not in s
        assert s["logged_in"] is True


def test_portal_home_requires_client_login(client):
    resp = client.get("/portal/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/login")


def test_portal_home_rejects_admin_only_session(client):
    with client.session_transaction() as s:
        s["logged_in"] = True
        s["username"] = "staff"

    resp = client.get("/portal/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/login")


def test_admin_route_rejects_client_only_session(client):
    with client.session_transaction() as s:
        s["client_logged_in"] = True
        s["client_user_id"] = 1
        s["client_customer_id"] = "c1"

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_portal_home_renders_when_logged_in(client):
    client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
    )
    resp = client.get("/portal/")
    assert resp.status_code == 200
    assert b"Test Co" in resp.data


def test_portal_logout_clears_only_client_keys(client):
    client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
    )
    resp = client.get("/portal/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/login")
    with client.session_transaction() as s:
        assert "client_logged_in" not in s
