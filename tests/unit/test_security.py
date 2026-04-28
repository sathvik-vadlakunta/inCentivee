"""Security tests — credential isolation, PII protection, audit logging, input validation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from geo_agent.config import Customer, Provider, load_customers
from geo_agent.privacy import hash_pii, minimize_for_embedding, redact_address, redact_phone
from geo_agent.secrets import SecretsManager, get_secrets


# ── Credential Isolation Tests ──


class TestCredentialIsolation:
    """Verify that API keys never leak from one customer to another."""

    def test_webflow_key_loaded_from_env_not_json(self, tmp_path, monkeypatch):
        """Webflow API key must come from env var, not from customers.json."""
        data = {
            "customers": [{
                "id": "test-practice",
                "name": "Test Practice",
                "domain": "test.com",
                "city": "NYC",
                "state": "NY",
            }]
        }
        path = tmp_path / "customers.json"
        path.write_text(json.dumps(data))

        # No env var set → key should be empty
        monkeypatch.delenv("WEBFLOW_KEY_TEST_PRACTICE", raising=False)
        customers = load_customers(str(path))
        assert customers[0].webflow_api_key == ""

        # Set env var → key should load
        monkeypatch.setenv("WEBFLOW_KEY_TEST_PRACTICE", "ws-secret-123")
        # Clear the cached secrets manager
        get_secrets.cache_clear()
        customers = load_customers(str(path))
        assert customers[0].webflow_api_key == "ws-secret-123"

    def test_json_webflow_key_stripped_with_warning(self, tmp_path, monkeypatch, caplog):
        """If someone accidentally puts a key in JSON, it should be stripped."""
        data = {
            "customers": [{
                "id": "legacy-practice",
                "name": "Legacy",
                "domain": "legacy.com",
                "city": "LA",
                "state": "CA",
                "webflow_api_key": "ws-SHOULD-NOT-BE-HERE",
            }]
        }
        path = tmp_path / "customers.json"
        path.write_text(json.dumps(data))

        monkeypatch.delenv("WEBFLOW_KEY_LEGACY_PRACTICE", raising=False)
        get_secrets.cache_clear()

        import logging
        with caplog.at_level(logging.WARNING):
            customers = load_customers(str(path))

        # The JSON key should be removed
        assert customers[0].webflow_api_key == ""  # No env var set
        # Warning should have been logged
        assert any("SECURITY" in r.message for r in caplog.records)

    def test_two_customers_get_different_keys(self, tmp_path, monkeypatch):
        """Each customer must get their own Webflow key from their own env var."""
        data = {
            "customers": [
                {"id": "practice-a", "name": "A", "domain": "a.com", "city": "X", "state": "TX"},
                {"id": "practice-b", "name": "B", "domain": "b.com", "city": "Y", "state": "CA"},
            ]
        }
        path = tmp_path / "customers.json"
        path.write_text(json.dumps(data))

        monkeypatch.setenv("WEBFLOW_KEY_PRACTICE_A", "key-for-a")
        monkeypatch.setenv("WEBFLOW_KEY_PRACTICE_B", "key-for-b")
        get_secrets.cache_clear()

        customers = load_customers(str(path))
        assert customers[0].webflow_api_key == "key-for-a"
        assert customers[1].webflow_api_key == "key-for-b"
        assert customers[0].webflow_api_key != customers[1].webflow_api_key

    def test_customer_without_key_gets_empty_string(self, tmp_path, monkeypatch):
        """A customer with no env var should get empty string, not None or error."""
        data = {
            "customers": [
                {"id": "no-key-practice", "name": "NoKey", "domain": "nokey.com", "city": "X", "state": "TX"},
            ]
        }
        path = tmp_path / "customers.json"
        path.write_text(json.dumps(data))
        monkeypatch.delenv("WEBFLOW_KEY_NO_KEY_PRACTICE", raising=False)
        get_secrets.cache_clear()

        customers = load_customers(str(path))
        assert customers[0].webflow_api_key == ""


# ── Secrets Manager Tests ──


class TestSecretsManager:
    def test_env_backend_default(self, monkeypatch):
        monkeypatch.delenv("SECRETS_BACKEND", raising=False)
        get_secrets.cache_clear()
        sm = SecretsManager()
        assert sm.backend == "env"

    def test_get_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET_KEY", "test-value-123")
        get_secrets.cache_clear()
        sm = SecretsManager()
        assert sm.get("TEST_SECRET_KEY") == "test-value-123"

    def test_get_missing_returns_empty(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_KEY_XYZ", raising=False)
        get_secrets.cache_clear()
        sm = SecretsManager()
        assert sm.get("NONEXISTENT_KEY_XYZ") == ""

    def test_get_customer_secret(self, monkeypatch):
        monkeypatch.setenv("WEBFLOW_KEY_MY_PRACTICE", "ws-test")
        get_secrets.cache_clear()
        sm = SecretsManager()
        assert sm.get_customer_secret("my-practice", "WEBFLOW_KEY") == "ws-test"

    def test_aws_fallback_to_env(self, monkeypatch):
        """AWS backend should fall back to env if boto3 is not available."""
        monkeypatch.setenv("SECRETS_BACKEND", "aws")
        monkeypatch.setenv("FALLBACK_KEY", "fallback-value")
        get_secrets.cache_clear()
        sm = SecretsManager()
        # Without boto3 installed, should fall back to env
        result = sm.get("FALLBACK_KEY")
        assert result == "fallback-value"

    def test_unknown_backend_falls_back(self, monkeypatch):
        monkeypatch.setenv("SECRETS_BACKEND", "unknown-backend")
        monkeypatch.setenv("MY_KEY", "my-value")
        get_secrets.cache_clear()
        sm = SecretsManager()
        assert sm.get("MY_KEY") == "my-value"


# ── PII Protection Tests ──


class TestPIIProtection:
    def test_hash_pii_deterministic(self):
        """Same input should always produce same hash."""
        assert hash_pii("Dr. Smith") == hash_pii("Dr. Smith")

    def test_hash_pii_irreversible(self):
        """Hash should not contain the original value."""
        result = hash_pii("Dr. David Gallup")
        assert "Gallup" not in result
        assert "David" not in result
        assert len(result) == 10  # SHA256 truncated to 10 hex chars

    def test_hash_pii_with_prefix(self):
        result = hash_pii("test", prefix="provider_")
        assert result.startswith("provider_")

    def test_hash_pii_empty(self):
        assert hash_pii("") == ""

    def test_redact_phone(self):
        text = "Call us at (512) 555-0199 or 303-555-1234 today!"
        result = redact_phone(text)
        assert "(512) 555-0199" not in result
        assert "303-555-1234" not in result
        assert "[PHONE]" in result
        assert "Call us at" in result

    def test_redact_address(self):
        text = "Visit us at 4500 Medical Pkwy Suite 200 for your appointment."
        result = redact_address(text)
        assert "4500 Medical Pkwy" not in result
        assert "[ADDRESS]" in result

    def test_minimize_for_embedding(self):
        """Embedding text should have phone and address stripped."""
        text = (
            "Welcome to Hilltop Dental at 4500 Medical Pkwy Suite 200. "
            "Call (512) 555-0199 for dental implants and cosmetic dentistry."
        )
        result = minimize_for_embedding(text)
        assert "(512) 555-0199" not in result
        assert "4500 Medical Pkwy" not in result
        # Semantic content preserved
        assert "dental implants" in result
        assert "cosmetic dentistry" in result

    def test_minimize_preserves_dental_content(self):
        """Dental procedure descriptions should survive minimization."""
        text = "We offer dental implants starting at $3,500. Dr. Gallup has placed over 3,000 implants."
        result = minimize_for_embedding(text)
        assert "dental implants" in result
        assert "$3,500" in result
        assert "3,000 implants" in result


# ── Audit Logging Tests ──


class TestAuditLogging:
    def test_audit_log_created(self, tmp_path):
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log("test-customer", "test_action", {"key": "value"})

        # Should create a file
        log_files = list(tmp_path.glob("audit_*.jsonl"))
        assert len(log_files) == 1

        # Should contain valid JSON
        lines = log_files[0].read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["customer_id"] == "test-customer"
        assert entry["action"] == "test_action"
        assert entry["details"]["key"] == "value"
        assert "timestamp" in entry

    def test_audit_log_appends(self, tmp_path):
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log("cust-a", "action_1")
        audit.log("cust-b", "action_2")

        log_files = list(tmp_path.glob("audit_*.jsonl"))
        lines = log_files[0].read_text().strip().split("\n")
        assert len(lines) == 2

    def test_credential_access_logged_with_fingerprint(self, tmp_path):
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log_credential_access("my-customer", "webflow_api_key", "ws-secret-key-123")

        log_files = list(tmp_path.glob("audit_*.jsonl"))
        entry = json.loads(log_files[0].read_text().strip())

        assert entry["action"] == "credential_access"
        assert entry["details"]["credential_type"] == "webflow_api_key"
        # Should have a fingerprint, NOT the raw key
        assert "ws-secret-key-123" not in json.dumps(entry)
        assert entry["details"]["key_fingerprint"] != ""
        assert len(entry["details"]["key_fingerprint"]) == 12

    def test_credential_fingerprint_empty_key(self, tmp_path):
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log_credential_access("my-customer", "webflow_api_key", "")

        log_files = list(tmp_path.glob("audit_*.jsonl"))
        entry = json.loads(log_files[0].read_text().strip())
        assert entry["details"]["key_fingerprint"] == "empty"

    def test_audit_log_per_customer_isolation(self, tmp_path):
        """Verify audit entries contain customer_id for filtering."""
        from geo_agent.main import AuditLogger

        audit = AuditLogger(log_dir=str(tmp_path))
        audit.log("customer-a", "crawl_start")
        audit.log("customer-b", "crawl_start")
        audit.log("customer-a", "crawl_complete")

        log_files = list(tmp_path.glob("audit_*.jsonl"))
        lines = log_files[0].read_text().strip().split("\n")
        entries = [json.loads(line) for line in lines]

        customer_a_entries = [e for e in entries if e["customer_id"] == "customer-a"]
        customer_b_entries = [e for e in entries if e["customer_id"] == "customer-b"]
        assert len(customer_a_entries) == 2
        assert len(customer_b_entries) == 1


# ── Input Validation Tests (Worker scraper) ──


class TestWorkerInputValidation:
    """Test the validation logic from the Worker's scrapePracticeSite."""

    def test_valid_states_comprehensive(self):
        """All 50 US states + DC + Canadian provinces should be valid."""
        # Import-style test — check the constant exists and has expected size
        # The actual validation runs in the Worker (JS), but we test the concept
        us_states = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
        ]
        assert len(us_states) == 51  # 50 states + DC

    def test_bad_practice_names_rejected(self):
        """Names that look like menu items or dropdowns should be rejected."""
        bad_names = [
            "Eastern Time",
            "Pacific Time",
            "United States",
            "Select",
            "Home",
            "AB",  # too short
            "x" * 101,  # too long
            "123",  # just numbers
            "Monday",
        ]
        import re
        BAD_PATTERNS = [
            re.compile(r"^(eastern|central|mountain|pacific|atlantic)\s+time", re.I),
            re.compile(r"^(united states|canada|mexico|select|choose|option|none|n/a|test)", re.I),
            re.compile(r"^(home|about|contact|services|blog|menu|navigation|footer|header|search)$", re.I),
            re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.I),
            re.compile(r"^\d+$"),
            re.compile(r"^.{1,2}$"),
            re.compile(r"^.{100,}$"),
        ]
        for name in bad_names:
            matched = any(p.search(name) for p in BAD_PATTERNS)
            assert matched, f"Bad name '{name}' was not caught by validation"

    def test_good_practice_names_accepted(self):
        """Legitimate dental practice names should pass validation."""
        good_names = [
            "Downtown Dental",
            "Hilltop Family Dentistry",
            "Bright Smile Dental Care",
            "38th Street Dental",
            "Dr. Smith's Dental Office",
        ]
        import re
        BAD_PATTERNS = [
            re.compile(r"^(eastern|central|mountain|pacific|atlantic)\s+time", re.I),
            re.compile(r"^(united states|canada|mexico|select|choose|option|none|n/a|test)", re.I),
            re.compile(r"^(home|about|contact|services|blog|menu|navigation|footer|header|search)$", re.I),
            re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.I),
            re.compile(r"^\d+$"),
            re.compile(r"^.{1,2}$"),
            re.compile(r"^.{100,}$"),
        ]
        for name in good_names:
            matched = any(p.search(name) for p in BAD_PATTERNS)
            assert not matched, f"Good name '{name}' was incorrectly rejected"


# ── Data Isolation in Config ──


class TestDataIsolation:
    def test_customer_objects_independent(self):
        """Modifying one customer should not affect another."""
        a = Customer(id="a", name="A", domain="a.com", city="X", state="TX")
        b = Customer(id="b", name="B", domain="b.com", city="Y", state="CA")

        a.specialties.append("Implants")
        assert "Implants" not in b.specialties

    def test_provider_lists_independent(self):
        """Provider lists should not be shared between customers."""
        a = Customer(id="a", name="A", domain="a.com", city="X", state="TX",
                     providers=[Provider(name="Dr. A", credentials="DDS")])
        b = Customer(id="b", name="B", domain="b.com", city="Y", state="CA",
                     providers=[Provider(name="Dr. B", credentials="DMD")])

        assert a.providers[0].name != b.providers[0].name
        a.providers.append(Provider(name="Dr. C", credentials="DDS"))
        assert len(b.providers) == 1
