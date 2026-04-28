"""Tests for config.py — dataclass loading, file parsing, defaults, credential security."""

from __future__ import annotations

import json

import pytest

from geo_agent.config import Customer, Provider, load_customers
from geo_agent.secrets import get_secrets


class TestProvider:
    def test_defaults(self):
        p = Provider(name="Dr. X", credentials="DDS")
        assert p.specialties == []
        assert p.years_experience is None
        assert p.bio == ""

    def test_full(self):
        p = Provider(name="Dr. X", credentials="DMD", specialties=["Ortho"], years_experience=10, bio="Expert.")
        assert p.name == "Dr. X"
        assert p.credentials == "DMD"
        assert p.specialties == ["Ortho"]
        assert p.years_experience == 10


class TestCustomer:
    def test_from_dict_minimal(self, monkeypatch):
        monkeypatch.delenv("WEBFLOW_KEY_TEST", raising=False)
        get_secrets.cache_clear()
        c = Customer.from_dict({"id": "test", "name": "Test", "domain": "test.com", "city": "LA", "state": "CA"})
        assert c.id == "test"
        assert c.brand_voice == "Professional and warm"
        assert c.providers == []
        assert c.emergency_available is False
        assert c.webflow_api_key == ""  # No env var → empty

    def test_from_dict_with_providers(self, monkeypatch):
        monkeypatch.delenv("WEBFLOW_KEY_TEST", raising=False)
        get_secrets.cache_clear()
        data = {
            "id": "test",
            "name": "Test Dental",
            "domain": "test.com",
            "city": "LA",
            "state": "CA",
            "providers": [
                {"name": "Dr. A", "credentials": "DDS", "specialties": ["Implants"]},
            ],
        }
        c = Customer.from_dict(data)
        assert len(c.providers) == 1
        assert c.providers[0].name == "Dr. A"
        assert c.providers[0].specialties == ["Implants"]

    def test_from_dict_all_fields(self, sample_customer):
        assert sample_customer.id == "hilltop-dental"
        assert sample_customer.emergency_available is True
        assert len(sample_customer.providers) == 2
        assert sample_customer.zip_code == "78756"

    def test_webflow_key_from_env(self, monkeypatch):
        """Webflow key should be loaded from env var based on customer ID."""
        monkeypatch.setenv("WEBFLOW_KEY_MY_DENTAL", "ws-from-env")
        get_secrets.cache_clear()
        c = Customer.from_dict({"id": "my-dental", "name": "My", "domain": "my.com", "city": "X", "state": "TX"})
        assert c.webflow_api_key == "ws-from-env"


class TestLoadCustomers:
    def test_load_from_file(self, customers_json_file):
        customers = load_customers(str(customers_json_file))
        assert len(customers) == 1
        assert customers[0].id == "hilltop-dental"
        assert customers[0].providers[0].name == "Dr. David Gallup"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_customers(str(tmp_path / "nonexistent.json"))

    def test_multiple_customers(self, tmp_path, monkeypatch):
        data = {
            "customers": [
                {"id": "a", "name": "A", "domain": "a.com", "city": "X", "state": "TX"},
                {"id": "b", "name": "B", "domain": "b.com", "city": "Y", "state": "CA"},
            ]
        }
        path = tmp_path / "multi.json"
        path.write_text(json.dumps(data))
        monkeypatch.delenv("WEBFLOW_KEY_A", raising=False)
        monkeypatch.delenv("WEBFLOW_KEY_B", raising=False)
        get_secrets.cache_clear()
        customers = load_customers(str(path))
        assert len(customers) == 2
        assert {c.id for c in customers} == {"a", "b"}

    def test_json_key_stripped(self, tmp_path, monkeypatch, caplog):
        """Keys in JSON should be stripped with a security warning."""
        data = {
            "customers": [{
                "id": "insecure",
                "name": "Insecure",
                "domain": "insecure.com",
                "city": "X",
                "state": "TX",
                "webflow_api_key": "ws-should-not-be-here",
            }]
        }
        path = tmp_path / "insecure.json"
        path.write_text(json.dumps(data))
        monkeypatch.delenv("WEBFLOW_KEY_INSECURE", raising=False)
        get_secrets.cache_clear()

        import logging
        with caplog.at_level(logging.WARNING):
            customers = load_customers(str(path))

        assert customers[0].webflow_api_key == ""
        assert any("SECURITY" in r.message for r in caplog.records)
