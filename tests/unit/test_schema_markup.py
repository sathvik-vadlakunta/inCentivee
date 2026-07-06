"""Tests for generators/schema_markup.py — Dentist, Person, FAQ, Service schemas."""

from __future__ import annotations

import json

from geo_agent.schema_validator import _validate_schema_fields
from geo_agent.generators.schema_markup import (
    generate_all_schemas,
    generate_dentist_schema,
    generate_faq_schema,
    generate_provider_schemas,
    generate_service_schema,
    schema_to_js_injection,
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
        # medicalSpecialty must be a valid schema.org enum value
        assert s["medicalSpecialty"] == "Dentistry"
        # Specific specialties go in knowsAbout
        assert "Dental Implants" in s["knowsAbout"]

    def test_emergency_service(self, sample_customer):
        s = generate_dentist_schema(sample_customer)
        catalog = s["hasOfferCatalog"]
        assert catalog["@type"] == "OfferCatalog"
        offered = catalog["itemListElement"][0]["itemOffered"]
        assert offered["@type"] == "Service"
        assert "Emergency" in offered["name"]

    def test_no_emergency_when_disabled(self, sample_customer):
        sample_customer.emergency_available = False
        s = generate_dentist_schema(sample_customer)
        assert "hasOfferCatalog" not in s

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


class TestSchemaToJsInjection:
    def test_wraps_in_js_script(self):
        schema = {"@type": "Test", "name": "Foo"}
        tag = schema_to_js_injection(schema)
        assert tag.startswith("<script>")
        assert tag.endswith("</script>")
        assert "application/ld+json" in tag
        assert "document.head.appendChild" in tag

    def test_contains_valid_json(self):
        schema = {"@type": "LocalBusiness", "name": "O'Malley's Dental"}
        tag = schema_to_js_injection(schema)
        # Extract the JSON from s.textContent='...';
        import re
        match = re.search(r"s\.textContent='(.+?)';", tag)
        assert match
        json_str = match.group(1).replace("\\'", "'").replace("\\\\", "\\")
        import json
        parsed = json.loads(json_str)
        assert parsed["@type"] == "LocalBusiness"
        assert parsed["name"] == "O'Malley's Dental"

    def test_no_newlines_in_output(self):
        """Webflow would break JSON with newlines — JS injection must be single-line."""
        schema = {
            "@type": "LocalBusiness",
            "name": "Test Business",
            "description": "A very long description that would normally wrap in Webflow editor " * 5,
            "address": {"@type": "PostalAddress", "streetAddress": "123 Main St"},
        }
        tag = schema_to_js_injection(schema)
        assert "\n" not in tag


class TestGenerateAllSchemas:
    def test_contains_dentist_and_providers(self, sample_customer):
        html = generate_all_schemas(sample_customer)
        # 1 dentist + 2 providers + FAQPage (+ any Service schemas)
        assert html.count("application/ld+json") >= 3
        assert '"Dentist"' in html
        assert '"Person"' in html
        assert '"FAQPage"' in html  # now emitted (highest-impact AI-citation schema)

    def test_returns_html_string(self, sample_customer):
        html = generate_all_schemas(sample_customer)
        assert "<script" in html
        assert "</script>" in html

    def test_passes_verified_data_to_dentist_schema(self, sample_customer, sample_verified_data):
        html = generate_all_schemas(sample_customer, verified_data=sample_verified_data)
        assert '"AggregateRating"' in html

    def test_sameas_emitted_when_present(self, sample_customer):
        sample_customer.same_as = ["https://g.page/acme", "https://www.yelp.com/biz/acme"]
        html = generate_all_schemas(sample_customer)
        assert '"sameAs"' in html and "yelp.com/biz/acme" in html

    def test_legal_provider_is_attorney_with_credential(self):
        from geo_agent.config import Customer, Provider
        from geo_agent.generators.schema_markup import generate_provider_schemas
        c = Customer(id="f", name="Falcon Law", domain="falcon.com", city="Reno", state="NV",
                     business_type="legal",
                     providers=[Provider(name="Jane Doe", credentials="Esq., NV Bar")])
        schemas = generate_provider_schemas(c)
        assert schemas[0]["@type"] == ["Person", "Attorney"]
        assert schemas[0]["hasCredential"]["credentialCategory"] == "Bar Admission"

    def test_webflow_safe_uses_js_injection(self, sample_customer):
        html = generate_all_schemas(sample_customer, webflow_safe=True)
        assert "document.head.appendChild" in html
        assert "\n" not in html.split("\n")[0]  # First tag is single-line
        # Should NOT contain a RAW JSON-LD <script> tag (Webflow strips those).
        # The JS injection legitimately sets s.type="application/ld+json", so check
        # for the raw opening-tag form, not the bare attribute substring.
        assert '<script type="application/ld+json"' not in html

    def test_webflow_safe_contains_valid_json(self, sample_customer):
        import re
        html = generate_all_schemas(sample_customer, webflow_safe=True)
        matches = re.findall(r"s\.textContent='(.+?)';", html)
        assert len(matches) >= 1
        for m in matches:
            json_str = m.replace("\\'", "'").replace("\\\\", "\\")
            parsed = json.loads(json_str)
            assert "@type" in parsed


class TestProductValidation:
    """Google Rich Results requires offers/review/aggregateRating on Product types."""

    def test_product_without_offers_flagged(self):
        schema = {"@type": "Product", "name": "Gold Jewelry", "description": "We buy gold."}
        issues = _validate_schema_fields(schema, "Product")
        assert any("offers" in i for i in issues)

    def test_product_with_offers_passes(self):
        schema = {
            "@type": "Product", "name": "Gold Jewelry",
            "offers": {"@type": "Offer", "price": "100"},
        }
        issues = _validate_schema_fields(schema, "Product")
        assert not any("offers" in i and "review" in i for i in issues)

    def test_product_with_aggregate_rating_passes(self):
        schema = {
            "@type": "Product", "name": "Gold Jewelry",
            "aggregateRating": {"@type": "AggregateRating", "ratingValue": "5"},
        }
        issues = _validate_schema_fields(schema, "Product")
        assert not any("offers" in i and "review" in i for i in issues)

    def test_nested_product_in_offer_catalog_flagged(self):
        schema = {
            "@type": "LocalBusiness",
            "name": "Test",
            "address": {"@type": "PostalAddress", "streetAddress": "x",
                        "addressLocality": "y", "addressRegion": "z", "postalCode": "0"},
            "telephone": "555",
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "itemListElement": [
                    {"@type": "Offer", "itemOffered": {
                        "@type": "Product", "name": "Watches",
                        "description": "Luxury watches",
                    }},
                ],
            },
        }
        issues = _validate_schema_fields(schema, "LocalBusiness")
        assert any("Nested Product" in i and "Watches" in i for i in issues)

    def test_nested_service_in_offer_catalog_clean(self):
        schema = {
            "@type": "LocalBusiness",
            "name": "Test",
            "address": {"@type": "PostalAddress", "streetAddress": "x",
                        "addressLocality": "y", "addressRegion": "z", "postalCode": "0"},
            "telephone": "555",
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "itemListElement": [
                    {"@type": "Offer", "itemOffered": {
                        "@type": "Service", "name": "Gold Buying",
                        "description": "We buy gold.",
                    }},
                ],
            },
        }
        issues = _validate_schema_fields(schema, "LocalBusiness")
        assert not any("Nested Product" in i for i in issues)


class TestValidateSiteSchemaTargets:
    """Regression: the site validator must probe REAL pages, never an assumed
    dental-style path list that 404s on other sites and fires bogus alerts."""

    def _targets(self, domain, pages=None):
        from unittest.mock import patch
        import geo_agent.schema_validator as sv
        with patch.object(sv, "_validate_page_schema", side_effect=lambda u: u):
            return sv.validate_site_schema(domain, pages=pages)

    def test_default_is_homepage_only(self):
        assert self._targets("ex.com") == ["https://ex.com/"]

    def test_never_assumes_services_path(self):
        # The Paradigm bug: /services was probed on a site that has no such page.
        assert all("/services" not in u for u in self._targets("paradigmexperts.com"))

    def test_full_urls_passed_through(self):
        out = self._targets("ex.com", pages=["https://ex.com/team", "/about"])
        assert "https://ex.com/team" in out
        assert "https://ex.com/about" in out

    def test_dedupes_repeated_pages(self):
        out = self._targets("ex.com", pages=["/", "https://ex.com/", "/about"])
        assert out.count("https://ex.com/") == 1
