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

    def close(self):
        self.client.close()
