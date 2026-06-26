"""Tests for geo_agent.gbp_client (read-only M1). All HTTP is mocked — no live GBP calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from geo_agent.gbp_client import (
    DEFAULT_PERF_METRICS,
    GBPClient,
    GBPLocation,
    _parse_location,
)


def _client(**creds):
    base = dict(client_id="cid", client_secret="sec", refresh_token="rt")
    base.update(creds)
    return GBPClient(**base)


class TestAuth:
    def test_available_true_when_all_creds(self):
        assert _client().available() is True

    def test_available_false_when_missing(self):
        assert GBPClient(client_id="", client_secret="", refresh_token="").available() is False

    def test_access_token_none_when_unconfigured(self):
        assert GBPClient(client_id="", client_secret="", refresh_token="")._access_token() is None

    def test_token_is_cached_until_near_expiry(self):
        c = _client()
        with patch("geo_agent.gbp_client.httpx.post") as mp:
            mp.return_value = MagicMock(
                raise_for_status=lambda: None,
                json=lambda: {"access_token": "tok123", "expires_in": 3600},
            )
            assert c._access_token() == "tok123"
            assert c._access_token() == "tok123"  # cached
            mp.assert_called_once()  # only one refresh

    def test_token_refresh_failure_returns_none(self):
        c = _client()
        with patch("geo_agent.gbp_client.httpx.post", side_effect=RuntimeError("boom")):
            assert c._access_token() is None


class TestResourceNameMapping:
    """The v1 ↔ v4 ↔ performance resource-name split is the #1 GBP gotcha."""

    def test_v4_name_built_from_account_plus_location_id(self):
        loc = GBPLocation(name="locations/123", account="accounts/456")
        assert loc.v4_name == "accounts/456/locations/123"

    def test_perf_name_is_locations_form(self):
        assert GBPLocation(name="locations/123", account="accounts/456").perf_name == "locations/123"
        # even if a full path sneaks in, it normalizes
        assert GBPLocation(name="accounts/456/locations/123", account="accounts/456").perf_name == "locations/123"


class TestParseLocation:
    def test_parses_title_phone_website_address(self):
        raw = {
            "name": "locations/999",
            "title": "Acme Dental",
            "phoneNumbers": {"primaryPhone": "(555) 111-2222"},
            "websiteUri": "https://acme.com",
            "storefrontAddress": {
                "addressLines": ["123 Main St"],
                "locality": "Westfield", "administrativeArea": "NJ", "postalCode": "07090",
            },
            "metadata": {"placeId": "PLACE123"},
        }
        loc = _parse_location(raw, "accounts/1")
        assert loc.title == "Acme Dental"
        assert loc.phone == "(555) 111-2222"
        assert loc.website == "https://acme.com"
        assert "123 Main St" in loc.address and "Westfield" in loc.address
        assert loc.place_id == "PLACE123"
        assert loc.account == "accounts/1"


class TestReadPaths:
    def test_list_locations_paginates_and_parses(self):
        c = _client()
        pages = {
            "accounts": {"accounts": [{"name": "accounts/1"}]},
            "p1": {"locations": [{"name": "locations/1", "title": "One"}], "nextPageToken": "tok2"},
            "p2": {"locations": [{"name": "locations/2", "title": "Two"}]},
        }
        calls = {"n": 0}

        def fake_get(url, params=None):
            if url.endswith("/accounts"):
                return pages["accounts"]
            calls["n"] += 1
            return pages["p1"] if calls["n"] == 1 else pages["p2"]

        with patch.object(c, "_get", side_effect=fake_get):
            locs = c.list_locations()
        assert [l.title for l in locs] == ["One", "Two"]
        assert calls["n"] == 2  # followed nextPageToken

    def test_find_location_exact_and_substring(self):
        c = _client()
        locs = [
            GBPLocation(name="locations/1", account="accounts/1", title="Downtown Dental"),
            GBPLocation(name="locations/2", account="accounts/1", title="Westfield Smiles"),
        ]
        with patch.object(c, "list_locations", return_value=locs):
            assert c.find_location("Downtown Dental").name == "locations/1"
            assert c.find_location("downtown").name == "locations/1"
            assert c.find_location("nonexistent") is None

    def test_list_reviews_hits_v4_resource(self):
        c = _client()
        loc = GBPLocation(name="locations/5", account="accounts/9")
        captured = {}

        def fake_get(url, params=None):
            captured["url"] = url
            return {"reviews": [{"reviewId": "r1"}]}

        with patch.object(c, "_get", side_effect=fake_get):
            reviews = c.list_reviews(loc)
        assert captured["url"].endswith("/accounts/9/locations/5/reviews")
        assert reviews[0]["reviewId"] == "r1"

    def test_get_performance_sends_metrics_and_date_range(self):
        c = _client()
        loc = GBPLocation(name="locations/5", account="accounts/9")
        captured = {}

        def fake_get(url, params=None):
            captured["url"] = url
            captured["params"] = params
            return {"multiDailyMetricTimeSeries": []}

        with patch.object(c, "_get", side_effect=fake_get):
            c.get_performance(loc, "2026-05-01", "2026-05-31")
        assert captured["url"].endswith("locations/5:fetchMultiDailyMetricsTimeSeries")
        metric_vals = [v for k, v in captured["params"] if k == "dailyMetrics"]
        assert metric_vals == DEFAULT_PERF_METRICS
        # date range params present
        assert ("dailyRange.start_date.year", 2026) in captured["params"]
        assert ("dailyRange.end_date.day", 31) in captured["params"]

    def test_read_methods_failsafe_to_empty(self):
        c = _client()
        with patch.object(c, "_get", return_value=None):
            assert c.list_accounts() == []
            assert c.list_locations() == []
            assert c.list_reviews(GBPLocation(name="locations/1", account="accounts/1")) == []


class TestWriteStubsAreGuarded:
    @pytest.mark.parametrize("call", [
        lambda c, loc: c.create_post(loc, {}),
        lambda c, loc: c.upload_photo(loc, {}),
        lambda c, loc: c.update_info(loc, {}),
    ])
    def test_write_paths_not_implemented_yet(self, call):
        c = _client()
        loc = GBPLocation(name="locations/1", account="accounts/1")
        with pytest.raises(NotImplementedError):
            call(c, loc)

    def test_reply_review_not_implemented(self):
        with pytest.raises(NotImplementedError):
            _client().reply_review("accounts/1/locations/1/reviews/r1", "thanks!")
