"""Search-intent classification — locks the canonical high-intent targets.

The whole point: action/purchase searches ("where to sell gold", "best dentist in austin")
must rank ABOVE research ("are antique tea sets valuable").
"""

from __future__ import annotations

import pytest

from geo_agent import keyword_intent as ki


@pytest.mark.parametrize("kw", [
    "where do i sell my gold",
    "where to sell silver near me",
    "sell jewelry fairfax va",
    "sell my gold coins",
    "gold buyer near me",
    "cash for gold",
    "how much can i get for my gold",
    "sell silver coins springfield",
    "pawn shop near me",
    "dentist near me",
    "dental implants cost",
    "book a dentist appointment",
])
def test_transactional(kw):
    assert ki.classify_intent(kw) == "transactional", kw


@pytest.mark.parametrize("kw", [
    "best dentist in austin",
    "new dentist in austin",          # default money tier
    "dentist austin",                 # bare service+city → commercial
    "top gold buyers",
    "best place to sell gold reviews",  # 'sell' could be transactional, but it has 'sell' → transactional
])
def test_commercial_or_better(kw):
    # These are all purchase-decision searches — never informational.
    assert ki.classify_intent(kw) in ("commercial", "transactional"), kw
    assert ki.is_action(kw) is True


@pytest.mark.parametrize("kw", [
    "are antique tea sets valuable",
    "history of silver coins",
    "what is sterling silver",
    "how does gold plating work",
    "types of diamond cuts",
])
def test_informational(kw):
    assert ki.classify_intent(kw) == "informational", kw
    assert ki.is_action(kw) is False


def test_local_action_outranks_everything():
    # "best dentist in austin" (local commercial) beats "dental implants" (commercial, no local);
    # "sell gold near me" (local transactional) is the top.
    assert ki.target_priority("sell gold near me") > ki.target_priority("sell gold")
    assert ki.target_priority("best dentist in austin") > ki.target_priority("what is a root canal")
    assert ki.target_priority("sell gold near me") > ki.target_priority("best dentist in austin")


def test_has_local_intent():
    assert ki.has_local_intent("sell gold near me")
    assert ki.has_local_intent("dentist in Austin")
    assert ki.has_local_intent("jeweler in McLean, VA")
    assert not ki.has_local_intent("sell gold online")


def test_intent_meta_shape():
    m = ki.intent_meta("where to sell gold")
    assert m["tier"] == "transactional" and m["label"] and m["color"] and m["format"]
