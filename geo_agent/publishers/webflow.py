"""Publish schema markup and content updates to Webflow sites."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class WebflowPublisher:
    """Push schema markup and page updates to Webflow via API."""

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

    def inject_schema_to_site(self, schema_html: str) -> bool:
        """Inject JSON-LD schema markup into site-level head code.

        This puts the Dentist + Provider schemas in the <head> of every page.
        """
        try:
            # Get existing custom code
            resp = self.client.get(f"/sites/{self.site_id}/custom_code")
            existing_head = ""
            if resp.status_code == 200:
                existing_head = resp.json().get("headCode", "") or ""

            # Remove any previous DentalRank schema blocks
            if "<!-- DentalRank Schema Start -->" in existing_head:
                before = existing_head.split("<!-- DentalRank Schema Start -->")[0]
                after_parts = existing_head.split("<!-- DentalRank Schema End -->")
                after = after_parts[1] if len(after_parts) > 1 else ""
                existing_head = before + after

            # Add new schema block
            new_head = (
                existing_head.strip()
                + "\n<!-- DentalRank Schema Start -->\n"
                + schema_html
                + "\n<!-- DentalRank Schema End -->"
            )

            # Update site custom code
            resp = self.client.put(
                f"/sites/{self.site_id}/custom_code",
                json={"headCode": new_head.strip()},
            )
            resp.raise_for_status()
            logger.info("Schema markup injected into site head code")
            return True
        except Exception as e:
            logger.error(f"Failed to inject schema: {e}")
            return False

    def publish_site(self) -> bool:
        """Publish all staged changes on the Webflow site."""
        try:
            resp = self.client.post(f"/sites/{self.site_id}/publish")
            resp.raise_for_status()
            logger.info("Webflow site published successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to publish site: {e}")
            return False

    def close(self):
        self.client.close()
