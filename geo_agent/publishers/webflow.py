"""Publish schema markup and content updates to Webflow sites via v2 API.

Webflow's Custom Code API requires OAuth tokens and uses a two-step process:
1. Register an inline script (hosted by Webflow as a JS file)
2. Apply the registered script to the site's head

Since Webflow forces all scripts to type="text/javascript", we wrap JSON-LD
in a JS snippet that dynamically creates <script type="application/ld+json">
elements at runtime.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

SCRIPT_ID = "practicerank_schema"


class WebflowPublisher:
    """Push schema markup and page updates to Webflow via v2 API."""

    BASE_URL = "https://api.webflow.com/v2"

    def __init__(self, api_key: str, site_id: str):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.site_id = site_id

    def _schema_to_js(self, schema_html: str) -> str:
        """Convert JSON-LD <script> blocks into JS that injects them at runtime."""
        blocks = re.findall(r"<script[^>]*>(.*?)</script>", schema_html, re.DOTALL)
        if not blocks:
            return schema_html  # Not JSON-LD, return as-is

        js_parts = []
        for block in blocks:
            js_parts.append(
                '(function(){var s=document.createElement("script");'
                's.type="application/ld+json";'
                f"s.textContent={json.dumps(block.strip())};"
                "document.head.appendChild(s);})()"
            )
        return ";".join(js_parts) + ";"

    def _get_current_version(self) -> str | None:
        """Get the current registered script version, if any."""
        try:
            resp = self.client.get(f"/sites/{self.site_id}/registered_scripts")
            if resp.status_code == 200:
                for script in resp.json().get("registeredScripts", []):
                    if script.get("id") == SCRIPT_ID:
                        return script["version"]
        except Exception:
            pass
        return None

    def _bump_version(self, current: str | None) -> str:
        """Increment patch version."""
        if not current:
            return "1.0.0"
        parts = current.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)

    def inject_schema_to_site(self, schema_html: str) -> bool:
        """Inject JSON-LD schema markup via Webflow Custom Code API.

        Registers an inline script that creates JSON-LD elements at runtime,
        then applies it to the site's head.
        """
        try:
            js_code = self._schema_to_js(schema_html)

            # Get current version and bump it
            current_version = self._get_current_version()
            new_version = self._bump_version(current_version)

            # Remove existing custom code from site (so we can re-register)
            self.client.delete(f"/sites/{self.site_id}/custom_code")

            # Register inline script
            resp = self.client.post(
                f"/sites/{self.site_id}/registered_scripts/inline",
                json={
                    "sourceCode": js_code,
                    "displayName": "PracticeRank Schema",
                    "version": new_version,
                    "canCopy": False,
                },
            )
            resp.raise_for_status()
            logger.info(f"Registered schema script v{new_version}")

            # Apply to site head
            resp = self.client.put(
                f"/sites/{self.site_id}/custom_code",
                json={
                    "scripts": [{
                        "id": SCRIPT_ID,
                        "location": "header",
                        "version": new_version,
                    }]
                },
            )
            resp.raise_for_status()
            logger.info("Schema script applied to site head")
            return True
        except Exception as e:
            logger.error(f"Failed to inject schema: {e}")
            return False

    def publish_site(self) -> bool:
        """Publish all staged changes on the Webflow site."""
        try:
            # Get domain IDs (required by v2 publish endpoint)
            resp = self.client.get(f"/sites/{self.site_id}")
            resp.raise_for_status()
            site = resp.json()
            domain_ids = [d["id"] for d in site.get("customDomains", [])]

            resp = self.client.post(
                f"/sites/{self.site_id}/publish",
                json={
                    "customDomains": domain_ids,
                    "publishToWebflowSubdomain": True,
                },
            )
            resp.raise_for_status()
            logger.info("Webflow site published successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to publish site: {e}")
            return False

    # --- CMS Collection Management ---

    def list_collections(self) -> list[dict]:
        """List all CMS collections on the site."""
        try:
            resp = self.client.get(f"/sites/{self.site_id}/collections")
            resp.raise_for_status()
            return resp.json().get("collections", [])
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def get_collection(self, collection_id: str) -> dict | None:
        """Get collection details including fields."""
        try:
            resp = self.client.get(f"/collections/{collection_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get collection {collection_id}: {e}")
            return None

    def find_collection(self, display_name: str) -> dict | None:
        """Find a collection by display name (case-insensitive)."""
        for col in self.list_collections():
            if col.get("displayName", "").lower() == display_name.lower():
                return col
        return None

    def create_collection(self, display_name: str, slug: str) -> dict | None:
        """Create a new CMS collection."""
        try:
            resp = self.client.post(
                f"/sites/{self.site_id}/collections",
                json={"displayName": display_name, "singularName": display_name, "slug": slug},
            )
            resp.raise_for_status()
            collection = resp.json()
            logger.info(f"Created collection: {display_name} ({collection.get('id', '')})")
            return collection
        except Exception as e:
            logger.error(f"Failed to create collection {display_name}: {e}")
            return None

    def list_collection_items(self, collection_id: str) -> list[dict]:
        """List all items in a collection."""
        items = []
        offset = 0
        while True:
            try:
                resp = self.client.get(
                    f"/collections/{collection_id}/items",
                    params={"offset": offset, "limit": 100},
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("items", [])
                items.extend(batch)
                if len(batch) < 100:
                    break
                offset += 100
            except Exception as e:
                logger.error(f"Failed to list collection items: {e}")
                break
        return items

    def create_collection_item(self, collection_id: str, fields: dict, publish: bool = False) -> dict | None:
        """Create a new item in a CMS collection."""
        try:
            payload = {"fieldData": fields}
            resp = self.client.post(
                f"/collections/{collection_id}/items",
                json=payload,
                params={"live": "true"} if publish else {},
            )
            resp.raise_for_status()
            item = resp.json()
            logger.info(f"Created collection item: {fields.get('name', fields.get('slug', 'unknown'))}")
            return item
        except Exception as e:
            logger.error(f"Failed to create collection item: {e}")
            return None

    def update_collection_item(self, collection_id: str, item_id: str, fields: dict, publish: bool = False) -> bool:
        """Update an existing CMS collection item."""
        try:
            payload = {"fieldData": fields}
            resp = self.client.patch(
                f"/collections/{collection_id}/items/{item_id}",
                json=payload,
                params={"live": "true"} if publish else {},
            )
            resp.raise_for_status()
            logger.info(f"Updated collection item: {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update collection item {item_id}: {e}")
            return False

    def delete_collection_item(self, collection_id: str, item_id: str) -> bool:
        """Delete a CMS collection item."""
        try:
            resp = self.client.delete(f"/collections/{collection_id}/items/{item_id}")
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection item {item_id}: {e}")
            return False

    # --- Page Content ---

    def list_pages(self) -> list[dict]:
        """List all pages on the site."""
        pages = []
        offset = 0
        while True:
            try:
                resp = self.client.get(
                    f"/sites/{self.site_id}/pages",
                    params={"offset": offset, "limit": 100},
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("pages", [])
                pages.extend(batch)
                if len(batch) < 100:
                    break
                offset += 100
            except Exception as e:
                logger.error(f"Failed to list pages: {e}")
                break
        return pages

    def update_page_seo(self, page_id: str, title: str | None = None,
                        description: str | None = None) -> bool:
        """Update a page's SEO title and meta description."""
        try:
            body: dict = {}
            if title:
                body["seo"] = body.get("seo", {})
                body["seo"]["title"] = title
            if description:
                body["seo"] = body.get("seo", {})
                body["seo"]["description"] = description
            if not body:
                return True
            resp = self.client.put(f"/pages/{page_id}", json=body)
            resp.raise_for_status()
            logger.info(f"Updated SEO for page {page_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update page SEO {page_id}: {e}")
            return False

    def close(self):
        self.client.close()
