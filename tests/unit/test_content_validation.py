"""Tests for the deterministic content validator (geo_agent.content_validation).

These guard the failure classes found in the Downtown Dental content review: unverified
credential claims, marketing superlatives, dangerous YMYL absolutes, and future-dated
"freshness" stamps — all caught with no LLM/network so they're fast and deterministic.
"""

from __future__ import annotations

from datetime import date

import pytest

from geo_agent.config import Customer, Provider
from geo_agent.content_validation import (
    BLOCK,
    WARN,
    auto_soften,
    summarize,
    validate_html_claims,
)

TODAY = date(2026, 6, 26)


def _cust(**kw) -> Customer:
    base = dict(id="c", name="Test Dental", domain="t.com", city="Westfield", state="NJ")
    base.update(kw)
    return Customer(**base)


# Mirrors the real Downtown Dental profile: prosthodontist + ACP Fellow, NOT board-certified.
DOWNTOWN = _cust(
    specialties=["Prosthodontics"],
    providers=[
        Provider(
            name="Dr. Paul Zhivago",
            credentials="DDS",
            specialties=["Prosthodontics"],
            bio="Fellow of the American College of Prosthodontists. NYU faculty.",
        )
    ],
)


def _categories(findings):
    return {f["category"] for f in findings}


class TestCredentialGrounding:
    def test_unlisted_board_certified_is_blocked(self):
        html = "<p>Dr. Zhivago is a Board Certified Prosthodontist in Westfield.</p>"
        findings = validate_html_claims(html, DOWNTOWN, today=TODAY)
        cred = [f for f in findings if f["category"] == "credential"]
        assert cred and cred[0]["severity"] == BLOCK

    def test_board_certified_passes_when_listed(self):
        cust = _cust(
            providers=[Provider(name="Dr. X", credentials="DDS, Board Certified Prosthodontist")]
        )
        html = "<p>Dr. X is a Board Certified Prosthodontist.</p>"
        assert "credential" not in _categories(validate_html_claims(html, cust, today=TODAY))

    def test_specialist_ok_when_practice_has_recognized_specialty(self):
        # Prosthodontics is an ADA-recognized specialty → "specialist" is grounded.
        html = "<p>Our prosthodontic specialist serves Westfield, NJ.</p>"
        assert "credential" not in _categories(validate_html_claims(html, DOWNTOWN, today=TODAY))

    def test_specialist_flagged_for_general_practice(self):
        cust = _cust(providers=[Provider(name="Dr. Y", credentials="DDS")])  # no specialty
        html = "<p>Dr. Y is a cosmetic specialist.</p>"
        assert "credential" in _categories(validate_html_claims(html, cust, today=TODAY))

    def test_diplomate_blocked_when_absent(self):
        html = "<p>A Diplomate of the American Board of Prosthodontics.</p>"
        assert "credential" in _categories(validate_html_claims(html, DOWNTOWN, today=TODAY))

    def test_works_with_dict_customer(self):
        # The docx path passes a config Customer, but the validator must also tolerate dicts.
        cust = {"specialties": [], "providers": [{"name": "Dr Z", "credentials": "DDS"}]}
        html = "<p>Board Certified Prosthodontist.</p>"
        assert "credential" in _categories(validate_html_claims(html, cust, today=TODAY))


class TestYmylAbsolutes:
    @pytest.mark.parametrize("phrase", ["painless", "pain-free", "guaranteed", "completely safe"])
    def test_absolutes_blocked(self, phrase):
        html = f"<p>Our {phrase} treatment is great.</p>"
        findings = validate_html_claims(html, DOWNTOWN, today=TODAY)
        assert "ymyl-absolute" in _categories(findings)

    def test_lasts_a_lifetime_blocked(self):
        html = "<p>Implants that last a lifetime.</p>"
        assert "ymyl-absolute" in _categories(validate_html_claims(html, DOWNTOWN, today=TODAY))


class TestSuperlatives:
    @pytest.mark.parametrize("phrase", ["the best dentist", "#1 in NJ", "premier practice",
                                        "world-class care", "top-rated"])
    def test_superlatives_warn(self, phrase):
        html = f"<p>We are {phrase}.</p>"
        findings = validate_html_claims(html, DOWNTOWN, today=TODAY)
        sup = [f for f in findings if f["category"] == "superlative"]
        assert sup and sup[0]["severity"] == WARN


class TestFutureDates:
    def test_future_iso_and_month_blocked(self):
        html = ('<time datetime="2026-08-01">x</time> Last updated: August 2026')
        findings = validate_html_claims(html, DOWNTOWN, today=TODAY)
        assert "future-date" in _categories(findings)

    def test_past_and_present_dates_ok(self):
        html = '<time datetime="2026-06-01">x</time> Last updated: June 2026'
        assert "future-date" not in _categories(validate_html_claims(html, DOWNTOWN, today=TODAY))

    def test_clean_content_has_no_findings(self):
        html = ("<p>Dr. Zhivago provides prosthodontic care in Westfield, NJ. "
                "Last updated: June 2026.</p>")
        assert validate_html_claims(html, DOWNTOWN, today=TODAY) == []


class TestAutoSoften:
    def test_softens_painless_and_lifetime(self):
        html = "<p>Painless implants that last a lifetime.</p>"
        out, changes = auto_soften(html, today=TODAY)
        assert "painless" not in out.lower()
        assert "last a lifetime" not in out.lower()
        assert changes

    def test_rewrites_future_last_updated_to_current_month(self):
        out, changes = auto_soften("Last updated: August 2026", today=TODAY)
        assert "June 2026" in out
        assert "August 2026" not in out

    def test_leaves_clean_content_untouched(self):
        html = "<p>Comfortable care in Westfield. Last updated: June 2026.</p>"
        out, changes = auto_soften(html, today=TODAY)
        assert out == html and changes == []


def test_summarize_counts():
    findings = [
        {"severity": BLOCK, "category": "credential", "message": "x"},
        {"severity": BLOCK, "category": "future-date", "message": "y"},
        {"severity": WARN, "category": "superlative", "message": "z"},
    ]
    assert summarize(findings) == (2, 1)
