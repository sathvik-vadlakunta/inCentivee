"""Tests for publishers/webflow_content.py — CMS content publishing."""

from __future__ import annotations

import httpx
import respx

from geo_agent.db import CustomerDB
from geo_agent.publishers.webflow import WebflowPublisher
from geo_agent.publishers.webflow_content import (
    WebflowContentPublisher,
    slugify,
    CMS_PUBLISHABLE_TYPES,
)


SITE_ID = "site_test123"
CUSTOMER_ID = "hilltop-dental"
COLLECTION_ID = "col_blog_abc"
FAQ_COLLECTION_ID = "col_faq_xyz"


def _make_db(tmp_path) -> CustomerDB:
    """Create an in-memory DB with test data."""
    db = CustomerDB(db_path=str(tmp_path / "test.db"))
    db.conn.execute(
        """INSERT INTO customers (id, name, domain, webflow_site_id)
        VALUES (?, ?, ?, ?)""",
        (CUSTOMER_ID, "Hilltop Dental", "hilltopdental.com", SITE_ID),
    )
    db.conn.commit()
    return db


def _make_rec(rec_id="rec-001", rec_type="blog_post", status="approved", **kwargs) -> dict:
    """Create a sample content recommendation dict."""
    rec = {
        "id": rec_id,
        "customer_id": CUSTOMER_ID,
        "rec_type": rec_type,
        "target_page": "",
        "title": "5 Tips for Better Dental Hygiene",
        "description": "A comprehensive guide to dental hygiene for families.",
        "html_snippet": "<p>Brush twice daily for two minutes...</p>",
        "priority": 2,
        "category": "hygiene",
        "status": status,
        "ai_impact_reason": "Targets high-volume keyword",
    }
    rec.update(kwargs)
    return rec


def _insert_rec(db: CustomerDB, rec: dict) -> None:
    db.add_content_recommendation(rec)
    # If status isn't pending, update it
    if rec["status"] != "pending":
        db.update_content_recommendation_status(rec["id"], rec["status"])


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("What's the Cost? (2024)") == "whats-the-cost-2024"

    def test_multiple_spaces(self):
        assert slugify("  multiple   spaces  ") == "multiple-spaces"

    def test_truncation(self):
        long_title = "a" * 100
        assert len(slugify(long_title)) == 80


class TestEnsureCollection:
    @respx.mock
    def test_uses_db_cache(self, tmp_path):
        db = _make_db(tmp_path)
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.ensure_collection("blog_posts")
        assert result == COLLECTION_ID
        pub.close()
        db.close()

    @respx.mock
    def test_finds_existing_on_webflow(self, tmp_path):
        db = _make_db(tmp_path)

        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}/collections").mock(
            return_value=httpx.Response(200, json={
                "collections": [{"id": COLLECTION_ID, "displayName": "Blog Posts", "slug": "blog-posts"}]
            })
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.ensure_collection("blog_posts")
        assert result == COLLECTION_ID
        # Should be cached now
        cached = db.get_webflow_collection(CUSTOMER_ID, "blog_posts")
        assert cached["webflow_collection_id"] == COLLECTION_ID
        pub.close()
        db.close()

    @respx.mock
    def test_creates_when_missing(self, tmp_path):
        db = _make_db(tmp_path)

        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}/collections").mock(
            return_value=httpx.Response(200, json={"collections": []})
        )
        respx.post(f"https://api.webflow.com/v2/sites/{SITE_ID}/collections").mock(
            return_value=httpx.Response(200, json={"id": "new_col_123", "displayName": "Blog Posts"})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.ensure_collection("blog_posts")
        assert result == "new_col_123"
        pub.close()
        db.close()

    @respx.mock
    def test_handles_api_failure(self, tmp_path):
        db = _make_db(tmp_path)

        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}/collections").mock(
            return_value=httpx.Response(200, json={"collections": []})
        )
        respx.post(f"https://api.webflow.com/v2/sites/{SITE_ID}/collections").mock(
            return_value=httpx.Response(500, json={"error": "Internal error"})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.ensure_collection("blog_posts")
        assert result is None
        pub.close()
        db.close()


class TestMapRecommendation:
    def test_blog_post_mapping(self, tmp_path):
        db = _make_db(tmp_path)
        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        rec = _make_rec()
        col_type, fields = content_pub.map_recommendation_to_fields(rec)

        assert col_type == "blog_posts"
        assert fields["name"] == rec["title"]
        assert fields["slug"] == "5-tips-for-better-dental-hygiene"
        assert fields["post-body"] == rec["html_snippet"]
        assert fields["author"] == "PracticeRank"
        assert fields["category"] == "hygiene"
        assert "meta-description" in fields
        pub.close()
        db.close()

    def test_faq_mapping(self, tmp_path):
        db = _make_db(tmp_path)
        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        rec = _make_rec(rec_type="faq_update", title="How much do implants cost?")
        col_type, fields = content_pub.map_recommendation_to_fields(rec)

        assert col_type == "faqs"
        assert fields["name"] == "How much do implants cost?"
        assert fields["answer"] == rec["html_snippet"]
        assert fields["page-category"] == "hygiene"
        pub.close()
        db.close()

    def test_unsupported_type(self, tmp_path):
        db = _make_db(tmp_path)
        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        rec = _make_rec(rec_type="expert_quote")
        col_type, fields = content_pub.map_recommendation_to_fields(rec)

        assert col_type is None
        assert fields == {}
        pub.close()
        db.close()


class TestPublishRecommendation:
    @respx.mock
    def test_creates_item_successfully(self, tmp_path):
        db = _make_db(tmp_path)
        rec = _make_rec()
        _insert_rec(db, rec)
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "item_new_001", "fieldData": {}})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("rec-001")
        assert result["ok"] is True
        assert result["webflow_item_id"] == "item_new_001"

        # Check DB updated
        updated = db.get_content_recommendation("rec-001")
        assert updated["status"] == "published"
        assert updated["webflow_item_id"] == "item_new_001"
        assert updated["webflow_collection_id"] == COLLECTION_ID
        pub.close()
        db.close()

    @respx.mock
    def test_updates_existing_item(self, tmp_path):
        db = _make_db(tmp_path)
        rec = _make_rec(status="published")
        rec["webflow_item_id"] = "existing_item"
        rec["webflow_collection_id"] = COLLECTION_ID
        # Insert manually with webflow fields
        db.add_content_recommendation(rec)
        db.conn.execute(
            "UPDATE content_recommendations SET webflow_item_id = ?, webflow_collection_id = ?, status = 'published' WHERE id = ?",
            ("existing_item", COLLECTION_ID, rec["id"]),
        )
        db.conn.commit()
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.patch(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items/existing_item").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("rec-001")
        assert result["ok"] is True
        assert result["webflow_item_id"] == "existing_item"
        pub.close()
        db.close()

    def test_rejects_non_approved(self, tmp_path):
        db = _make_db(tmp_path)
        rec = _make_rec(status="pending")
        _insert_rec(db, rec)

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("rec-001")
        assert result["ok"] is False
        assert "approved" in result["error"]
        pub.close()
        db.close()

    def test_rejects_unsupported_type(self, tmp_path):
        db = _make_db(tmp_path)
        rec = _make_rec(rec_type="expert_quote")
        _insert_rec(db, rec)

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("rec-001")
        assert result["ok"] is False
        assert "not CMS-publishable" in result["error"]
        pub.close()
        db.close()

    @respx.mock
    def test_stores_error_on_failure(self, tmp_path):
        db = _make_db(tmp_path)
        rec = _make_rec()
        _insert_rec(db, rec)
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("rec-001")
        assert result["ok"] is False

        updated = db.get_content_recommendation("rec-001")
        assert updated["publish_error"] is not None
        pub.close()
        db.close()

    def test_not_found(self, tmp_path):
        db = _make_db(tmp_path)

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        result = content_pub.publish_recommendation("nonexistent")
        assert result["ok"] is False
        assert "not found" in result["error"]
        pub.close()
        db.close()


class TestPublishBatch:
    @respx.mock
    def test_publishes_multiple_and_publishes_site(self, tmp_path, monkeypatch):
        # Disable sleep for tests
        monkeypatch.setattr("geo_agent.publishers.webflow_content.time.sleep", lambda x: None)

        db = _make_db(tmp_path)
        rec1 = _make_rec(rec_id="rec-001")
        rec2 = _make_rec(rec_id="rec-002", title="Another Post")
        _insert_rec(db, rec1)
        _insert_rec(db, rec2)
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "item_batch", "fieldData": {}})
        )
        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}").mock(
            return_value=httpx.Response(200, json={"customDomains": [{"id": "dom1"}]})
        )
        respx.post(f"https://api.webflow.com/v2/sites/{SITE_ID}/publish").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        results = content_pub.publish_batch(["rec-001", "rec-002"])
        assert len(results) == 2
        assert all(r["ok"] for r in results)
        pub.close()
        db.close()

    @respx.mock
    def test_handles_partial_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("geo_agent.publishers.webflow_content.time.sleep", lambda x: None)

        db = _make_db(tmp_path)
        rec1 = _make_rec(rec_id="rec-001")
        rec2 = _make_rec(rec_id="rec-002", rec_type="expert_quote")  # unsupported
        _insert_rec(db, rec1)
        _insert_rec(db, rec2)
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "item_001", "fieldData": {}})
        )
        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}").mock(
            return_value=httpx.Response(200, json={"customDomains": []})
        )
        respx.post(f"https://api.webflow.com/v2/sites/{SITE_ID}/publish").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="key", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        results = content_pub.publish_batch(["rec-001", "rec-002"])
        assert results[0]["ok"] is True
        assert results[1]["ok"] is False
        pub.close()
        db.close()
