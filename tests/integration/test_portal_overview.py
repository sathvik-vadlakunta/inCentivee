"""Client-portal Overview page (Ticket 4): score hero, pillar breakdown,
supporting cards, and the "no report yet" empty state.
"""

from __future__ import annotations

import json

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


REALISTIC_PAYLOAD = {
    "score": {
        "score": 78,
        "grade": {"letter": "B", "label": "Strong", "color": "#65a30d"},
        "pillars": {
            "ai_visibility": {"score": 71, "available": True,
                              "detail": {"trend": "up"}},
            "technical_health": {"score": 88, "available": True, "detail": {}},
            "content_velocity": {"score": 74, "available": True, "detail": {}},
            "reputation": {"score": 69, "available": True, "detail": {}},
            "search_growth": {"score": None, "available": False, "detail": {}},
        },
    },
    "score_prev": 74,
    "sections": {
        "search": {
            "cur": {"clicks": 312, "impressions": 4400, "ctr": 0.07, "position": 8.2},
            "prev": {"clicks": 264, "impressions": 4100, "ctr": 0.06, "position": 9.1},
        },
        "ai": {
            "rolling": {"current_rate": 0.58},
            "llms": None,
            "latest": {"total_queries": 8, "mention_rate": 0.58, "avg_position": 2.1},
            "engines": {
                "Claude": {"mentions": 8, "total": 8, "status": "active"},
                "ChatGPT": {"mentions": 6, "total": 8, "status": "active"},
                "Gemini": {"mentions": 0, "total": 8, "status": "pending"},
            },
            "sov": None,
            "sov_flag": None,
        },
        "reviews": {
            "places": {"rating": 4.7, "review_count": 128},
            "new_count": 3,
            "new_five_star": 2,
            "gap": None,
            "velocity": None,
        },
        "wins": {
            "published": [
                {"title": "Emergency Dental Care in Casper"},
                {"title": "What to Do If You Chip a Tooth"},
            ],
            "intent_mix": None,
        },
    },
}


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "t.db")
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c, dbp


def test_portal_overview_renders_real_snapshot(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    db.close()

    resp = c.get("/portal/")
    assert resp.status_code == 200
    body = resp.data.decode()

    # Score hero
    assert "78" in body
    assert "Grade B" in body
    assert "▲ 4 pts vs last period" in body

    # Pillar breakdown — labels, weights, and the unavailable pillar skipped
    assert "AI Visibility" in body
    assert "30% of your score" in body
    assert "GEO Foundation" in body
    assert "Content &amp; Coverage" in body or "Content & Coverage" in body
    assert "Reputation" in body
    assert "Search Performance" not in body  # unavailable pillar must be skipped
    assert '/portal/pillar/ai-visibility' in body
    assert '/portal/pillar/geo-foundation' in body

    # Supporting cards
    assert "312" in body  # search clicks
    assert "58%" in body  # AI hit rate
    assert "Claude" in body
    assert "4.7" in body  # review rating
    assert "128" in body  # review count
    assert "Emergency Dental Care in Casper" in body

    # Explicit out-of-scope content must never render here
    assert "Domain Authority" not in body
    assert "FATJOE" not in body
    assert "domain-authority" not in body.lower()


def test_portal_overview_no_report_yet(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    resp = c.get("/portal/")
    assert resp.status_code == 200
    assert b"No report yet" in resp.data


def test_portal_overview_falls_back_to_monthly_snapshot(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "monthly", "2026-06-14", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    db.close()

    resp = c.get("/portal/")
    assert resp.status_code == 200
    assert b"78" in resp.data
