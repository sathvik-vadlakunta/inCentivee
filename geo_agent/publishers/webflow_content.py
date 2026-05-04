"""Publish content recommendations to Webflow CMS collections.

Maps approved content (blog posts, FAQs) to Webflow CMS items and pushes them live.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from geo_agent.db import CustomerDB
from geo_agent.publishers.webflow import WebflowPublisher

logger = logging.getLogger(__name__)

# Rec types that can be published to CMS collections
CMS_PUBLISHABLE_TYPES = {"blog_post", "new_page", "faq_update"}

# Collection type mapping
COLLECTION_SCHEMAS = {
    "blog_posts": {
        "display_name": "Blog Posts",
        "slug": "blog-posts",
    },
    "faqs": {
        "display_name": "FAQs",
        "slug": "faqs",
    },
}

REC_TYPE_TO_COLLECTION = {
    "blog_post": "blog_posts",
    "new_page": "blog_posts",
    "faq_update": "faqs",
}


def slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


class WebflowContentPublisher:
    """Publish content recommendations to Webflow CMS."""

    def __init__(self, publisher: WebflowPublisher, db: CustomerDB, customer_id: str):
        self.publisher = publisher
        self.db = db
        self.customer_id = customer_id

    def ensure_collection(self, collection_type: str) -> str | None:
        """Ensure the CMS collection exists, return its ID.

        Checks DB cache first, then Webflow API, creates if missing.
        """
        # Check DB cache
        cached = self.db.get_webflow_collection(self.customer_id, collection_type)
        if cached:
            return cached["webflow_collection_id"]

        schema = COLLECTION_SCHEMAS.get(collection_type)
        if not schema:
            logger.error(f"Unknown collection type: {collection_type}")
            return None

        # Check if collection exists on Webflow
        existing = self.publisher.find_collection(schema["display_name"])
        if existing:
            col_id = existing["id"]
            self.db.save_webflow_collection(
                self.customer_id, collection_type, col_id, schema["display_name"]
            )
            return col_id

        # Create collection
        created = self.publisher.create_collection(schema["display_name"], schema["slug"])
        if not created:
            return None

        col_id = created["id"]
        self.db.save_webflow_collection(
            self.customer_id, collection_type, col_id, schema["display_name"]
        )
        return col_id

    def map_recommendation_to_fields(self, rec: dict) -> tuple[str | None, dict]:
        """Map a recommendation to (collection_type, webflow_field_data).

        Returns (None, {}) for unsupported types.
        """
        rec_type = rec.get("rec_type", "")
        collection_type = REC_TYPE_TO_COLLECTION.get(rec_type)

        if not collection_type:
            return None, {}

        if collection_type == "blog_posts":
            return collection_type, {
                "name": rec["title"],
                "slug": slugify(rec["title"]),
                "post-body": rec.get("html_snippet", ""),
                "author": "PracticeRank",
                "category": rec.get("category", "general"),
                "published-on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "meta-description": rec.get("description", "")[:160],
            }
        elif collection_type == "faqs":
            return collection_type, {
                "name": rec["title"],
                "slug": slugify(rec["title"]),
                "answer": rec.get("html_snippet", ""),
                "page-category": rec.get("category", "general"),
                "sort-order": rec.get("priority", 3),
            }

        return None, {}

    def publish_recommendation(self, rec_id: str) -> dict:
        """Publish a single recommendation to Webflow CMS.

        Returns dict with keys: ok, error, webflow_item_id
        """
        rec = self.db.get_content_recommendation(rec_id)
        if not rec:
            return {"ok": False, "error": "Recommendation not found"}

        if rec["status"] not in ("approved", "published"):
            return {"ok": False, "error": f"Cannot publish rec with status '{rec['status']}'. Must be approved first."}

        if rec["rec_type"] not in CMS_PUBLISHABLE_TYPES:
            return {"ok": False, "error": f"Type '{rec['rec_type']}' is not CMS-publishable. Use manual publish."}

        collection_type, fields = self.map_recommendation_to_fields(rec)
        if not collection_type:
            return {"ok": False, "error": "Failed to map recommendation to CMS fields"}

        # Ensure collection exists
        collection_id = self.ensure_collection(collection_type)
        if not collection_id:
            error = "Failed to find or create Webflow collection"
            self.db.set_recommendation_publish_error(rec_id, error)
            return {"ok": False, "error": error}

        try:
            # Update existing item or create new
            if rec.get("webflow_item_id"):
                success = self.publisher.update_collection_item(
                    collection_id, rec["webflow_item_id"], fields, publish=True
                )
                if not success:
                    error = "Failed to update existing Webflow item"
                    self.db.set_recommendation_publish_error(rec_id, error)
                    return {"ok": False, "error": error}
                item_id = rec["webflow_item_id"]
            else:
                item = self.publisher.create_collection_item(
                    collection_id, fields, publish=True
                )
                if not item:
                    error = "Failed to create Webflow CMS item"
                    self.db.set_recommendation_publish_error(rec_id, error)
                    return {"ok": False, "error": error}
                item_id = item.get("id", item.get("_id", ""))

            # Update DB with success
            self.db.update_recommendation_webflow_ids(rec_id, item_id, collection_id)
            return {"ok": True, "webflow_item_id": item_id}

        except Exception as e:
            error = str(e)
            self.db.set_recommendation_publish_error(rec_id, error)
            return {"ok": False, "error": error}

    def publish_batch(self, rec_ids: list[str]) -> list[dict]:
        """Publish multiple recommendations, then publish the site once.

        Returns list of result dicts (one per rec_id).
        """
        results = []
        any_success = False

        for rec_id in rec_ids:
            result = self.publish_recommendation(rec_id)
            result["rec_id"] = rec_id
            results.append(result)
            if result["ok"]:
                any_success = True
            # Rate limit: 1s between API calls
            time.sleep(1)

        # Publish site once if any items were pushed
        if any_success:
            published = self.publisher.publish_site()
            if not published:
                for r in results:
                    if r["ok"]:
                        r["warning"] = "Item created but site publish failed"

        return results
