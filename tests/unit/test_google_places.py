"""Tests for google_places.py — Places API verification and competitor discovery."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from geo_agent.google_places import (
    CompetitorData,
    VerifiedBusinessData,
    _name_similarity,
    _normalize_domain,
    _normalize_phone,
    _score_match,
    fetch_nearby_competitors,
    fetch_place_data,
    get_place_types,
    is_trusted,
    validate_competitors,
    verify_customer,
)


class TestNormalizeDomain:
    def test_strips_www(self):
        assert _normalize_domain("www.hilltopdental.com") == "hilltopdental.com"

    def test_extracts_from_url(self):
        assert _normalize_domain("https://www.hilltopdental.com/about") == "hilltopdental.com"

    def test_handles_bare_domain(self):
        assert _normalize_domain("hilltopdental.com") == "hilltopdental.com"

    def test_empty_string(self):
        assert _normalize_domain("") == ""


class TestNormalizePhone:
    def test_strips_formatting(self):
        assert _normalize_phone("(512) 555-0199") == "5125550199"

    def test_empty(self):
        assert _normalize_phone("") == ""


class TestScoreMatch:
    def test_domain_match_high_confidence(self):
        place = VerifiedBusinessData(
            place_id="p1", name="Hilltop Dental", address="123 Main St",
            website="https://hilltopdental.com",
        )
        score, result = _score_match(place, "Hilltop Dental", "hilltopdental.com", "")
        assert score >= 100
        assert result.domain_match is True
        assert result.match_confidence == "high"

    def test_name_match_medium_confidence(self):
        place = VerifiedBusinessData(place_id="p1", name="Hilltop Family Dental", address="123 Main St")
        score, result = _score_match(place, "Hilltop Family Dental", "other.com", "")
        assert result.name_match is True
        assert result.match_confidence == "medium"

    def test_phone_match_adds_score(self):
        place = VerifiedBusinessData(place_id="p1", name="Some Dental", address="123 Main St", phone="(512) 555-0199")
        score, _ = _score_match(place, "Other Name", "other.com", "(512) 555-0199")
        assert score >= 30

    def test_no_match_low_confidence(self):
        place = VerifiedBusinessData(place_id="p1", name="Totally Different", address="123 Main St")
        score, result = _score_match(place, "Hilltop Dental", "hilltopdental.com", "")
        assert result.match_confidence == "low"

    def test_city_mismatch_rejected(self):
        """A result in the wrong city gets confidence='none' regardless of other signals."""
        place = VerifiedBusinessData(
            place_id="p1", name="Hilltop Dental", address="123 Main St",
            city="Dallas", website="https://hilltopdental.com",
        )
        score, result = _score_match(place, "Hilltop Dental", "hilltopdental.com", "", city="Austin")
        assert score == 0
        assert result.match_confidence == "none"


class TestIsTrusted:
    def test_none_data(self):
        assert is_trusted(None, "medium") is False

    def test_high_meets_medium(self):
        data = VerifiedBusinessData(place_id="p1", name="Test", address="a", match_confidence="high")
        assert is_trusted(data, "medium") is True

    def test_low_fails_medium(self):
        data = VerifiedBusinessData(place_id="p1", name="Test", address="a", match_confidence="low")
        assert is_trusted(data, "medium") is False

    def test_none_confidence_fails_all(self):
        data = VerifiedBusinessData(place_id="p1", name="Test", address="a", match_confidence="none")
        assert is_trusted(data, "low") is False


class TestFetchPlaceData:
    def test_returns_none_without_api_key(self):
        result = fetch_place_data("Test", "Austin", "TX", api_key="")
        assert result is None

    @patch("geo_agent.google_places.httpx.Client")
    def test_successful_lookup(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "places": [{
                "id": "place123",
                "displayName": {"text": "Hilltop Family Dental"},
                "formattedAddress": "4500 Medical Pkwy, Austin, TX 78756",
                "addressComponents": [
                    {"types": ["locality"], "longText": "Austin"},
                    {"types": ["administrative_area_level_1"], "longText": "TX"},
                    {"types": ["postal_code"], "longText": "78756"},
                ],
                "nationalPhoneNumber": "(512) 555-0199",
                "websiteUri": "https://hilltopdental.com",
                "rating": 4.7,
                "userRatingCount": 156,
                "location": {"latitude": 30.31, "longitude": -97.74},
                "businessStatus": "OPERATIONAL",
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = fetch_place_data(
            "Hilltop Family Dental", "Austin", "TX",
            domain="hilltopdental.com", api_key="test-key"
        )

        assert result is not None
        assert result.name == "Hilltop Family Dental"
        assert result.rating == 4.7
        assert result.review_count == 156
        assert result.domain_match is True
        assert result.match_confidence == "high"

    @patch("geo_agent.google_places.httpx.Client")
    def test_api_error_returns_none(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = Exception("API error")
        mock_client_cls.return_value = mock_client

        result = fetch_place_data("Test", "Austin", "TX", api_key="test-key")
        assert result is None

    @patch("geo_agent.google_places.httpx.Client")
    def test_empty_results_returns_none(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"places": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = fetch_place_data("Nonexistent", "Nowhere", "XX", api_key="test-key")
        assert result is None


class TestFetchNearbyCompetitors:
    def test_returns_empty_without_api_key(self):
        result = fetch_nearby_competitors(30.0, -97.0, "Test", api_key="")
        assert result == []

    @patch("geo_agent.google_places.httpx.Client")
    def test_filters_self_and_sorts(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "places": [
                {"id": "p1", "displayName": {"text": "Hilltop Family Dental"}, "rating": 4.7, "userRatingCount": 156, "formattedAddress": "addr1"},
                {"id": "p2", "displayName": {"text": "Walden Dental"}, "rating": 4.5, "userRatingCount": 200, "formattedAddress": "addr2"},
                {"id": "p3", "displayName": {"text": "River Rock Dental"}, "rating": 4.2, "userRatingCount": 80, "formattedAddress": "addr3"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = fetch_nearby_competitors(30.0, -97.0, "Hilltop Family Dental", api_key="test-key")

        # Self should be filtered out
        assert len(result) == 2
        assert result[0].name == "Walden Dental"  # Highest review count first
        assert result[1].name == "River Rock Dental"

    @patch("geo_agent.google_places.httpx.Client")
    def test_api_error_returns_empty(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        result = fetch_nearby_competitors(30.0, -97.0, "Test", api_key="test-key")
        assert result == []


class TestNameSimilarity:
    def test_identical_names(self):
        assert _name_similarity("FRB Law", "FRB Law") == 1.0

    def test_completely_different(self):
        assert _name_similarity("FRB Law", "Harold Dee Attorney") == 0.0

    def test_similar_with_suffix(self):
        # "group" is filler, so "FRB" matches "FRB" = 1.0
        assert _name_similarity("FRB Law", "FRB Law Group") == 1.0

    def test_partial_overlap(self):
        # "smith" overlaps but "jones" and "wilson" don't
        sim = _name_similarity("Smith Jones Legal", "Smith Wilson Legal")
        assert 0.3 <= sim <= 0.7

    def test_empty_strings(self):
        assert _name_similarity("", "Test") == 0.0
        assert _name_similarity("Test", "") == 0.0

    def test_all_filler_words(self):
        # All words are filler — returns 0.0
        assert _name_similarity("The Law Firm", "Law Office") == 0.0

    def test_self_filter_threshold(self):
        # Same business with slight variation should still be >= 0.5
        assert _name_similarity("Hilltop Family Dental", "Hilltop Dental") >= 0.5


class TestGetPlaceTypes:
    def test_dental(self):
        assert get_place_types("practice") == ["dentist"]

    def test_legal(self):
        assert get_place_types("legal") == ["lawyer"]

    def test_medical(self):
        assert get_place_types("medical") == ["doctor", "hospital"]

    def test_jewelry(self):
        assert get_place_types("jewelry") == ["jewelry_store"]

    def test_fitness(self):
        assert get_place_types("fitness") == ["gym"]

    def test_unknown_returns_empty(self):
        assert get_place_types("technology") == []
        assert get_place_types("unknown") == []

    def test_service_returns_empty_for_text_search(self):
        """Service/technology/ecommerce have no good place types — use text search."""
        assert get_place_types("service") == []
        assert get_place_types("ecommerce") == []
        assert get_place_types("product") == []


class TestValidateCompetitors:
    def test_excludes_by_name_keyword(self):
        comps = [
            CompetitorData(name="Optima Tax Relief", place_id="p1", rating=4.0, review_count=100),
            CompetitorData(name="Smith & Associates", place_id="p2", rating=4.5, review_count=200),
        ]
        result = validate_competitors(comps, "legal")
        assert len(result) == 1
        assert result[0].name == "Smith & Associates"

    def test_keeps_all_valid_competitors(self):
        comps = [
            CompetitorData(name="Downtown Law", place_id="p1", rating=4.0, review_count=100),
            CompetitorData(name="River City Legal", place_id="p2", rating=4.5, review_count=200),
        ]
        result = validate_competitors(comps, "legal")
        assert len(result) == 2

    def test_dental_excludes_veterinary(self):
        comps = [
            CompetitorData(name="Happy Paws Vet Clinic", place_id="p1", rating=4.8, review_count=300),
            CompetitorData(name="Bright Smile Dentistry", place_id="p2", rating=4.2, review_count=150),
        ]
        result = validate_competitors(comps, "practice")
        assert len(result) == 1
        assert result[0].name == "Bright Smile Dentistry"

    def test_medical_excludes_dental(self):
        comps = [
            CompetitorData(name="Main Street Dentist", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="City Health Clinic", place_id="p2", rating=4.3, review_count=150),
        ]
        result = validate_competitors(comps, "medical")
        assert len(result) == 1
        assert result[0].name == "City Health Clinic"

    def test_empty_list(self):
        assert validate_competitors([], "legal") == []

    def test_unknown_business_type_keeps_all(self):
        comps = [
            CompetitorData(name="Some Business", place_id="p1", rating=4.0, review_count=100),
        ]
        result = validate_competitors(comps, "technology")
        assert len(result) == 1

    @patch("geo_agent.google_places.httpx.Client")
    def test_website_validation_filters_wrong_industry(self, mock_client_cls):
        """Competitor with website lacking industry keywords gets filtered."""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>Tax preparation and accounting services</body></html>"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        comps = [
            CompetitorData(
                name="Johnson Associates",
                place_id="p1", rating=4.0, review_count=100,
                website="https://johnson-tax.com",
            ),
        ]
        result = validate_competitors(comps, "legal")
        assert len(result) == 0

    @patch("geo_agent.google_places.httpx.Client")
    def test_website_validation_keeps_correct_industry(self, mock_client_cls):
        """Competitor with industry-relevant website is kept."""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>Personal injury attorney. Our lawyers handle litigation.</body></html>"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        comps = [
            CompetitorData(
                name="Johnson Law Firm",
                place_id="p1", rating=4.0, review_count=100,
                website="https://johnsonlaw.com",
            ),
        ]
        result = validate_competitors(comps, "legal")
        assert len(result) == 1


class TestVerifyCustomer:
    @patch("geo_agent.google_places.fetch_nearby_competitors")
    @patch("geo_agent.google_places.fetch_place_data")
    def test_returns_none_without_api_key(self, mock_fetch, mock_nearby):
        from geo_agent.config import Customer
        customer = Customer(id="test", name="Test", domain="test.com", city="Austin", state="TX")

        with patch("geo_agent.secrets.get_secrets") as mock_secrets:
            mock_secrets.return_value.get.return_value = ""
            result, comps = verify_customer(customer)

        assert result is None
        assert comps == []
        mock_fetch.assert_not_called()


class TestNonDentalCompetitorDiscovery:
    """Tests for industry-aware competitor discovery (non-dental verticals)."""

    def test_jewelry_place_types(self):
        assert get_place_types("jewelry") == ["jewelry_store"]

    def test_salon_place_types(self):
        assert get_place_types("salon") == ["beauty_salon", "hair_care"]

    def test_auto_place_types(self):
        assert get_place_types("auto") == ["car_dealer", "car_repair"]

    def test_finance_place_types(self):
        assert get_place_types("finance") == ["accounting"]

    def test_technology_empty_for_text_search(self):
        assert get_place_types("technology") == []

    def test_service_empty_for_text_search(self):
        assert get_place_types("service") == []

    def test_jewelry_excludes_dental(self):
        """Dental clinics should NOT appear as competitors for a jewelry business."""
        comps = [
            CompetitorData(name="Bright Smile Dentist", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="Gold Exchange Co", place_id="p2", rating=4.3, review_count=150),
            CompetitorData(name="Main Street Dental", place_id="p3", rating=4.0, review_count=100),
        ]
        result = validate_competitors(comps, "jewelry")
        assert len(result) == 1
        assert result[0].name == "Gold Exchange Co"

    def test_service_excludes_dental(self):
        comps = [
            CompetitorData(name="Family Dentistry Center", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="Pro Consulting Group", place_id="p2", rating=4.0, review_count=100),
        ]
        result = validate_competitors(comps, "service")
        assert len(result) == 1
        assert result[0].name == "Pro Consulting Group"

    def test_retail_excludes_lawyers(self):
        comps = [
            CompetitorData(name="Smith & Associates Lawyer", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="Bob's Hardware Store", place_id="p2", rating=4.0, review_count=100),
        ]
        result = validate_competitors(comps, "retail")
        assert len(result) == 1
        assert result[0].name == "Bob's Hardware Store"

    @patch("geo_agent.google_places.httpx.Client")
    def test_text_search_fallback_used_when_no_place_types(self, mock_client_cls):
        """When place_types is empty and text_query is set, use searchText API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "places": [
                {
                    "id": "place1",
                    "displayName": {"text": "Gold Buyers Express"},
                    "rating": 4.2,
                    "userRatingCount": 80,
                    "formattedAddress": "123 Main St, Springfield, VA",
                    "websiteUri": "https://goldbuyersexpress.com",
                    "primaryType": "store",
                },
            ]
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = fetch_nearby_competitors(
            lat=38.7, lng=-77.2,
            practice_name="Paradigm Experts",
            api_key="test-key",
            place_types=None,
            text_query="gold buyer near Springfield VA",
        )

        assert len(result) == 1
        assert result[0].name == "Gold Buyers Express"
        # Verify it used the text search URL, not nearby search
        call_args = mock_client.post.call_args
        assert "searchText" in call_args[0][0]
        assert call_args[1]["json"]["textQuery"] == "gold buyer near Springfield VA"

    @patch("geo_agent.google_places.httpx.Client")
    def test_nearby_search_used_when_place_types_set(self, mock_client_cls):
        """When place_types is set, use searchNearby API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"places": []}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        fetch_nearby_competitors(
            lat=30.0, lng=-97.0,
            practice_name="Test Dental",
            api_key="test-key",
            place_types=["dentist"],
        )

        call_args = mock_client.post.call_args
        assert "searchNearby" in call_args[0][0]

    @patch("geo_agent.google_places.validate_competitors")
    @patch("geo_agent.google_places.fetch_nearby_competitors")
    @patch("geo_agent.google_places.fetch_place_data")
    def test_verify_customer_builds_text_query_for_niche(self, mock_fetch, mock_nearby, mock_validate):
        """verify_customer should build text_query from specialties for niche businesses."""
        from geo_agent.config import Customer

        mock_fetch.return_value = VerifiedBusinessData(
            place_id="p1", name="Paradigm Experts",
            address="123 Main St", city="Springfield", state="VA",
            lat=38.7, lng=-77.2, match_confidence="high",
        )
        mock_nearby.return_value = []
        mock_validate.return_value = []

        customer = Customer(
            id="paradigm", name="Paradigm Experts",
            domain="paradigmexperts.com",
            city="Springfield", state="VA",
            business_type="jewelry",
            specialties=["gold buyer", "silver buyer"],
        )

        with patch("geo_agent.secrets.get_secrets") as mock_secrets:
            mock_secrets.return_value.get.return_value = "test-key"
            verify_customer(customer, api_key="test-key")

        # Should have called with text_query since jewelry has place types
        call_kwargs = mock_nearby.call_args[1]
        assert call_kwargs.get("place_types") == ["jewelry_store"]

    @patch("geo_agent.google_places.validate_competitors")
    @patch("geo_agent.google_places.fetch_nearby_competitors")
    @patch("geo_agent.google_places.fetch_place_data")
    def test_verify_customer_text_query_for_no_place_types(self, mock_fetch, mock_nearby, mock_validate):
        """verify_customer should use text_query when business has no place types."""
        from geo_agent.config import Customer

        mock_fetch.return_value = VerifiedBusinessData(
            place_id="p1", name="TechCorp",
            address="456 Tech Blvd", city="Austin", state="TX",
            lat=30.3, lng=-97.7, match_confidence="high",
        )
        mock_nearby.return_value = []
        mock_validate.return_value = []

        customer = Customer(
            id="techcorp", name="TechCorp",
            domain="techcorp.io",
            city="Austin", state="TX",
            business_type="technology",
            specialties=["cloud infrastructure", "DevOps"],
        )

        with patch("geo_agent.secrets.get_secrets") as mock_secrets:
            mock_secrets.return_value.get.return_value = "test-key"
            verify_customer(customer, api_key="test-key")

        call_kwargs = mock_nearby.call_args[1]
        assert call_kwargs.get("text_query") == "cloud infrastructure near Austin TX"
        assert call_kwargs.get("place_types") is None


class TestDynamicVerticalEdgeCases:
    """Regression tests for dynamic vertical support (P1 fixes)."""

    def test_medical_has_multiple_place_types(self):
        """Medical should search for both doctors and hospitals."""
        types = get_place_types("medical")
        assert "doctor" in types
        assert "hospital" in types
        assert len(types) >= 2

    def test_dental_default_for_practice(self):
        """'practice' business_type should default to dental."""
        assert get_place_types("practice") == ["dentist"]

    def test_validate_excludes_cross_vertical_by_name(self):
        """A dental clinic should not appear as a legal competitor."""
        comps = [
            CompetitorData(name="Bright Smile Dental Care", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="Smith Attorney at Law", place_id="p2", rating=4.3, review_count=150),
        ]
        result = validate_competitors(comps, "legal")
        names = [c.name for c in result]
        assert "Smith Attorney at Law" in names
        assert "Bright Smile Dental Care" not in names

    def test_validate_keeps_ambiguous_names_for_unknown_vertical(self):
        """Unknown verticals should keep all competitors (no keyword filter)."""
        comps = [
            CompetitorData(name="Acme Solutions", place_id="p1", rating=4.0, review_count=100),
            CompetitorData(name="Widget Corp", place_id="p2", rating=4.2, review_count=80),
        ]
        result = validate_competitors(comps, "saas")
        assert len(result) == 2

    def test_validate_medical_excludes_lawyers(self):
        """Law firms should not show up as medical competitors."""
        comps = [
            CompetitorData(name="Johnson & Associates Law Firm", place_id="p1", rating=4.5, review_count=200),
            CompetitorData(name="City Health Medical Center", place_id="p2", rating=4.3, review_count=150),
        ]
        result = validate_competitors(comps, "medical")
        names = [c.name for c in result]
        assert "City Health Medical Center" in names
        assert "Johnson & Associates Law Firm" not in names

    def test_validate_legal_excludes_dental(self):
        """Dental practices should not show up as legal competitors."""
        comps = [
            CompetitorData(name="Family Dentistry of Springfield", place_id="p1", rating=4.8, review_count=300),
            CompetitorData(name="Springfield Legal Associates", place_id="p2", rating=4.5, review_count=150),
        ]
        result = validate_competitors(comps, "legal")
        names = [c.name for c in result]
        assert "Springfield Legal Associates" in names
        assert "Family Dentistry of Springfield" not in names

    @patch("geo_agent.google_places.httpx.Client")
    def test_nearby_search_passes_multiple_place_types(self, mock_client_cls):
        """When place_types has multiple entries, all are passed to searchNearby."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"places": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        fetch_nearby_competitors(
            lat=30.0, lng=-97.0,
            practice_name="Test Medical",
            api_key="test-key",
            place_types=["doctor", "hospital"],
        )

        call_args = mock_client.post.call_args
        body = call_args[1]["json"]
        assert body["includedTypes"] == ["doctor", "hospital"]

    @patch("geo_agent.google_places.httpx.Client")
    def test_text_search_fallback_when_nearby_returns_empty(self, mock_client_cls):
        """If searchNearby returns no results and text_query is set, fall back to searchText."""
        # First call (searchNearby) returns empty, second call (searchText) returns results
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"places": []}
        empty_resp.raise_for_status = MagicMock()

        text_resp = MagicMock()
        text_resp.json.return_value = {
            "places": [{
                "id": "p1",
                "displayName": {"text": "Gold Exchange"},
                "rating": 4.2,
                "userRatingCount": 50,
                "formattedAddress": "123 Main St",
            }]
        }
        text_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        # No place_types and text_query provided → goes to text search directly
        mock_client.post.return_value = text_resp
        mock_client_cls.return_value = mock_client

        result = fetch_nearby_competitors(
            lat=38.7, lng=-77.2,
            practice_name="Paradigm Experts",
            api_key="test-key",
            place_types=None,
            text_query="gold buyer near Springfield VA",
        )

        assert len(result) == 1
        assert result[0].name == "Gold Exchange"
