"""Tests for the weekly report's 'progress since you started' trends."""

from __future__ import annotations

import os
import tempfile

import pytest

from geo_agent import weekly_report as wr
from geo_agent.db import CustomerDB


@pytest.fixture
def db():
    path = os.path.join(tempfile.mkdtemp(), "prog.db")
    d = CustomerDB(db_path=path)
    d.add_customer("c1", name="Alpha", domain="a.com")
    yield d
    d.close()


def _seed(db):
    # ascending months
    for i, (date, clicks, da, mentions) in enumerate([
        ("2026-04-01", 140, 18, 2),
        ("2026-05-01", 240, 20, 5),
        ("2026-06-01", 410, 24, 11),
    ]):
        db.record_kpi("c1", "organic_clicks", clicks, date)
        db.record_kpi("c1", "domain_authority", da, date)
        db.record_kpi("c1", "ai_mentions", mentions, date)
    db.save_practicerank_score("c1", "2026-04-01", 42, 20, 40, 60, 30, 55)
    db.save_practicerank_score("c1", "2026-05-01", 55, 35, 55, 65, 50, 60)
    db.save_practicerank_score("c1", "2026-06-01", 68, 55, 70, 72, 65, 70)


def test_progress_start_to_now(db):
    _seed(db)
    prog = wr._progress_since_start(db, "c1")
    assert prog is not None
    assert prog["start_date"] == "2026-04-01"
    by = {m["label"]: m for m in prog["metrics"]}
    # score 42 -> 68, series in ascending order
    assert by["PracticeRank score"]["start"] == 42
    assert by["PracticeRank score"]["current"] == 68
    assert by["PracticeRank score"]["series"] == [42, 55, 68]
    assert by["PracticeRank score"]["delta"] == 26
    assert by["Organic clicks / mo"]["cur_str"] == "410"
    assert by["AI mentions"]["delta"] == 9


def test_metric_needs_two_points(db):
    db.record_kpi("c1", "organic_clicks", 100, "2026-06-01")  # single point only
    prog = wr._progress_since_start(db, "c1")
    assert prog is None  # nothing has >=2 points


def test_lower_is_better_position_direction(db):
    db.record_kpi("c1", "avg_search_position", 18.0, "2026-04-01")
    db.record_kpi("c1", "avg_search_position", 9.0, "2026-06-01")
    prog = wr._progress_since_start(db, "c1")
    pos = next(m for m in prog["metrics"] if m["label"] == "Avg search position")
    # delta is negative (18 -> 9) but that's an IMPROVEMENT since lower is better
    assert pos["delta"] == -9.0
    assert pos["higher_better"] is False


def test_sparkline_and_chart_svg(db):
    assert _svg_ok(wr._sparkline_svg([1, 3, 2, 5]))
    assert wr._sparkline_svg([5]) == ""  # <2 points
    chart = wr._trend_chart_svg([("2026-04-01", 42), ("2026-06-01", 68)], title="Score")
    assert "<svg" in chart and "Score" in chart and "polyline" in chart


def test_render_includes_progress_section(db):
    _seed(db)
    data = wr.build_report_data(db, "c1")
    html = wr.render_html(data)
    assert "Your progress since 2026-04-01" in html
    assert "PracticeRank Score" in html  # headline chart title
    assert "class=\"pm\"" in html


def _svg_ok(s: str) -> bool:
    return s.startswith("<svg") and "polyline" in s and s.endswith("</svg>")


def test_maturation_note_anchors_on_changes_live_not_signup():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    # changes went live ~2 weeks ago → note is anchored on go-live, "weeks ago"
    recent = (now - timedelta(weeks=2)).strftime("%Y-%m-%d")
    note = wr._maturation_note({"changes_live_at": recent, "progress": {"start_date": "2020-01-01"}})
    assert "went live about 2 weeks ago" in note
    assert "6+ weeks" in note
    # crucially it must NOT report signup tenure ("7 weeks in" style)
    assert "weeks in" not in note
    # established (~6 months live) → "past the initial ramp"
    old = (now - timedelta(weeks=26)).strftime("%Y-%m-%d")
    assert "months" in wr._maturation_note({"changes_live_at": old})
    # no go-live date → neutral copy, no asserted timeline, no "weeks in/ago"
    neutral = wr._maturation_note({"progress": {"start_date": recent}})
    assert "6+ weeks" in neutral
    assert "weeks in" not in neutral and "weeks ago" not in neutral


def test_render_includes_expectations(db):
    _seed(db)
    html = wr.render_html(wr.build_report_data(db, "c1"))
    assert "What to expect" in html
    assert "normal noise" in html


def test_avg_position_dilution_footnote(db):
    _seed(db)
    db.record_kpi("c1", "avg_search_position", 16.0, "2026-04-01")
    db.record_kpi("c1", "avg_search_position", 24.0, "2026-06-01")
    html = wr.render_html(wr.build_report_data(db, "c1"))
    assert "About average position" in html          # footnote present
    assert "ranking for" in html and "more" in html   # dilution explanation
