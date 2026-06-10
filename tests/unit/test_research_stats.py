"""Guard: every RESEARCH_STATS entry must cite a specific page, not a homepage.

This locks in the source-quality cleanup — a future stat added with only a bare
domain (or a generic /marketing-statistics landing page) will fail CI.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from geo_agent.content_recommender import RESEARCH_STATS

# Generic landing pages that don't substantiate a specific claim.
_GENERIC_PATHS = {"marketing-statistics", "about_the_aba/profession_statistics"}

_ALL = [(bt, s) for bt, items in RESEARCH_STATS.items() for s in items]


@pytest.mark.parametrize("bt,stat", _ALL, ids=[f"{bt}:{s['stat'][:30]}" for bt, s in _ALL])
def test_stat_cites_a_specific_page(bt, stat):
    url = stat.get("url", "")
    path = urlparse(url).path.strip("/")
    assert path, f"[{bt}] stat cites a bare domain (no specific page): {url}"
    assert path.lower() not in _GENERIC_PATHS, f"[{bt}] stat cites a generic landing page: {url}"
    assert stat.get("source"), f"[{bt}] stat is missing a source name"


def test_each_pool_has_enough_stats():
    # The content prompt asks for several stat injections; keep a healthy floor.
    for bt, items in RESEARCH_STATS.items():
        assert len(items) >= 4, f"{bt} pool has only {len(items)} stats"
