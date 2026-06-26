"""P2: striking-distance keyword opportunities — page-2 keywords with volume to target next."""
from __future__ import annotations
from dashboard.app import _compute_striking_distance


def _kw(keyword, position, impressions, clicks=0):
    return {"keyword": keyword, "current_position": position,
            "current_impressions": impressions, "current_clicks": clicks}


def test_surfaces_page2_high_impression_keywords_sorted():
    ks = [
        _kw("gemstone buyers near me", 10.8, 112),   # page 2, high impr
        _kw("sell coins near me", 12.0, 81),          # page 2
        _kw("paradigm experts", 1.1, 500),            # page 1 -> excluded
        _kw("obscure term", 18.0, 5),                 # page 2 but tiny impr -> excluded
        _kw("untracked", None, 0),                    # no position -> excluded
        _kw("page 3 term", 25.0, 200),                # page 3 -> excluded
    ]
    out = _compute_striking_distance(ks)
    kws = [o["keyword"] for o in out]
    assert kws == ["gemstone buyers near me", "sell coins near me"]  # sorted by impressions
    assert "paradigm experts" not in kws  # already page 1
    assert "obscure term" not in kws       # below impression floor


def test_empty():
    assert _compute_striking_distance([]) == []
    assert _compute_striking_distance(None) == []
