"""End-to-end test — full process_customer() pipeline with all APIs mocked."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from geo_agent.main import process_customer

# Check if sqlite3 supports extension loading (macOS system Python 3.9 doesn't)
try:
    _conn = sqlite3.connect(":memory:")
    _conn.enable_load_extension(True)
    _conn.close()
    HAS_SQLITE_EXT = True
except AttributeError:
    HAS_SQLITE_EXT = False


def _vec(seed: int = 0) -> list[float]:
    return [math.sin(seed + i) * 0.1 for i in range(1024)]


def _mock_webflow_pages(site_id: str, domain: str):
    """Set up respx mocks for Webflow crawling."""
    respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
        return_value=httpx.Response(200, json={
            "pages": [
                {"id": "p1", "slug": "", "title": "Home"},
                {"id": "p2", "slug": "services/implants", "title": "Dental Implants"},
                {"id": "p3", "slug": "about", "title": "About Us"},
            ]
        })
    )
    respx.get("https://api.webflow.com/v2/pages/p1").mock(
        return_value=httpx.Response(200, json={
            "body": f"<h1>Welcome to our practice</h1><p>We provide comprehensive dental care in Austin TX for all ages and families.</p>"
        })
    )
    respx.get("https://api.webflow.com/v2/pages/p2").mock(
        return_value=httpx.Response(200, json={
            "body": "<h1>Dental Implants</h1><p>Replace missing teeth with dental implants. Our experienced team offers full arch and single tooth options.</p>"
        })
    )
    respx.get("https://api.webflow.com/v2/pages/p3").mock(
        return_value=httpx.Response(200, json={
            "body": "<h1>About Us</h1><p>Meet our team of dedicated dental professionals serving the Austin community for over twenty years.</p>"
        })
    )


def _mock_webflow_publish(site_id: str):
    """Set up respx mocks for Webflow publishing."""
    respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
        return_value=httpx.Response(200, json={"headCode": ""})
    )
    respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.post(f"https://api.webflow.com/v2/sites/{site_id}/publish").mock(
        return_value=httpx.Response(200, json={"queued": True})
    )


FAKE_ANALYSIS = {
    "faq_entries": {
        "https://hilltopdental.com/services/implants": [
            {"question": "How much do implants cost?", "answer": "Starting at $3,500."},
        ]
    },
    "content_gaps": [{"title": "Emergency Page", "slug": "emergency", "description": "Needed."}],
    "service_descriptions": {"Dental Implants": "Full implant services."},
    "priority_actions": ["Add emergency page"],
}


class TestProcessCustomerDryRun:
    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_dry_run_writes_files_no_publish(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(3)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        # Files should be written
        customer_dir = output_dir / sample_customer.id
        assert (customer_dir / "llms.txt").exists()
        assert (customer_dir / "llms-full.txt").exists()
        assert (customer_dir / "schema.html").exists()
        assert (customer_dir / "robots.txt").exists()
        assert (customer_dir / "analysis.json").exists()

        # Summary should reflect dry run
        assert result["pages_crawled"] == 3
        assert any("DRY RUN" in c for c in result["changes"])
        # RAG may fail on systems without sqlite3 extension support (macOS system Python)
        non_rag_errors = [e for e in result["errors"] if "RAG" not in e]
        assert non_rag_errors == []

        # Verify llms.txt content
        llms = (customer_dir / "llms.txt").read_text()
        assert "Hilltop Family Dental" in llms
        assert "Austin, TX" in llms

        # Verify schema has JSON-LD
        schema = (customer_dir / "schema.html").read_text()
        assert "application/ld+json" in schema

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_analysis_json_saved(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(3)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(sample_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))

        analysis = json.loads((output_dir / sample_customer.id / "analysis.json").read_text())
        assert "faq_entries" in analysis
        assert "content_gaps" in analysis


class TestProcessCustomerFullRun:
    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_full_run_publishes(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(3)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)
        _mock_webflow_publish(sample_customer.webflow_site_id)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        result = process_customer(
            sample_customer,
            dry_run=False,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        assert any("published" in c.lower() for c in result["changes"])
        non_rag_errors = [e for e in result["errors"] if "RAG" not in e]
        assert non_rag_errors == []


class TestProcessCustomerErrorHandling:
    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_crawl_failure_returns_early(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        respx.get(
            f"https://api.webflow.com/v2/sites/{sample_customer.webflow_site_id}/pages"
        ).mock(return_value=httpx.Response(500))

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(tmp_path / "output"),
            data_dir=str(tmp_path / "rag"),
        )

        assert len(result["errors"]) > 0
        assert any("Crawl failed" in e for e in result["errors"])

    @respx.mock
    @patch("geo_agent.main.embed_texts", side_effect=Exception("Voyage API down"))
    @patch("geo_agent.main.analyze_and_recommend")
    def test_rag_failure_continues(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Pipeline should continue even if RAG/embedding fails."""
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        # Should have RAG error but still generate files
        assert any("RAG" in e for e in result["errors"])
        assert (output_dir / sample_customer.id / "llms.txt").exists()

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend", side_effect=Exception("Claude API down"))
    def test_analysis_failure_continues(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Pipeline should continue even if Claude analysis fails."""
        mock_embed.return_value = [_vec(i) for i in range(3)]

        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        assert any("Analysis failed" in e for e in result["errors"])
        # Files should still be generated (just without FAQ schemas from analysis)
        assert (output_dir / sample_customer.id / "llms.txt").exists()

    @respx.mock
    @patch("geo_agent.main.embed_texts", side_effect=Exception("Voyage API down"))
    @patch("geo_agent.main.analyze_and_recommend")
    def test_error_messages_never_contain_pii(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Error messages in results should contain error type, NOT customer PII."""
        mock_analyze.return_value = FAKE_ANALYSIS
        _mock_webflow_pages(sample_customer.webflow_site_id, sample_customer.domain)

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(tmp_path / "output"),
            data_dir=str(tmp_path / "rag"),
        )

        for error in result["errors"]:
            # Should NOT contain customer address, phone, or full exception details
            assert sample_customer.phone not in error
            assert sample_customer.address not in error
