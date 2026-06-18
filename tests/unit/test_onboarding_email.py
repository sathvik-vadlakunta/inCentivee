"""Tests for the dynamic onboarding-email checklist builder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard"))

import app  # noqa: E402


CUST = {"name": "Sojo Dental", "platform": "squarespace", "city": "South Jordan", "state": "UT"}
CMS_STEPS = "**Squarespace** — add kdoherty@practicerank.ai as contributor"


def test_pending_items_only_list_outstanding():
    access = [
        {"platform": "gsc", "status": "granted"},
        {"platform": "ga", "status": "pending"},
        {"platform": "gtm", "status": "pending"},
        {"platform": "gbp", "status": "granted"},
        {"platform": "squarespace", "status": "pending"},
        {"platform": "cloudflare", "status": "pending"},
    ]
    full, pending = app._onboarding_blocks(CUST, access, {"nap_confirmed": True}, CMS_STEPS)
    # Granted/confirmed items show as ✓ in the full list, absent from pending.
    assert "✓ **Google Search Console" in full
    assert "✓ **Google Business Profile" in full
    assert "Google Search Console" not in pending
    assert "Google Business Profile" not in pending
    # Outstanding ones appear in pending.
    assert "Google Analytics 4" in pending
    assert "Google Tag Manager" in pending
    # The new non-access asks are present when not yet satisfied.
    assert "logo" in pending.lower()
    assert "services & service-area" in pending.lower()
    # NAP was confirmed, so it's not in pending.
    assert "exact business info" not in pending.lower()


def test_all_satisfied_shows_nothing_outstanding():
    access = [
        {"platform": p, "status": "granted"}
        for p in ("gsc", "ga", "gtm", "gbp", "squarespace", "cloudflare")
    ]
    checklist = {"nap_confirmed": True, "brand_assets_received": True, "services_confirmed": True}
    full, pending = app._onboarding_blocks(CUST, access, checklist, CMS_STEPS)
    assert "no outstanding items" in pending.lower()
    assert "1." not in full  # nothing numbered — everything is ✓


def test_cms_item_uses_platform_access_steps():
    access = [{"platform": "squarespace", "status": "pending"}]
    full, pending = app._onboarding_blocks(CUST, access, {}, CMS_STEPS)
    assert CMS_STEPS in full
    assert CMS_STEPS in pending
