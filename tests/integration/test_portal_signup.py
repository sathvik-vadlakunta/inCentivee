"""Client-portal signup flow (Ticket 12): GET/POST /portal/signup/<token>.

Covers the happy path (valid token -> form -> password set -> auto-login),
validation failures that must not consume the token, and the critical
double-use edge case -- a second visit/submit of an already-consumed token
must never silently overwrite the first password.
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
        ("c1", "Test Practice Dental", "testco.example", "Reno", "NV", "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.close()
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


def _make_invite(dbp, username="davidg", display_name="Dr. David Gallup"):
    db = CustomerDB(db_path=dbp)
    result = db.create_client_user("c1", username, display_name=display_name)
    db.close()
    return result["signup_token"]


def test_get_valid_token_shows_form_with_practice_and_username(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    resp = client.get(f"/portal/signup/{token}")
    assert resp.status_code == 200
    assert b"Test Practice Dental" in resp.data
    assert b"davidg" in resp.data
    assert b"invalid or has already been used" not in resp.data


def test_get_unknown_token_shows_friendly_message(client):
    resp = client.get("/portal/signup/not-a-real-token")
    assert resp.status_code == 200
    assert b"invalid or has already been used" in resp.data
    # No raw 404/stack trace content
    assert b"Traceback" not in resp.data


def test_post_unknown_token_shows_friendly_message(client):
    resp = client.post(
        "/portal/signup/not-a-real-token",
        data={"password": "correcthorse", "confirm_password": "correcthorse"},
    )
    assert resp.status_code == 200
    assert b"invalid or has already been used" in resp.data


def test_mismatched_passwords_reshow_form_token_still_valid(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    resp = client.post(
        f"/portal/signup/{token}",
        data={"password": "correcthorse", "confirm_password": "differenthorse"},
    )
    assert resp.status_code == 200
    assert b"do not match" in resp.data
    # token was not consumed -- still shows the form, not the dead-end message
    assert b"invalid or has already been used" not in resp.data
    assert b"Test Practice Dental" in resp.data

    # Follow-up request with matching passwords succeeds on the SAME token.
    resp2 = client.post(
        f"/portal/signup/{token}",
        data={"password": "correcthorse", "confirm_password": "correcthorse"},
        follow_redirects=False,
    )
    assert resp2.status_code == 302
    assert resp2.headers["Location"].endswith("/portal/")


def test_password_under_8_chars_rejected(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    resp = client.post(
        f"/portal/signup/{token}",
        data={"password": "short", "confirm_password": "short"},
    )
    assert resp.status_code == 200
    assert b"at least 8 characters" in resp.data
    assert b"invalid or has already been used" not in resp.data

    # Token still valid afterward.
    resp2 = client.get(f"/portal/signup/{token}")
    assert resp2.status_code == 200
    assert b"Test Practice Dental" in resp2.data


def test_successful_signup_auto_logs_in_and_lands_on_portal_home(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    resp = client.post(
        f"/portal/signup/{token}",
        data={"password": "correcthorse", "confirm_password": "correcthorse"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/")

    with client.session_transaction() as s:
        assert s["client_logged_in"] is True
        assert s["client_customer_id"] == "c1"
        assert s["client_display_name"] == "Dr. David Gallup"

    # Subsequent authenticated request succeeds (no redirect to login).
    resp2 = client.get("/portal/")
    assert resp2.status_code == 200
    assert b"Test Practice Dental" in resp2.data


def test_double_use_token_rejected_and_first_password_still_works(client, tmp_path):
    """The critical edge case: complete signup once, then prove the same token
    cannot be used again -- neither via GET nor via a second POST with a
    different password -- and that the FIRST password still logs in
    (i.e. the account was never silently overwritten)."""
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    # First, successful signup.
    resp = client.post(
        f"/portal/signup/{token}",
        data={"password": "firstpassword", "confirm_password": "firstpassword"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Log out so we can independently probe the token/login again.
    client.get("/portal/logout")

    # Re-GET the same token URL -- must show the friendly dead-end message,
    # not the form.
    resp_get = client.get(f"/portal/signup/{token}")
    assert resp_get.status_code == 200
    assert b"invalid or has already been used" in resp_get.data
    assert b"Test Practice Dental" not in resp_get.data

    # A second POST to the same (now-stale) token with a DIFFERENT password
    # must be rejected, not silently overwrite the account.
    resp_post = client.post(
        f"/portal/signup/{token}",
        data={"password": "secondpassword", "confirm_password": "secondpassword"},
        follow_redirects=False,
    )
    assert resp_post.status_code == 200
    assert b"invalid or has already been used" in resp_post.data

    with client.session_transaction() as s:
        assert "client_logged_in" not in s

    # The FIRST password still works for login...
    resp_login_first = client.post(
        "/portal/login",
        data={"username": "davidg", "password": "firstpassword"},
        follow_redirects=False,
    )
    assert resp_login_first.status_code == 302
    assert resp_login_first.headers["Location"].endswith("/portal/")
    client.get("/portal/logout")

    # ...while the SECOND (rejected) password does not.
    resp_login_second = client.post(
        "/portal/login",
        data={"username": "davidg", "password": "secondpassword"},
        follow_redirects=True,
    )
    assert b"Invalid username or password" in resp_login_second.data


def test_full_roundtrip_signup_then_logout_then_login_again(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp, username="drjones", display_name="Dr. Jones")

    client.post(
        f"/portal/signup/{token}",
        data={"password": "roundtrippass", "confirm_password": "roundtrippass"},
    )
    client.get("/portal/logout")

    with client.session_transaction() as s:
        assert "client_logged_in" not in s

    resp = client.post(
        "/portal/login",
        data={"username": "drjones", "password": "roundtrippass"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/")
    with client.session_transaction() as s:
        assert s["client_logged_in"] is True
        assert s["client_display_name"] == "Dr. Jones"


def test_successful_signup_clears_active_admin_session(client, tmp_path):
    dbp = str(tmp_path / "t.db")
    token = _make_invite(dbp)

    with client.session_transaction() as s:
        s["logged_in"] = True
        s["username"] = "staff"
        s["display_name"] = "Staff Person"

    client.post(
        f"/portal/signup/{token}",
        data={"password": "correcthorse", "confirm_password": "correcthorse"},
    )

    with client.session_transaction() as s:
        assert "logged_in" not in s
        assert "username" not in s
        assert "display_name" not in s
        assert s["client_logged_in"] is True
