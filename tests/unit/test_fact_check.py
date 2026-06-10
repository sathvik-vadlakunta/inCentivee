"""Tests for the pre-publish fact-check (grounding generated content)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from geo_agent.config import Customer, Provider
from geo_agent.fact_check import build_profile, fact_check_html


def _customer() -> Customer:
    return Customer(
        id="c1", name="Hilltop Dental", domain="hilltop.com", city="Austin", state="TX",
        services=["cleanings", "implants"],
        providers=[Provider(name="Dr. Smith", credentials="DDS")],
    )


def _client_returning(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    client = MagicMock()
    client.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = msg
    return client


def test_build_profile_includes_services_and_credentials():
    profile = build_profile(_customer())
    assert "cleanings, implants" in profile
    assert "Dr. Smith (DDS)" in profile
    # No verified quotes -> explicit prohibition
    assert "no testimonials" in profile.lower()


def test_clean_content_returns_no_findings():
    client = _client_returning("[]")
    findings = fact_check_html(_customer(), "<p>We offer cleanings.</p>", client=client)
    assert findings == []


def test_flags_unsupported_claim():
    payload = json.dumps([{"claim": "Dr. Jones, MD", "reason": "provider not in profile"}])
    client = _client_returning(payload)
    findings = fact_check_html(_customer(), "<p>See Dr. Jones, MD for surgery.</p>", client=client)
    assert len(findings) == 1
    assert findings[0]["claim"] == "Dr. Jones, MD"


def test_empty_html_skips_call():
    client = _client_returning("should not be used")
    assert fact_check_html(_customer(), "", client=client) == []
    client.messages.stream.assert_not_called()


def test_fails_open_on_api_error():
    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("api down")
    # An infra error must not block publishing (human approval already happened).
    assert fact_check_html(_customer(), "<p>hi</p>", client=client) == []
