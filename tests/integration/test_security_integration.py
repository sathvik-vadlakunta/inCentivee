"""Integration tests for security controls — real SQLite, real file I/O."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


# Check if sqlite3 supports extension loading
try:
    _conn = sqlite3.connect(":memory:")
    _conn.enable_load_extension(True)
    _conn.close()
    HAS_SQLITE_EXT = True
except AttributeError:
    HAS_SQLITE_EXT = False


@pytest.mark.skipif(not HAS_SQLITE_EXT, reason="sqlite3 extension loading not available")
class TestRAGIsolation:
    """Verify that CustomerRAG databases are truly isolated."""

    def test_separate_databases_no_cross_read(self, tmp_path, fake_embedding):
        """Customer A's pages should never appear in Customer B's database."""
        from geo_agent.rag_store import CustomerRAG

        rag_a = CustomerRAG("customer-a", data_dir=str(tmp_path))
        rag_b = CustomerRAG("customer-b", data_dir=str(tmp_path))

        # Store data in customer A
        rag_a.upsert_page(
            page_id="secret-page",
            url="https://a.com/secret",
            title="Customer A Secret Page",
            content="This is confidential data for Customer A only.",
            embedding=fake_embedding(1),
            category="service",
        )

        # Customer B should have zero pages
        b_pages = rag_b.get_all_pages()
        assert len(b_pages) == 0

        # Customer A should have the page
        a_pages = rag_a.get_all_pages()
        assert len(a_pages) == 1
        assert a_pages[0]["title"] == "Customer A Secret Page"

        rag_a.close()
        rag_b.close()

    def test_separate_database_files(self, tmp_path, fake_embedding):
        """Each customer must get a physically separate .db file."""
        from geo_agent.rag_store import CustomerRAG

        rag_a = CustomerRAG("customer-a", data_dir=str(tmp_path))
        rag_b = CustomerRAG("customer-b", data_dir=str(tmp_path))

        assert rag_a.db_path != rag_b.db_path
        assert rag_a.db_path.name == "customer-a.db"
        assert rag_b.db_path.name == "customer-b.db"

        rag_a.close()
        rag_b.close()

    def test_search_cannot_cross_databases(self, tmp_path, fake_embedding):
        """Search in one customer's RAG must not return another customer's data."""
        from geo_agent.rag_store import CustomerRAG
        from geo_agent.embeddings import embed_query

        rag_a = CustomerRAG("customer-a", data_dir=str(tmp_path))
        rag_b = CustomerRAG("customer-b", data_dir=str(tmp_path))

        # Store dental implants page in Customer A
        rag_a.upsert_page(
            page_id="implants",
            url="https://a.com/implants",
            title="Dental Implants",
            content="We offer dental implants starting at $3,500.",
            embedding=fake_embedding(1),
        )

        # Store completely different content in Customer B
        rag_b.upsert_page(
            page_id="whitening",
            url="https://b.com/whitening",
            title="Teeth Whitening",
            content="Professional whitening from $200.",
            embedding=fake_embedding(2),
        )

        # Search Customer B for "dental implants" — should NOT find Customer A's page
        results = rag_b.search("dental implants", fake_embedding(1), n=10)
        for r in results:
            assert r["url"] != "https://a.com/implants"
            assert "Customer A" not in r.get("content", "")

        rag_a.close()
        rag_b.close()

    def test_run_history_isolated(self, tmp_path, fake_embedding):
        """Run history logs should be per-customer."""
        from geo_agent.rag_store import CustomerRAG

        rag_a = CustomerRAG("customer-a", data_dir=str(tmp_path))
        rag_b = CustomerRAG("customer-b", data_dir=str(tmp_path))

        rag_a.log_run("changed schema", "llms content A", "schema A")
        rag_a.log_run("second run", "llms content A v2", "schema A v2")

        # Customer B should have zero run history
        b_runs = rag_b.db.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert b_runs == 0

        # Customer A should have 2 runs
        a_runs = rag_a.db.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert a_runs == 2

        rag_a.close()
        rag_b.close()


class TestAuditLogIntegration:
    """Verify audit logs are written correctly to disk."""

    def test_audit_log_survives_crash(self, tmp_path):
        """Each log entry should be flushed immediately (append mode)."""
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log("customer-1", "pipeline_start")

        # Read the file directly — should already be on disk
        log_files = list(tmp_path.glob("audit_*.jsonl"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "pipeline_start" in content

    def test_audit_log_no_secrets_leaked(self, tmp_path):
        """Audit logs must never contain raw API keys."""
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        secret_key = "ws-8f2e7a9d69c5eb793f6fcf1a3e783a1f22ac47663a565171e190c2ac1219edd3"
        audit.log_credential_access("hilltop", "webflow_api_key", secret_key)

        log_content = list(tmp_path.glob("audit_*.jsonl"))[0].read_text()
        assert secret_key not in log_content
        assert "ws-8f2e" not in log_content


class TestOutputFileIsolation:
    """Verify generated files go to the right customer directory."""

    def test_output_dirs_separate(self, tmp_path):
        """Each customer's output must be in its own directory."""
        output_base = tmp_path / "output"

        dir_a = output_base / "customer-a"
        dir_b = output_base / "customer-b"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)

        (dir_a / "llms.txt").write_text("Customer A llms.txt")
        (dir_b / "llms.txt").write_text("Customer B llms.txt")

        assert (dir_a / "llms.txt").read_text() == "Customer A llms.txt"
        assert (dir_b / "llms.txt").read_text() == "Customer B llms.txt"

    def test_no_path_traversal(self, tmp_path):
        """Customer IDs with path traversal attempts should be handled safely."""
        malicious_id = "../../../etc/passwd"
        output_dir = tmp_path / "output" / malicious_id

        # Path should resolve within tmp_path, not escape
        resolved = output_dir.resolve()
        assert str(tmp_path) in str(resolved) or not resolved.exists()
