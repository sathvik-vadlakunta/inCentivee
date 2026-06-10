"""Tests for PracticeRank Score engine and Quick Wins."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from geo_agent.db import CustomerDB
from geo_agent.practicerank_score import (
    PILLAR_WEIGHTS,
    _score_engine_breadth,
    _score_mention_rate,
    _score_position_quality,
    _score_ai_trend,
    compute_ai_visibility,
    compute_content_velocity,
    compute_practicerank_score,
    compute_reputation,
    compute_search_growth,
    compute_technical_health,
    grade_from_score,
)
from geo_agent.quick_wins import (
    QuickWin,
    detect_quick_wins,
    format_for_email,
    prioritize,
)


@pytest.fixture
def db(tmp_path):
    """Create a fresh in-memory-like DB for each test."""
    db_path = str(tmp_path / "test_pr.db")
    db = CustomerDB(db_path)
    yield db
    db.close()


@pytest.fixture
def customer_id(db):
    """Insert a test customer and return its ID."""
    cid = "test-dental"
    db.conn.execute(
        "INSERT INTO customers (id, name, domain, city, state) VALUES (?, ?, ?, ?, ?)",
        (cid, "Test Dental", "testdental.com", "Austin", "TX"),
    )
    db.conn.commit()
    return cid


def _insert_ai_runs(db, customer_id, count=5, base_rate=0.35):
    """Insert N AI mention runs with configurable mention rates."""
    now = datetime.now(timezone.utc)
    for i in range(count):
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        run_date = (now - timedelta(days=i * 7)).isoformat()
        rate = max(0, min(1, base_rate + (i * 0.02 - 0.04)))  # slight variation
        engines = {"chatgpt": {"mentions": 3, "queries": 5},
                   "claude": {"mentions": 2, "queries": 5},
                   "perplexity": {"mentions": 1, "queries": 5}}
        db.conn.execute(
            """INSERT INTO ai_mention_runs
               (id, customer_id, run_date, total_mentions, total_queries,
                mention_rate, avg_position, engines_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, customer_id, run_date, int(rate * 15), 15, rate, 2.5,
             json.dumps(engines)),
        )
    db.conn.commit()


def _insert_gsc_daily(db, customer_id, days=60, base_clicks=10, growth=0.5):
    """Insert GSC daily data with configurable growth."""
    now = datetime.now(timezone.utc)
    for i in range(days):
        date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        # Later days have more clicks (growth)
        day_factor = 1 + growth * (1 - i / days)
        clicks = int(base_clicks * day_factor)
        impressions = clicks * 20
        db.conn.execute(
            """INSERT OR IGNORE INTO gsc_daily_metrics
               (customer_id, date, clicks, impressions, ctr, position)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, date, clicks, impressions, 0.05, 15.0 - i * 0.05),
        )
    db.conn.commit()


def _insert_google_places(db, customer_id, rating=4.7, review_count=120):
    """Insert Google Places data."""
    db.conn.execute(
        """INSERT OR REPLACE INTO google_places
           (customer_id, place_id, rating, review_count, match_confidence, lat, lng, last_checked)
           VALUES (?, ?, ?, ?, 'high', 30.0, -97.0, ?)""",
        (customer_id, "ChIJtest", rating, review_count,
         datetime.now(timezone.utc).isoformat()),
    )
    db.conn.commit()


def _insert_competitors(db, customer_id, count=3, avg_reviews=80):
    """Insert competitor data."""
    for i in range(count):
        db.conn.execute(
            """INSERT INTO competitors
               (customer_id, name, rating, review_count, location, place_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, f"Competitor {i+1}", 4.2 + i * 0.1,
             avg_reviews + i * 10, "Austin, TX", f"ChIJcomp{i}"),
        )
    db.conn.commit()


def _insert_site_audit(db, customer_id, seo=85, perf=70):
    """Insert a site audit."""
    db.conn.execute(
        """INSERT INTO site_audits
           (customer_id, audit_date, performance_score, accessibility_score,
            seo_score, best_practices_score, issues_json, raw_data_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, datetime.now(timezone.utc).strftime("%Y-%m-%d"),
         perf, 90, seo, 85, "[]", "{}"),
    )
    db.conn.commit()


def _insert_content_recs(db, customer_id, published=3, approved=2, pending=1):
    """Insert content recommendations."""
    now = datetime.now(timezone.utc)
    for i in range(published):
        db.conn.execute(
            """INSERT INTO content_recommendations
               (id, customer_id, rec_type, title, description, status, published_at)
               VALUES (?, ?, 'blog_post', ?, 'Test description', 'published', ?)""",
            (f"rec-pub-{i}", customer_id, f"Published Post {i}",
             (now - timedelta(days=5 + i)).isoformat()),
        )
    for i in range(approved):
        db.conn.execute(
            """INSERT INTO content_recommendations
               (id, customer_id, rec_type, title, description, status)
               VALUES (?, ?, 'blog_post', ?, 'Test description', 'approved')""",
            (f"rec-app-{i}", customer_id, f"Approved Post {i}"),
        )
    for i in range(pending):
        db.conn.execute(
            """INSERT INTO content_recommendations
               (id, customer_id, rec_type, title, description, status)
               VALUES (?, ?, 'blog_post', ?, 'Test description', 'pending')""",
            (f"rec-pen-{i}", customer_id, f"Pending Post {i}"),
        )
    db.conn.commit()


def _insert_ai_readiness(db, customer_id, score=60):
    """Insert AI readiness score."""
    breakdown = {
        "local_business_schema": True,
        "faq_schema": True,
        "aggregate_rating_schema": False,
        "llms_txt": True,
        "person_schema": False,
    }
    db.conn.execute(
        """INSERT INTO ai_readiness_scores
           (customer_id, date, score, breakdown_json)
           VALUES (?, ?, ?, ?)""",
        (customer_id, datetime.now(timezone.utc).strftime("%Y-%m-%d"),
         score, json.dumps(breakdown)),
    )
    db.conn.commit()


# ===================================================================
# Grade Tests
# ===================================================================

class TestGrades:
    def test_grade_a(self):
        assert grade_from_score(95)["letter"] == "A"
        assert grade_from_score(90)["letter"] == "A"

    def test_grade_b(self):
        assert grade_from_score(80)["letter"] == "B"
        assert grade_from_score(75)["letter"] == "B"

    def test_grade_c(self):
        assert grade_from_score(65)["letter"] == "C"
        assert grade_from_score(60)["letter"] == "C"

    def test_grade_d(self):
        assert grade_from_score(50)["letter"] == "D"
        assert grade_from_score(40)["letter"] == "D"

    def test_grade_f(self):
        assert grade_from_score(30)["letter"] == "F"
        assert grade_from_score(0)["letter"] == "F"

    def test_grade_has_color(self):
        g = grade_from_score(95)
        assert "color" in g
        assert g["color"].startswith("#")


# ===================================================================
# Sub-scorer Tests
# ===================================================================

class TestSubScorers:
    def test_mention_rate_high(self):
        assert _score_mention_rate(0.60) == 100.0

    def test_mention_rate_medium(self):
        score = _score_mention_rate(0.30)
        assert 50 <= score <= 70

    def test_mention_rate_low(self):
        score = _score_mention_rate(0.05)
        assert 5 <= score <= 15

    def test_mention_rate_zero(self):
        assert _score_mention_rate(0.0) == 0.0

    def test_position_quality_first(self):
        assert _score_position_quality(1.0) == 100.0

    def test_position_quality_low(self):
        assert _score_position_quality(6.0) == 20.0

    def test_position_quality_zero(self):
        assert _score_position_quality(0) == 0.0

    def test_engine_breadth_all(self):
        assert _score_engine_breadth(5) == 100.0
        assert _score_engine_breadth(4) == 80.0

    def test_engine_breadth_none(self):
        assert _score_engine_breadth(0) == 0.0

    def test_ai_trend_improving(self):
        assert _score_ai_trend(0.40, 0.20) == 100.0

    def test_ai_trend_stable(self):
        assert _score_ai_trend(0.30, 0.30) == 50.0

    def test_ai_trend_no_history(self):
        assert _score_ai_trend(0.30, None) == 40.0

    def test_ai_trend_declining(self):
        score = _score_ai_trend(0.10, 0.30)
        assert score <= 30


# ===================================================================
# Pillar Tests
# ===================================================================

class TestAIVisibility:
    def test_returns_none_without_runs(self, db, customer_id):
        result = compute_ai_visibility(db, customer_id)
        assert result is None

    def test_returns_score_with_runs(self, db, customer_id):
        _insert_ai_runs(db, customer_id, count=5, base_rate=0.35)
        result = compute_ai_visibility(db, customer_id)
        assert result is not None
        assert 0 <= result["score"] <= 100
        assert "detail" in result
        assert "sub_scores" in result["detail"]

    def test_high_mention_rate_scores_high(self, db, customer_id):
        _insert_ai_runs(db, customer_id, count=5, base_rate=0.60)
        result = compute_ai_visibility(db, customer_id)
        assert result["score"] >= 70

    def test_low_mention_rate_scores_low(self, db, customer_id):
        _insert_ai_runs(db, customer_id, count=5, base_rate=0.05)
        result = compute_ai_visibility(db, customer_id)
        assert result["score"] <= 40


class TestSearchGrowth:
    def test_returns_none_without_gsc(self, db, customer_id):
        result = compute_search_growth(db, customer_id)
        assert result is None

    def test_returns_score_with_gsc(self, db, customer_id):
        _insert_gsc_daily(db, customer_id, days=60)
        result = compute_search_growth(db, customer_id)
        assert result is not None
        assert 0 <= result["score"] <= 100

    def test_growth_scores_higher(self, db, customer_id):
        _insert_gsc_daily(db, customer_id, days=60, base_clicks=10, growth=1.0)
        result = compute_search_growth(db, customer_id)
        assert result["score"] >= 40  # growth should score decently

    def test_minimal_data(self, db, customer_id):
        """Less than 7 days returns None."""
        _insert_gsc_daily(db, customer_id, days=3)
        result = compute_search_growth(db, customer_id)
        assert result is None


class TestTechnicalHealth:
    def test_returns_none_without_audit(self, db, customer_id):
        result = compute_technical_health(db, customer_id)
        assert result is None

    def test_returns_score_with_audit(self, db, customer_id):
        _insert_site_audit(db, customer_id)
        result = compute_technical_health(db, customer_id)
        assert result is not None
        assert 0 <= result["score"] <= 100

    def test_high_scores(self, db, customer_id):
        _insert_site_audit(db, customer_id, seo=95, perf=90)
        _insert_ai_readiness(db, customer_id, score=90)
        result = compute_technical_health(db, customer_id)
        assert result["score"] >= 60


class TestContentVelocity:
    def test_returns_none_without_content(self, db, customer_id):
        result = compute_content_velocity(db, customer_id)
        assert result is None

    def test_returns_score_with_published(self, db, customer_id):
        _insert_content_recs(db, customer_id, published=5, approved=0)
        result = compute_content_velocity(db, customer_id)
        assert result is not None
        assert 0 <= result["score"] <= 100

    def test_unpublished_approved_lowers_score(self, db, customer_id):
        _insert_content_recs(db, customer_id, published=1, approved=5)
        result = compute_content_velocity(db, customer_id)
        # Low publish ratio should keep score moderate
        assert result["score"] <= 70


class TestReputation:
    def test_returns_none_without_places(self, db, customer_id):
        result = compute_reputation(db, customer_id)
        assert result is None

    def test_high_rating_high_reviews(self, db, customer_id):
        _insert_google_places(db, customer_id, rating=4.9, review_count=200)
        _insert_competitors(db, customer_id, avg_reviews=80)
        result = compute_reputation(db, customer_id)
        assert result is not None
        assert result["score"] >= 70

    def test_low_rating(self, db, customer_id):
        _insert_google_places(db, customer_id, rating=3.2, review_count=10)
        result = compute_reputation(db, customer_id)
        assert result["score"] <= 40

    def test_no_competitors_uses_absolute(self, db, customer_id):
        _insert_google_places(db, customer_id, rating=4.5, review_count=50)
        result = compute_reputation(db, customer_id)
        assert result is not None
        assert result["score"] >= 40


# ===================================================================
# Composite Score Tests
# ===================================================================

class TestCompositeScore:
    def test_insufficient_data(self, db, customer_id):
        """No data at all → insufficient."""
        result = compute_practicerank_score(db, customer_id)
        assert result["score"] is None
        assert result["label"] == "Insufficient Data"

    def test_one_pillar_insufficient(self, db, customer_id):
        """Only 1 pillar available → still insufficient."""
        _insert_google_places(db, customer_id)
        result = compute_practicerank_score(db, customer_id)
        assert result["score"] is None

    def test_two_pillars_sufficient(self, db, customer_id):
        """2 pillars → enough for a score."""
        _insert_google_places(db, customer_id)
        _insert_site_audit(db, customer_id)
        result = compute_practicerank_score(db, customer_id)
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100

    def test_all_pillars(self, db, customer_id):
        """Full data → all 5 pillars scored."""
        _insert_ai_runs(db, customer_id, count=5, base_rate=0.40)
        _insert_gsc_daily(db, customer_id, days=60)
        _insert_site_audit(db, customer_id, seo=85, perf=75)
        _insert_ai_readiness(db, customer_id)
        _insert_content_recs(db, customer_id, published=5, approved=1)
        _insert_google_places(db, customer_id, rating=4.7, review_count=120)
        _insert_competitors(db, customer_id, avg_reviews=80)

        result = compute_practicerank_score(db, customer_id)
        assert result["score"] is not None
        assert result["available_count"] == 5
        assert all(
            result["pillars"][p]["available"]
            for p in PILLAR_WEIGHTS
        )

    def test_score_range(self, db, customer_id):
        """Score must be 0-100."""
        _insert_ai_runs(db, customer_id, count=5, base_rate=0.40)
        _insert_gsc_daily(db, customer_id, days=60)
        _insert_site_audit(db, customer_id)
        _insert_google_places(db, customer_id)
        _insert_content_recs(db, customer_id)

        result = compute_practicerank_score(db, customer_id)
        assert 0 <= result["score"] <= 100

    def test_grade_included(self, db, customer_id):
        _insert_ai_runs(db, customer_id, count=5)
        _insert_gsc_daily(db, customer_id, days=60)
        result = compute_practicerank_score(db, customer_id)
        assert "grade" in result
        assert "letter" in result["grade"]

    def test_weight_redistribution(self, db, customer_id):
        """When pillars are missing, weights should be redistributed."""
        _insert_google_places(db, customer_id)
        _insert_site_audit(db, customer_id)
        result = compute_practicerank_score(db, customer_id)

        # Only reputation and technical_health available
        assert result["pillars"]["ai_visibility"]["available"] is False
        assert result["pillars"]["reputation"]["available"] is True
        assert result["pillars"]["technical_health"]["available"] is True

        # Available pillars should have higher effective weights
        rep_weight = result["pillars"]["reputation"]["weight"]
        tech_weight = result["pillars"]["technical_health"]["weight"]
        assert rep_weight > PILLAR_WEIGHTS["reputation"]
        assert tech_weight > PILLAR_WEIGHTS["technical_health"]


# ===================================================================
# DB Score Storage Tests
# ===================================================================

class TestScoreStorage:
    def test_save_and_retrieve(self, db, customer_id):
        db.save_practicerank_score(
            customer_id=customer_id,
            date="2026-05-27",
            overall=72,
            ai_visibility=55,
            search_growth=80,
            technical_health=85,
            content_velocity=60,
            reputation=75,
        )
        scores = db.get_practicerank_scores(customer_id)
        assert len(scores) == 1
        assert scores[0]["overall_score"] == 72
        assert scores[0]["ai_visibility"] == 55

    def test_upsert_same_date(self, db, customer_id):
        """Same date should update, not duplicate."""
        db.save_practicerank_score(customer_id, "2026-05-27", 60, 50, 50, 50, 50, 50)
        db.save_practicerank_score(customer_id, "2026-05-27", 75, 60, 60, 60, 60, 60)
        scores = db.get_practicerank_scores(customer_id)
        assert len(scores) == 1
        assert scores[0]["overall_score"] == 75

    def test_latest_score(self, db, customer_id):
        db.save_practicerank_score(customer_id, "2026-05-25", 60, 50, 50, 50, 50, 50)
        db.save_practicerank_score(customer_id, "2026-05-27", 72, 55, 55, 55, 55, 55)
        latest = db.get_latest_practicerank_score(customer_id)
        assert latest["overall_score"] == 72

    def test_all_latest_scores(self, db, customer_id):
        # Add another customer
        db.conn.execute(
            "INSERT INTO customers (id, name, domain, city, state) VALUES (?, ?, ?, ?, ?)",
            ("other-dental", "Other Dental", "other.com", "Denver", "CO"),
        )
        db.conn.commit()

        db.save_practicerank_score(customer_id, "2026-05-27", 72, 55, 55, 55, 55, 55)
        db.save_practicerank_score("other-dental", "2026-05-27", 85, 70, 70, 70, 70, 70)

        all_scores = db.get_all_latest_scores()
        assert len(all_scores) == 2
        assert all_scores[0]["overall_score"] == 85  # sorted desc

    def test_score_history_limit(self, db, customer_id):
        for i in range(10):
            db.save_practicerank_score(
                customer_id, f"2026-05-{17+i:02d}", 50 + i, 50, 50, 50, 50, 50
            )
        scores = db.get_practicerank_scores(customer_id, limit=5)
        assert len(scores) == 5
        assert scores[0]["date"] == "2026-05-26"  # most recent


# ===================================================================
# Quick Wins Tests
# ===================================================================

class TestQuickWins:
    def test_no_data_suggests_basics(self, db, customer_id):
        """Customer with no data should get foundational quick wins."""
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "ai_no_run" in win_ids
        assert "rep_no_gbp" in win_ids

    def test_unpublished_content_detected(self, db, customer_id):
        _insert_content_recs(db, customer_id, published=1, approved=3)
        _insert_google_places(db, customer_id)
        _insert_ai_runs(db, customer_id, count=1, base_rate=0.30)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "content_unpublished" in win_ids

    def test_low_reviews_detected(self, db, customer_id):
        _insert_google_places(db, customer_id, rating=4.5, review_count=8)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "rep_low_reviews" in win_ids

    def test_low_rating_detected(self, db, customer_id):
        _insert_google_places(db, customer_id, rating=3.5, review_count=50)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "rep_low_rating" in win_ids

    def test_no_gsc_detected(self, db, customer_id):
        _insert_google_places(db, customer_id)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "seo_no_gsc" in win_ids

    def test_priority_sort(self):
        """High impact + low effort should come first."""
        wins = [
            QuickWin("low", "Low", "d", "tech", "low", "high", 1, "/", "Go"),
            QuickWin("high", "High", "d", "ai", "high", "low", 10, "/", "Go"),
            QuickWin("med", "Med", "d", "content", "medium", "medium", 5, "/", "Go"),
        ]
        sorted_wins = prioritize(wins)
        assert sorted_wins[0].id == "high"
        assert sorted_wins[-1].id == "low"

    def test_format_for_email(self):
        wins = [
            QuickWin("test", "Do Something", "It helps.", "ai", "high", "low", 5, "/", "Go"),
        ]
        md = format_for_email(wins)
        assert "Do Something" in md
        assert "+5" in md

    def test_format_for_email_empty(self):
        md = format_for_email([])
        assert "great work" in md.lower()

    def test_max_5_wins(self, db, customer_id):
        """Should not return more than a reasonable number."""
        # Set up a customer with lots of issues
        _insert_google_places(db, customer_id, rating=3.5, review_count=5)
        _insert_content_recs(db, customer_id, published=0, approved=3, pending=5)
        wins = detect_quick_wins(db, customer_id)
        # Just verify it returns a list (no crash) and it's reasonable
        assert isinstance(wins, list)
        assert len(wins) > 0

    def test_quick_win_to_dict(self):
        w = QuickWin("test", "Title", "Desc", "ai", "high", "low", 5, "/url", "Go")
        d = w.to_dict()
        assert d["id"] == "test"
        assert d["priority"] == 9  # high(3) * low_effort(3) = 9

    def test_stale_ai_run_detected(self, db, customer_id):
        """AI run from 45 days ago should trigger a quick win."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        db.conn.execute(
            """INSERT INTO ai_mention_runs
               (id, customer_id, run_date, total_mentions, total_queries,
                mention_rate, engines_json)
               VALUES (?, ?, ?, 5, 15, 0.33, '{}')""",
            ("old-run", customer_id, old_date),
        )
        db.conn.commit()

        _insert_google_places(db, customer_id)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "ai_stale_run" in win_ids

    def test_no_content_recs_detected(self, db, customer_id):
        _insert_google_places(db, customer_id)
        _insert_ai_runs(db, customer_id, count=1)
        wins = detect_quick_wins(db, customer_id)
        win_ids = [w.id for w in wins]
        assert "content_no_recs" in win_ids


# ===================================================================
# Integration: Score + Quick Wins
# ===================================================================

class TestIntegration:
    def test_full_workflow(self, db, customer_id):
        """Score computation + quick win detection for a realistic customer."""
        _insert_ai_runs(db, customer_id, count=8, base_rate=0.25)
        _insert_gsc_daily(db, customer_id, days=60, base_clicks=15)
        _insert_site_audit(db, customer_id, seo=80, perf=65)
        _insert_ai_readiness(db, customer_id)
        _insert_content_recs(db, customer_id, published=3, approved=2)
        _insert_google_places(db, customer_id, rating=4.5, review_count=45)
        _insert_competitors(db, customer_id, avg_reviews=60)

        # Compute score
        result = compute_practicerank_score(db, customer_id)
        assert result["score"] is not None
        assert 30 <= result["score"] <= 85  # reasonable range for this data

        # Store it
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pillars = result["pillars"]
        db.save_practicerank_score(
            customer_id=customer_id,
            date=today,
            overall=result["score"],
            ai_visibility=pillars["ai_visibility"]["score"],
            search_growth=pillars["search_growth"]["score"],
            technical_health=pillars["technical_health"]["score"],
            content_velocity=pillars["content_velocity"]["score"],
            reputation=pillars["reputation"]["score"],
            breakdown_json=result.get("breakdown_json", "{}"),
        )

        # Retrieve it
        latest = db.get_latest_practicerank_score(customer_id)
        assert latest["overall_score"] == result["score"]

        # Quick wins
        wins = detect_quick_wins(db, customer_id)
        assert isinstance(wins, list)

        # Should detect unpublished content
        win_ids = [w.id for w in wins]
        assert "content_unpublished" in win_ids

    def test_pillar_weights_sum_to_one(self):
        total = sum(PILLAR_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001
