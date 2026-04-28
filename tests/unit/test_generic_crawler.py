"""Tests for the generic HTTP crawler."""

from __future__ import annotations

import pytest

from geo_agent.crawler import GenericCrawler, _guess_category, _clean_html, get_crawler


class TestCleanHtml:
    def test_strips_scripts(self):
        html = '<p>Hello</p><script>alert("x")</script><p>World</p>'
        assert "alert" not in _clean_html(html)
        assert "Hello" in _clean_html(html)
        assert "World" in _clean_html(html)

    def test_strips_styles(self):
        html = "<style>.foo { color: red; }</style><p>Content</p>"
        assert "color" not in _clean_html(html)
        assert "Content" in _clean_html(html)

    def test_collapses_whitespace(self):
        html = "<p>Hello   \n\n   World</p>"
        result = _clean_html(html)
        assert "  " not in result


class TestGuessCategory:
    def test_service_pages(self):
        assert _guess_category("dental-implants", "Dental Implants") == "service"
        assert _guess_category("services/whitening", "Teeth Whitening") == "service"
        assert _guess_category("invisalign", "Invisalign Clear Aligners") == "service"

    def test_about_pages(self):
        assert _guess_category("about", "About Us") == "about"
        assert _guess_category("our-team", "Our Team") == "about"
        assert _guess_category("dr-smith", "Dr. Smith") == "about"

    def test_contact_pages(self):
        assert _guess_category("contact", "Contact Us") == "contact"
        assert _guess_category("location", "Our Location") == "contact"

    def test_home_page(self):
        assert _guess_category("", "Home") == "home"
        assert _guess_category("/", "Welcome") == "home"

    def test_generic_page(self):
        assert _guess_category("privacy-policy", "Privacy Policy") == "page"


class TestGetCrawler:
    def test_returns_webflow_crawler(self):
        crawler = get_crawler(
            platform="webflow",
            domain="test.com",
            api_key="test-key",
            site_id="site-123",
        )
        assert type(crawler).__name__ == "WebflowCrawler"
        crawler.close()

    def test_returns_generic_for_squarespace(self):
        crawler = get_crawler(platform="squarespace", domain="test.com")
        assert type(crawler).__name__ == "GenericCrawler"
        crawler.close()

    def test_returns_generic_for_wordpress(self):
        crawler = get_crawler(platform="wordpress", domain="test.com")
        assert type(crawler).__name__ == "GenericCrawler"
        crawler.close()

    def test_returns_generic_when_no_webflow_key(self):
        crawler = get_crawler(platform="webflow", domain="test.com")
        assert type(crawler).__name__ == "GenericCrawler"
        crawler.close()
