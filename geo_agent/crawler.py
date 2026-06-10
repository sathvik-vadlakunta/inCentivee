"""Crawl a customer's website and extract page content.

Supports:
- Webflow API crawler (for Webflow sites with API access)
- Generic HTTP crawler (for Squarespace, WordPress, or any site)
"""

from __future__ import annotations

import html as html_lib
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
    # Strip semantic nav/header/footer blocks before converting to text —
    # WordPress themes (DentalQore, etc.) use proper <nav>, <header>, <footer>
    # elements that contain massive menu trees and repeated contact info
    text = re.sub(r"<nav[^>]*>.*?</nav>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<header[^>]*>.*?</header>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<footer[^>]*>.*?</footer>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Pages that should never appear in llms.txt
EXCLUDED_SLUGS = {
    "/cart", "/checkout", "/search", "/404", "/password",
    "/login", "/register", "/signup", "/account", "/thank-you",
    "/confirmation", "/unsubscribe", "/privacy-policy", "/terms",
    "/terms-of-service", "/cookie-policy",
}


def is_excluded_page(slug: str) -> bool:
    """Check if a page slug should be excluded from llms.txt output."""
    normalized = "/" + slug.strip("/").lower() if slug.strip("/") else "/"
    return normalized in EXCLUDED_SLUGS


def clean_page_content(raw_text: str) -> str:
    """Strip nav/header/footer boilerplate from page text content.

    The raw text from _clean_html still contains navigation menus, footer links,
    copyright notices, phone/email in headers, etc. This strips common boilerplate
    so that _extract_description gets clean body text.
    """
    text = raw_text

    # Remove phone numbers at the start of text (common in Webflow header bars)
    text = re.sub(r"^\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\s*", "", text).strip()

    # Remove email addresses at the start
    text = re.sub(r"^\s*\S+@\S+\.\S+\s*", "", text).strip()

    # Remove common nav patterns (e.g. "Home Services About Contact Blog")
    # These appear as space-separated menu items at the start
    text = re.sub(
        r"^(Home\s+)?(What We \w+\s+)?(Services?\s+)?(Products?\s+)?(About\s+)?"
        r"(Contact\s+)?(Blog\s+)?(FAQ\s+)?(Reviews?\s+)?"
        r"(Patient\s+)?(Insurance\s+)?(Locations?\s+)?(Schedule\s+)?(New Patients?\s+)?",
        "", text, count=1, flags=re.IGNORECASE
    ).strip()

    # Strip Webflow-style nav blocks. Webflow renders nav as plain text:
    # "<Title> <phone> <email> <nav links> <nav links again (mobile)> <actual content>"
    # Detect by finding repeated nav marker words like "FAQ Blog" or "Contact More"
    nav_end_markers = [
        r"(?:FAQ|Blog|Testimonials?|Reviews?)\s+(?:FAQ|Blog|Testimonials?|Reviews?|Home)",
        r"More\s+Virtual\s+",
        r"(?:Contact|Blog|FAQ)\s+More\s+",
    ]
    best_pos = 0
    for marker in nav_end_markers:
        # Find the LAST occurrence (the second/mobile nav ends here)
        for m in re.finditer(marker, text[:1000], re.IGNORECASE):
            pos = m.end()
            if pos > best_pos:
                best_pos = pos
    if best_pos > 50:
        remainder = text[best_pos:].strip()
        # Strip any trailing nav word remnants at the start
        remainder = re.sub(
            r"^(Home|Blog|FAQ|Testimonials?|Reviews?|Contact|Virtual|More)\s+",
            "", remainder, count=1, flags=re.IGNORECASE
        ).strip()
        if len(remainder) > 100:
            text = remainder

    # Strip WordPress/DentalQore-style nav blocks:
    # "Home About Us Meet Our Doctors/Dentists Meet Our Team Our Services ... Request Appointment"
    # These survive _clean_html when the theme uses <div> instead of <nav>
    text = re.sub(
        r"Home About Us Meet Our (?:Doctors|Dentists|Team).*?(?:Request Appointment|Pay Now|Call Us)\s*",
        " ", text
    ).strip()

    # Remove footer boilerplate patterns
    footer_patterns = [
        r"©\s*\d{4}.*$",  # © 2024 Practice Name...
        r"Copyright\s+\d{4}.*$",
        r"All\s+[Rr]ights\s+[Rr]eserved.*$",
        r"Privacy\s+Policy\s+Terms.*$",
        r"Powered\s+by\s+\w+.*$",
        r"Website\s+by\s+\w+.*$",
        r"Follow\s+[Uu]s\s+(on\s+)?(Facebook|Instagram|Twitter|LinkedIn|YouTube).*$",
        # WordPress footer with contact/hours block
        r"Contact\s+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\s+\d+.*?(?:Sunday\s+Closed|©).*$",
    ]
    for pattern in footer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    # Decode HTML entities
    text = html_lib.unescape(text)

    return text


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication (strip trailing slash, fragments, query, www)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{host}{path}"


def _guess_category(slug: str, title: str, service_keywords: list[str] | None = None) -> str:
    """Guess page category from slug and title for organizing llms.txt.

    Args:
        slug: URL slug (e.g. "/dental-implants")
        title: Page title
        service_keywords: Optional list of keywords that indicate service pages.
            If not provided, uses a broad default set.
    """
    slug_lower = slug.lower()
    title_lower = title.lower()
    combined = f"{slug_lower} {title_lower}"

    # Check specific page types BEFORE service keywords — service keywords can be
    # broad for some industries (e.g. "gold" for precious metals) and would
    # incorrectly capture FAQ, blog, testimonials, etc.
    if any(kw in combined for kw in ["about", "team", "doctor", "dr-", "provider", "staff",
                                      "career"]):
        return "about"
    if any(kw in combined for kw in ["faq", "question", "frequently asked"]):
        return "faq"
    if any(kw in combined for kw in ["blog", "article", "post", "news", "insight", "guide"]):
        return "blog"
    if any(kw in combined for kw in ["contact", "location", "direction", "appointment", "schedule"]):
        return "contact"
    if any(kw in combined for kw in ["review", "testimonial"]):
        return "reviews"
    if any(kw in combined for kw in ["insurance", "payment", "financing", "fee"]):
        return "insurance"
    if any(kw in combined for kw in ["patient", "new-patient", "first-visit", "form"]):
        return "patient_resources"

    # Now check service keywords — these come last because some industries have
    # broad keywords that overlap with page titles
    svc_kw = service_keywords or [
        "service", "product", "solution", "platform", "feature",
        "integration", "api", "pricing", "demo", "case-study", "partner",
    ]
    if any(kw in combined for kw in svc_kw):
        return "service"
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
                title = html_lib.unescape(page.get("title", slug))

                # Skip excluded pages
                if is_excluded_page(slug):
                    logger.debug(f"Skipping excluded page: {slug}")
                    continue

                # Fetch full page content
                detail = self._get_page_detail(page_id)
                html = detail.get("body", "") or ""
                raw_content = _clean_html(html)

                if not raw_content or len(raw_content) < 50:
                    logger.debug(f"Skipping thin page: {slug}")
                    continue

                content = clean_page_content(raw_content)
                if not content or len(content) < 50:
                    logger.debug(f"Skipping thin page after cleaning: {slug}")
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


# Universal paths that apply to any business website
COMMON_SLUGS = [
    "/", "/about", "/about-us", "/team", "/our-team",
    "/services", "/our-services",
    "/contact", "/contact-us",
    "/pricing", "/faq",
    "/blog", "/news",
    "/careers",
    "/products", "/resources", "/support",
    "/partners", "/integrations",
    "/demo", "/case-studies",
    "/testimonials", "/reviews",
]

# Dental-specific paths (only probed for practice sites)
DENTAL_SLUGS = [
    "/doctors", "/dental-services",
    "/location", "/locations",
    "/insurance", "/financing", "/payment",
    "/new-patients", "/patient-info", "/patient-resources", "/first-visit",
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
    Scrapes common paths and follows internal links.
    """

    def __init__(self, domain: str, extra_slugs: list[str] | None = None,
                 business_type: str = "practice",
                 service_keywords: list[str] | None = None):
        self.domain = domain.removeprefix("www.")
        self.base_url = f"https://{domain}"
        self.client = httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "PracticeRank-Crawler/1.0"},
        )
        self.extra_slugs = extra_slugs or []
        self.business_type = business_type
        self.service_keywords = service_keywords
        self._visited: set[str] = set()

    def get_pages(self) -> list[PageData]:
        """Crawl the site and return extracted pages."""
        pages = []
        slugs_to_try = list(COMMON_SLUGS)
        if self.business_type == "practice":
            slugs_to_try += DENTAL_SLUGS
        slugs_to_try += self.extra_slugs

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
        # Skip excluded pages
        if is_excluded_page(slug):
            return None

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

        raw_content = _clean_html(html)
        if not raw_content or len(raw_content) < 50:
            return None

        # Clean boilerplate from content
        content = clean_page_content(raw_content)
        if not content or len(content) < 50:
            return None

        # Extract title from HTML and decode entities
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = _clean_html(title_match.group(1)).strip() if title_match else slug.strip("/").replace("-", " ").title()
        title = html_lib.unescape(title)
        # Strip stray brackets from titles — breaks markdown link syntax in llms.txt
        title = title.replace("[", "").replace("]", "")

        # Normalize slug
        slug = slug.rstrip("/") or "/"
        category = _guess_category(slug, title, service_keywords=self.service_keywords)

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
        **kwargs: Additional args (api_key, site_id for Webflow;
                  business_type, service_keywords for GenericCrawler)

    Returns:
        A crawler instance with get_pages() and close() methods.
    """
    if platform == "webflow" and kwargs.get("api_key") and kwargs.get("site_id"):
        return WebflowCrawler(
            api_key=kwargs["api_key"],
            site_id=kwargs["site_id"],
            domain=domain,
        )
    return GenericCrawler(
        domain=domain,
        business_type=kwargs.get("business_type", "practice"),
        service_keywords=kwargs.get("service_keywords"),
    )
