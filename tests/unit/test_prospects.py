"""Tests for the prospect / sales pipeline database operations."""

from __future__ import annotations

import json
import pytest

from geo_agent.db import CustomerDB


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = CustomerDB(db_path=db_path)
    yield database
    database.close()


@pytest.fixture
def sample_prospect(db):
    """Create a sample prospect and return its ID."""
    return db.upsert_prospect(
        prospect_id="smith-law",
        domain="smithlaw.com",
        name="Smith & Associates",
        email="info@smithlaw.com",
        contact_name="John Smith",
        phone="(555) 123-4567",
        vertical="legal",
        overall_score=45,
        grade="F",
    )


class TestProspectCRUD:
    def test_create_prospect(self, db, sample_prospect):
        assert sample_prospect == "smith-law"
        p = db.get_prospect("smith-law")
        assert p is not None
        assert p["name"] == "Smith & Associates"
        assert p["domain"] == "smithlaw.com"
        assert p["email"] == "info@smithlaw.com"
        assert p["vertical"] == "legal"
        assert p["stage"] == "new_lead"
        assert p["overall_score"] == 45
        assert p["grade"] == "F"

    def test_get_prospect_by_domain(self, db, sample_prospect):
        p = db.get_prospect_by_domain("smithlaw.com")
        assert p is not None
        assert p["id"] == "smith-law"

    def test_get_nonexistent_prospect(self, db):
        assert db.get_prospect("nonexistent") is None
        assert db.get_prospect_by_domain("nobody.com") is None

    def test_upsert_updates_existing(self, db, sample_prospect):
        result = db.upsert_prospect(
            prospect_id="smith-law-2",
            domain="smithlaw.com",
            name="Smith & Associates Updated",
            email="new@smithlaw.com",
            overall_score=60,
        )
        # Should return existing ID, not the new one
        assert result == "smith-law"
        p = db.get_prospect("smith-law")
        assert p["email"] == "new@smithlaw.com"
        assert p["overall_score"] == 60

    def test_upsert_ignores_invalid_columns(self, db, sample_prospect):
        """Ensure SQL injection via kwargs keys is impossible."""
        db.update_prospect(
            "smith-law",
            **{"notes": "legit", "evil_col; DROP TABLE prospects--": "bad"},
        )
        # Table should still exist and prospect should be fine
        p = db.get_prospect("smith-law")
        assert p is not None
        assert p["notes"] == "legit"

    def test_unique_domain_constraint(self, db, sample_prospect):
        """Second insert with same domain updates, doesn't create duplicate."""
        db.upsert_prospect("other-id", "smithlaw.com", "Other Name", overall_score=99)
        all_prospects = db.get_prospects_by_stage()
        domains = [p["domain"] for p in all_prospects]
        assert domains.count("smithlaw.com") == 1

    def test_update_prospect(self, db, sample_prospect):
        db.update_prospect("smith-law", notes="Called, left voicemail")
        p = db.get_prospect("smith-law")
        assert p["notes"] == "Called, left voicemail"

    def test_update_prospect_rejects_bad_columns(self, db, sample_prospect):
        result = db.update_prospect("smith-law", bad_column="evil")
        assert result is False


class TestProspectStages:
    def test_stage_change(self, db, sample_prospect):
        ok = db.update_prospect_stage("smith-law", "outreach_sent", created_by="jon")
        assert ok is True
        p = db.get_prospect("smith-law")
        assert p["stage"] == "outreach_sent"

    def test_stage_change_logs_activity(self, db, sample_prospect):
        db.update_prospect_stage("smith-law", "interested", created_by="ethan")
        activities = db.get_prospect_activities("smith-law")
        assert len(activities) == 1
        a = activities[0]
        assert a["activity_type"] == "stage_change"
        assert a["stage_from"] == "new_lead"
        assert a["stage_to"] == "interested"
        assert a["created_by"] == "ethan"

    def test_lost_with_reason(self, db, sample_prospect):
        db.update_prospect_stage("smith-law", "lost", lost_reason="Chose competitor")
        p = db.get_prospect("smith-law")
        assert p["stage"] == "lost"
        assert p["lost_reason"] == "Chose competitor"

    def test_stage_change_nonexistent(self, db):
        ok = db.update_prospect_stage("nonexistent", "interested")
        assert ok is False

    def test_multiple_stage_transitions(self, db, sample_prospect):
        db.update_prospect_stage("smith-law", "outreach_sent")
        db.update_prospect_stage("smith-law", "follow_up")
        db.update_prospect_stage("smith-law", "interested")
        activities = db.get_prospect_activities("smith-law")
        assert len(activities) == 3
        # Most recent first
        assert activities[0]["stage_to"] == "interested"
        assert activities[2]["stage_to"] == "outreach_sent"


class TestProspectGrouped:
    def test_grouped_empty(self, db):
        grouped = db.get_all_prospects_grouped()
        assert "new_lead" in grouped
        assert "lost" in grouped
        assert all(len(v) == 0 for v in grouped.values())

    def test_grouped_with_prospects(self, db):
        db.upsert_prospect("p1", "one.com", "One", vertical="dental")
        db.upsert_prospect("p2", "two.com", "Two", vertical="legal")
        db.update_prospect_stage("p2", "interested")
        grouped = db.get_all_prospects_grouped()
        assert len(grouped["new_lead"]) == 1
        assert len(grouped["interested"]) == 1

    def test_counts(self, db):
        db.upsert_prospect("p1", "one.com", "One")
        db.upsert_prospect("p2", "two.com", "Two")
        db.upsert_prospect("p3", "three.com", "Three")
        db.update_prospect_stage("p2", "outreach_sent")
        db.update_prospect_stage("p3", "outreach_sent")
        counts = db.get_prospect_counts()
        assert counts.get("new_lead") == 1
        assert counts.get("outreach_sent") == 2


class TestProspectActivities:
    def test_add_note(self, db, sample_prospect):
        aid = db.add_prospect_activity("smith-law", "note", body="Good conversation", created_by="jon")
        assert aid > 0
        activities = db.get_prospect_activities("smith-law")
        assert len(activities) == 1
        assert activities[0]["body"] == "Good conversation"
        assert activities[0]["activity_type"] == "note"

    def test_add_email_sent(self, db, sample_prospect):
        db.add_prospect_activity(
            "smith-law", "email_sent",
            subject="Your firm scores 35/100",
            body="Hi there, we ran an analysis...",
            created_by="ethan",
        )
        activities = db.get_prospect_activities("smith-law")
        assert activities[0]["subject"] == "Your firm scores 35/100"
        assert activities[0]["activity_type"] == "email_sent"

    def test_activity_limit(self, db, sample_prospect):
        for i in range(10):
            db.add_prospect_activity("smith-law", "note", body=f"Note {i}")
        activities = db.get_prospect_activities("smith-law", limit=5)
        assert len(activities) == 5

    def test_activity_ordering(self, db, sample_prospect):
        db.add_prospect_activity("smith-law", "note", body="First")
        db.add_prospect_activity("smith-law", "note", body="Second")
        activities = db.get_prospect_activities("smith-law")
        # Most recent first
        assert activities[0]["body"] == "Second"
        assert activities[1]["body"] == "First"


class TestProspectWithReportData:
    def test_prospect_with_report_json(self, db):
        report = {
            "categories": {
                "ai_readiness": {"score": 15, "status": "critical"},
                "reviews": {"score": 78, "count": 162, "rating": 4.9},
                "content": {"score": 40, "status": "needs work"},
            },
            "executive_summary": "Test summary",
        }
        db.upsert_prospect(
            "test-firm", "testfirm.com", "Test Firm",
            vertical="legal", overall_score=49, grade="F",
            report_data=json.dumps(report),
        )
        p = db.get_prospect("test-firm")
        data = json.loads(p["report_data"])
        assert data["categories"]["ai_readiness"]["score"] == 15
        assert data["categories"]["reviews"]["count"] == 162
