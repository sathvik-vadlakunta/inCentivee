"""Tests for generators/schema_markup.py — Dentist, Person, FAQ, Service schemas."""

from __future__ import annotations

import json

from geo_agent.generators.schema_markup import (
    generate_all_schemas,
    generate_dentist_schema,
    generate_faq_schema,
    generate_provider_schemas,
    generate_service_schema,
    schema_to_script_tag,
)


class TestDentistSchema:
    def test_type_and_context(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert s["@context"] == "https://schema.org"
        assert s["@type"] == "Dentist"

    def test_id_uses_domain(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert s["@id"] == "https://hilltopdental.com/#dentist"

    def test_address_fields(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        addr = s["address"]
        assert addr["@type"] == "PostalAddress"
        assert addr["addressLocality"] == "Austin"
        assert addr["addressRegion"] == "TX"
        assert addr["postalCode"] == "78756"

    def test_specialties(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert "Dental Implants" in s["medicalSpecialty"]

    def test_emergency_service(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert s["availableService"]["@type"] == "MedicalProcedure"
        assert "Emergency" in s["availableService"]["name"]

    def test_no_emergency_when_disabled(self, sample_customer):
        sample_customer.emergency_available = False
        s = generate_dentist_schema(sample_customer)
        assert "availableService" not in s

    def test_opening_hours(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert s["openingHours"] == "Mon-Fri 8am-5pm, Sat 9am-2pm"

    def test_no_hours_when_empty(self, sample_customer):
        sample_customer.hours = ""
        s = generate_dentist_schema(sample_customer)
        assert "openingHours" not in s


class TestProviderSchemas:
    def test_generates_per_provider(self, sample_customer):
        schemas = generate_provider_schemas(sample_customer)
        assert len(schemas) == 2

    def test_person_type(self, sample_customer):
        schemas = generate_provider_schemas(sample_customer)
        for s in schemas:
            assert s["@type"] == "Person"

    def test_works_for_reference(self, sample_customer):
        schemas = generate_provider_schemas(sample_customer)
        assert schemas[0]["worksFor"]["@id"] == "https://hilltopdental.com/#dentist"

    def test_knows_about(self, sample_customer):
        schemas = generate_provider_schemas(sample_customer)
        assert "Implants" in schemas[0]["knowsAbout"]

    def test_bio_as_description(self, sample_customer):
        schemas = generate_provider_schemas(sample_customer)
        assert "Board-certified" in schemas[0]["description"]

    def test_no_bio_no_description(self, sample_customer):
        sample_customer.providers[0].bio = ""
        schemas = generate_provider_schemas(sample_customer)
        assert "description" not in schemas[0]


class TestServiceSchema:
    def test_type(self, sample_customer):
        s = generate_service_schema("Dental Implants", "Full implant services.", "https://test.com/implants", sample_customer)
        assert s["@type"] == "Service"
        assert s["name"] == "Dental Implants"

    def test_provider_reference(self, sample_customer):
        s = generate_service_schema("X", "Y", "https://test.com/x", sample_customer)
        assert s["provider"]["@type"] == "Dentist"
        assert s["provider"]["@id"] == "https://hilltopdental.com/#dentist"

    def test_area_served(self, sample_customer):
        s = generate_service_schema("X", "Y", "https://test.com/x", sample_customer)
        assert s["areaServed"]["name"] == "Austin"

    def test_description_truncated(self, sample_customer):
        long_desc = "x" * 500
        s = generate_service_schema("X", long_desc, "https://test.com/x", sample_customer)
        assert len(s["description"]) == 300


class TestFaqSchema:
    def test_type(self):
        s = generate_faq_schema([{"question": "Q?", "answer": "A."}])
        assert s["@type"] == "FAQPage"

    def test_main_entity(self):
        faqs = [
            {"question": "How much?", "answer": "$100"},
            {"question": "Where?", "answer": "Austin TX"},
        ]
        s = generate_faq_schema(faqs)
        assert len(s["mainEntity"]) == 2
        assert s["mainEntity"][0]["@type"] == "Question"
        assert s["mainEntity"][0]["name"] == "How much?"
        assert s["mainEntity"][0]["acceptedAnswer"]["@type"] == "Answer"
        assert s["mainEntity"][0]["acceptedAnswer"]["text"] == "$100"


class TestSchemaToScriptTag:
    def test_wraps_in_script(self):
        schema = {"@type": "Test"}
        tag = schema_to_script_tag(schema)
        assert tag.startswith('<script type="application/ld+json">')
        assert tag.endswith("</script>")
        assert '"@type": "Test"' in tag

    def test_valid_json_inside(self):
        schema = {"@type": "Dentist", "name": "Test"}
        tag = schema_to_script_tag(schema)
        json_str = tag.split("\n", 1)[1].rsplit("\n", 1)[0]
        parsed = json.loads(json_str)
        assert parsed["@type"] == "Dentist"


class TestAggregateRating:
    def test_added_when_verified_data_has_reviews(self, sample_customer, sample_verified_data):
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        assert "aggregateRating" in s
        assert s["aggregateRating"]["@type"] == "AggregateRating"
        assert s["aggregateRating"]["ratingValue"] == "4.7"
        assert s["aggregateRating"]["reviewCount"] == "156"

    def test_absent_without_verified_data(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        assert "aggregateRating" not in s

    def test_absent_when_zero_reviews(self, sample_customer, sample_verified_data):
        sample_verified_data.review_count = 0
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        assert "aggregateRating" not in s

    def test_address_override_high_confidence(self, sample_customer, sample_verified_data):
        sample_verified_data.match_confidence = "high"
        sample_verified_data.phone = "(512) 999-0000"
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        assert s["telephone"] == "(512) 999-0000"
        assert "geo" in s

    def test_no_address_override_low_confidence(self, sample_customer, sample_verified_data):
        sample_verified_data.match_confidence = "low"
        sample_verified_data.phone = "(512) 999-0000"
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        # Phone should remain the original customer phone
        assert s["telephone"] == sample_customer.phone
        assert "geo" not in s

    def test_no_reviews_at_low_confidence(self, sample_customer, sample_verified_data):
        """Low confidence match should NOT get AggregateRating — could be wrong business."""
        sample_verified_data.match_confidence = "low"
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        assert "aggregateRating" not in s

    def test_reviews_at_medium_confidence(self, sample_customer, sample_verified_data):
        """Medium confidence (name match) is sufficient for reviews."""
        sample_verified_data.match_confidence = "medium"
        s = generate_dentist_schema(sample_customer, verified_data=sample_verified_data)
        assert "aggregateRating" in s


class TestGenerateAllSchemas:
    def test_contains_dentist_and_providers(self, sample_customer):
        html = generate_all_schemas(sample_customer)
        assert html.count("application/ld+json") == 3  # 1 dentist + 2 providers
        assert '"Dentist"' in html
        assert '"Person"' in html

    def test_returns_html_string(self, sample_customer):
        html = generate_all_schemas(sample_customer)
        assert "<script" in html
        assert "</script>" in html

    def test_passes_verified_data_to_dentist_schema(self, sample_customer, sample_verified_data):
        html = generate_all_schemas(sample_customer, verified_data=sample_verified_data)
        assert '"AggregateRating"' in html
