"""Tests for the GA4 conversion-tracking client (R3).

These never touch the network: the BetaAnalyticsDataClient and credential
loaders are monkeypatched, so they pass whether or not google-analytics-data is
installed.
"""

from __future__ import annotations

import pytest

from geo_agent import ga4_client
from geo_agent.db import CustomerDB


@pytest.fixture
def db(tmp_path):
    database = CustomerDB(db_path=str(tmp_path / "ga4.db"))
    database.add_customer(id="c1", name="Test Dental", domain="test.com")
    yield database
    database.close()


# --- helpers to fake a GA4 response ----------------------------------------

class _DV:
    def __init__(self, value): self.value = value


class _MV:
    def __init__(self, value): self.value = value


class _Row:
    def __init__(self, date, event, channel, count):
        self.dimension_values = [_DV(date), _DV(event), _DV(channel)]
        self.metric_values = [_MV(str(count))]


def _use_rows(monkeypatch, rows):
    """Stub the network boundary: a non-None client + canned report rows.

    This isolates the row→DB mapping logic from the GA4 SDK (which is a
    server-only dependency, not installed in the test env)."""
    monkeypatch.setattr(ga4_client, "_client", lambda: object())
    monkeypatch.setattr(ga4_client, "_run_report_paged", lambda *a, **k: rows)


def _normalize_property_id_cases():
    return [("123456789", "123456789"), ("properties/123", "123"),
            (123, "123"), (None, None), ("", None), ("abc", None)]


@pytest.mark.parametrize("raw,expected", _normalize_property_id_cases())
def test_normalize_property_id(raw, expected):
    assert ga4_client._normalize_property_id(raw) == expected


def test_skips_when_no_property(db):
    # No ga4 integration configured → None, nothing written.
    assert ga4_client.track_conversions(db, "c1") is None
    assert db.get_conversions("c1", "2000-01-01", "2100-01-01") == {}


def test_skips_when_no_credentials(db, monkeypatch):
    db.save_integration("c1", "ga4", {"property_id": "123"}, "configured")
    monkeypatch.setattr(ga4_client, "_client", lambda: None)
    assert ga4_client.track_conversions(db, "c1") is None


def test_track_conversions_writes_and_normalizes(db, monkeypatch):
    db.save_integration("c1", "ga4", {"property_id": "properties/123456789"}, "configured")
    rows = [
        _Row("20260610", "phone_click", "Organic Search", 3),
        _Row("20260610", "generate_lead", "Organic Search", 2),   # → form_submit
        _Row("20260611", "book_appointment", "Direct", 1),         # → appointment_request
        _Row("20260611", "scroll", "Organic Search", 99),          # not a lead → ignored by filter map
        _Row("20260611", "form_submit", "Organic Search", 0),      # zero count → skipped
    ]
    _use_rows(monkeypatch, rows)

    written = ga4_client.track_conversions(db, "c1", days=30)
    assert written == 3  # scroll + zero-count excluded

    # organic totals: phone 3, form 2 (appt is Direct, not organic)
    organic = db.get_conversions("c1", "2026-06-01", "2026-06-30", channel="organic")
    assert organic == {"phone_click": 3, "form_submit": 2}
    # appointment landed under direct
    direct = db.get_conversions("c1", "2026-06-01", "2026-06-30", channel="direct")
    assert direct == {"appointment_request": 1}

    # integration marked active
    integ = db.get_integration("c1", "ga4")
    assert integ["status"] == "active"


def test_track_conversions_is_idempotent(db, monkeypatch):
    db.save_integration("c1", "ga4", {"property_id": "123"}, "configured")
    _use_rows(monkeypatch, [_Row("20260610", "phone_click", "Organic Search", 5)])
    ga4_client.track_conversions(db, "c1")
    ga4_client.track_conversions(db, "c1")  # re-run same day
    organic = db.get_conversions("c1", "2026-06-01", "2026-06-30", channel="organic")
    assert organic == {"phone_click": 5}  # upsert, not doubled


def test_report_failure_marks_error(db, monkeypatch):
    db.save_integration("c1", "ga4", {"property_id": "123"}, "configured")
    monkeypatch.setattr(ga4_client, "_client", lambda: object())
    monkeypatch.setattr(ga4_client, "_run_report_paged", lambda *a, **k: None)
    assert ga4_client.track_conversions(db, "c1") is None
    assert db.get_integration("c1", "ga4")["status"] == "error"


def test_custom_conversion_events_from_config(db, monkeypatch):
    db.save_integration("c1", "ga4",
                        {"property_id": "123", "conversion_events": ["chat_started"]},
                        "configured")
    _use_rows(monkeypatch, [_Row("20260610", "chat_started", "Organic Search", 4)])
    written = ga4_client.track_conversions(db, "c1")
    assert written == 1
    organic = db.get_conversions("c1", "2026-06-01", "2026-06-30", channel="organic")
    assert organic == {"chat_started": 4}  # unknown event normalizes to itself
