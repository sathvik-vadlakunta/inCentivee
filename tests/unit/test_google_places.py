"""Tests for google_places.py — Places API verification and competitor discovery."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from geo_agent.google_places import (
    CompetitorData,
    VerifiedBusinessData,
    _normalize_domain,
    _normalize_phone,
    _score_match,
    fetch_nearby_competitors,
    fetch_place_data,
    is_trusted,
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
