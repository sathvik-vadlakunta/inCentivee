"""save_site_audit must not pile up duplicate open issues across runs."""
from __future__ import annotations
import pytest
from geo_agent.db import CustomerDB


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "a.db"))
    d.add_customer(id="c1", name="Test", domain="t.com")
    yield d
    d.close()


def test_repeated_audits_dont_duplicate_issues(db):
    issue = {"category": "schema", "severity": "warning",
             "title": "No FAQ schema markup", "description": "x"}
    for day in ("2026-06-13", "2026-06-14", "2026-06-15"):
        db.save_site_audit("c1", day, {"performance": 50}, [issue])
    openi = db.get_audit_issues("c1", status="open")
    assert len(openi) == 1, f"expected 1 deduped issue, got {len(openi)}"


def test_distinct_issues_still_recorded(db):
    db.save_site_audit("c1", "2026-06-15", {}, [
        {"category": "schema", "severity": "warning", "title": "No FAQ schema", "description": ""},
        {"category": "seo", "severity": "critical", "title": "Missing title", "description": ""},
    ])
    assert len(db.get_audit_issues("c1", status="open")) == 2
