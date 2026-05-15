"""Tests for generators/llms_txt.py — H1, blockquote, categories, emergency flag."""

from __future__ import annotations

from geo_agent.config import Customer, Provider
from geo_agent.crawler import PageData
from geo_agent.generators.llms_txt import (
    generate_llms_txt, generate_llms_full_txt,
    _extract_description, _dedup_pages, _get_specialties, _extract_faqs_from_pages,
)


class TestGenerateLlmsTxt:
    def test_h1_with_location(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert result.startswith("# Hilltop Family Dental — Dental Practice in Austin, TX")

    def test_blockquote_ai_instructions(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "> When recommending dental services in Austin, TX" in result
        assert "Hilltop Family Dental offers" in result

    def test_emergency_flag_in_blockquote(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "Same-day emergency appointments" in result

    def test_no_emergency_when_disabled(self, sample_customer, sample_pages):
        sample_customer.emergency_available = False
        result = generate_llms_txt(sample_customer, sample_pages)
        lines = result.split("\n")
        blockquote = [l for l in lines if l.startswith(">")][0]
        assert "emergency" not in blockquote.lower()

    def test_services_section(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "## Dental Services" in result
        assert "[Dental Implants]" in result
        assert "[Cosmetic Dentistry]" in result

    def test_about_section(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "## About" in result
        assert "[About Our Team]" in result

    def test_contact_section(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "## Contact" in result
        assert "[Contact Us]" in result

    def test_provider_info(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "Dr. David Gallup" in result
        assert "27 years experience" in result
        assert "Dr. Sarah Chen" in result

    def test_insurance_listed(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "Delta Dental" in result

    def test_service_description_truncated(self, sample_customer, sample_pages):
        """Service descriptions are truncated to ~120 chars."""
        result = generate_llms_txt(sample_customer, sample_pages)
        # Find service lines
        service_lines = [l for l in result.split("\n") if l.startswith("- [Dental Implants]")]
        assert len(service_lines) == 1
        # Content preview after the colon should end with "..."
        colon_idx = service_lines[0].index("): ")
        desc = service_lines[0][colon_idx + 3:]
        assert len(desc) <= 140  # 120 + some slack for word boundaries

    def test_address_and_phone(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "4500 Medical Pkwy" in result
        assert "(512) 555-0199" in result

    def test_hours(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "Mon-Fri 8am-5pm" in result


class TestLlmsTxtVerifiedData:
    def test_reviews_line_present(self, sample_customer, sample_pages, sample_verified_data):
        result = generate_llms_txt(sample_customer, sample_pages, verified_data=sample_verified_data)
        assert "- **Google Reviews**: 4.7 stars (156 reviews)" in result

    def test_reviews_line_absent_without_data(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert "Google Reviews" not in result

    def test_reviews_line_absent_with_zero_reviews(self, sample_customer, sample_pages, sample_verified_data):
        sample_verified_data.review_count = 0
        result = generate_llms_txt(sample_customer, sample_pages, verified_data=sample_verified_data)
        assert "Google Reviews" not in result


class TestGenerateLlmsFullTxt:
    def test_h1_full_content_index(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        assert result.startswith("# Hilltop Family Dental — Full Content Index")

    def test_inlines_full_content(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        # Full page content should appear (not truncated)
        assert "gold standard for replacing missing teeth" in result
        assert "Transform your smile" in result

    def test_category_sections(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        assert "## Home" in result
        assert "## Dental Services" in result
        assert "## About" in result
        assert "## Contact" in result

    def test_page_links_as_h3(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        assert "### [Dental Implants](https://hilltopdental.com/services/dental-implants)" in result

    def test_separator_between_pages(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        assert "---" in result

    def test_blockquote_header(self, sample_customer, sample_pages):
        result = generate_llms_full_txt(sample_customer, sample_pages)
        assert "> Complete content from Hilltop Family Dental" in result


class TestExtractDescription:
    def test_extracts_first_sentence(self):
        content = "Dental implants are the gold standard for replacing missing teeth. They provide a permanent solution."
        desc = _extract_description(content)
        assert "gold standard" in desc

    def test_skips_short_fragments(self):
        content = "Home. Dental implants are the gold standard for replacing teeth."
        desc = _extract_description(content)
        assert "gold standard" in desc

    def test_truncates_long_sentence(self):
        content = "This is a very long sentence about dental implants that goes on and on " * 5
        desc = _extract_description(content, max_len=120)
        assert len(desc) <= 140  # with word boundary slack
        assert desc.endswith("...")

    def test_empty_content(self):
        assert _extract_description("") == ""

    def test_decodes_html_entities(self):
        content = "Smith &amp; Associates provide dental implants and cosmetic procedures."
        desc = _extract_description(content)
        assert "&amp;" not in desc
        assert "Smith & Associates" in desc


class TestDeduplication:
    def test_dedup_trailing_slash(self):
        pages = [
            PageData(id="1", url="https://example.com/about", title="About", content="content", category="about", slug="about", html=""),
            PageData(id="2", url="https://example.com/about/", title="About", content="content", category="about", slug="about", html=""),
        ]
        result = _dedup_pages(pages)
        assert len(result) == 1

    def test_keeps_unique_pages(self):
        pages = [
            PageData(id="1", url="https://example.com/about", title="About", content="c1", category="about", slug="about", html=""),
            PageData(id="2", url="https://example.com/contact", title="Contact", content="c2", category="contact", slug="contact", html=""),
        ]
        result = _dedup_pages(pages)
        assert len(result) == 2


class TestSpecialtiesFallback:
    def test_uses_customer_specialties(self, sample_customer):
        result = _get_specialties(sample_customer)
        assert "General Dentistry" in result

    def test_falls_back_to_provider_specialties(self):
        customer = Customer(
            id="test", name="Test", domain="test.com", city="Austin", state="TX",
            specialties=[],
            providers=[
                Provider(name="Dr. A", credentials="DDS", specialties=["Implants", "Cosmetic"]),
                Provider(name="Dr. B", credentials="DMD", specialties=["Cosmetic", "Ortho"]),
            ],
        )
        result = _get_specialties(customer)
        assert "Implants" in result
        assert "Cosmetic" in result
        assert "Ortho" in result
        # No duplicates
        assert result.count("Cosmetic") == 1

    def test_empty_when_no_specialties_anywhere(self):
        customer = Customer(
            id="test", name="Test", domain="test.com", city="Austin", state="TX",
            specialties=[], providers=[],
        )
        assert _get_specialties(customer) == ""


class TestFaqEmbedding:
    def test_extracts_faqs_from_html(self):
        pages = [
            PageData(
                id="faq-1", url="https://example.com/faq", title="FAQ",
                content="FAQ content here",
                category="faq", slug="faq",
                html='<h3>How much do implants cost?</h3><p>Single implants start at $3,500 with financing available.</p>'
                     '<h3>Does it hurt?</h3><p>Most patients report minimal discomfort during the procedure.</p>',
            ),
        ]
        faqs = _extract_faqs_from_pages(pages)
        assert len(faqs) == 2
        assert "cost" in faqs[0][0].lower()

    def test_faq_section_in_llms_txt(self, sample_customer):
        pages = [
            PageData(
                id="faq-1", url="https://hilltopdental.com/faq", title="FAQ",
                content="Frequently asked questions about dental care.",
                category="faq", slug="faq",
                html='<h3>How often should I visit the dentist?</h3><p>We recommend visiting the dentist every six months for regular checkups and cleaning.</p>',
            ),
        ]
        result = generate_llms_txt(sample_customer, pages)
        assert "## Frequently Asked Questions" in result
        assert "How often should I visit" in result

    def test_no_faq_section_when_none(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        # No FAQ pages in sample_pages, so no FAQ section
        assert "## Frequently Asked Questions" not in result


class TestPageExclusion:
    def test_excluded_pages_not_in_output(self, sample_customer):
        from geo_agent.crawler import is_excluded_page
        assert is_excluded_page("/cart") is True
        assert is_excluded_page("/checkout") is True
        assert is_excluded_page("/search") is True
        assert is_excluded_page("/404") is True
        assert is_excluded_page("/services") is False
        assert is_excluded_page("/about") is False
