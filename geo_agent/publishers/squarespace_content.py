"""Publish content recommendations to Squarespace as drafts via Playwright.

All content is created as DRAFTS — a human must still click Publish in Squarespace admin.
Uses browser automation since Squarespace doesn't have a public CMS write API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DRAFT_PUBLISHABLE_TYPES = {"blog_post", "new_page", "faq_update"}


class SquarespaceContentPublisher:
    """Push content drafts to Squarespace via Playwright browser automation."""

    def __init__(self, db, customer_id: str, email: str, password_encrypted: str, site_url: str):
        self.db = db
        self.customer_id = customer_id
        self.email = email
        self.password_encrypted = password_encrypted
        self.site_url = site_url.rstrip("/")
        self.browser = None
        self.page = None
        self._data_dir = Path(os.environ.get("DATA_DIR", "data")) / "customers" / customer_id

    def _decrypt_password(self) -> str:
        from cryptography.fernet import Fernet
        key = os.environ.get("PRACTICERANK_ENCRYPTION_KEY", "")
        if not key:
            raise RuntimeError("PRACTICERANK_ENCRYPTION_KEY not set")
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(self.password_encrypted.encode()).decode()

    async def _launch(self):
        """Launch headless Chromium browser."""
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=True)

        # Try loading saved session cookies
        session_file = self._data_dir / "squarespace_session.json"
        context_opts = {"viewport": {"width": 1280, "height": 900}}
        if session_file.exists():
            try:
                storage = json.loads(session_file.read_text())
                context_opts["storage_state"] = storage
            except Exception:
                pass

        self.context = await self.browser.new_context(**context_opts)
        self.page = await self.context.new_page()

    async def _save_session(self):
        """Save session cookies for reuse."""
        session_file = self._data_dir / "squarespace_session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        storage = await self.context.storage_state()
        session_file.write_text(json.dumps(storage))

    async def _login(self) -> bool:
        """Login to Squarespace admin."""
        try:
            await self.page.goto(f"{self.site_url}/config", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Check if already logged in
            if "/config" in self.page.url and "login" not in self.page.url:
                logger.info("Already logged in to Squarespace")
                return True

            # Fill login form
            password = self._decrypt_password()
            await self.page.fill('input[name="email"], input[type="email"]', self.email)
            await self.page.fill('input[name="password"], input[type="password"]', password)
            await self.page.click('button[type="submit"]')

            # Wait for navigation to /config
            await self.page.wait_for_url("**/config**", timeout=30000)
            await asyncio.sleep(2)

            await self._save_session()
            logger.info("Logged in to Squarespace successfully")
            return True
        except Exception as e:
            logger.error(f"Squarespace login failed: {e}")
            await self._screenshot_debug("login_failed")
            return False

    async def _ensure_logged_in(self):
        """Ensure we have an active session."""
        if not self.browser:
            await self._launch()
        if not self.page:
            self.page = await self.context.new_page()

        # Quick check if session is valid
        await self.page.goto(f"{self.site_url}/config", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)
        if "login" in self.page.url:
            success = await self._login()
            if not success:
                raise RuntimeError("Could not login to Squarespace")

    async def create_blog_draft(self, title: str, html_body: str, category: str = "",
                                meta_description: str = "") -> str:
        """Create a blog post draft. Returns the draft URL."""
        await self._ensure_logged_in()

        try:
            # Navigate to blog pages
            await self.page.goto(f"{self.site_url}/config/pages", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Find and click the Blog section
            blog_link = self.page.locator('text=Blog').first
            await blog_link.click()
            await asyncio.sleep(2)

            # Click the "+" button to add new post
            add_btn = self.page.locator('[data-test="blog-add-item"], button:has-text("+"), [aria-label="Add"]').first
            await add_btn.click()
            await asyncio.sleep(3)

            # Fill in the title
            title_field = self.page.locator('[data-test="blog-item-title"], .blog-item-title input, [placeholder*="title" i]').first
            await title_field.fill(title)
            await asyncio.sleep(1)

            # Add content via code block (for raw HTML)
            # Click into the content area
            content_area = self.page.locator('.sqs-editing-overlay, .content-editor, [contenteditable]').first
            await content_area.click()
            await asyncio.sleep(1)

            # Use the insert block menu to add a Code block
            # This approach uses keyboard shortcut or block inserter
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(0.5)

            # Try to find block inserter
            inserter = self.page.locator('[data-test="block-inserter"], .block-inserter-button, button:has-text("Add Block")').first
            if await inserter.is_visible():
                await inserter.click()
                await asyncio.sleep(1)
                code_option = self.page.locator('text=Code').first
                await code_option.click()
                await asyncio.sleep(1)
                # Paste HTML into code block
                code_textarea = self.page.locator('textarea, [contenteditable].code-block').first
                await code_textarea.fill(html_body)
            else:
                # Fallback: paste content directly
                await self.page.keyboard.type(title)

            await asyncio.sleep(1)

            # Open post settings for SEO
            settings_btn = self.page.locator('[data-test="blog-item-settings"], button:has-text("Settings"), .settings-icon').first
            if await settings_btn.is_visible():
                await settings_btn.click()
                await asyncio.sleep(1)

                if meta_description:
                    desc_field = self.page.locator('[name="description"], [placeholder*="description" i]').first
                    if await desc_field.is_visible():
                        await desc_field.fill(meta_description)

                # Close settings
                close_btn = self.page.locator('button:has-text("Save"), button:has-text("Done")').first
                if await close_btn.is_visible():
                    await close_btn.click()

            await asyncio.sleep(2)

            # Save as draft (don't publish)
            save_btn = self.page.locator('button:has-text("Save"), [data-test="save-button"]').first
            if await save_btn.is_visible():
                await save_btn.click()
                await asyncio.sleep(2)

            draft_url = self.page.url
            await self._save_session()
            logger.info(f"Created Squarespace blog draft: {title}")
            return draft_url

        except Exception as e:
            logger.error(f"Failed to create blog draft: {e}")
            await self._screenshot_debug(f"blog_draft_failed_{title[:20]}")
            raise

    async def publish_recommendation(self, rec_id: str) -> dict:
        """Push a single recommendation as a draft. Returns {ok, error, draft_url}."""
        rec = self.db.get_content_recommendation(rec_id)
        if not rec:
            return {"ok": False, "error": "Recommendation not found", "rec_id": rec_id}

        if rec["rec_type"] not in DRAFT_PUBLISHABLE_TYPES:
            return {"ok": False, "error": f"Type '{rec['rec_type']}' not publishable to Squarespace", "rec_id": rec_id}

        if rec["status"] != "approved":
            return {"ok": False, "error": f"Status is '{rec['status']}', must be 'approved'", "rec_id": rec_id}

        try:
            draft_url = await self.create_blog_draft(
                title=rec["title"],
                html_body=rec.get("html_snippet", ""),
                category=rec.get("category", ""),
                meta_description=rec.get("description", ""),
            )
            # Update DB
            self.db.set_recommendation_platform_ids(rec_id, "", draft_url)
            return {"ok": True, "draft_url": draft_url, "rec_id": rec_id}
        except Exception as e:
            error_msg = str(e)[:200]
            self.db.set_recommendation_publish_error(rec_id, error_msg)
            return {"ok": False, "error": error_msg, "rec_id": rec_id}

    async def publish_batch(self, rec_ids: list[str]) -> list[dict]:
        """Push multiple recommendations as drafts with rate limiting."""
        results = []
        for i, rec_id in enumerate(rec_ids):
            if i > 0:
                await asyncio.sleep(5)  # Rate limit between posts
            result = await self.publish_recommendation(rec_id)
            results.append(result)
        return results

    async def close(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if hasattr(self, '_pw') and self._pw:
            await self._pw.stop()
            self._pw = None

    async def _screenshot_debug(self, name: str):
        """Save a debug screenshot on failure."""
        try:
            debug_dir = self._data_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            await self.page.screenshot(path=str(debug_dir / f"{name}_{ts}.png"))
        except Exception:
            pass
