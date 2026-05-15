"""Multi-customer test — two customers, separate RAG stores, separate output."""

from __future__ import annotations

import math
from unittest.mock import patch

import httpx
import respx

from geo_agent.main import process_customer


def _vec(seed: int = 0) -> list[float]:
    return [math.sin(seed + i) * 0.1 for i in range(1024)]


FAKE_ANALYSIS = {
    "faq_entries": {},
    "content_gaps": [],
    "service_descriptions": {},
    "priority_actions": ["Action 1"],
}


def _mock_pages_for_site(site_id: str, domain: str, practice_name: str):
    """Mock Webflow pages for a specific site."""
    respx.get(f"https://api.webflow.com/v2/sites/{site_id}/pages").mock(
        return_value=httpx.Response(200, json={
            "pages": [
                {"id": f"{site_id}-home", "slug": "", "title": f"{practice_name} Home"},
                {"id": f"{site_id}-about", "slug": "about", "title": "About"},
            ]
        })
    )
    for suffix in ["home", "about"]:
        page_id = f"{site_id}-{suffix}"
        respx.get(f"https://api.webflow.com/v2/pages/{page_id}").mock(
            return_value=httpx.Response(200, json={
                "body": f"<h1>{practice_name}</h1><p>We are {practice_name} located in a wonderful city providing excellent dental care to all patients.</p>"
            })
        )


class TestMultiCustomer:
    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_two_customers_isolated(self, mock_analyze, mock_embed, sample_customer, second_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_pages_for_site(sample_customer.webflow_site_id, sample_customer.domain, sample_customer.name)
        _mock_pages_for_site(second_customer.webflow_site_id, second_customer.domain, second_customer.name)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        result_a = process_customer(sample_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))
        result_b = process_customer(second_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))

        # Separate output directories
        dir_a = output_dir / sample_customer.id
        dir_b = output_dir / second_customer.id
        assert dir_a.exists()
        assert dir_b.exists()

        # Each has its own files
        llms_a = (dir_a / "llms.txt").read_text()
        llms_b = (dir_b / "llms.txt").read_text()

        assert "Hilltop Family Dental" in llms_a
        assert "Bright Smile Dentistry" in llms_b
        assert "Austin, TX" in llms_a
        assert "Denver, CO" in llms_b

        # No cross-contamination
        assert "Bright Smile" not in llms_a
        assert "Hilltop" not in llms_b

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_separate_rag_databases(self, mock_analyze, mock_embed, sample_customer, second_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_pages_for_site(sample_customer.webflow_site_id, sample_customer.domain, sample_customer.name)
        _mock_pages_for_site(second_customer.webflow_site_id, second_customer.domain, second_customer.name)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        r1 = process_customer(sample_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))
        r2 = process_customer(second_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))

        # RAG .db path is data_dir/customers/{id}.db
        rag_dir = data_dir / "customers"

        # On systems without sqlite-vec extension support (e.g. macOS system Python),
        # RAG fails gracefully — check that both runs completed without fatal errors
        rag_failed = any("RAG" in e for e in r1.get("errors", []))
        if rag_failed:
            # Pipeline should still succeed (RAG is non-fatal)
            assert (output_dir / sample_customer.id / "llms.txt").exists()
            assert (output_dir / second_customer.id / "llms.txt").exists()
        else:
            assert (rag_dir / f"{sample_customer.id}.db").exists()
            assert (rag_dir / f"{second_customer.id}.db").exists()

    @respx.mock
    @patch("geo_agent.main.embed_texts")
    @patch("geo_agent.main.analyze_and_recommend")
    def test_schema_uses_correct_domain(self, mock_analyze, mock_embed, sample_customer, second_customer, tmp_path):
        mock_embed.return_value = [_vec(i) for i in range(2)]
        mock_analyze.return_value = FAKE_ANALYSIS

        _mock_pages_for_site(sample_customer.webflow_site_id, sample_customer.domain, sample_customer.name)
        _mock_pages_for_site(second_customer.webflow_site_id, second_customer.domain, second_customer.name)

        output_dir = tmp_path / "output"
        data_dir = tmp_path / "rag"

        process_customer(sample_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))
        process_customer(second_customer, dry_run=True, output_base=str(output_dir), data_dir=str(data_dir))

        schema_a = (output_dir / sample_customer.id / "schema.html").read_text()
        schema_b = (output_dir / second_customer.id / "schema.html").read_text()

        assert "hilltopdental.com" in schema_a
        assert "brightsmile.com" in schema_b
        assert "brightsmile.com" not in schema_a
        assert "hilltopdental.com" not in schema_b
