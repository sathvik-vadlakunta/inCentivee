"""Client-portal AI Visibility pillar-detail page (Ticket 6): frozen-snapshot
hit-rate-by-engine, share-of-voice, and questions-we-test sections.
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


RUN_ID = "run-current-2026w28"
OTHER_RUN_ID = "run-old-2026w20"

# 4 of the 5 engines have data this snapshot; Grok is deliberately absent from
# the dict entirely (never run as of this snapshot) so tests can assert it
# still renders a 0% / "not yet tested" row.
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
        "ai": {
            "rolling": {"current_rate": 0.58},
            "llms": None,
            "llms_prev": None,
            "latest": {
                "id": RUN_ID,
                "total_queries": 10,
                "mention_rate": 0.58,
                "avg_position": 2.1,
                "run_date": "2026-07-10",
            },
            "engines": {
                "Claude": {"mentions": 9, "total": 10, "status": "active"},
                "ChatGPT": {"mentions": 7, "total": 10, "status": "active"},
                "Perplexity": {"mentions": 4, "total": 10, "status": "active"},
                "Gemini": {"mentions": 2, "total": 10, "status": "active"},
                # Grok intentionally absent.
            },
            "sov": {
                "customer_share": 0.34,
                "customer_mentions": 34,
                "customer_rank": 1,
                "competitors": [
                    {"name": "Casper Dental Group", "normalized_name": "casper dental group",
                     "mention_count": 28, "share": 0.28, "avg_position": 2.0, "unique_queries": 5},
                    {"name": "Wyoming Smiles", "normalized_name": "wyoming smiles",
                     "mention_count": 19, "share": 0.19, "avg_position": 3.0, "unique_queries": 4},
                ],
                "total_entity_mentions": 100,
                "total_unique_entities": 6,
                "runs_analyzed": 3,
            },
            "sov_flag": None,
        },
    },
}


def _seed_ai_mention_results(db: CustomerDB, run_id: str, prompts: list[dict]):
    """Seed ai_mention_runs + ai_mention_results rows for a given run_id.

    `prompts` is a list of {"prompt": str, "hits": [bool, ...]} — one bool
    per engine queried for that prompt.
    """
    db.save_ai_mention_run({
        "id": run_id, "customer_id": "c1", "run_date": "2026-07-10",
        "total_mentions": 0, "total_queries": len(prompts), "mention_rate": 0.0,
        "avg_position": None, "engines": {}, "prompt_set": "benchmark",
    })
    engine_names = ["Claude", "ChatGPT", "Perplexity", "Gemini"]
    for p in prompts:
        for engine, mentioned in zip(engine_names, p["hits"]):
            db.save_ai_mention_result({
                "run_id": run_id, "customer_id": "c1", "engine": engine,
                "prompt": p["prompt"], "mentioned": mentioned,
                "position": 1 if mentioned else None,
            })


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "t.db")
    app.DB_PATH = dbp
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c, dbp


def test_pillar_ai_all_five_engines_always_render(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    _seed_ai_mention_results(db, RUN_ID, [
        {"prompt": "Best emergency dentist near me", "hits": [True, True, True, False]},
        {"prompt": "Family dentist that takes new patients", "hits": [True, True, False, False]},
        {"prompt": "Same-day crowns dentist in Casper", "hits": [True, False, False, False]},
        {"prompt": "Cheapest teeth whitening in Casper Wyoming", "hits": [False, False, False, False]},
    ])
    db.close()

    resp = c.get("/portal/pillar/ai-visibility")
    assert resp.status_code == 200
    body = resp.data.decode()

    # All 5 engines always render a row, including the one absent from the
    # snapshot's engines dict.
    for name in ("Claude", "ChatGPT", "Perplexity", "Gemini", "Grok"):
        assert name in body

    # Percentages exactly match sections.ai.engines from the frozen payload —
    # not a live ai_mention_runs re-query.
    assert "90%" in body  # Claude 9/10
    assert "70%" in body  # ChatGPT 7/10
    assert "40%" in body  # Perplexity 4/10
    assert "20%" in body  # Gemini 2/10

    # Grok has no entry in engines dict at all -> 0% / not-yet-tested row.
    assert "not yet tested" in body


def test_pillar_ai_score_matches_overview_byte_for_byte(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    _seed_ai_mention_results(db, RUN_ID, [
        {"prompt": "Best emergency dentist near me", "hits": [True, True, True, False]},
    ])
    db.close()

    overview_body = c.get("/portal/").data.decode()
    pillar_body = c.get("/portal/pillar/ai-visibility").data.decode()

    # Overview's pillar bar and this page's hero badge must both show 71 for
    # the AI Visibility pillar of this same snapshot.
    assert "<b>71</b>" in pillar_body
    # portal_home.html renders the pillar score as "71 ▲" inside the trend span.
    assert "71 ▲" in overview_body

    # Same color for the same score (grade_from_score is deterministic, but
    # confirm both pages actually resolved through it, not a stray literal).
    from geo_agent.practicerank_score import grade_from_score
    expected_color = grade_from_score(71)["color"]
    assert expected_color in overview_body
    assert expected_color in pillar_body


def test_pillar_ai_share_of_voice_renders(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    _seed_ai_mention_results(db, RUN_ID, [
        {"prompt": "Best emergency dentist near me", "hits": [True, False, False, False]},
    ])
    db.close()

    body = c.get("/portal/pillar/ai-visibility").data.decode()
    assert "Hilltop Family Dental" in body
    assert "34%" in body
    assert "Casper Dental Group" in body
    assert "28%" in body
    assert "Wyoming Smiles" in body
    assert "19%" in body
    assert "Everyone else" in body


def test_pillar_ai_share_of_voice_none_shows_empty_state(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    payload = json.loads(json.dumps(REALISTIC_PAYLOAD))
    payload["sections"]["ai"]["sov"] = None

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(payload), "<html></html>",
    )
    _seed_ai_mention_results(db, RUN_ID, [
        {"prompt": "Best emergency dentist near me", "hits": [True, False, False, False]},
    ])
    db.close()

    body = c.get("/portal/pillar/ai-visibility").data.decode()
    assert "hasn't been calculated yet" in body
    assert "Casper Dental Group" not in body


def test_pillar_ai_questions_scoped_to_snapshot_run_id_only(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    db = CustomerDB(db_path=dbp)
    db.save_report_snapshot(
        "c1", "weekly", "2026-07-07", "2026-07-14", 78,
        json.dumps(REALISTIC_PAYLOAD), "<html></html>",
    )
    _seed_ai_mention_results(db, RUN_ID, [
        {"prompt": "Best emergency dentist near me", "hits": [True, True, True, False]},
        {"prompt": "Cheapest teeth whitening in Casper Wyoming", "hits": [False, False, False, False]},
    ])
    # A different, newer-looking run_id whose questions must NOT leak into
    # this snapshot's page even though it technically exists in the DB.
    _seed_ai_mention_results(db, OTHER_RUN_ID, [
        {"prompt": "This question belongs to a different run entirely", "hits": [True, True, True, True]},
    ])
    db.close()

    body = c.get("/portal/pillar/ai-visibility").data.decode()
    assert "Best emergency dentist near me" in body
    assert "Cheapest teeth whitening in Casper Wyoming" in body
    assert "Not mentioned" in body
    assert "This question belongs to a different run entirely" not in body


def test_pillar_ai_no_report_yet(client):
    c, dbp = client
    _seed_customer_and_login(dbp, c)

    resp = c.get("/portal/pillar/ai-visibility")
    assert resp.status_code == 200
    assert b"No report yet" in resp.data
