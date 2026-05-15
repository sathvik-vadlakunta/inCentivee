"""Tests for analyzer.py — JSON parsing, code-fence strip, error fallback."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from geo_agent.analyzer import analyze_and_recommend, grade_analysis
from geo_agent.google_places import VerifiedBusinessData


def _mock_response(text: str) -> MagicMock:
    """Build a mock Anthropic response with given text."""
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


class TestAnalyzeAndRecommend:
    @patch("geo_agent.analyzer.get_client")
    def test_parses_clean_json(self, mock_get_client, sample_customer, sample_pages, fake_analysis_response):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        result = analyze_and_recommend(sample_customer, sample_pages)

        assert "faq_entries" in result
        assert "content_gaps" in result
        assert "priority_actions" in result
        assert len(result["content_gaps"]) == 2

    @patch("geo_agent.analyzer.get_client")
    def test_strips_code_fences(self, mock_get_client, sample_customer, sample_pages, fake_analysis_response):
        fenced = f"```json\n{json.dumps(fake_analysis_response)}\n```"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(fenced)
        mock_get_client.return_value = mock_client

        result = analyze_and_recommend(sample_customer, sample_pages)

        assert "faq_entries" in result
        assert len(result["priority_actions"]) == 5

    @patch("geo_agent.analyzer.get_client")
    def test_invalid_json_returns_fallback(self, mock_get_client, sample_customer, sample_pages):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response("This is not JSON at all")
        mock_get_client.return_value = mock_client

        result = analyze_and_recommend(sample_customer, sample_pages)

        assert result["faq_entries"] == {}
        assert result["content_gaps"] == []
        assert "Error" in result["priority_actions"][0]

    @patch("geo_agent.analyzer.get_client")
    def test_uses_correct_model(self, mock_get_client, sample_customer, sample_pages, fake_analysis_response):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        analyze_and_recommend(sample_customer, sample_pages)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"
        assert call_kwargs["max_tokens"] == 8192

    @patch("geo_agent.analyzer.get_client")
    def test_truncates_page_content(self, mock_get_client, sample_customer, fake_analysis_response):
        """Pages with long content are truncated to 2000 chars in the prompt."""
        long_page_content = "x" * 5000
        from geo_agent.crawler import PageData
        pages = [PageData(id="p1", url="https://test.com/long", title="Long", content=long_page_content, category="page", slug="long", html="")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        analyze_and_recommend(sample_customer, pages)

        call_args = mock_client.messages.create.call_args.kwargs
        user_msg = call_args["messages"][0]["content"]
        # The full 5000 chars should NOT appear in the prompt
        assert "x" * 5000 not in user_msg

    @patch("geo_agent.analyzer.get_client")
    def test_prompt_includes_verified_data(self, mock_get_client, sample_customer, sample_pages, sample_verified_data, sample_competitors, fake_analysis_response):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        analyze_and_recommend(sample_customer, sample_pages, verified_data=sample_verified_data, competitors=sample_competitors)

        call_args = mock_client.messages.create.call_args.kwargs
        user_msg = call_args["messages"][0]["content"]
        assert "Google-Verified Business Data" in user_msg
        assert "4.7 stars (156 reviews)" in user_msg
        assert "CRITICAL: Use these EXACT numbers" in user_msg

    @patch("geo_agent.analyzer.get_client")
    def test_prompt_includes_competitors(self, mock_get_client, sample_customer, sample_pages, sample_verified_data, sample_competitors, fake_analysis_response):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        analyze_and_recommend(sample_customer, sample_pages, verified_data=sample_verified_data, competitors=sample_competitors)

        call_args = mock_client.messages.create.call_args.kwargs
        user_msg = call_args["messages"][0]["content"]
        assert "Walden Dental" in user_msg
        assert "Nearby Competitors" in user_msg

    @patch("geo_agent.analyzer.get_client")
    def test_prompt_warns_when_no_verified_data(self, mock_get_client, sample_customer, sample_pages, fake_analysis_response):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(json.dumps(fake_analysis_response))
        mock_get_client.return_value = mock_client

        analyze_and_recommend(sample_customer, sample_pages, verified_data=None, competitors=None)

        call_args = mock_client.messages.create.call_args.kwargs
        user_msg = call_args["messages"][0]["content"]
        assert "Google Places data was not available" in user_msg
        assert "Do NOT fabricate" in user_msg


class TestGradeAnalysis:
    def test_passes_clean_response(self, sample_customer, fake_analysis_response):
        issues = grade_analysis(fake_analysis_response, sample_customer)
        assert len(issues) == 0

    def test_detects_missing_keys(self, sample_customer):
        result = {"faq_entries": {}}  # missing content_gaps and priority_actions
        issues = grade_analysis(result, sample_customer)
        assert any("Missing required key" in i for i in issues)

    def test_blocks_competitor_in_faq(self, sample_customer, fake_analysis_response):
        """FAQ answers mentioning a competitor should be blocked and scrubbed."""
        fake_analysis_response["faq_entries"]["https://hilltopdental.com/services/dental-implants"][0]["answer"] = (
            "waldendental.com offers cheaper implants than us."
        )
        issues = grade_analysis(fake_analysis_response, sample_customer)
        blocked = [i for i in issues if "BLOCKED" in i]
        assert len(blocked) >= 1
        assert "waldendental.com" in blocked[0]
        # The answer should have been scrubbed
        scrubbed = fake_analysis_response["faq_entries"]["https://hilltopdental.com/services/dental-implants"][0]["answer"]
        assert "waldendental.com" not in scrubbed

    def test_detects_fabricated_rating(self, sample_customer, sample_verified_data):
        result = {
            "faq_entries": {},
            "content_gaps": [],
            "priority_actions": ["We have 4.2 stars on Google"],
        }
        issues = grade_analysis(result, sample_customer, verified_data=sample_verified_data)
        assert any("Fabricated rating" in i for i in issues)

    def test_detects_fabricated_review_count(self, sample_customer, sample_verified_data):
        result = {
            "faq_entries": {},
            "content_gaps": [],
            "priority_actions": ["With over 500 reviews on Google..."],
        }
        issues = grade_analysis(result, sample_customer, verified_data=sample_verified_data)
        assert any("Fabricated review count" in i for i in issues)

    def test_accurate_numbers_pass(self, sample_customer, sample_verified_data):
        result = {
            "faq_entries": {},
            "content_gaps": [],
            "priority_actions": [f"With {sample_verified_data.rating} stars and {sample_verified_data.review_count} reviews"],
        }
        issues = grade_analysis(result, sample_customer, verified_data=sample_verified_data)
        assert not any("Fabricated" in i for i in issues)
