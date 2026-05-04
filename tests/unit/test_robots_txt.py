"""Tests for generators/robots_txt.py — training bots blocked, search bots allowed."""

from __future__ import annotations

from geo_agent.generators.robots_txt import generate_robots_txt


class TestGenerateRobotsTxt:
    def test_blocks_training_bots(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        for bot in ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "meta-externalagent", "Applebot-Extended"]:
            assert f"User-agent: {bot}\nDisallow: /" in result

    def test_allows_search_bots(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        for bot in ["ChatGPT-User", "Claude-SearchBot", "Claude-User", "OAI-SearchBot",
                     "PerplexityBot", "Perplexity-User", "Googlebot", "Applebot"]:
            assert f"User-agent: {bot}\nAllow: /" in result

    def test_wildcard_allow(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        assert "User-agent: *\nAllow: /" in result

    def test_sitemap_url(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        assert "Sitemap: https://hilltopdental.com/sitemap.xml" in result

    def test_customer_name_in_header(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        assert "Hilltop Family Dental" in result

    def test_practicerank_attribution(self, sample_customer):
        result = generate_robots_txt(sample_customer)
        assert "PracticeRank GEO Agent" in result
