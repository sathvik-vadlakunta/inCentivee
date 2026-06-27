"""GBP Q&A engine + the Local SEO checklist collapse + gbp_qa→checklist mapping."""

from __future__ import annotations

import json
from unittest.mock import patch

from geo_agent import gbp_qa


def _seed(db):
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,business_type,city,status,platform) "
        "VALUES (?,?,?,?,?,?,?)",
        ("c1", "Test Metals", "t.example", "precious_metals_buyer", "Springfield VA", "active", "webflow"),
    )
    db.conn.execute(
        "INSERT INTO keyword_tracking (customer_id, keyword, source, is_tracked) VALUES (?,?,?,1)",
        ("c1", "sell gold coins springfield", "manual"),
    )
    # A corrupted CSV-imported keyword that must be filtered out.
    db.conn.execute(
        "INSERT INTO keyword_tracking (customer_id, keyword, source, is_tracked) VALUES (?,?,?,1)",
        ("c1", "best way to sell gold coins,1,1440,0.07%", "gsc"),
    )
    db.conn.commit()


def test_target_keywords_filters_corrupted(tmp_path):
    from geo_agent.db import CustomerDB
    db = CustomerDB(db_path=str(tmp_path / "k.db"))
    _seed(db)
    kws = gbp_qa._target_keywords(db, "c1")
    assert "sell gold coins springfield" in kws
    assert all("," not in k for k in kws)  # corrupted one dropped
    db.close()


def test_generate_gbp_qa_creates_rec_and_is_idempotent(tmp_path, monkeypatch):
    from geo_agent.db import CustomerDB
    db = CustomerDB(db_path=str(tmp_path / "g.db"))
    _seed(db)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    fake = json.dumps({"qa": [
        {"question": "Where can I sell gold coins in Springfield VA?",
         "answer": "Paradigm Experts buys gold coins in Springfield and across Northern Virginia. Stop in for a free evaluation."},
        {"question": "Do you buy sterling silver?",
         "answer": "Yes, we purchase sterling silver flatware and tea sets. Bring your items in for an assessment."},
    ]})

    with patch("anthropic.Anthropic"), \
         patch.object(gbp_qa, "complete", return_value=fake):
        rec = gbp_qa.generate_gbp_qa(db, "c1", today="2026-06-15")

    assert rec is not None
    assert rec["rec_type"] == "gbp_qa"
    assert rec["status"] == "pending"
    assert "GBP Q&A" in rec["title"] and "June 2026" in rec["title"]
    assert "<h3>" in rec["html_snippet"]
    stored = db.get_content_recommendations("c1", limit=10)
    assert any(r["rec_type"] == "gbp_qa" for r in stored)

    # Second run same month → idempotent (returns None, no duplicate).
    with patch("anthropic.Anthropic"), patch.object(gbp_qa, "complete", return_value=fake):
        again = gbp_qa.generate_gbp_qa(db, "c1", today="2026-06-28")
    assert again is None
    assert sum(1 for r in db.get_content_recommendations("c1", limit=10) if r["rec_type"] == "gbp_qa") == 1
    db.close()


def test_gbp_qa_publish_ticks_checklist():
    from geo_agent.status_checker import _content_task_status
    recs = [{"rec_type": "gbp_qa", "status": "published"}]
    out = _content_task_status(recs, customer=None, domain="")
    assert out.get("seo_gbp_qa") is True


def test_local_seo_checklist_collapsed():
    """The 6 granular citation items are gone; the 2 consolidated ones + Apple remain."""
    import dashboard.app as app
    tasks = app._get_seo_tasks({}, business_type="precious_metals_buyer")
    keys = {t["key"] for t in tasks}
    # Removed
    for gone in ("seo_yelp", "seo_facebook", "seo_bing_places",
                 "seo_nap_consistent", "seo_tier2_citations"):
        assert gone not in keys, f"{gone} should be removed"
    # Present
    for present in ("seo_citations_ordered", "seo_listings_verified", "seo_apple_business"):
        assert present in keys, f"{present} should be present"
