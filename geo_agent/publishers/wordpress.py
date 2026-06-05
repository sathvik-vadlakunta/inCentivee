"""Publish content, schema, and SEO files to WordPress via PracticeRank plugin REST API.

Requires the PracticeRank SEO plugin (v2.0+) installed on the WordPress site.
The plugin exposes /wp-json/practicerank/v1/* endpoints authenticated by API key.

Usage:
    publisher = WordPressPublisher(
        site_url="https://example.com",
        api_key="...",  # from WP Admin → Settings → PracticeRank
    )
    publisher.push_schema(global_schemas=[...], page_schemas={"services": [...]})
    publisher.push_content(title="...", content_html="...", category="Blog")
    publisher.push_files(llms_txt="...", robots_txt="...")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)


class WordPressPublisher:
    """Push schema, content, and SEO files to WordPress via PracticeRank plugin API."""

    def __init__(self, site_url: str, api_key: str):
        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/wp-json/practicerank/v1"
        self.client = httpx.Client(
            headers={
                "X-PracticeRank-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    # ── Health / Discovery ───────────────────────────────────────────────

    def health_check(self) -> dict | None:
        """Check if the plugin is installed and reachable."""
        try:
            resp = self.client.get(f"{self.api_base}/health")
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"WordPress connected: {data.get('site_name')} (WP {data.get('wp_version')})")
                return data
            logger.warning(f"Health check failed: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Cannot reach WordPress site: {e}")
            return None

    def get_site_info(self) -> dict | None:
        """Get site pages, posts, categories, and theme info."""
        try:
            resp = self.client.get(f"{self.api_base}/site-info")
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Site info failed: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Site info error: {e}")
            return None

    # ── Schema Markup ────────────────────────────────────────────────────

    def push_schema(
        self,
        global_schemas: list[dict] | None = None,
        page_schemas: dict[str, list[dict]] | None = None,
        faq_schemas: dict[str, dict] | None = None,
    ) -> dict | None:
        """Push JSON-LD schema markup to WordPress.

        Args:
            global_schemas: List of schema dicts injected on every page
                (LocalBusiness, Organization, AggregateRating).
            page_schemas: Dict of {page_slug: [schema_dicts]} for page-specific schemas
                (Service, MedicalProcedure).
            faq_schemas: Dict of {page_slug: faq_schema_dict} for FAQ schemas.
        """
        payload = {}
        if global_schemas:
            payload["global"] = global_schemas
        if page_schemas:
            payload["pages"] = page_schemas
        if faq_schemas:
            payload["faqs"] = faq_schemas

        if not payload:
            logger.warning("No schemas to push")
            return None

        try:
            resp = self.client.post(f"{self.api_base}/schema", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"Schema pushed: {result.get('updated', [])}")
                return result
            logger.error(f"Schema push failed: {resp.status_code} {resp.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"Schema push error: {e}")
            return None

    # ── Content Publishing ───────────────────────────────────────────────

    def push_content(
        self,
        title: str,
        content_html: str,
        content_type: str = "post",
        slug: str | None = None,
        excerpt: str = "",
        category: str = "",
        tags: list[str] | None = None,
        meta_description: str = "",
        author: str = "",
        featured_image_url: str = "",
        faq_schema: dict | None = None,
        page_schema: list[dict] | None = None,
        publish: bool = False,
    ) -> dict | None:
        """Push a blog post or page to WordPress.

        By default, content is created as a draft (controlled by plugin settings).
        Set publish=True to force immediate publishing.

        Returns dict with post_id, url, slug, publish_status on success.
        """
        payload = {
            "type": content_type,
            "title": title,
            "content": content_html,
        }
        if slug:
            payload["slug"] = slug
        if excerpt:
            payload["excerpt"] = excerpt
        if category:
            payload["category"] = category
        if tags:
            payload["tags"] = tags
        if meta_description:
            payload["meta_description"] = meta_description
        if author:
            payload["author"] = author
        if featured_image_url:
            payload["featured_image_url"] = featured_image_url
        if faq_schema:
            payload["faq_schema"] = faq_schema
        if page_schema:
            payload["page_schema"] = page_schema
        if publish:
            payload["publish"] = True

        try:
            resp = self.client.post(f"{self.api_base}/content", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(
                    f"Content pushed: {result.get('post_type')} '{title}' "
                    f"→ {result.get('url')} ({result.get('publish_status')})"
                )
                return result

            # Handle duplicate slug
            if resp.status_code == 409:
                data = resp.json()
                existing_id = data.get("data", {}).get("existing_id")
                if existing_id:
                    logger.info(f"Post already exists (ID {existing_id}), updating instead")
                    return self.update_content(
                        post_id=existing_id,
                        title=title,
                        content_html=content_html,
                        meta_description=meta_description,
                        category=category,
                        tags=tags,
                        faq_schema=faq_schema,
                        page_schema=page_schema,
                    )

            logger.error(f"Content push failed: {resp.status_code} {resp.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"Content push error: {e}")
            return None

    def update_content(
        self,
        post_id: int,
        title: str | None = None,
        content_html: str | None = None,
        excerpt: str | None = None,
        status: str | None = None,
        meta_description: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        faq_schema: dict | None = None,
        page_schema: list[dict] | None = None,
    ) -> dict | None:
        """Update an existing post or page."""
        payload = {}
        if title is not None:
            payload["title"] = title
        if content_html is not None:
            payload["content"] = content_html
        if excerpt is not None:
            payload["excerpt"] = excerpt
        if status is not None:
            payload["status"] = status
        if meta_description is not None:
            payload["meta_description"] = meta_description
        if category is not None:
            payload["category"] = category
        if tags is not None:
            payload["tags"] = tags
        if faq_schema is not None:
            payload["faq_schema"] = faq_schema
        if page_schema is not None:
            payload["page_schema"] = page_schema

        try:
            resp = self.client.put(f"{self.api_base}/content/{post_id}", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"Content updated: ID {post_id} → {result.get('url')}")
                return result
            logger.error(f"Content update failed: {resp.status_code} {resp.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"Content update error: {e}")
            return None

    # ── SEO Files ────────────────────────────────────────────────────────

    def push_files(
        self,
        llms_txt: str | None = None,
        llms_full_txt: str | None = None,
        robots_txt: str | None = None,
    ) -> dict | None:
        """Push llms.txt, llms-full.txt, and/or robots.txt to WordPress."""
        payload = {}
        if llms_txt is not None:
            payload["llms.txt"] = llms_txt
        if llms_full_txt is not None:
            payload["llms-full.txt"] = llms_full_txt
        if robots_txt is not None:
            payload["robots.txt"] = robots_txt

        if not payload:
            return None

        try:
            resp = self.client.post(f"{self.api_base}/files", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"Files pushed: {result.get('written', [])}")
                return result
            logger.error(f"File push failed: {resp.status_code} {resp.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"File push error: {e}")
            return None

    # ── Batch Content Publishing ─────────────────────────────────────────

    def publish_approved_content(self, db: CustomerDB, customer_id: str) -> list[dict]:
        """Publish all approved content recommendations for a customer.

        Reads from content_recommendations table, pushes to WordPress,
        and updates status to 'published' on success.

        Returns list of results.
        """
        recs = db.get_content_recommendations(customer_id, status="approved")
        if not recs:
            logger.info(f"No approved content to publish for {customer_id}")
            return []

        results = []
        for rec in recs:
            rec_type = rec.get("rec_type", "blog_post")

            # Map rec types to WordPress content types
            if rec_type in ("blog_post", "new_page"):
                wp_type = "post" if rec_type == "blog_post" else "page"
            elif rec_type == "faq_update":
                wp_type = "post"
            else:
                logger.info(f"Skipping non-publishable rec type: {rec_type}")
                continue

            content_html = rec.get("generated_content", "")
            if not content_html:
                logger.warning(f"Rec {rec['id']} has no generated content, skipping")
                continue

            # Build FAQ schema if the content has Q&A structure
            faq_schema = None
            if rec_type == "faq_update" and rec.get("faqs"):
                from geo_agent.generators.schema_markup import generate_faq_schema
                faq_schema = generate_faq_schema(rec["faqs"])

            result = self.push_content(
                title=rec.get("title", rec.get("rec_title", "Untitled")),
                content_html=content_html,
                content_type=wp_type,
                slug=rec.get("slug"),
                excerpt=rec.get("meta_description", "")[:160],
                category=rec.get("category", ""),
                tags=rec.get("tags", []),
                meta_description=rec.get("meta_description", ""),
                faq_schema=faq_schema,
            )

            if result and result.get("post_id"):
                # Mark as published in our DB
                db.update_content_recommendation(rec["id"], {
                    "status": "published",
                    "published_url": result.get("url", ""),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "wp_post_id": result["post_id"],
                })
                logger.info(f"Published: {rec.get('title', 'Untitled')} → {result.get('url')}")
            else:
                logger.error(f"Failed to publish rec {rec['id']}: {rec.get('title', 'Untitled')}")

            results.append({
                "rec_id": rec["id"],
                "title": rec.get("title", ""),
                "success": bool(result and result.get("post_id")),
                "result": result,
            })

        return results

    # ── Full Pipeline ────────────────────────────────────────────────────

    def full_sync(
        self,
        db: CustomerDB,
        customer_id: str,
        customer,
        llms_txt: str | None = None,
        llms_full_txt: str | None = None,
        robots_txt: str | None = None,
        global_schemas: list[dict] | None = None,
        page_schemas: dict[str, list[dict]] | None = None,
        faq_schemas: dict[str, dict] | None = None,
        publish_content: bool = True,
    ) -> dict:
        """Run full sync: schema + files + content.

        Returns summary of what was pushed.
        """
        summary = {"schema": None, "files": None, "content": []}

        # 1. Push schema
        if global_schemas or page_schemas or faq_schemas:
            summary["schema"] = self.push_schema(
                global_schemas=global_schemas,
                page_schemas=page_schemas,
                faq_schemas=faq_schemas,
            )

        # 2. Push SEO files
        if llms_txt or llms_full_txt or robots_txt:
            summary["files"] = self.push_files(
                llms_txt=llms_txt,
                llms_full_txt=llms_full_txt,
                robots_txt=robots_txt,
            )

        # 3. Publish approved content
        if publish_content:
            summary["content"] = self.publish_approved_content(db, customer_id)

        return summary

    def close(self):
        self.client.close()
