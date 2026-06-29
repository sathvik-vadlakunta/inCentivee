"""Unit tests for the SEO Health Score (no bucket double-count, distinct signals,
stable window) and the tier-driven monthly content quota."""

from geo_agent.fatjoe_plan import DEFAULT_CONTENT_QUOTA, monthly_content_quota
from geo_agent.seo_health import compute_seo_health


def _audit(perf=50, seo=100, bp=90, a11y=80):
    return {
        "performance_score": perf,
        "seo_score": seo,
        "best_practices_score": bp,
        "accessibility_score": a11y,
    }


def _days(clicks_each, n):
    return [{"clicks": clicks_each, "impressions": clicks_each * 10} for _ in range(n)]


class TestSeoHealthBuckets:
    def test_four_distinct_buckets_each_25pct(self):
        out = compute_seo_health(_audit(), [], [])
        keys = [b["key"] for b in out["buckets"]]
        assert keys == ["pagespeed", "keyword_coverage", "traffic_trend", "technical"]
        assert all(b["weight"] == 25 for b in out["buckets"])

    def test_performance_and_technical_are_not_identical(self):
        # The old bug: technical just copied the PageSpeed average. Now Performance =
        # raw perf score, Technical = avg(seo, best-practices, a11y) — must differ.
        out = compute_seo_health(_audit(perf=50, seo=100, bp=90, a11y=80), [], [])
        perf = next(b for b in out["buckets"] if b["key"] == "pagespeed")
        tech = next(b for b in out["buckets"] if b["key"] == "technical")
        assert perf["value"] == 50
        assert tech["value"] == 90  # round((100+90+80)/3)
        assert perf["value"] != tech["value"]

    def test_keyword_coverage_is_pct_in_top20(self):
        ks = [{"current_position": 5}, {"current_position": 25},
              {"current_position": 18}, {"current_position": None}]
        out = compute_seo_health(None, ks, [])
        cov = next(b for b in out["buckets"] if b["key"] == "keyword_coverage")
        assert cov["value"] == 50  # 2 of 4 in top 20

    def test_traffic_neutral_without_history(self):
        out = compute_seo_health(_audit(), [], _days(3, 5))  # <14 days
        traffic = next(b for b in out["buckets"] if b["key"] == "traffic_trend")
        assert traffic["value"] == 50

    def test_traffic_rewards_growth(self):
        # prior 30 days flat at 2 clicks, recent 30 days at 4 → +100% → capped band
        series = _days(2, 30) + _days(4, 30)
        out = compute_seo_health(_audit(), [], series)
        traffic = next(b for b in out["buckets"] if b["key"] == "traffic_trend")
        assert traffic["value"] > 50

    def test_score_is_weighted_average_of_buckets(self):
        out = compute_seo_health(_audit(), [], [])
        expected = round(sum(b["value"] for b in out["buckets"]) / 4)
        # alltolerance: buckets are pre-rounded so allow 1pt rounding drift
        assert abs(out["score"] - expected) <= 1


class TestTierContentQuota:
    def test_known_tiers(self):
        assert monthly_content_quota("PracticeRank Optimize") == 2
        assert monthly_content_quota("Grow plan") == 4
        assert monthly_content_quota("Dominate — Founding") == 8

    def test_unknown_tier_falls_back_to_default(self):
        assert monthly_content_quota("Samuel Doherty") == DEFAULT_CONTENT_QUOTA
        assert monthly_content_quota(None) == DEFAULT_CONTENT_QUOTA

    def test_override_wins(self):
        assert monthly_content_quota("Samuel Doherty", "grow") == 4
