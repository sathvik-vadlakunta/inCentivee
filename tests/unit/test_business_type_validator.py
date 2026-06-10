"""Tests for validators/business_type_check.py — contamination detection."""

from __future__ import annotations

from geo_agent.business_profiles import get_profile
from geo_agent.validators.business_type_check import validate_output, validate_schema_type


class TestValidateOutput:
    def test_clean_dental_output(self):
        profile = get_profile("practice")
        files = {
            "llms.txt": "# Test Dental — Dentist in Austin, TX\nDental services available.",
            "schema.html": '<script type="application/ld+json">{"@type": "Dentist"}</script>',
        }
        warnings = validate_output(profile, files, business_type="practice")
        assert warnings == []

    def test_dental_contamination_in_non_dental(self):
        profile = get_profile("service")
        files = {
            "llms.txt": "# Gold Buyer\nWe are a dental practice in Austin.",
            "schema.html": '<script type="application/ld+json">{"@type": "Dentist"}</script>',
        }
        warnings = validate_output(profile, files, business_type="service")
        assert len(warnings) > 0
        assert any("dental" in w.lower() for w in warnings)

    def test_precious_metals_no_dental(self):
        profile = get_profile("precious_metals_buyer")
        files = {
            "llms.txt": "# Paradigm Experts — Precious metals buyer in Springfield, VA",
            "robots.txt": "# Allow bots so customers can find this business",
        }
        warnings = validate_output(profile, files, business_type="precious_metals_buyer")
        assert warnings == []

    def test_precious_metals_with_dental_contamination(self):
        profile = get_profile("precious_metals_buyer")
        files = {
            "llms.txt": "# Paradigm Experts — Dental Lab & Services",
        }
        warnings = validate_output(profile, files, business_type="precious_metals_buyer")
        assert len(warnings) > 0

    def test_empty_files_no_warnings(self):
        profile = get_profile("service")
        files = {"llms.txt": "", "schema.html": ""}
        warnings = validate_output(profile, files, business_type="service")
        assert warnings == []

    def test_technology_no_dental(self):
        profile = get_profile("technology")
        files = {
            "llms.txt": "# SmileShape — AI platform for digital design",
        }
        warnings = validate_output(profile, files, business_type="technology")
        assert warnings == []


    def test_legal_no_dental_contamination(self):
        profile = get_profile("legal")
        files = {
            "llms.txt": "# FRB Law — Personal injury attorneys in New York\nLitigation and legal services.",
        }
        warnings = validate_output(profile, files, business_type="legal")
        assert warnings == []

    def test_legal_with_dental_contamination(self):
        profile = get_profile("legal")
        files = {
            "llms.txt": "# FRB Law — Dental practice in New York",
        }
        warnings = validate_output(profile, files, business_type="legal")
        assert len(warnings) > 0
        assert any("dental" in w.lower() for w in warnings)

    def test_medical_no_contamination(self):
        profile = get_profile("medical")
        files = {
            "llms.txt": "# City Health — Primary care physicians in Austin",
        }
        warnings = validate_output(profile, files, business_type="medical")
        assert warnings == []

    def test_medical_with_legal_contamination(self):
        profile = get_profile("medical")
        files = {
            "llms.txt": "# City Health — Personal injury attorney consultations",
        }
        warnings = validate_output(profile, files, business_type="medical")
        assert len(warnings) > 0

    def test_dental_with_legal_contamination(self):
        profile = get_profile("practice")
        files = {
            "llms.txt": "# Hilltop Dental — Attorney and litigation services",
        }
        warnings = validate_output(profile, files, business_type="practice")
        assert len(warnings) > 0


class TestValidateSchemaType:
    def test_correct_dental_schema(self):
        profile = get_profile("practice")
        schema = '{"@type": "Dentist", "name": "Test"}'
        warnings = validate_schema_type(profile, schema)
        assert warnings == []

    def test_dentist_schema_for_non_dental(self):
        profile = get_profile("service")
        schema = '{"@type": "Dentist", "name": "Test"}'
        warnings = validate_schema_type(profile, schema)
        assert len(warnings) > 0
        assert any("Dentist" in w for w in warnings)

    def test_correct_local_business_schema(self):
        profile = get_profile("service")
        schema = '{"@type": "LocalBusiness", "name": "Test"}'
        warnings = validate_schema_type(profile, schema)
        assert warnings == []

    def test_medical_specialty_for_non_medical(self):
        profile = get_profile("precious_metals_buyer")
        schema = '{"@type": "LocalBusiness", "medicalSpecialty": "Dentistry"}'
        warnings = validate_schema_type(profile, schema)
        assert len(warnings) > 0
        assert any("medicalSpecialty" in w for w in warnings)

    def test_legal_schema_correct(self):
        profile = get_profile("legal")
        schema = '{"@type": "LegalService", "name": "FRB Law"}'
        warnings = validate_schema_type(profile, schema)
        assert warnings == []

    def test_legal_schema_with_dentist_type(self):
        profile = get_profile("legal")
        schema = '{"@type": "Dentist", "name": "FRB Law"}'
        warnings = validate_schema_type(profile, schema)
        assert len(warnings) == 1
        assert "Dentist" in warnings[0]

    def test_medical_schema_correct(self):
        profile = get_profile("medical")
        schema = '{"@type": "MedicalBusiness", "name": "City Health"}'
        warnings = validate_schema_type(profile, schema)
        assert warnings == []

    def test_medical_schema_with_legal_type(self):
        profile = get_profile("medical")
        schema = '{"@type": "LegalService", "name": "City Health"}'
        warnings = validate_schema_type(profile, schema)
        assert len(warnings) == 1
        assert "LegalService" in warnings[0]

    def test_no_duplicate_warnings(self):
        """Ensure the new wrong_types check doesn't duplicate the legacy is_practice check."""
        profile = get_profile("legal")
        schema = '{"@type": "Dentist", "name": "Test"}'
        warnings = validate_schema_type(profile, schema)
        dentist_warnings = [w for w in warnings if "Dentist" in w]
        assert len(dentist_warnings) == 1

    def test_empty_schema_no_warnings(self):
        profile = get_profile("service")
        warnings = validate_schema_type(profile, "")
        assert warnings == []
