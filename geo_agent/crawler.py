"""Crawl a customer's website and extract page content.

Supports:
- Webflow API crawler (for Webflow sites with API access)
- Generic HTTP crawler (for Squarespace, WordPress, or any site)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    id: str
    url: str
    title: str
    content: str  # cleaned text content
    category: str  # service, about, contact, blog, etc.
    slug: str
    html: str  # raw HTML for schema injection


def _clean_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to get plain text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _guess_category(slug: str, title: str) -> str:
    """Guess page category from slug and title for organizing llms.txt."""
    slug_lower = slug.lower()
    title_lower = title.lower()
    combined = f"{slug_lower} {title_lower}"

    if any(kw in combined for kw in ["service", "implant", "cosmetic", "whitening",
                                      "crown", "veneer", "invisalign", "orthodont",
                                      "cleaning", "filling", "root canal", "extraction",
                                      "denture", "bridge", "sedation", "emergency"]):
        return "service"
    if any(kw in combined for kw in ["about", "team", "doctor", "dr-", "provider", "staff"]):
        return "about"
    if any(kw in combined for kw in ["contact", "location", "direction", "appointment", "schedule"]):
        return "contact"
    if any(kw in combined for kw in ["review", "testimonial"]):
        return "reviews"
    if any(kw in combined for kw in ["blog", "article", "post", "news"]):
        return "blog"
    if any(kw in combined for kw in ["faq", "question"]):
        return "faq"
    if any(kw in combined for kw in ["insurance", "payment", "financing", "fee"]):
        return "insurance"
    if any(kw in combined for kw in ["patient", "new-patient", "first-visit", "form"]):
        return "patient_resources"
    if slug_lower in ("", "/", "index", "home"):
        return "home"
    return "page"


class WebflowCrawler:
    """Fetch all published pages from a Webflow site via API."""

    BASE_URL = "https://api.webflow.com/v2"

    def __init__(self, api_key: str, site_id: str, domain: str):
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        self.site_id = site_id
        self.domain = domain

    def get_pages(self) -> list[PageData]:
        """Fetch all pages from the Webflow site."""
        pages = []
        offset = 0
        limit = 100

        while True:
            resp = self.client.get(
                f"/sites/{self.site_id}/pages",
                params={"offset": offset, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("pages", []):
                page_id = page["id"]
                slug = page.get("slug", "")
                title = page.get("title", slug)

                # Fetch full page content
                detail = self._get_page_detail(page_id)
                html = detail.get("body", "") or ""
                content = _clean_html(html)

                if not content or len(content) < 50:
                    logger.debug(f"Skipping thin page: {slug}")
                    continue

                url = f"https://{self.domain}/{slug}" if slug else f"https://{self.domain}/"
                category = _guess_category(slug, title)

                pages.append(PageData(
                    id=page_id,
                    url=url,
                    title=title,
                    content=content,
                    category=category,
                    slug=slug,
                    html=html,
                ))

            # Pagination
            if len(data.get("pages", [])) < limit:
                break
            offset += limit

        logger.info(f"Crawled {len(pages)} pages from {self.domain}")
        return pages

    def _get_page_detail(self, page_id: str) -> dict:
        """Get detailed page content including body HTML."""
        resp = self.client.get(f"/pages/{page_id}")
        resp.raise_for_status()
        return resp.json()

    def get_site_custom_code(self) -> str:
        """Get site-level custom code (for schema injection)."""
        resp = self.client.get(f"/sites/{self.site_id}/custom_code")
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        data = resp.json()
        return data.get("headCode", "") or ""

    def close(self):
        self.client.close()


# Common dental site paths to crawl
COMMON_SLUGS = [
    "/", "/about", "/about-us", "/our-team", "/team", "/doctors",
    "/services", "/our-services", "/dental-services",
    "/contact", "/contact-us", "/location", "/locations",
    "/insurance", "/financing", "/payment",
    "/new-patients", "/patient-info", "/patient-resources", "/first-visit",
    "/faq", "/reviews", "/testimonials",
    "/blog", "/news",
    "/emergency", "/emergency-dentist",
    # Common service pages
    "/dental-implants", "/implants",
    "/cosmetic-dentistry", "/cosmetic",
    "/teeth-whitening", "/whitening",
    "/invisalign", "/orthodontics", "/braces",
    "/veneers", "/porcelain-veneers",
    "/crowns", "/dental-crowns", "/bridges",
    "/root-canal", "/root-canal-therapy",
    "/sedation-dentistry", "/sedation",
    "/dentures",
    "/cleanings", "/preventive-care",
    "/services/dental-implants", "/services/cosmetic-dentistry",
    "/services/teeth-whitening", "/services/invisalign",
]


class GenericCrawler:
    """Crawl any website via HTTP to extract page content.

    Works with Squarespace, WordPress, static sites, etc.
    Scrapes common dental site paths and follows internal links.
    """

    def __init__(self, domain: str, extra_slugs: list[str] | None = None):
        self.domain = domain.removeprefix("www.")
        self.base_url = f"https://{domain}"
        self.client = httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "PracticeRank-Crawler/1.0"},
        )
        self.extra_slugs = extra_slugs or []
        self._visited: set[str] = set()

    def get_pages(self) -> list[PageData]:
        """Crawl the site and return extracted pages."""
        pages = []
        slugs_to_try = list(COMMON_SLUGS) + self.extra_slugs

        for slug in slugs_to_try:
            url = f"{self.base_url}{slug}"
            if url in self._visited:
                continue
            self._visited.add(url)

            page = self._fetch_page(url, slug)
            if page:
                pages.append(page)

        # Also discover links from the homepage
        homepage_links = self._discover_internal_links(self.base_url)
        for link_url in homepage_links:
            if link_url in self._visited:
                continue
            self._visited.add(link_url)
            parsed = urlparse(link_url)
            slug = parsed.path
            page = self._fetch_page(link_url, slug)
            if page:
                pages.append(page)

        logger.info(f"Generic crawler: {len(pages)} pages from {self.domain}")
        return pages

    def _fetch_page(self, url: str, slug: str) -> PageData | None:
        """Fetch and parse a single page."""
        try:
            resp = self.client.get(url)
            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            html = resp.text
        except Exception:
            return None

        content = _clean_html(html)
        if not content or len(content) < 50:
            return None

        # Extract title from HTML
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = _clean_html(title_match.group(1)).strip() if title_match else slug.strip("/").replace("-", " ").title()

        # Normalize slug
        slug = slug.rstrip("/") or "/"
        category = _guess_category(slug, title)

        # Generate a stable page ID from the URL
        page_id = f"generic-{slug.strip('/').replace('/', '-') or 'home'}"

        return PageData(
            id=page_id,
            url=url,
            title=title,
            content=content,
            category=category,
            slug=slug.lstrip("/"),
            html=html,
        )

    def _discover_internal_links(self, url: str) -> list[str]:
        """Extract internal links from a page's HTML."""
        try:
            resp = self.client.get(url)
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception:
            return []

        links = []
        for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
            href = match.group(1)

            # Skip anchors, javascript, mailto, tel
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Resolve relative URLs
            full_url = urljoin(url, href)
            parsed = urlparse(full_url)

            # Only follow links on the same domain
            link_domain = parsed.hostname or ""
            if link_domain.removeprefix("www.") != self.domain:
                continue

            # Skip non-HTML resources
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in (".pdf", ".jpg", ".png", ".gif", ".css", ".js", ".svg", ".ico")):
                continue

            # Normalize
            clean_url = f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
            if clean_url not in links:
                links.append(clean_url)

        return links[:50]  # Cap to avoid runaway crawling

    def close(self):
        self.client.close()


def get_crawler(platform: str, domain: str, **kwargs):
    """Factory function to get the right crawler based on platform.

    Args:
        platform: "webflow", "squarespace", "wordpress", or "generic"
        domain: Site domain
        **kwargs: Additional args (api_key, site_id for Webflow)

    Returns:
        A crawler instance with get_pages() and close() methods.
    """
    if platform == "webflow" and kwargs.get("api_key") and kwargs.get("site_id"):
        return WebflowCrawler(
            api_key=kwargs["api_key"],
            site_id=kwargs["site_id"],
            domain=domain,
        )
    return GenericCrawler(domain=domain)
