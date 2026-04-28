"""Squarespace publishing support.

Squarespace doesn't have a content API like Webflow, so publishing works differently:
- Schema markup -> Code Injection via Squarespace API (Settings > Advanced > Code Injection)
- llms.txt -> Cloudflare Worker in front of the domain (already built in cloudflare.py)
- Content pages -> Manual via Squarespace editor (VA or client)
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class SquarespacePublisher:
    """Publish schema markup to Squarespace via API.

    Squarespace API v1 (legacy) supports code injection via:
    PUT /api/settings with siteHeaderCode field.

    Note: For most Squarespace sites, schema injection may need to go through
    the Squarespace panel manually (VA step) or via their newer GraphQL API.
    This class provides the programmatic path where API access is available.
    """

    BASE_URL = "https://api.squarespace.com/1.0"

    def __init__(self, api_key: str, site_id: str = ""):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "PracticeRank/1.0",
            },
            timeout=30.0,
        )
        self.site_id = site_id

    def inject_schema_to_site(self, schema_html: str) -> bool:
        """Inject JSON-LD schema markup via Squarespace code injection.

        Uses the Squarespace settings API to update the site header code.
        """
        try:
            # Get existing header code
            resp = self.client.get("/settings")
            if resp.status_code == 200:
                settings = resp.json()
                existing_head = settings.get("siteHeaderCode", "") or ""
            else:
                existing_head = ""

            # Remove any previous PracticeRank schema blocks
            if "<!-- PracticeRank Schema Start -->" in existing_head:
                before = existing_head.split("<!-- PracticeRank Schema Start -->")[0]
                after_parts = existing_head.split("<!-- PracticeRank Schema End -->")
                after = after_parts[1] if len(after_parts) > 1 else ""
                existing_head = before + after

            # Add new schema block
            new_head = (
                existing_head.strip()
                + "\n<!-- PracticeRank Schema Start -->\n"
                + schema_html
                + "\n<!-- PracticeRank Schema End -->"
            )

            # Update site header code
            resp = self.client.put(
                "/settings",
                json={"siteHeaderCode": new_head.strip()},
            )
            resp.raise_for_status()
            logger.info("Schema markup injected into Squarespace header code")
            return True
        except Exception as e:
            logger.error(f"Failed to inject schema to Squarespace: {e}")
            return False

    def get_site_info(self) -> dict:
        """Get basic site information."""
        try:
            resp = self.client.get("/settings")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get Squarespace site info: {e}")
            return {}

    def close(self):
        self.client.close()
