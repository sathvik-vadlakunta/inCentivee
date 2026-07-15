"""Client-portal Pillar Detail pages (Ticket 5): GEO Foundation, Content &
Coverage, Reputation, Search Performance. AI Visibility (Ticket 6) is out of
scope here.
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


# Full, "current" snapshot payload — includes every detail sub-dict and the new
# traffic_series/ai_mention_series fields a snapshot generated after this
# ticket's weekly_report.py change would carry.
REALISTIC_PILLAR_PAYLOAD = {
    "score": {
        "score": 78,
        "grade": {"letter": "B", "label": "Strong", "color": "#65a30d"},
        "pillars": {
            "ai_visibility": {"score": 71, "available": True, "weight": 0.30,
                               "detail": {"trend": "up"}},
            "technical_health": {"score": 88, "available": True, "weight": 0.30,
                                  "detail": {
                                      "deliverables_done": 7,
                                      "deliverables_total": 8,
                                      "items": {
                                          "seo_schema_localbusiness": True,
                                          "seo_schema_faq": True,
                                          "seo_llms_txt": True,
                                          "seo_robots_txt": True,
                                          "seo_llms_full": False,
                                          "seo_xml_sitemap": True,
                                          "seo_schema_review": True,
                                          "seo_structured_headings": True,
                                      },
                                  }},
            "content_velocity": {"score": 74, "available": True, "weight": 0.20,
                                  "detail": {
                                      "areas_covered": 3,
                                      "service_areas": 4,
                                      "covered_areas": ["Casper, WY", "Mills, WY", "Evansville, WY"],
                                      "uncovered_areas": ["East Casper, WY"],
                                  }},
            "reputation": {"score": 69, "available": True, "weight": 0.10,
                           "detail": {"rating": 4.7, "review_count": 128}},
            "search_growth": {"score": 82, "available": True, "weight": 0.10,
                               "detail": {}},
        },
    },
    "score_prev": 74,
    "sections": {
        "search": {
            "cur": {"clicks": 312, "impressions": 9840, "ctr": 0.032, "position": 8.1},
            "prev": {"clicks": 264, "impressions": 8850, "ctr": 0.029, "position": 9.0},
        },
        "keywords": {
            "movers": {
                "up": [
                    {"query": "emergency dentist casper", "clicks": 41, "position": 6.8, "move": 3.5},
                    {"query": "dentist casper wy", "clicks": 74, "position": 4.1, "move": 1.2},
                ],
                "down": [
                    {"query": "family dentist near me", "clicks": 28, "position": 11.4, "move": -0.6},
                ],
            },
        },
        "traffic_series": [
            {"label": "4/28", "clicks": 37, "ctr": 0.026},
            {"label": "5/5", "clicks": 44, "ctr": 0.028},
            {"label": "5/12", "clicks": 41, "ctr": 0.027},
            {"label": "5/19", "clicks": 53, "ctr": 0.029},
            {"label": "5/26", "clicks": 57, "ctr": 0.030},
            {"label": "6/2", "clicks": 64, "ctr": 0.031},
            {"label": "6/9", "clicks": 78, "ctr": 0.033},
            {"label": "6/16", "clicks": 92, "ctr": 0.034},
        ],
        "ai_mention_series": [
            {"label": "4/28", "mention_rate": 0.34},
            {"label": "5/5", "mention_rate": 0.37},
            {"label": "5/12", "mention_rate": 0.39},
            {"label": "5/19", "mention_rate": 0.42},
            {"label": "5/26", "mention_rate": 0.46},
            {"label": "6/2", "mention_rate": 0.49},
            {"label": "6/9", "mention_rate": 0.53},
            {"label": "6/16", "mention_rate": 0.58},
        ],
        "ai": {
            "rolling": {"current_rate": 0.58},
            "llms": None,
            "latest": {"total_queries": 8, "mention_rate": 0.58, "avg_position": 2.1},
            "engines": {"Claude": {"mentions": 8, "total": 8, "status": "active"}},
            "sov": None,
            "sov_flag": None,
        },
        "reviews": {
            "places": {"rating": 4.7, "review_count": 128},
            "new_count": 2,
            "new_five_star": 2,
            "gap": None,
            "velocity": None,
        },
        "wins": {
            "published": [
                {"title": "Casper Emergency Dental Page", "rec_type": "new_page"},
                {"title": "Mills Family Dentist Page", "rec_type": "new_page"},
                {"title": "Evansville Dentist Page", "rec_type": "new_page"},
                {"title": "What to Do If You Chip a Tooth", "rec_type": "blog_post"},
                {"title": "Best Toothpaste for Sensitive Teeth", "rec_type": "blog_post"},
                {"title": "Emergency Dental FAQ", "rec_type": "blog_post"},
                {"title": "Invisalign Guide", "rec_type": "blog_post"},
                {"title": "Do You Take My Insurance?", "rec_type": "faq_update"},
                {"title": "What Ages Do You See?", "rec_type": "faq_update"},
                {"title": "2026 Hours Update", "rec_type": "freshness_update"},
            ],
            "intent_mix": None,
        },
    },
}


# Old-style snapshot — matches the pre-Ticket-5 shape (same as
# test_portal_overview.REALISTIC_PAYLOAD): pillar `detail` dicts are empty and
# there's no traffic_series/ai_mention_series/covered_areas at all. Regression
# fixture for the "must not crash on an old snapshot" requirement.
OLD_STYLE_PAYLOAD = {
    "score": {
        "score": 78,
        "grade": {"letter": "B", "label": "Strong", "color": "#65a30d"},
        "pillars": {
            "ai_visibility": {"score": 71, "available": True, "detail": {"trend": "up"}},
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


def test_portal_pillar_geo_foundation(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get("/portal/pillar/geo-foundation")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "88" in body  # pillar-hero score matches score.pillars.technical_health.score
    assert "GEO Foundation" in body
    assert "7 of 8 deliverables complete" in body
    assert "Business info schema" in body
    assert "Extended AI content file" in body  # the one pending item (seo_llms_full: False)


def test_portal_pillar_content_coverage(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get("/portal/pillar/content-coverage")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "74" in body  # pillar-hero score
    assert "Content" in body and "Coverage" in body
    assert "Location &amp; service pages" in body or "Location & service pages" in body
    assert "3 of 4 area" in body
    assert "Casper, WY" in body
    assert "East Casper, WY" in body  # uncovered chip still rendered (pending dot)


def test_portal_pillar_reputation(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    # Seed a couple of "rating" KPI points directly — the same metric
    # kpi_tracker.track_google_reviews() records on its own schedule (the
    # live, non-payload exception documented in the route) — to exercise
    # the trend rendering.
    db.record_kpi("c1", "rating", 4.5, date="2026-06-01")
    db.record_kpi("c1", "rating", 4.7, date="2026-07-01")
    db.close()

    resp = c.get("/portal/pillar/reputation")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "69" in body  # pillar-hero score
    assert "4.7★" in body  # current rating card
    assert "128" in body  # total reviews
    assert "Rating trend" in body
    assert "06/01" in body or "6/01" in body  # trend row label present


def test_portal_pillar_reputation_no_kpi_history_yet(client):
    """No "rating" KPI rows at all — must render the 'not enough history
    yet' message, not crash."""
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get("/portal/pillar/reputation")
    assert resp.status_code == 200
    assert b"Not enough history yet" in resp.data


def test_portal_pillar_search_performance(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get("/portal/pillar/search-performance")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "82" in body  # pillar-hero score
    assert "312" in body  # clicks KPI card
    assert "3.2%" in body  # CTR card (0.032 -> 3.2%)
    # Weekly numbers stored in the snapshot's payload_json (not a live query)
    # must show up verbatim in the collapsible table.
    assert "37" in body and "2.6%" in body  # first week: clicks=37, ctr=2.6%
    assert "92" in body  # last week's clicks, also the chart endpoint label
    assert "58%" in body  # last week's AI mention rate
    assert "emergency dentist casper" in body
    assert "family dentist near me" in body


def test_portal_pillar_unknown_key_404s(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(REALISTIC_PILLAR_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get("/portal/pillar/not-a-real-pillar")
    assert resp.status_code == 404


def test_portal_pillar_no_report_yet(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    resp = c.get("/portal/pillar/geo-foundation")
    assert resp.status_code == 200
    assert b"No report yet" in resp.data


@pytest.mark.parametrize("key", [
    "geo-foundation", "content-coverage", "reputation", "search-performance",
])
def test_portal_pillar_degrades_gracefully_on_old_snapshot(client, key):
    """An old snapshot predating this ticket's payload additions (no
    covered_areas/traffic_series/ai_mention_series, empty `detail` dicts) must
    still render 200, not crash."""
    c, dbp = client
    _seed_customer_and_login(dbp, c)
    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot("c1", "weekly", "2026-07-07", "2026-07-14", 78,
                             json.dumps(OLD_STYLE_PAYLOAD), "<html></html>")
    db.close()

    resp = c.get(f"/portal/pillar/{key}")
    assert resp.status_code == 200
