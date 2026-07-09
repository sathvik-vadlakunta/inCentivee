"""Tests for the daily status reconciliation (geo_agent/status_checker.py).

Live-site calls (run_site_audit, detect_live_status, _content_is_live,
_recent_data) are monkeypatched so the reconcile *logic* is tested in isolation.
"""

from __future__ import annotations

import pytest

from geo_agent import status_checker as sc
from geo_agent.db import CustomerDB


@pytest.fixture
def db(tmp_path):
    database = CustomerDB(db_path=str(tmp_path / "sc.db"))
    database.add_customer(id="c1", name="Test Dental", domain="test.com")
    yield database
    database.close()


def _open_issue(db, cid, category, title, severity="warning"):
    db.conn.execute(
        "INSERT INTO audit_issues (customer_id, category, severity, title, description, status) "
        "VALUES (?, ?, ?, ?, '', 'open')", (cid, category, severity, title))
    db.conn.commit()


def _rec(db, cid, rid, title, status="pending", target_page="/x"):
    db.add_content_recommendation({"id": rid, "customer_id": cid, "rec_type": "blog_post",
                                   "title": title, "target_page": target_page, "status": status})


def _fully_live(monkeypatch, audit_issues=None):
    monkeypatch.setattr(sc, "run_site_audit", lambda *a, **k: {"issues": audit_issues or []})
    monkeypatch.setattr(sc, "detect_live_status", lambda d: {
        "seo_schema_localbusiness": True, "seo_llms_txt": True, "seo_robots_txt": True})
    monkeypatch.setattr(sc, "_recent_data", lambda *a, **k: True)


def test_content_is_live_fuzzy_match(monkeypatch):
    # Page text reworded/reformatted vs the stored title — should still match on
    # word overlap (the "edited after we tracked it" case).
    page_html = ("<html><body><h1>Emergency Dental Care in Casper, WY</h1>"
                 "<p>Same-day emergency appointments for chipped teeth.</p></body></html>")
    monkeypatch.setattr(sc, "_fetch_words", lambda url, cache: sc._page_words(page_html))
    rec = {"id": "r1", "title": "Emergency Dental Care Casper", "target_page": "/emergency"}
    assert sc._content_is_live("example.com", rec, {}) is True


def test_content_is_live_no_match(monkeypatch):
    monkeypatch.setattr(sc, "_fetch_words", lambda url, cache: sc._page_words("<p>About our team</p>"))
    rec = {"id": "r1", "title": "Dental Implants Cost Guide", "target_page": "/x"}
    assert sc._content_is_live("example.com", rec, {}) is False


def test_content_is_live_cms_item_id_counts(monkeypatch):
    # If we already pushed it to the CMS, it's live without crawling.
    rec = {"id": "r1", "title": "x", "webflow_item_id": "abc123"}
    assert sc._content_is_live("example.com", rec, {}) is True


class _Resp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_detect_area_pages_live_matches_sitemap_slugs(monkeypatch):
    # Dev-built city pages in the sitemap are credited even though we never
    # published them. Multi-word cities ('Jersey City' -> /jersey-city-nj) match;
    # an unlisted city does not.
    sitemap = ("<urlset><url><loc>https://x.com/newark-nj</loc></url>"
               "<url><loc>https://x.com/jersey-city-nj/</loc></url>"
               "<url><loc>https://x.com/about</loc></url></urlset>")
    monkeypatch.setattr(sc.httpx, "get",
                        lambda url, **k: _Resp(200, sitemap) if "sitemap.xml" in url else _Resp(404))
    areas = ["Newark, NJ", "Jersey City, NJ", "Paramus, NJ"]
    assert sc.detect_area_pages_live("x.com", areas) == ["Newark, NJ", "Jersey City, NJ"]


def test_detect_live_status_ticks_sitemap_and_modern_robots(monkeypatch):
    # robots.txt naming GPTBot (not the legacy ChatGPT-User) still counts, and a
    # live sitemap.xml now ticks seo_xml_sitemap (previously never probed).
    def fake_get(url, **k):
        if url.endswith("/robots.txt"):
            return _Resp(200, "User-agent: GPTBot\nDisallow:\nSitemap: https://x.com/sitemap.xml")
        if url.endswith("/sitemap.xml"):
            return _Resp(200, "<urlset><url><loc>https://x.com/</loc></url></urlset>")
        return _Resp(404)
    monkeypatch.setattr(sc.httpx, "get", fake_get)
    det = sc.detect_live_status("x.com")
    assert det.get("seo_robots_txt") is True
    assert det.get("seo_xml_sitemap") is True


def test_resolves_fixed_audit_issues(db, monkeypatch):
    _open_issue(db, "c1", "Schema", "Missing FAQ schema")
    _open_issue(db, "c1", "Performance", "Slow LCP")
    # current audit only still reports the perf issue → FAQ should resolve
    monkeypatch.setattr(sc, "run_site_audit", lambda *a, **k: {
        "issues": [{"category": "Performance", "title": "Slow LCP", "severity": "warning"}]})
    monkeypatch.setattr(sc, "detect_live_status", lambda d: {})
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: False)
    monkeypatch.setattr(sc, "_recent_data", lambda *a, **k: False)

    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert [i["title"] for i in r["issues_fixed"]] == ["Missing FAQ schema"]
    assert len(db.get_audit_issues("c1", status="open")) == 1  # perf still open


def test_dry_run_writes_nothing(db, monkeypatch):
    _open_issue(db, "c1", "Schema", "Missing FAQ schema")
    monkeypatch.setattr(sc, "run_site_audit", lambda *a, **k: {"issues": []})
    monkeypatch.setattr(sc, "detect_live_status", lambda d: {"seo_schema_faq": True})
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: True)
    monkeypatch.setattr(sc, "_recent_data", lambda *a, **k: True)
    _rec(db, "c1", "r1", "My Post")

    r = sc.reconcile_customer(db, "c1", dry_run=True)
    assert r["issues_fixed"] and r["todos_ticked"] and r["content_published"]
    # …but nothing actually changed
    assert len(db.get_audit_issues("c1", status="open")) == 1
    assert db.get_checklist("c1").get("seo_schema_faq") in (None, False)
    assert db.get_content_recommendations("c1", status="published") == []


def test_marks_live_content_published(db, monkeypatch):
    _rec(db, "c1", "r1", "Live Post")
    _rec(db, "c1", "r2", "Not Live Post")
    monkeypatch.setattr(sc, "run_site_audit", lambda *a, **k: {"issues": []})
    monkeypatch.setattr(sc, "detect_live_status", lambda d: {})
    monkeypatch.setattr(sc, "_recent_data", lambda *a, **k: False)
    monkeypatch.setattr(sc, "_content_is_live", lambda dom, rec, *a: rec["id"] == "r1")

    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert [c["id"] for c in r["content_published"]] == ["r1"]
    pub = {x["id"] for x in db.get_content_recommendations("c1", status="published")}
    assert pub == {"r1"}


def test_auto_advances_when_fully_live(db, monkeypatch):
    db.set_onboarding_step("c1", "review")  # status defaults to 'onboarding'
    _rec(db, "c1", "r1", "Post", status="published")  # 1/1 published → ratio 1.0
    _fully_live(monkeypatch)
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: False)

    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert r["transition"] == {"from": "onboarding/review", "to": "active/monitoring"}
    c = db.get_customer("c1")
    assert c["status"] == "active" and c["onboarding_step"] == "monitoring"


def test_pending_content_does_not_block_advance(db, monkeypatch):
    # draft/pending recs are an idea backlog and must NOT block going live.
    db.set_onboarding_step("c1", "review")
    _rec(db, "c1", "r1", "Idea", status="pending")
    _fully_live(monkeypatch)
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: False)
    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert r["transition"]["to"] == "active/monitoring"


def test_approved_unpublished_content_blocks_advance(db, monkeypatch):
    # work we committed to (approved) but isn't live yet DOES block.
    db.set_onboarding_step("c1", "review")
    _rec(db, "c1", "r1", "Committed Page", status="approved")
    _fully_live(monkeypatch)
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: False)
    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert r["transition"] is None
    assert "approved_content_published" in r["advance_blockers"]
    assert db.get_customer("c1")["status"] == "onboarding"


def test_regression_flags_attention(db, monkeypatch):
    db.set_customer_status("c1", "active")
    db.set_onboarding_step("c1", "monitoring")
    # schema/llms now missing → should flag attention
    monkeypatch.setattr(sc, "run_site_audit", lambda *a, **k: {"issues": []})
    monkeypatch.setattr(sc, "detect_live_status", lambda d: {})
    monkeypatch.setattr(sc, "_content_is_live", lambda *a, **k: False)
    monkeypatch.setattr(sc, "_recent_data", lambda *a, **k: True)

    r = sc.reconcile_customer(db, "c1", dry_run=False)
    assert r["transition"] == {"from": "active/monitoring", "to": "active/attention"}
    c = db.get_customer("c1")
    assert c["status"] == "active" and c["onboarding_step"] == "attention"
    assert any(a["alert_type"] == "regression" for a in db.get_alerts("c1"))
