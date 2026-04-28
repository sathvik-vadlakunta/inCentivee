"""Integration tests for rag_store.py — real SQLite + sqlite-vec with tmp_path.

These tests require a Python build with sqlite3 extension loading support.
macOS system Python 3.9 doesn't support this — run in Docker or with a pyenv build.
"""

from __future__ import annotations

import math
import sqlite3

import pytest

# Skip entire module if sqlite3 doesn't support extensions
try:
    _conn = sqlite3.connect(":memory:")
    _conn.enable_load_extension(True)
    _conn.close()
    _has_extensions = True
except AttributeError:
    _has_extensions = False

pytestmark = pytest.mark.skipif(not _has_extensions, reason="sqlite3 extension loading not supported on this Python build")

from geo_agent.rag_store import CustomerRAG, EMBEDDING_DIM


def _vec(seed: int = 0) -> list[float]:
    """Deterministic 1024-dim vector from seed."""
    return [math.sin(seed + i) * 0.1 for i in range(EMBEDDING_DIM)]


class TestCustomerRAG:
    def test_upsert_and_retrieve(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))
        rag.upsert_page(
            page_id="p1",
            url="https://test.com/about",
            title="About Us",
            content="We are a dental practice in Austin.",
            embedding=_vec(1),
            category="about",
        )

        pages = rag.get_all_pages()
        assert len(pages) == 1
        assert pages[0]["id"] == "p1"
        assert pages[0]["title"] == "About Us"
        assert pages[0]["category"] == "about"
        rag.close()

    def test_upsert_replaces_existing(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))
        rag.upsert_page("p1", "https://test.com/a", "Old Title", "Old content", _vec(1), "page")
        rag.upsert_page("p1", "https://test.com/a", "New Title", "New content", _vec(2), "page")

        pages = rag.get_all_pages()
        assert len(pages) == 1
        assert pages[0]["title"] == "New Title"
        assert pages[0]["content"] == "New content"
        rag.close()

    def test_multiple_pages(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))
        for i in range(5):
            rag.upsert_page(f"p{i}", f"https://test.com/{i}", f"Page {i}", f"Content {i}", _vec(i), "page")

        pages = rag.get_all_pages()
        assert len(pages) == 5
        rag.close()

    def test_hybrid_search_returns_results(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))

        rag.upsert_page("p1", "https://test.com/implants", "Dental Implants",
                         "Full dental implant procedures available", _vec(1), "service")
        rag.upsert_page("p2", "https://test.com/about", "About Us",
                         "Our team of experienced dentists", _vec(2), "about")
        rag.upsert_page("p3", "https://test.com/whitening", "Teeth Whitening",
                         "Professional teeth whitening services", _vec(3), "service")

        results = rag.search("dental implants", _vec(1), n=3)

        assert len(results) > 0
        assert results[0]["id"] == "p1"  # closest vector match
        assert "score" in results[0]
        rag.close()

    def test_search_empty_store(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))
        results = rag.search("anything", _vec(0), n=5)
        assert results == []
        rag.close()

    def test_separate_customer_databases(self, tmp_path):
        rag_a = CustomerRAG("customer-a", data_dir=str(tmp_path))
        rag_b = CustomerRAG("customer-b", data_dir=str(tmp_path))

        rag_a.upsert_page("p1", "https://a.com/", "A Home", "Customer A content", _vec(1), "home")
        rag_b.upsert_page("p1", "https://b.com/", "B Home", "Customer B content", _vec(2), "home")

        pages_a = rag_a.get_all_pages()
        pages_b = rag_b.get_all_pages()

        assert len(pages_a) == 1
        assert len(pages_b) == 1
        assert pages_a[0]["content"] == "Customer A content"
        assert pages_b[0]["content"] == "Customer B content"

        rag_a.close()
        rag_b.close()

        # Verify separate .db files
        assert (tmp_path / "customer-a.db").exists()
        assert (tmp_path / "customer-b.db").exists()

    def test_log_run(self, tmp_path):
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))
        rag.log_run(
            changes="Generated llms.txt",
            llms_txt="# Test Practice",
            schema_updates='<script type="application/ld+json">...</script>',
        )

        rows = rag.db.execute("SELECT * FROM run_history").fetchall()
        assert len(rows) == 1
        assert "Generated llms.txt" in rows[0][2]
        rag.close()

    def test_db_file_created(self, tmp_path):
        rag = CustomerRAG("my-practice", data_dir=str(tmp_path))
        assert (tmp_path / "my-practice.db").exists()
        rag.close()

    def test_search_scored_results_ordered(self, tmp_path):
        """Results should be ordered by RRF score (highest first)."""
        rag = CustomerRAG("test-customer", data_dir=str(tmp_path))

        # Insert pages with varied content and vectors
        rag.upsert_page("p1", "https://test.com/1", "Implants", "dental implant surgery", _vec(10), "service")
        rag.upsert_page("p2", "https://test.com/2", "Cleaning", "regular teeth cleaning", _vec(20), "service")
        rag.upsert_page("p3", "https://test.com/3", "Implant FAQ", "dental implant questions", _vec(11), "faq")

        results = rag.search("dental implants", _vec(10), n=3)

        assert len(results) >= 2
        # Scores should be in descending order
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        rag.close()
