"""Tests for crawler.py — HTML cleaning, category guessing, WebflowCrawler."""

from __future__ import annotations

import httpx
import pytest
import respx

from geo_agent.crawler import PageData, WebflowCrawler, _clean_html, _guess_category


class TestCleanHtml:
    def test_strips_tags(self):
        assert _clean_html("<p>Hello</p>") == "Hello"

    def test_strips_scripts(self):
        html = '<script>alert("x")</script><p>Content</p>'
        assert "alert" not in _clean_html(html)
        assert "Content" in _clean_html(html)

    def test_strips_styles(self):
        html = "<style>.x{color:red}</style><p>Content</p>"
        assert "color" not in _clean_html(html)
        assert "Content" in _clean_html(html)

    def test_collapses_whitespace(self):
        html = "<p>Hello   \n\n   World</p>"
        assert _clean_html(html) == "Hello World"

    def test_empty_input(self):
        assert _clean_html("") == ""

    def test_nested_tags(self):
        html = "<div><ul><li>Item 1</li><li>Item 2</li></ul></div>"
        result = _clean_html(html)
        assert "Item 1" in result
        assert "Item 2" in result


class TestGuessCategory:
    @pytest.mark.parametrize("slug,title,expected", [
        ("services/dental-implants", "Dental Implants", "service"),
        ("services/cosmetic-dentistry", "Cosmetic Dentistry", "service"),
        ("invisalign", "Invisalign Treatment", "service"),
        ("teeth-whitening", "Whitening", "service"),
        ("root-canal", "Root Canal Therapy", "service"),
        ("emergency", "Emergency Dental", "service"),
        ("about", "About Us", "about"),
        ("our-team", "Meet the Team", "about"),
        ("dr-smith", "Dr. Smith", "about"),
        ("contact", "Contact Us", "contact"),
        ("schedule-appointment", "Schedule Appointment", "contact"),
        ("reviews", "Patient Reviews", "reviews"),
        ("testimonials", "Testimonials", "reviews"),
        ("blog", "Our Blog", "blog"),
        ("blog/post-1", "Article Title", "blog"),
        ("faq", "Frequently Asked Questions", "faq"),
        ("insurance", "Insurance Plans", "insurance"),
        ("financing", "Payment Options", "insurance"),
        ("new-patient", "New Patient Info", "patient_resources"),
        ("first-visit", "Your First Visit", "patient_resources"),
        ("", "Home", "home"),
        ("home", "Home", "home"),
        ("privacy-policy", "Privacy Policy", "page"),
    ])
    def test_category_detection(self, slug, title, expected):
        assert _guess_category(slug, title) == expected


class TestWebflowCrawler:
    @respx.mock
    def test_get_pages_basic(self):
        site_id = "site_test"
        api_key = "test-key"

        # Mock page listing
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
            return_value=httpx.Response(200, json={
                "pages": [
                    {"id": "p1", "slug": "about", "title": "About Us"},
                    {"id": "p2", "slug": "thin", "title": "Thin Page"},
                ]
            })
        )

        # Mock page details
        respx.get("https://api.webflow.com/v2/pages/p1").mock(
            return_value=httpx.Response(200, json={
                "body": "<h1>About Us</h1><p>We are a dental practice in Austin TX with a full team of experienced providers and staff.</p>",
            })
        )
        respx.get("https://api.webflow.com/v2/pages/p2").mock(
            return_value=httpx.Response(200, json={
                "body": "<p>Hi</p>",  # < 50 chars → should be skipped
            })
        )

        crawler = WebflowCrawler(api_key=api_key, site_id=site_id, domain="test.com")
        pages = crawler.get_pages()
        crawler.close()

        assert len(pages) == 1
        assert pages[0].id == "p1"
        assert pages[0].category == "about"
        assert "dental practice" in pages[0].content

    @respx.mock
    def test_pagination(self):
        site_id = "site_test"

        # First page — 100 results (triggers next page fetch)
        page1_items = [{"id": f"p{i}", "slug": f"page-{i}", "title": f"Page {i}"} for i in range(100)]
        respx.get(
            f"https://api.webflow.com/v2/sites/{site_id}/pages",
            params={"offset": "0", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json={"pages": page1_items}))

        # Second page — fewer than 100 (stops pagination)
        page2_items = [{"id": "p100", "slug": "page-100", "title": "Page 100"}]
        respx.get(
            f"https://api.webflow.com/v2/sites/{site_id}/pages",
            params={"offset": "100", "limit": "100"},
        ).mock(return_value=httpx.Response(200, json={"pages": page2_items}))

        # Mock all page details with enough content
        for i in range(101):
            respx.get(f"https://api.webflow.com/v2/pages/p{i}").mock(
                return_value=httpx.Response(200, json={
                    "body": f"<p>This is page {i} with enough content to pass the 50 char minimum threshold for inclusion in results.</p>",
                })
            )

        crawler = WebflowCrawler(api_key="key", site_id=site_id, domain="test.com")
        pages = crawler.get_pages()
        crawler.close()

        assert len(pages) == 101

    @respx.mock
    def test_skips_thin_pages(self):
        site_id = "site_test"
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
            return_value=httpx.Response(200, json={
                "pages": [{"id": "p1", "slug": "thin", "title": "Thin"}]
            })
        )
        respx.get("https://api.webflow.com/v2/pages/p1").mock(
            return_value=httpx.Response(200, json={"body": "<p>Short</p>"})
        )

        crawler = WebflowCrawler(api_key="key", site_id=site_id, domain="test.com")
        pages = crawler.get_pages()
        crawler.close()

        assert len(pages) == 0

    @respx.mock
    def test_empty_body_skipped(self):
        site_id = "site_test"
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
            return_value=httpx.Response(200, json={
                "pages": [{"id": "p1", "slug": "empty", "title": "Empty"}]
            })
        )
        respx.get("https://api.webflow.com/v2/pages/p1").mock(
            return_value=httpx.Response(200, json={"body": ""})
        )

        crawler = WebflowCrawler(api_key="key", site_id=site_id, domain="test.com")
        pages = crawler.get_pages()
        crawler.close()

        assert len(pages) == 0
