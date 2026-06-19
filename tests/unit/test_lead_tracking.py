"""The lead-tracking snippet must fire the exact GA4 events the puller ingests."""

from __future__ import annotations

from geo_agent.ga4_client import DEFAULT_CONVERSION_EVENTS
from geo_agent.lead_tracking import INSTALL_STEPS, lead_tracker_snippet


def test_snippet_fires_the_three_lead_events():
    js = lead_tracker_snippet()
    for ev in ("phone_click", "form_submit", "appointment_request"):
        assert f"'{ev}'" in js, f"snippet should fire {ev}"


def test_events_are_recognized_by_ga4_puller():
    # Every event the snippet fires must be in the GA4 ingestion map, or the
    # report would never see the leads.
    recognized = set(DEFAULT_CONVERSION_EVENTS)
    for ev in ("phone_click", "form_submit", "appointment_request"):
        assert ev in recognized


def test_snippet_is_idempotent_and_selfcontained():
    js = lead_tracker_snippet()
    assert "__prLeadsInit" in js          # re-init guard
    assert "<script>" in js and "</script>" in js
    assert "gtag" in js and "dataLayer" in js  # works with GA4 or GTM


def test_install_steps_cover_main_platforms():
    for p in ("gtm", "webflow", "squarespace", "wordpress", "managed"):
        assert p in INSTALL_STEPS and INSTALL_STEPS[p]
