"""Tests for business_profiles.py — profile resolution and multi-industry support."""

from __future__ import annotations

import pytest

from geo_agent.business_profiles import BusinessProfile, PROFILES, get_profile
from geo_agent.config import Customer


class TestGetProfile:
    def test_practice_type(self):
        profile = get_profile("practice")
        assert profile.schema_type == "Dentist"
        assert profile.is_practice is True
        assert profile.customer_term == "patients"
        assert profile.schema_specialty == "Dentistry"

    def test_technology_type(self):
        profile = get_profile("technology")
        assert profile.schema_type == "Organization"
        assert profile.is_practice is False
        assert profile.customer_term == "clients"
        assert profile.additional_schema_type == "https://schema.org/SoftwareApplication"

    def test_service_type(self):
        profile = get_profile("service")
        assert profile.schema_type == "LocalBusiness"
        assert profile.is_practice is False
        assert profile.customer_term == "customers"

    def test_precious_metals_buyer(self):
        profile = get_profile("precious_metals_buyer")
        assert profile.schema_type == "LocalBusiness"
        assert "gold" in profile.service_keywords
        assert "silver" in profile.service_keywords
        assert profile.customer_term == "customers"

    def test_legal_type(self):
        profile = get_profile("legal")
        assert profile.schema_type == "LegalService"
        assert profile.is_practice is False
        assert profile.customer_term == "clients"
        assert profile.provider_term == "attorneys"
        assert profile.service_category == "practice areas"

    def test_medical_type(self):
        profile = get_profile("medical")
        assert profile.schema_type == "MedicalBusiness"
        assert profile.is_practice is True
        assert profile.customer_term == "patients"
        assert profile.provider_term == "providers"
        assert profile.schema_specialty == "Medicine"

    def test_unknown_type_returns_generic(self):
        profile = get_profile("unknown_type")
        assert profile.schema_type == "LocalBusiness"
        assert profile.is_practice is False
        assert profile.industry == "unknown_type"

    def test_empty_type_returns_generic(self):
        profile = get_profile("")
        assert profile.schema_type == "LocalBusiness"

    def test_customer_object(self):
        customer = Customer(
            id="test", name="Test", domain="test.com",
            city="Austin", state="TX", business_type="practice",
        )
        profile = get_profile(customer)
        assert profile.schema_type == "Dentist"
        assert profile.is_practice is True

    def test_customer_non_dental(self):
        customer = Customer(
            id="test", name="Test", domain="test.com",
            city="Austin", state="TX", business_type="service",
        )
        profile = get_profile(customer)
        assert profile.schema_type == "LocalBusiness"
        assert profile.is_practice is False


class TestProfilesComplete:
    def test_all_profiles_have_required_fields(self):
        for name, profile in PROFILES.items():
            assert profile.schema_type, f"{name} missing schema_type"
            assert profile.industry, f"{name} missing industry"
            assert profile.customer_term, f"{name} missing customer_term"
            assert profile.provider_term, f"{name} missing provider_term"
            assert profile.service_category, f"{name} missing service_category"
            assert profile.service_keywords, f"{name} missing service_keywords"

    def test_dental_profile_has_dental_keywords(self):
        profile = PROFILES["practice"]
        assert "implant" in profile.service_keywords
        assert "cosmetic" in profile.service_keywords
        assert "emergency" in profile.service_keywords

    def test_non_dental_profiles_no_dental_keywords(self):
        dental_only = {"implant", "cosmetic", "whitening", "invisalign", "orthodont",
                       "denture", "bridge", "sedation", "filling"}
        for name, profile in PROFILES.items():
            if name == "practice":
                continue
            overlap = dental_only & set(profile.service_keywords)
            assert not overlap, f"{name} has dental keywords: {overlap}"
