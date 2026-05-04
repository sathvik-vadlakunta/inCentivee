"""Integration tests for content recommendation → Webflow publish flow.

Uses real SQLite (in tmp_path) with mocked Webflow API via respx.
"""

from __future__ import annotations

import httpx
import respx

from geo_agent.db import CustomerDB
from geo_agent.publishers.webflow import WebflowPublisher
from geo_agent.publishers.webflow_content import WebflowContentPublisher


SITE_ID = "site_integration"
CUSTOMER_ID = "test-practice"
COLLECTION_ID = "col_blog_int"
FAQ_COLLECTION_ID = "col_faq_int"


def _setup_db(tmp_path) -> CustomerDB:
    db = CustomerDB(db_path=str(tmp_path / "integration.db"))
    db.conn.execute(
        "INSERT INTO customers (id, name, domain, webflow_site_id) VALUES (?, ?, ?, ?)",
        (CUSTOMER_ID, "Test Practice", "testpractice.com", SITE_ID),
    )
    db.conn.commit()
    return db


class TestFullPublishFlow:
    @respx.mock
    def test_generate_approve_publish(self, tmp_path, monkeypatch):
        monkeypatch.setattr("geo_agent.publishers.webflow_content.time.sleep", lambda x: None)
        db = _setup_db(tmp_path)

        # 1. Generate rec (simulate)
        rec_id = db.add_content_recommendation({
            "id": "int-rec-001",
            "customer_id": CUSTOMER_ID,
            "rec_type": "blog_post",
            "title": "Top 10 Dental Tips",
            "description": "Helpful tips for patients.",
            "html_snippet": "<h2>Tip 1</h2><p>Brush twice daily.</p>",
            "priority": 1,
            "category": "hygiene",
        })

        # 2. Approve
        db.update_content_recommendation_status(rec_id, "approved")
        rec = db.get_content_recommendation(rec_id)
        assert rec["status"] == "approved"

        # 3. Publish to Webflow
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "wf_item_001"})
        )

        pub = WebflowPublisher(api_key="token", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)
        result = content_pub.publish_recommendation(rec_id)

        assert result["ok"] is True
        assert result["webflow_item_id"] == "wf_item_001"

        # 4. Verify DB state
        final = db.get_content_recommendation(rec_id)
        assert final["status"] == "published"
        assert final["webflow_item_id"] == "wf_item_001"
        assert final["webflow_collection_id"] == COLLECTION_ID
        assert final["published_at"] is not None
        assert final["publish_error"] is None

        pub.close()
        db.close()

    @respx.mock
    def test_publish_then_update(self, tmp_path, monkeypatch):
        monkeypatch.setattr("geo_agent.publishers.webflow_content.time.sleep", lambda x: None)
        db = _setup_db(tmp_path)

        rec_id = db.add_content_recommendation({
            "id": "int-rec-002",
            "customer_id": CUSTOMER_ID,
            "rec_type": "blog_post",
            "title": "Original Title",
            "html_snippet": "<p>Original content</p>",
        })
        db.update_content_recommendation_status(rec_id, "approved")
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")

        # First publish
        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "wf_item_002"})
        )

        pub = WebflowPublisher(api_key="token", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)
        result = content_pub.publish_recommendation(rec_id)
        assert result["ok"] is True

        # Now re-publish (update) — item already has webflow_item_id
        respx.patch(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items/wf_item_002").mock(
            return_value=httpx.Response(200, json={})
        )

        result2 = content_pub.publish_recommendation(rec_id)
        assert result2["ok"] is True
        assert result2["webflow_item_id"] == "wf_item_002"

        pub.close()
        db.close()

    @respx.mock
    def test_batch_publish_mixed_types(self, tmp_path, monkeypatch):
        monkeypatch.setattr("geo_agent.publishers.webflow_content.time.sleep", lambda x: None)
        db = _setup_db(tmp_path)

        # Blog post
        db.add_content_recommendation({
            "id": "int-batch-blog",
            "customer_id": CUSTOMER_ID,
            "rec_type": "blog_post",
            "title": "Blog About Veneers",
            "html_snippet": "<p>Veneers are great.</p>",
        })
        db.update_content_recommendation_status("int-batch-blog", "approved")

        # FAQ
        db.add_content_recommendation({
            "id": "int-batch-faq",
            "customer_id": CUSTOMER_ID,
            "rec_type": "faq_update",
            "title": "How long do veneers last?",
            "html_snippet": "<p>10-15 years with proper care.</p>",
        })
        db.update_content_recommendation_status("int-batch-faq", "approved")

        # Setup collections
        db.save_webflow_collection(CUSTOMER_ID, "blog_posts", COLLECTION_ID, "Blog Posts")
        db.save_webflow_collection(CUSTOMER_ID, "faqs", FAQ_COLLECTION_ID, "FAQs")

        respx.post(f"https://api.webflow.com/v2/collections/{COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "wf_blog_item"})
        )
        respx.post(f"https://api.webflow.com/v2/collections/{FAQ_COLLECTION_ID}/items").mock(
            return_value=httpx.Response(200, json={"id": "wf_faq_item"})
        )
        respx.get(f"https://api.webflow.com/v2/sites/{SITE_ID}").mock(
            return_value=httpx.Response(200, json={"customDomains": [{"id": "d1"}]})
        )
        respx.post(f"https://api.webflow.com/v2/sites/{SITE_ID}/publish").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="token", site_id=SITE_ID)
        content_pub = WebflowContentPublisher(pub, db, CUSTOMER_ID)

        results = content_pub.publish_batch(["int-batch-blog", "int-batch-faq"])
        assert len(results) == 2
        assert results[0]["ok"] is True
        assert results[1]["ok"] is True

        blog = db.get_content_recommendation("int-batch-blog")
        faq = db.get_content_recommendation("int-batch-faq")
        assert blog["webflow_item_id"] == "wf_blog_item"
        assert faq["webflow_item_id"] == "wf_faq_item"

        pub.close()
        db.close()
