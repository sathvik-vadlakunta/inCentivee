"""Tests for the grounded AI-visibility instrument (engine queries + parsing)."""

from __future__ import annotations

import os

import pytest

from scripts import check_ai_mentions as cai


def _clear_keys(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize("fn", [
    cai.query_claude, cai.query_openai, cai.query_perplexity, cai.query_gemini, cai.query_grok,
])
def test_engines_return_none_without_key(monkeypatch, fn):
    _clear_keys(monkeypatch)
    assert fn("best dentist in austin") is None


def test_engine_result_shape():
    er = cai.EngineResult(text="hi", citations=["https://a.com"], model="m")
    assert er.text == "hi" and er.citations == ["https://a.com"] and er.model == "m"
    # citations defaults to an empty list, not shared mutable state
    assert cai.EngineResult(text="x").citations == []


def test_grounded_models_are_flagship_and_search_capable():
    # Guard against silently reverting to the old cheap/ungrounded models.
    assert cai.ENGINE_MODELS["openai"].endswith("search-preview")
    assert cai.ENGINE_MODELS["perplexity"] == "sonar-pro"
    assert "mini" not in cai.ENGINE_MODELS["claude"]
    assert "mini" not in cai.ENGINE_MODELS["grok"]


def test_dedup_preserves_order_and_drops_falsy():
    assert cai._dedup(["a", "a", None, "b", "", "a"]) == ["a", "b"]


def test_find_position_bullet_is_one_based():
    text = "Here are options:\n- Acme Dental — great\n- Other Place — ok"
    assert cai._find_position(text, "Acme Dental") == 1  # first bullet, not falsy 0


def test_find_position_numbered():
    text = "1. First Dental\n2. Hilltop Family Dental\n3. Third"
    assert cai._find_position(text, "Hilltop Family Dental") == 2


# --- mention-detection reliability (false positives + recall) ---

def test_no_false_positive_on_bare_generic_token():
    # The old logic matched any response containing 'summit'. It must NOT now.
    r = cai.check_mention("Summit Medical Center is a great hospital downtown.", "Summit Dental Care")
    assert r["mentioned"] is False


def test_matches_distinctive_bigram():
    r = cai.check_mention("I'd recommend Summit Dental for implants.", "Summit Dental Care")
    assert r["mentioned"] is True


def test_matches_full_name():
    r = cai.check_mention("Hilltop Family Dental is excellent in Austin.", "Hilltop Family Dental")
    assert r["mentioned"] is True


def test_no_match_when_only_unrelated_words_present():
    r = cai.check_mention("The dental care here is good, very caring family practice.", "Summit Dental Care")
    assert r["mentioned"] is False


def test_core_tokens_drops_generics():
    assert cai._core_tokens("Summit Dental Care") == ["summit"]
    assert "law" not in cai._core_tokens("Parian Lawyers Law Group")


def test_no_false_positive_on_of_city_name():
    # "Dental Care of Austin" must NOT match generic "best dentists of Austin".
    r = cai.check_mention("The best dentists of Austin are highly rated.", "Dental Care of Austin")
    assert r["mentioned"] is False


def test_error_result_distinct_from_no_key():
    er = cai._err("some-model", RuntimeError("410 Gone"))
    assert er.error and "410" in er.error and er.model == "some-model" and er.text == ""
    # A no-key path returns None, an error path returns a result with .error set.
    assert cai.EngineResult(text="ok").error == ""
