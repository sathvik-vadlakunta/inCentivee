"""Host llms.txt and robots.txt via Cloudflare Workers.

Webflow can't serve raw .txt files at arbitrary root paths, so we use
a Cloudflare Worker to intercept requests for /llms.txt, /llms-full.txt,
and /robots.txt and serve the generated content.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


# Worker script that serves our generated files from KV storage
WORKER_SCRIPT = """\
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Serve generated files from KV
    const served_paths = ['/llms.txt', '/llms-full.txt', '/robots.txt'];
    if (served_paths.includes(path)) {
      const key = path.slice(1); // remove leading /
      const content = await env.GEO_FILES.get(key);
      if (content) {
        return new Response(content, {
          headers: {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'public, max-age=86400',
            'X-Generated-By': 'DentalRank GEO Agent',
          },
        });
      }
    }

    // Pass through to origin for everything else
    return fetch(request);
  },
};
"""


class CloudflarePublisher:
    """Publish llms.txt and robots.txt via Cloudflare KV + Workers."""

    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, account_id: str, zone_id: str):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self.account_id = account_id
        self.zone_id = zone_id
        self.kv_namespace_id: str | None = None

    def ensure_kv_namespace(self, name: str = "GEO_FILES") -> str:
        """Create or get the KV namespace for storing generated files."""
        # List existing namespaces
        resp = self.client.get(
            f"/accounts/{self.account_id}/storage/kv/namespaces"
        )
        resp.raise_for_status()
        for ns in resp.json().get("result", []):
            if ns["title"] == name:
                self.kv_namespace_id = ns["id"]
                return ns["id"]

        # Create new namespace
        resp = self.client.post(
            f"/accounts/{self.account_id}/storage/kv/namespaces",
            json={"title": name},
        )
        resp.raise_for_status()
        self.kv_namespace_id = resp.json()["result"]["id"]
        logger.info(f"Created KV namespace: {name} ({self.kv_namespace_id})")
        return self.kv_namespace_id

    def upload_file(self, filename: str, content: str) -> bool:
        """Upload a file to KV storage."""
        if not self.kv_namespace_id:
            self.ensure_kv_namespace()

        try:
            resp = self.client.put(
                f"/accounts/{self.account_id}/storage/kv/namespaces/{self.kv_namespace_id}/values/{filename}",
                content=content.encode(),
                headers={
                    "Authorization": f"Bearer {self.client.headers['Authorization'].split(' ')[1]}",
                    "Content-Type": "text/plain",
                },
            )
            resp.raise_for_status()
            logger.info(f"Uploaded {filename} to Cloudflare KV")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")
            return False

    def publish_files(
        self,
        llms_txt: str,
        llms_full_txt: str,
        robots_txt: str,
    ) -> bool:
        """Upload all generated files to KV."""
        success = True
        success &= self.upload_file("llms.txt", llms_txt)
        success &= self.upload_file("llms-full.txt", llms_full_txt)
        success &= self.upload_file("robots.txt", robots_txt)
        return success

    def close(self):
        self.client.close()
