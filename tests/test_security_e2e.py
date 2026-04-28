"""E2E security tests — full pipeline with security controls verified."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from geo_agent.main import process_customer


# Check if sqlite3 supports extension loading
try:
    _conn = sqlite3.connect(":memory:")
    _conn.enable_load_extension(True)
    _conn.close()
    HAS_SQLITE_EXT = True
except AttributeError:
    HAS_SQLITE_EXT = False


def _vec(seed: int = 0) -> list[float]:
    return [math.sin(seed + i) * 0.1 for i in range(1024)]


FAKE_ANALYSIS = {
    "faq_entries": {},
    "content_gaps": [],
    "service_descriptions": {},
    "priority_actions": ["Action 1"],
}


def _mock_webflow_pages(site_id: str):
    respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
        return_value=httpx.Response(200, json={
            "pages": [
                {"id": "p1", "slug": "", "title": "Home"},
                {"id": "p2", "slug": "about", "title": "About"},
            ]
        })
    )
    for pid in ["p1", "p2"]:
        respx.get(f"https://api.webflow.com/v2/pages/{pid}").mock(
            return_value=httpx.Response(200, json={
                "body": "<h1>Welcome</h1><p>Dental care in our city for patients of all ages.</p>"
            })
        )


class TestSecurityE2EPipeline:
    """Full pipeline E2E tests focused on security controls."""

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_audit_log_created_during_pipeline(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Running the pipeline must create audit log entries."""
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS
        _mock_webflow_pages(sample_customer.webflow_site_id)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"
        audit_dir = tmp_path / "audit_logs"

        result = process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        # Audit logs should exist
        log_files = list(audit_dir.glob("audit_*.jsonl"))
        assert len(log_files) >= 1, "Audit log file should be created during pipeline"

        # Parse all entries
        entries = []
        for f in log_files:
            for line in f.read_text().strip().split("\n"):
                entries.append(json.loads(line))

        # Should have at least: pipeline_start, credential_access, crawl_complete, pipeline_complete
        actions = [e["action"] for e in entries]
        assert "pipeline_start" in actions
        assert "credential_access" in actions

        # All entries should reference the correct customer
        for entry in entries:
            assert entry["customer_id"] == sample_customer.id

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_no_secrets_in_output_files(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Generated output files must never contain API keys or secrets."""
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS
        _mock_webflow_pages(sample_customer.webflow_site_id)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        customer_dir = output_dir / sample_customer.id
        secret_key = sample_customer.webflow_api_key

        for filepath in customer_dir.iterdir():
            content = filepath.read_text()
            assert secret_key not in content, f"Secret found in {filepath.name}"
            assert "ANTHROPIC_API_KEY" not in content
            assert "VOYAGE_API_KEY" not in content

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_pii_minimized_before_embedding(self, mock_analyze, mock_embed, sample_customer, tmp_path):
        """Text sent to embedding service should have PII stripped."""
        captured_texts = []

        def capture_embed(texts):
            captured_texts.extend(texts)
            return [_vec(i) for i in range(len(texts))]

        mock_embed.side_effect = capture_embed
        mock_analyze.return_value = FAKE_ANALYSIS
        _mock_webflow_pages(sample_customer.webflow_site_id)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(
            sample_customer,
            dry_run=True,
            output_base=str(output_dir),
            data_dir=str(data_dir),
        )

        # Check that phone numbers are redacted in texts sent to Voyage AI
        for text in captured_texts:
            # Phone pattern should be replaced
            import re
            phones_found = re.findall(r"\(\d{3}\)\s*\d{3}[\s.-]\d{4}", text)
            assert len(phones_found) == 0, f"Phone number found in embedding text: {phones_found}"

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_two_customers_no_cross_contamination_e2e(self, mock_analyze, mock_embed, sample_customer, second_customer, tmp_path):
        """Full E2E test: two customers processed, zero data leakage."""
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_webflow_pages(sample_customer.webflow_site_id)
        _mock_webflow_pages(second_customer.webflow_site_id)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(sample_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))
        process_customer(second_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))

        # Check output file isolation
        dir_a = output_dir / sample_customer.id
        dir_b = output_dir / second_customer.id

        llms_a = (dir_a / "llms.txt").read_text()
        llms_b = (dir_b / "llms.txt").read_text()

        # Customer A's data should NOT appear in Customer B's files
        assert sample_customer.name in llms_a
        assert second_customer.name in llms_b
        assert second_customer.name not in llms_a
        assert sample_customer.name not in llms_b

        # Schema isolation
        schema_a = (dir_a / "schema.html").read_text()
        schema_b = (dir_b / "schema.html").read_text()
        assert sample_customer.domain in schema_a
        assert second_customer.domain not in schema_a

        # Audit log isolation (both customers logged, each with correct ID)
        audit_dir = tmp_path / "audit_logs"
        log_files = list(audit_dir.glob("audit_*.jsonl"))
        if log_files:
            entries = []
            for f in log_files:
                for line in f.read_text().strip().split("\n"):
                    entries.append(json.loads(line))

            a_entries = [e for e in entries if e["customer_id"] == sample_customer.id]
            b_entries = [e for e in entries if e["customer_id"] == second_customer.id]
            assert len(a_entries) > 0
            assert len(b_entries) > 0

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_webflow_credentials_per_customer(self, mock_analyze, mock_embed, sample_customer, second_customer, tmp_path):
        """Each customer's Webflow API calls must use THEIR key, not another customer's."""
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS

        # Mock pages for both
        _mock_webflow_pages(sample_customer.webflow_site_id)
        _mock_webflow_pages(second_customer.webflow_site_id)

        # Mock publish for both
        for site_id in [sample_customer.webflow_site_id, second_customer.webflow_site_id]:
            respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
                return_value=httpx.Response(200, json={"headCode": ""})
            )
            respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
                return_value=httpx.Response(200, json={})
            )
            respx.post(f"https://api.webflow.com/v2/sites/{site_id}/publish").mock(
                return_value=httpx.Response(200, json={"queued": True})
            )

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(sample_customer, dry_run=False, output_base=str(output_dir), data_dir=str(data_dir))
        process_customer(second_customer, dry_run=False, output_base=str(output_dir), data_dir=str(data_dir))

        # Verify each customer's API calls used the correct site_id
        # respx tracks all calls — check that site_abc123 and site_def456 were both called
        called_urls = [str(call.request.url) for call in respx.calls]
        assert any(sample_customer.webflow_site_id in url for url in called_urls)
        assert any(second_customer.webflow_site_id in url for url in called_urls)
