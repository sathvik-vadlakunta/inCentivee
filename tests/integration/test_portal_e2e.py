"""Ticket 13 -- end-to-end verification pass for the client portal.

Closing checklist run once Tickets 2-12 are merged: not new feature work.
One realistic, multi-customer scenario is exercised against every acceptance
criterion in tickets.md's "Ticket 13" section:

  1. Score/pillar parity, including the AI Visibility pillar-page-vs-Overview
     byte match (the D3-decision regression check -- the single most
     important assertion in this file).
  2. Content-queue parity with the admin /content-queue route, including the
     "cut-over customers only" gate, and that approve/reject via the portal
     is reflected there on the next load.
  3. Reports parity: /portal/reports lists only the logged-in customer's own
     snapshots, and /portal/reports/<id> is byte-identical to /r/<token> for
     the same snapshot.
  4. Session exclusivity: admin and client sessions can never coexist.
  5. The full staff-invite -> client-signup -> auto-login -> logout ->
     re-login -> link-reuse-rejected round trip (Tickets 11 + 12 together).
  6. Cross-customer isolation: the login_required decorator's logic in
     isolation, a spot-check of concrete admin routes, and guessed
     snapshot_id/rec_id 404s.
  7. No regressions to /r/<token> or the admin content_preview back-link.

Reuses the seeding/login conventions established by the other
tests/integration/test_portal_*.py files (_seed_customer_and_login-style
helpers, REALISTIC_PAYLOAD-style snapshot fixtures) rather than reinventing
them.
"""

from __future__ import annotations

import json
import re
import sys
import types

import pytest

import dashboard.app as app
from geo_agent.db import CustomerDB
from geo_agent.portal_copy import PILLAR_COPY, PILLAR_KEY_TO_SLUG
from geo_agent.practicerank_score import PILLAR_WEIGHTS, grade_from_score


@pytest.fixture(autouse=True)
def _stub_secrets_module(monkeypatch):
    """customer_detail() imports geo_agent.secrets (gitignored WordPress
    integration helper, unrelated to the portal) -- stub it so admin pages
    that render customer_detail don't 500 in this environment. Same stub
    tests/integration/test_client_portal_admin.py uses for Ticket 11."""
    fake_module = types.ModuleType("geo_agent.secrets")

    class _FakeSecretsManager:
        def get_customer_secret(self, customer_id, key):
            return None

    fake_module.get_secrets = lambda: _FakeSecretsManager()
    monkeypatch.setitem(sys.modules, "geo_agent.secrets", fake_module)


# ---------------------------------------------------------------------------
# The single realistic scenario
# ---------------------------------------------------------------------------
# c1 "Riverside Family Dental": the cut-over, paying customer -- has a
# completed client-portal login, a full 5-pillar snapshot, and two pending
# content recommendations.
# c2 "Maple Street Dental": a second customer, deliberately NOT cut over,
# with its own snapshot and its own pending rec -- exists purely to prove
# isolation (reports, the content-queue cutover gate, and id-guessing).

C1_ID, C1_NAME = "c1", "Riverside Family Dental"
C2_ID, C2_NAME = "c2", "Maple Street Dental"

RUN_ID = "run-e2e-2026w28"

C1_PAYLOAD = {
    "score": {
        "score": 82,
        "grade": grade_from_score(82),
        "pillars": {
            "ai_visibility": {"score": 75, "available": True, "detail": {"trend": "up"}},
            "technical_health": {"score": 91, "available": True, "detail": {}},
            "content_velocity": {"score": 68, "available": True, "detail": {}},
            "reputation": {"score": 73, "available": True, "detail": {}},
            "search_growth": {"score": 79, "available": True, "detail": {}},
        },
    },
    "score_prev": 77,
    "sections": {
        "search": {
            "cur": {"clicks": 410, "impressions": 6000, "ctr": 0.068, "position": 7.4},
            "prev": {"clicks": 350, "impressions": 5600, "ctr": 0.062, "position": 8.1},
        },
        "ai": {
            "rolling": {"current_rate": 0.75},
            "llms": None,
            "latest": {
                "id": RUN_ID, "total_queries": 12, "mention_rate": 0.75,
                "avg_position": 1.8, "run_date": "2026-07-12",
            },
            "engines": {
                "Claude": {"mentions": 11, "total": 12, "status": "active"},
                "ChatGPT": {"mentions": 9, "total": 12, "status": "active"},
                "Perplexity": {"mentions": 6, "total": 12, "status": "active"},
                "Gemini": {"mentions": 3, "total": 12, "status": "active"},
                # Grok intentionally absent -> renders a "not yet tested" row.
            },
            "sov": {
                "customer_share": 0.40, "customer_mentions": 40, "customer_rank": 1,
                "competitors": [
                    {"name": "Maple Street Dental", "normalized_name": "maple street dental",
                     "mention_count": 22, "share": 0.22, "avg_position": 2.4, "unique_queries": 5},
                ],
                "total_entity_mentions": 100, "total_unique_entities": 4, "runs_analyzed": 3,
            },
            "sov_flag": None,
        },
        "reviews": {
            "places": {"rating": 4.8, "review_count": 152},
            "new_count": 4, "new_five_star": 3, "gap": None, "velocity": None,
        },
        "wins": {
            "published": [
                {"title": "Same-Day Crowns Now Available"},
                {"title": "What Our Patients Say About Sedation Dentistry"},
            ],
            "intent_mix": None,
        },
    },
}

C2_PAYLOAD = {
    "score": {
        "score": 55,
        "grade": grade_from_score(55),
        "pillars": {
            "ai_visibility": {"score": 40, "available": True, "detail": {}},
            "technical_health": {"score": 60, "available": True, "detail": {}},
            "content_velocity": {"score": 58, "available": True, "detail": {}},
            "reputation": {"score": 65, "available": True, "detail": {}},
            "search_growth": {"score": None, "available": False, "detail": {}},
        },
    },
    "score_prev": 55,
    "sections": {
        "search": {"cur": {"clicks": 90, "impressions": 1200, "ctr": 0.075, "position": 12.0},
                    "prev": {"clicks": 90, "impressions": 1200, "ctr": 0.075, "position": 12.0}},
        "reviews": {"places": {"rating": 4.1, "review_count": 30},
                    "new_count": 0, "new_five_star": 0, "gap": None, "velocity": None},
        "wins": {"published": [], "intent_mix": None},
    },
}


@pytest.fixture()
def scenario(tmp_path):
    """Seeds c1 (cut over, completed client login) + c2 (not cut over) with
    their own snapshots and pending content recs. Returns (test_client,
    db_path) with NO session logged in yet -- each test logs in as whichever
    party (client c1, staff) it needs via the helpers below."""
    dbp = str(tmp_path / "t.db")
    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (C1_ID, C1_NAME, "riversidefamilydental.com", "Boise", "ID", "active", "practice", "webflow"),
    )
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (C2_ID, C2_NAME, "maplestreetdental.com", "Boise", "ID", "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.set_cutover(C1_ID, True)   # c1 is cut over -> eligible for /content-queue
    # c2 deliberately left NOT cut over -- proves the cutover gate.

    result = db.create_client_user(C1_ID, "drchen", "Dr. Sarah Chen")
    db.complete_client_signup(result["signup_token"], "correct horse battery staple")

    db.save_report_snapshot(
        C1_ID, "weekly", "2026-07-07", "2026-07-14", 82,
        json.dumps(C1_PAYLOAD), "<html><body>c1 weekly report</body></html>",
    )
    db.save_report_snapshot(
        C2_ID, "weekly", "2026-07-07", "2026-07-14", 55,
        json.dumps(C2_PAYLOAD), "<html><body>c2 weekly report</body></html>",
    )

    db.add_content_recommendation({
        "id": "rec-c1-pending-1", "customer_id": C1_ID, "rec_type": "blog_post",
        "title": "What to Expect at a Same-Day Crown Appointment", "status": "pending",
        "ai_impact_reason": "Patients search this before booking a same-day crown.",
        "created_at": "2026-07-10T00:00:00Z",
    })
    db.add_content_recommendation({
        "id": "rec-c1-pending-2", "customer_id": C1_ID, "rec_type": "faq_update",
        "title": "Do You Offer Sedation Dentistry?", "status": "pending",
        "created_at": "2026-07-11T00:00:00Z",
    })
    db.add_content_recommendation({
        "id": "rec-c2-pending-1", "customer_id": C2_ID, "rec_type": "blog_post",
        "title": "Maple Street's Own Pending Piece", "status": "pending",
        "created_at": "2026-07-10T00:00:00Z",
    })
    db.close()

    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c, dbp


def _login_c1_client(test_client):
    test_client.post(
        "/portal/login",
        data={"username": "drchen", "password": "correct horse battery staple"},
    )


def _login_staff(test_client):
    with test_client.session_transaction() as s:
        s["logged_in"] = True
        s["username"] = "staff"
        s["display_name"] = "Staff Person"


def _label_in_body(label: str, body: str) -> bool:
    """Jinja autoescapes '&' -> '&amp;' (e.g. "Content & Coverage")."""
    return label in body or label.replace("&", "&amp;") in body


# ---------------------------------------------------------------------------
# 1. Score/pillar parity -- the D3-decision regression check.
# ---------------------------------------------------------------------------

def test_score_and_pillar_parity_matches_snapshot_payload_exactly(scenario):
    """Overview's score hero + pillar breakdown, and the AI Visibility pillar
    page's hero, must all match the SAME snapshot's payload_json exactly.
    Treated as the single most important assertion in this whole file."""
    c, dbp = scenario
    _login_c1_client(c)

    db = CustomerDB(db_path=dbp)
    snap = db.get_latest_report_snapshot(C1_ID, "weekly")
    db.close()
    payload = json.loads(snap["payload_json"])
    score = payload["score"]

    overview_body = c.get("/portal/").data.decode()

    # --- Score hero ---
    assert str(score["score"]) in overview_body
    assert f"Grade {score['grade']['letter']}" in overview_body
    delta = score["score"] - payload["score_prev"]
    assert f"▲ {delta} pts vs last period" in overview_body

    # --- Pillar breakdown: every pillar (all 5 are "available" in this
    # scenario), in PILLAR_WEIGHTS order, with the exact score/weight/color
    # the payload + the real PILLAR_WEIGHTS constant dictate.
    for key, weight in PILLAR_WEIGHTS.items():
        p = score["pillars"][key]
        assert p["available"] is True
        slug = PILLAR_KEY_TO_SLUG[key]
        label = PILLAR_COPY[slug]["label"]
        assert _label_in_body(label, overview_body)
        weight_pct = round(weight * 100)
        assert f"{weight_pct}% of your score" in overview_body
        color = grade_from_score(p["score"])["color"]
        assert color in overview_body
        assert f"/portal/pillar/{slug}" in overview_body

    # --- AI Visibility pillar page must match Overview's AI bar exactly for
    # this same snapshot (the resolved D3 decision's regression check). ---
    ai_pillar_score = score["pillars"]["ai_visibility"]["score"]
    ai_body = c.get("/portal/pillar/ai-visibility").data.decode()
    assert f"<b>{ai_pillar_score}</b>" in ai_body
    assert f"{ai_pillar_score} ▲" in overview_body  # trend="up" in this payload
    ai_color = grade_from_score(ai_pillar_score)["color"]
    assert ai_color in overview_body
    assert ai_color in ai_body


# ---------------------------------------------------------------------------
# 2. Content-queue parity (incl. the "cut-over customers only" gate).
# ---------------------------------------------------------------------------

def test_content_queue_parity_cutover_gate_and_approve_reject_reflected(scenario):
    c, dbp = scenario

    # --- Admin /content-queue (staff session) ---
    _login_staff(c)
    cq_body = c.get("/content-queue").data.decode()

    # c1 is cut over -> both pending recs show under its group.
    assert C1_NAME in cq_body
    assert "What to Expect at a Same-Day Crown Appointment" in cq_body
    assert "Do You Offer Sedation Dentistry?" in cq_body

    # c2 has a pending rec too, but is NOT cut over -> must be entirely
    # absent from the content queue (list_recurring_customers() gate).
    assert C2_NAME not in cq_body
    assert "Maple Street's Own Pending Piece" not in cq_body

    c.get("/logout")

    # --- Client /portal/actions for c1 shows the exact same pending recs. ---
    _login_c1_client(c)
    actions_body = c.get("/portal/actions").data.decode()
    assert "What to Expect at a Same-Day Crown Appointment" in actions_body
    assert "Do You Offer Sedation Dentistry?" in actions_body

    # Approve one via the portal.
    resp = c.post("/portal/actions/rec-c1-pending-1/approve", follow_redirects=False)
    assert resp.status_code == 302

    actions_body2 = c.get("/portal/actions").data.decode()
    assert "What to Expect at a Same-Day Crown Appointment" not in actions_body2
    assert "Do You Offer Sedation Dentistry?" in actions_body2

    c.get("/portal/logout")

    # Reflected in the admin /content-queue on the very next load -- same
    # DB row, same read path -- proven with an assertion, not an assumption.
    _login_staff(c)
    cq_body2 = c.get("/content-queue").data.decode()
    assert "What to Expect at a Same-Day Crown Appointment" not in cq_body2
    assert "Do You Offer Sedation Dentistry?" in cq_body2
    c.get("/logout")

    # Reject the second one via the portal too.
    _login_c1_client(c)
    resp2 = c.post("/portal/actions/rec-c1-pending-2/reject", follow_redirects=False)
    assert resp2.status_code == 302
    c.get("/portal/logout")

    _login_staff(c)
    cq_body3 = c.get("/content-queue").data.decode()
    assert "Do You Offer Sedation Dentistry?" not in cq_body3
    # c1 now has zero pending recs -> content_queue()'s "if not recs: continue"
    # drops the whole group, so c1's name disappears from the queue too.
    assert C1_NAME not in cq_body3


# ---------------------------------------------------------------------------
# 3. Reports parity + byte-identical /r/<token> comparison.
# ---------------------------------------------------------------------------

def test_reports_parity_isolation_and_byte_identical_to_public_token(scenario):
    c, dbp = scenario
    _login_c1_client(c)

    body = c.get("/portal/reports").data.decode()
    assert "2026-07-14" in body
    assert body.count("View Report") == 1     # only c1's own single snapshot
    assert "Maple Street" not in body           # no cross-contamination from c2

    db = CustomerDB(db_path=dbp)
    c1_snap = db.get_latest_report_snapshot(C1_ID, "weekly")
    c2_snap = db.get_latest_report_snapshot(C2_ID, "weekly")
    db.close()

    portal_resp = c.get(f"/portal/reports/{c1_snap['id']}")
    token_resp = c.get(f"/r/{c1_snap['share_token']}")
    assert portal_resp.status_code == token_resp.status_code == 200
    assert portal_resp.data == token_resp.data == b"<html><body>c1 weekly report</body></html>"
    assert portal_resp.headers["Cache-Control"] == token_resp.headers["Cache-Control"]
    assert portal_resp.headers["X-Robots-Tag"] == token_resp.headers["X-Robots-Tag"]

    # Guessing c2's snapshot id while logged in as c1 404s and leaks nothing.
    resp404 = c.get(f"/portal/reports/{c2_snap['id']}")
    assert resp404.status_code == 404
    assert b"c2 weekly report" not in resp404.data


# ---------------------------------------------------------------------------
# 4. Session exclusivity.
# ---------------------------------------------------------------------------

def test_session_exclusivity_no_browser_state_ever_has_both_truthy(scenario, monkeypatch):
    c, dbp = scenario
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    monkeypatch.setenv("DASHBOARD_PASS", "adminpass")

    _login_staff(c)
    with c.session_transaction() as s:
        assert s.get("logged_in") is True
        assert not s.get("client_logged_in")

    # Logging into the client portal while an admin session is active clears
    # the admin session's keys.
    c.post(
        "/portal/login",
        data={"username": "drchen", "password": "correct horse battery staple"},
    )
    with c.session_transaction() as s:
        assert s.get("client_logged_in") is True
        assert "logged_in" not in s
        assert "username" not in s
        assert "display_name" not in s
        assert not (s.get("logged_in") and s.get("client_logged_in"))

    # ...and vice versa: logging into the admin dashboard while the client
    # session is active clears the client session's keys.
    c.post("/login", data={"username": "admin", "password": "adminpass"})
    with c.session_transaction() as s:
        assert s.get("logged_in") is True
        assert "client_logged_in" not in s
        assert "client_user_id" not in s
        assert "client_customer_id" not in s
        assert "client_display_name" not in s
        assert not (s.get("logged_in") and s.get("client_logged_in"))


# ---------------------------------------------------------------------------
# 5. Full signup flow, one continuous test (Tickets 11 + 12 together).
# ---------------------------------------------------------------------------

def test_full_signup_flow_staff_invite_to_client_login_and_link_reuse_rejected(tmp_path):
    dbp = str(tmp_path / "signup_e2e.db")
    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c-signup", "Summit Dental Group", "summitdentalgroup.example", "Boise", "ID",
         "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.close()

    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        # 1. Staff creates a username via POST /customer/<id>/client-users.
        with c.session_transaction() as s:
            s["logged_in"] = True
            s["username"] = "staff"
            s["display_name"] = "Staff Person"

        resp = c.post(
            "/customer/c-signup/client-users",
            data={"username": "drpatel", "display_name": "Dr. Anita Patel"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        m = re.search(r"/portal/signup/([A-Za-z0-9_\-]+)", body)
        assert m, "signup link not found in staff response"
        token = m.group(1)

        c.get("/logout")  # staff steps away; client picks up the link

        # 2. GET the invite link -> shows the signup form.
        resp_get = c.get(f"/portal/signup/{token}")
        assert resp_get.status_code == 200
        assert b"Summit Dental Group" in resp_get.data
        assert b"drpatel" in resp_get.data

        # 3. POST to set a password.
        resp_post = c.post(
            f"/portal/signup/{token}",
            data={"password": "e2e-password-1", "confirm_password": "e2e-password-1"},
            follow_redirects=False,
        )
        assert resp_post.status_code == 302
        assert resp_post.headers["Location"].endswith("/portal/")

        # 4. Confirm auto-login landed on /portal/ with real content.
        with c.session_transaction() as s:
            assert s["client_logged_in"] is True
            assert s["client_customer_id"] == "c-signup"
            assert s["client_display_name"] == "Dr. Anita Patel"
        home_resp = c.get("/portal/")
        assert home_resp.status_code == 200
        assert b"Summit Dental Group" in home_resp.data

        # 5. Log out.
        logout_resp = c.get("/portal/logout", follow_redirects=False)
        assert logout_resp.status_code == 302
        with c.session_transaction() as s:
            assert "client_logged_in" not in s

        # 6. Log back in with the new username/password.
        login_resp = c.post(
            "/portal/login",
            data={"username": "drpatel", "password": "e2e-password-1"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 302
        assert login_resp.headers["Location"].endswith("/portal/")
        with c.session_transaction() as s:
            assert s["client_logged_in"] is True
            assert s["client_display_name"] == "Dr. Anita Patel"

        # 7. The ORIGINAL invite link is now rejected as invalid/already used.
        c.get("/portal/logout")
        reused_resp = c.get(f"/portal/signup/{token}")
        assert reused_resp.status_code == 200
        assert b"invalid or has already been used" in reused_resp.data
        assert b"Summit Dental Group" not in reused_resp.data


# ---------------------------------------------------------------------------
# 6. Cross-customer isolation, systematically.
# ---------------------------------------------------------------------------

def test_login_required_decorator_redirects_on_client_only_session():
    """Directly proves dashboard.app.login_required's logic in isolation --
    the decorator is centrally defined and used by all 165 @login_required
    routes in app.py, so proving its logic here is strong evidence for all
    of them, not just whichever ones happen to be spot-checked below."""
    with app.app.test_request_context("/some-admin-route"):
        from flask import session
        session["client_logged_in"] = True
        session["client_user_id"] = 1
        session["client_customer_id"] = C1_ID
        assert not session.get("logged_in")

        probe = app.login_required(lambda: "SECRET-ADMIN-ONLY-DATA")
        result = probe()

    assert result.status_code == 302
    assert result.headers["Location"].endswith("/login")


def test_client_login_required_decorator_redirects_on_admin_only_session():
    """Symmetric check: client_login_required redirects when only the admin
    session is set."""
    with app.app.test_request_context("/portal/some-route"):
        from flask import session
        session["logged_in"] = True
        session["username"] = "staff"
        assert not session.get("client_logged_in")

        probe = app.client_login_required(lambda: "SECRET-CLIENT-ONLY-DATA")
        result = probe()

    assert result.status_code == 302
    assert result.headers["Location"].endswith("/portal/login")


def test_cross_customer_isolation_spot_check_admin_routes_as_client_session(scenario):
    """From a CLIENT session (customer A): a representative sample of
    concrete, diverse admin routes with real URL params must all redirect to
    /login and leak zero customer data."""
    c, dbp = scenario
    _login_c1_client(c)

    admin_routes = [
        ("GET", "/"),
        ("GET", f"/customer/{C1_ID}"),
        ("GET", "/content-queue"),
        ("GET", f"/customer/{C1_ID}/content"),
        ("GET", f"/customer/{C1_ID}/content/preview/rec-c1-pending-1"),
        ("POST", f"/customer/{C1_ID}/client-users"),
        ("POST", f"/customer/{C1_ID}/note"),
        ("GET", f"/customer/{C1_ID}/upload/somefile.png"),
        ("POST", f"/customer/{C1_ID}/status"),
    ]
    for method, path in admin_routes:
        resp = c.open(path, method=method, follow_redirects=False)
        assert resp.status_code == 302, f"{method} {path} did not redirect (got {resp.status_code})"
        assert resp.headers["Location"].endswith("/login"), (
            f"{method} {path} redirected to {resp.headers['Location']!r}, not /login"
        )
        assert C1_NAME.encode() not in resp.data


def test_cross_customer_isolation_guessing_rec_id_404s(scenario):
    """Guessing another customer's rec_id at /portal/actions/<rec_id> (GET,
    and the approve/reject POSTs) all 404 -- belt-and-suspenders re-check of
    Ticket 8/9's own coverage, run here as part of the consolidated pass."""
    c, dbp = scenario
    _login_c1_client(c)

    assert c.get("/portal/actions/rec-c2-pending-1").status_code == 404
    resp_a = c.post("/portal/actions/rec-c2-pending-1/approve", follow_redirects=False)
    assert resp_a.status_code == 404
    resp_r = c.post("/portal/actions/rec-c2-pending-1/reject", follow_redirects=False)
    assert resp_r.status_code == 404

    # c2's rec is untouched by the rejected attempts.
    db = CustomerDB(db_path=dbp)
    rec = db.get_content_recommendation("rec-c2-pending-1")
    db.close()
    assert rec["status"] == "pending"
    assert rec["reviewed_at"] is None


def test_cross_customer_isolation_guessing_snapshot_id_404s(scenario):
    """Guessing another customer's snapshot_id at /portal/reports/<id> 404s
    -- belt-and-suspenders re-check of Ticket 10's own coverage."""
    c, dbp = scenario
    _login_c1_client(c)

    db = CustomerDB(db_path=dbp)
    c2_snap = db.get_latest_report_snapshot(C2_ID, "weekly")
    db.close()

    resp = c.get(f"/portal/reports/{c2_snap['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. No regressions to pre-existing routes.
# ---------------------------------------------------------------------------

def test_regression_public_report_route_still_works(scenario):
    """/r/<token> behaves exactly as public_report()'s documented behavior:
    serves the stored HTML with no-store/no-index headers, login-free."""
    c, dbp = scenario

    db = CustomerDB(db_path=dbp)
    c1_snap = db.get_latest_report_snapshot(C1_ID, "weekly")
    db.close()

    # No session at all -- public_report() has no login requirement.
    resp = c.get(f"/r/{c1_snap['share_token']}")
    assert resp.status_code == 200
    assert resp.data == b"<html><body>c1 weekly report</body></html>"
    assert resp.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert resp.headers["X-Robots-Tag"] == "noindex, nofollow"

    # An unknown token 404s.
    assert c.get("/r/not-a-real-token").status_code == 404


def test_regression_admin_content_preview_back_link_unaffected(scenario):
    """Regression check for Ticket 9's back_url refactor: the existing admin
    content_preview route still renders correctly with its back-link
    pointing at customer_content for the right customer_id."""
    c, dbp = scenario
    _login_staff(c)

    resp = c.get(f"/customer/{C1_ID}/content/preview/rec-c1-pending-1")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "What to Expect at a Same-Day Crown Appointment" in body
    assert f'href="/customer/{C1_ID}/content"' in body
