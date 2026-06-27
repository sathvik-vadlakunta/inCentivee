"""The anti-fabrication gate: only quotes that appear verbatim in the source are stored."""

from __future__ import annotations

from unittest.mock import patch

from geo_agent import quote_sourcer as qs

SOURCE = (
    "Gold demand stayed resilient this quarter. "
    "“We expect central-bank buying to remain a structural driver of demand,” "
    "said John Reade, chief market strategist at the World Gold Council. "
    "Analysts noted prices held near record highs."
)
NORM = qs._normalize(SOURCE)


def test_verify_accepts_real_verbatim_quote():
    real = "We expect central-bank buying to remain a structural driver of demand"
    assert qs._verify(real, NORM) is True


def test_verify_accepts_with_curly_quotes_and_dashes():
    # Same quote but with smart punctuation — normalization must still match.
    real = "“We expect central-bank buying to remain a structural driver of demand,”"
    assert qs._verify(real, NORM) is True


def test_verify_rejects_fabricated_quote():
    fake = "Gold will absolutely double in value by next year, guaranteed for every investor"
    assert qs._verify(fake, NORM) is False


def test_verify_rejects_paraphrase_not_present_verbatim():
    paraphrase = "Central bank purchases are a long-term factor supporting gold demand levels"
    assert qs._verify(paraphrase, NORM) is False


def test_verify_rejects_too_short_or_too_few_words():
    assert qs._verify("held near record highs", NORM) is False  # < 40 chars / few words
    assert qs._verify("", NORM) is False


def test_normalize_unifies_punctuation_and_whitespace():
    assert qs._normalize("“Hello —  World”") == '"hello - world"'


def test_source_quotes_stores_only_verified(tmp_path, monkeypatch):
    from geo_agent.db import CustomerDB

    db = CustomerDB(db_path=str(tmp_path / "q.db"))
    db.conn.execute(
        "INSERT INTO customers (id,name,domain,business_type,status,platform) "
        "VALUES (?,?,?,?,?,?)",
        ("c1", "Test Metals", "t.example", "precious_metals_buyer", "active", "webflow"),
    )
    db.conn.commit()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    candidates = [
        {"quote": "We expect central-bank buying to remain a structural driver of demand",
         "speaker": "John Reade", "role": "Chief Market Strategist, World Gold Council"},
        {"quote": "Gold will absolutely double in value by next year, guaranteed",
         "speaker": "Nobody", "role": "Fabricated"},
    ]

    # Isolate to the single provided URL (skip the per-vertical seed sources).
    with patch.object(qs, "_sources_for", return_value=[]), \
         patch.object(qs, "_fetch", return_value=("plaintext", NORM)), \
         patch.object(qs, "_extract_candidates", return_value=candidates), \
         patch("anthropic.Anthropic"):
        report = qs.source_quotes_for_customer(db, "c1", extra_urls=["https://example.com/a"])

    stored = db.get_customer("c1")["verified_quotes"]
    assert report["accepted"] == 1 and report["rejected"] == 1
    assert len(stored) == 1
    assert stored[0]["quote"].startswith("We expect central-bank buying")
    assert stored[0]["source"] and stored[0]["url"]
    db.close()
