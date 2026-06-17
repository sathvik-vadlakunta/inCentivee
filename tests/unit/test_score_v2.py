"""PracticeRank Score v2 — calibration + robustness.

Target: a fully-executed *early* account (foundation done, content shipped, AI
building, no GSC yet) lands at a strong B (~80). A brand-new account stays low.
A PageSpeed timeout must not tank the score.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from geo_agent.db import CustomerDB
from geo_agent.practicerank_score import compute_practicerank_score


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "score.db"))
    d.add_customer(id="c1", name="Paradigm", domain="p.com", business_type="precious_metals_buyer")
    yield d
    d.close()


def _full_foundation(db, cid):
    for k in ("seo_schema_localbusiness", "seo_schema_faq", "seo_llms_txt", "seo_robots_txt",
              "seo_llms_full", "seo_xml_sitemap", "seo_schema_review", "seo_structured_headings"):
        db.set_checklist_item(cid, k, True)


def _publish(db, cid, rid, rec_type, title):
    db.add_content_recommendation({"id": rid, "customer_id": cid, "rec_type": rec_type,
                                   "title": title, "status": "published",
                                   "published_at": datetime.now(timezone.utc).isoformat()})


def _ai_run(db, cid, rate=0.30, pos=2.4):
    engines = {"Claude": {"status": "active", "mentions": 6, "total": 7},
               "Gemini": {"status": "active", "mentions": 5, "total": 7},
               "Perplexity": {"status": "active", "mentions": 6, "total": 7}}
    db.conn.execute(
        "INSERT INTO ai_mention_runs (id, customer_id, run_date, total_mentions, total_queries, "
        "mention_rate, avg_position, engines_json, prompt_set, methodology) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"{cid}-run", cid, "2026-06-17", 17, 21, rate, pos, json.dumps(engines), "benchmark", "2.0"))
    db.conn.commit()


def test_fully_executed_early_lands_strong_B(db):
    _full_foundation(db, "c1")
    db.update_customer("c1", service_areas=json.dumps(["Fairfax VA", "Vienna VA"]))
    _publish(db, "c1", "p1", "new_page", "Sell Gold in Fairfax VA")
    _publish(db, "c1", "p2", "new_page", "Sell Gold in Vienna VA")
    for i, t in enumerate(["blog_post", "faq_update", "expert_quote", "freshness_update",
                           "blog_post", "faq_update", "new_page", "stat_injection"]):
        _publish(db, "c1", f"x{i}", t, f"piece {i}")
    db.upsert_google_places("c1", place_id="x", rating=4.8, review_count=64,
                            match_confidence="high", lat=0, lng=0)
    _ai_run(db, "c1")
    # No GSC data → Search pillar omitted.

    s = compute_practicerank_score(db, "c1")
    print("fully-executed score:", s["score"], s["grade"]["letter"],
          {k: v.get("score") for k, v in s["pillars"].items()})
    assert 74 <= s["score"] <= 86, f"expected strong B (~80), got {s['score']}"
    assert s["grade"]["letter"] == "B"
    # Foundation (technical_health key) should be maxed.
    assert s["pillars"]["technical_health"]["score"] == 100
    # Search omitted, not zeroed.
    assert s["pillars"]["search_growth"]["available"] is False


def test_brand_new_account_low(db):
    # Only a Google rating exists (no foundation, no content, no AI runs).
    db.upsert_google_places("c1", place_id="x", rating=4.5, review_count=20,
                            match_confidence="high", lat=0, lng=0)
    s = compute_practicerank_score(db, "c1")
    print("baseline score:", s["score"])
    assert s["score"] is None or s["score"] <= 35


def test_baseline_locks_on_first_score(db):
    _full_foundation(db, "c1")
    db.upsert_google_places("c1", place_id="x", rating=4.8, review_count=64,
                            match_confidence="high", lat=0, lng=0)
    _ai_run(db, "c1")
    s1 = compute_practicerank_score(db, "c1")
    base = db.get_customer("c1")["baseline_score"]
    assert base == s1["score"]
    assert s1["delta_from_baseline"] == 0


def test_pagespeed_timeout_does_not_tank(db):
    # Full foundation but NO audit / perf data (PageSpeed timed out) — foundation
    # must still be ~100 (completion-based), not zeroed. (A second pillar present
    # so we clear the <2-pillar 'insufficient data' guard.)
    _full_foundation(db, "c1")
    db.upsert_google_places("c1", place_id="x", rating=4.7, review_count=40,
                            match_confidence="high", lat=0, lng=0)
    s = compute_practicerank_score(db, "c1")
    assert s["pillars"]["technical_health"]["score"] == 100
