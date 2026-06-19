"""Tests for the GSC-keyword content recommender."""

from __future__ import annotations

import pytest

from geo_agent.db import CustomerDB
from geo_agent.keyword_content import _classify, recommend_from_search_data


def test_classify_opportunity_types():
    assert _classify({"query": "how much do dental implants cost", "impressions": 50, "position": 30, "clicks": 0, "ctr": 0}) == "question"
    assert _classify({"query": "dental implants austin", "impressions": 120, "position": 12, "clicks": 1, "ctr": 0.008}) == "striking_distance"
    assert _classify({"query": "smith dental", "impressions": 400, "position": 4, "clicks": 1, "ctr": 0.0025}) == "high_impressions_low_ctr"
    assert _classify({"query": "teeth whitening round rock", "impressions": 80, "position": 34, "clicks": 0, "ctr": 0}) == "untapped"
    # Too few impressions → skip
    assert _classify({"query": "x", "impressions": 3, "position": 12, "clicks": 0, "ctr": 0}) is None


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "t.db"))
    d.add_customer(id="c1", name="C", domain="c.com")
    yield d
    d.close()


def _seed(db, date, rows):
    db.save_gsc_query_daily("c1", date, rows)


def test_recommend_creates_and_dedupes(db):
    rows = [
        {"query": "dental implants austin", "clicks": 1, "impressions": 200, "ctr": 0.005, "position": 11},
        {"query": "how much are veneers", "clicks": 0, "impressions": 90, "ctr": 0, "position": 18},
        {"query": "invisalign near me", "clicks": 0, "impressions": 60, "ctr": 0, "position": 25},
    ]
    _seed(db, "2026-06-10", rows)
    created = recommend_from_search_data(db, "c1", today="2026-06-19")
    assert len(created) == 3
    cats = {c["rec_type"] for c in created}
    assert "new_page" in cats and "faq_update" in cats
    # Persisted as pending recs
    pend = db.get_content_recommendations("c1", status="pending")
    assert len(pend) == 3
    # Re-run: nothing new (deduped on the query in target_page)
    again = recommend_from_search_data(db, "c1", today="2026-06-19")
    assert again == []


def test_no_data_returns_empty(db):
    assert recommend_from_search_data(db, "c1", today="2026-06-19") == []
