"""Client-portal Action Items page (Ticket 7): pending content recs needing
approval, a short "recently added" log, and secondary needs-from-you items.
"""

from __future__ import annotations

import pytest

import dashboard.app as app
from geo_agent.db import CustomerDB


def _seed_customer_and_login(db_path: str, test_client):
    db = CustomerDB(db_path=db_path)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c1", "Hilltop Family Dental", "hilltopfamilydental.com", "Casper", "WY",
         "active", "practice", "webflow"),
    )
    db.conn.commit()
    result = db.create_client_user("c1", "davidg", "Dr. David Gallup")
    db.complete_client_signup(result["signup_token"], "correct horse battery staple")
    db.close()

    test_client.post(
        "/portal/login",
        data={"username": "davidg", "password": "correct horse battery staple"},
    )


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "t.db")
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c, dbp


def test_actions_page_groups_pending_published_and_needs(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    # Mark the two default checklist needs-items complete so they don't
    # clutter this assertion -- we want exactly one controlled needs item.
    db.set_checklist_item("c1", "seo_gbp_photos", True)
    db.set_checklist_item("c1", "seo_gbp_qa", True)

    # One pending rec -> shows in "Needs your approval" AND (via
    # build_report_data's needs section) would normally also produce an
    # "Approve 1 piece(s) of content..." needs item -- that's the one the
    # route is supposed to filter out of "Other things we need from you".
    db.add_content_recommendation({
        "id": "rec-pending-1", "customer_id": "c1", "rec_type": "blog_post",
        "title": "What to Do If You Chip a Tooth", "status": "pending",
        "ai_impact_reason": "Patients search this exact question after a dental injury.",
        "created_at": "2026-07-01T00:00:00Z",
    })

    # Two published recs, seeded so that a priority-first sort would put the
    # OLD one first -- proves the route re-sorts published items by recency.
    db.add_content_recommendation({
        "id": "rec-pub-old", "customer_id": "c1", "rec_type": "new_page",
        "title": "Old Published Page", "status": "published", "priority": 1,
        "created_at": "2026-01-01T00:00:00Z",
    })
    db.add_content_recommendation({
        "id": "rec-pub-new", "customer_id": "c1", "rec_type": "faq_update",
        "title": "New Published FAQ", "status": "published", "priority": 5,
        "created_at": "2026-07-05T00:00:00Z",
    })

    # A distinct, controlled needs item via platform_access.
    db.add_platform_access("c1", "Webflow API token", status="pending")
    db.close()

    resp = c.get("/portal/actions")
    assert resp.status_code == 200
    body = resp.data.decode()

    # --- Needs your approval ---
    assert "Needs your approval" in body
    assert "1" in body.split("Needs your approval")[1].split("\n")[0]
    assert "What to Do If You Chip a Tooth" in body
    assert "Blog posts" in body  # _REC_TYPE_LABELS["blog_post"]
    assert "Patients search this exact question after a dental injury." in body
    assert '/portal/actions/rec-pending-1/approve' in body
    assert '/portal/actions/rec-pending-1/reject' in body
    assert '/portal/actions/rec-pending-1"' in body  # preview link

    # --- Recently added to your site (recency order, not priority order) ---
    assert "Recently added to your site" in body
    assert "Old Published Page" in body
    assert "New Published FAQ" in body
    assert body.index("New Published FAQ") < body.index("Old Published Page")

    # --- Other things we need from you ---
    assert "Other things we need from you" in body
    assert "Webflow API token" in body
    # The redundant "approve pending content" needs item must be filtered out
    # of this section (it's already covered by "Needs your approval" above).
    # (Note: the page's own lead copy legitimately contains "prepared for
    # your practice", so match on the needs-item's distinctive phrasing.)
    assert "piece(s) of content" not in body

    # Default checklist needs-items were marked complete, so they must not
    # leak in either.
    assert "Send us 10+ photos" not in body
    assert "Google Business Q&A" not in body


def test_actions_page_empty_state_when_all_caught_up(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.set_checklist_item("c1", "seo_gbp_photos", True)
    db.set_checklist_item("c1", "seo_gbp_qa", True)
    db.close()

    resp = c.get("/portal/actions")
    assert resp.status_code == 200
    body = resp.data.decode()

    assert "You&#39;re all caught up" in body or "You're all caught up" in body
    assert "Needs your approval" not in body
    assert "Recently added to your site" not in body
    assert "Other things we need from you" not in body


def test_approve_removes_from_pending_and_not_into_recently_added(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.add_content_recommendation({
        "id": "rec-approve-me", "customer_id": "c1", "rec_type": "blog_post",
        "title": "Approve Me Please", "status": "pending",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.post("/portal/actions/rec-approve-me/approve", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/actions")

    db = CustomerDB(db_path=dbp)
    rec = db.get_content_recommendation("rec-approve-me")
    db.close()
    assert rec["status"] == "approved"
    assert rec["reviewed_at"]

    body = c.get("/portal/actions").data.decode()
    assert "Approve Me Please" not in body  # removed from "Needs your approval"
    # approved != published, so it must not show up in "Recently added"
    assert "Recently added to your site" not in body


def test_reject_removes_from_pending(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.add_content_recommendation({
        "id": "rec-reject-me", "customer_id": "c1", "rec_type": "blog_post",
        "title": "Reject Me Please", "status": "pending",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.post("/portal/actions/rec-reject-me/reject", follow_redirects=False)
    assert resp.status_code == 302

    db = CustomerDB(db_path=dbp)
    rec = db.get_content_recommendation("rec-reject-me")
    db.close()
    assert rec["status"] == "rejected"
    assert rec["reviewed_at"]

    body = c.get("/portal/actions").data.decode()
    assert "Reject Me Please" not in body


def test_approve_reject_404_for_other_customers_rec_and_leaves_it_unchanged(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c2", "Other Practice", "otherpractice.com", "Denver", "CO",
         "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.add_content_recommendation({
        "id": "rec-other-cust", "customer_id": "c2", "rec_type": "blog_post",
        "title": "Belongs To Someone Else", "status": "pending",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.post("/portal/actions/rec-other-cust/approve", follow_redirects=False)
    assert resp.status_code == 404

    resp = c.post("/portal/actions/rec-other-cust/reject", follow_redirects=False)
    assert resp.status_code == 404

    db = CustomerDB(db_path=dbp)
    rec = db.get_content_recommendation("rec-other-cust")
    db.close()
    assert rec["status"] == "pending"
    assert rec["reviewed_at"] is None


def test_approve_reject_404_for_nonexistent_rec_id(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    assert c.post("/portal/actions/does-not-exist/approve").status_code == 404
    assert c.post("/portal/actions/does-not-exist/reject").status_code == 404


def test_approve_via_portal_is_reflected_in_admin_content_queue_read_path(client):
    """Cross-check (ticket acceptance criterion): portal approve and the admin
    content-queue view read the exact same DB row via the exact same method
    (db.get_content_recommendation / get_content_recommendations), so an
    approval made through the portal route must be visible there too."""
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.add_content_recommendation({
        "id": "rec-cross-check", "customer_id": "c1", "rec_type": "blog_post",
        "title": "Cross Check Me", "status": "pending",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.post("/portal/actions/rec-cross-check/approve", follow_redirects=False)
    assert resp.status_code == 302

    # Same read path the admin /content-queue and /customer/<id>/content views
    # use under the hood.
    db = CustomerDB(db_path=dbp)
    rec = db.get_content_recommendation("rec-cross-check")
    all_recs = db.get_content_recommendations("c1", limit=100)
    db.close()

    assert rec["status"] == "approved"
    matching = [r for r in all_recs if r["id"] == "rec-cross-check"]
    assert len(matching) == 1
    assert matching[0]["status"] == "approved"


# --- Ticket 9: recommendation preview route ---

def test_portal_action_preview_renders_title_and_body_with_back_link_to_actions(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.add_content_recommendation({
        "id": "rec-preview-me", "customer_id": "c1", "rec_type": "blog_post",
        "title": "Preview This Piece", "status": "pending",
        "html_snippet": "<p>Some body copy about chipped teeth.</p>",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.get("/portal/actions/rec-preview-me")
    assert resp.status_code == 200
    body = resp.data.decode()

    assert "Preview This Piece" in body
    assert "Some body copy about chipped teeth." in body
    assert 'href="/portal/actions"' in body  # back-link -> Action Items list
    # Confirm no admin-only fields leak (webflow ids, publish errors).
    assert "webflow_item_id" not in body
    assert "publish_error" not in body


def test_portal_action_preview_404_for_other_customers_rec(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,city,state,status,business_type,platform) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("c2", "Other Practice", "otherpractice.com", "Denver", "CO",
         "active", "practice", "webflow"),
    )
    db.conn.commit()
    db.add_content_recommendation({
        "id": "rec-preview-other-cust", "customer_id": "c2", "rec_type": "blog_post",
        "title": "Not Yours To Preview", "status": "pending",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    resp = c.get("/portal/actions/rec-preview-other-cust")
    assert resp.status_code == 404


def test_portal_action_preview_404_for_nonexistent_rec_id(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    assert c.get("/portal/actions/does-not-exist").status_code == 404


def test_admin_content_preview_route_unaffected_by_back_url_refactor(client):
    """Regression check for Ticket 9's template refactor: the existing admin
    content_preview route (app.py) must still render identically, with its
    back-link still pointing at customer_content for the same customer_id."""
    c, dbp = client
    _seed_customer_and_login(dbp, c)  # creates customer "c1", but logs in as a client

    db = CustomerDB(db_path=dbp)
    db.add_content_recommendation({
        "id": "rec-admin-preview", "customer_id": "c1", "rec_type": "blog_post",
        "title": "Admin Preview Piece", "status": "pending",
        "html_snippet": "<p>Admin-visible body copy.</p>",
        "created_at": "2026-07-01T00:00:00Z",
    })
    db.close()

    # Admin route requires admin ("logged_in") session, not client session.
    with c.session_transaction() as s:
        s["logged_in"] = True
        s["username"] = "staff"
        s["display_name"] = "Staff Person"

    resp = c.get("/customer/c1/content/preview/rec-admin-preview")
    assert resp.status_code == 200
    body = resp.data.decode()

    assert "Admin Preview Piece" in body
    assert "Admin-visible body copy." in body
    assert 'href="/customer/c1/content"' in body  # unchanged back-link target
