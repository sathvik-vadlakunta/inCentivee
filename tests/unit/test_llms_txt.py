"""Tests for generators/llms_txt.py — H1, blockquote, categories, emergency flag."""

from __future__ import annotations

from geo_agent.generators.llms_txt import generate_llms_txt, generate_llms_full_txt


class TestGenerateLlmsTxt:
    def test_h1_with_location(self, sample_customer, sample_pages):
        result = generate_llms_txt(sample_customer, sample_pages)
        assert result.startswith("# Hilltop Family Dental — Dentist in Austin, TX")

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
        assert "## Services" in result
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
        assert "## Services" in result
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
