"""End-to-end test for the proof-of-improvement chain: DB -> assembler -> template."""

from __future__ import annotations

from pathlib import Path

import pytest

from geo_agent.db import CustomerDB
from geo_agent.proof import build_proof_report


@pytest.fixture
def db(tmp_path):
    database = CustomerDB(db_path=str(tmp_path / "t.db"))
    database.add_customer(id="acme", name="Acme Dental", domain="acme.com", city="Austin", state="TX")
    yield database
    database.close()


def _save_run(db, run_id, date, rate, pos):
    db.save_ai_mention_run({
        "id": run_id, "customer_id": "acme", "run_date": date,
        "total_mentions": int(rate * 10), "total_queries": 10,
        "mention_rate": rate, "avg_position": pos, "engines": {"Claude": {}, "Perplexity": {}},
        "prompt_set": "benchmark",
    })


def test_baseline_and_citations(db):
    _save_run(db, "r1", "2026-01-01", 0.1, 5.0)   # baseline (earliest)
    _save_run(db, "r2", "2026-03-01", 0.4, 2.0)   # latest
    db.save_ai_mention_result({
        "run_id": "r2", "customer_id": "acme", "engine": "Perplexity",
        "prompt": "best dentist austin", "mentioned": True, "position": 1,
        "full_response": "Acme Dental is great", "model": "sonar-pro",
        "citations": ["https://www.yelp.com/biz/acme", "https://acme.com/services"],
    })

    base = db.ensure_baseline_run("acme")
    assert base["id"] == "r1"  # earliest auto-marked as baseline

    domains = db.get_citation_domains("acme")
    assert {"domain": "yelp.com", "count": 1} in domains
    assert any(d["domain"] == "acme.com" for d in domains)


def test_build_proof_report_shape(db):
    _save_run(db, "r1", "2026-01-01", 0.1, 5.0)
    _save_run(db, "r2", "2026-03-01", 0.4, 2.0)

    report = build_proof_report(db, "acme")
    assert report["customer_name"] == "Acme Dental"
    av = report["ai_visibility"]
    assert av["baseline_mention_rate"] == 10.0
    assert av["latest_mention_rate"] == 40.0
    assert av["mention_rate_delta"] == 30.0  # +30 points
    assert len(report["ai_trend"]) == 2
    assert report["ai_trend"][0]["is_baseline"] is True  # oldest first


def test_proof_template_renders(db):
    """The client-facing template renders the assembled report without errors."""
    from jinja2 import Environment, FileSystemLoader
    _save_run(db, "r1", "2026-01-01", 0.1, 5.0)
    _save_run(db, "r2", "2026-03-01", 0.4, 2.0)
    report = build_proof_report(db, "acme")

    tmpl_dir = Path(__file__).resolve().parents[2] / "dashboard" / "templates"
    env = Environment(loader=FileSystemLoader(str(tmpl_dir)))
    html = env.get_template("proof.html").render(report=report, public=True, share_url=None)
    assert "Acme Dental" in html
    assert "PracticeRank" in html


def test_minimal_report_no_runs(db):
    """A customer with no runs still produces a renderable (sparse) report."""
    report = build_proof_report(db, "acme")
    assert report["customer_name"] == "Acme Dental"
    assert report["ai_trend"] == []


def test_rolling_mention_rate(db):
    _save_run(db, "r1", "2026-01-01", 0.2, 4.0)
    _save_run(db, "r2", "2026-02-01", 0.4, 3.0)
    _save_run(db, "r3", "2026-03-01", 0.6, 2.0)
    rolling = db.get_rolling_mention_rate("acme", prompt_set="benchmark", window=4)
    assert rolling["runs"] == 3
    assert abs(rolling["rate"] - 0.4) < 1e-9  # (0.2+0.4+0.6)/3


def test_baseline_skips_aborted_zero_query_run(db):
    # An aborted run (total_queries=0) must NOT become the baseline.
    db.save_ai_mention_run({
        "id": "aborted", "customer_id": "acme", "run_date": "2025-12-01",
        "total_mentions": 0, "total_queries": 0, "mention_rate": 0.0,
        "avg_position": None, "engines": {}, "prompt_set": "benchmark",
    })
    _save_run(db, "good", "2026-01-01", 0.3, 3.0)
    base = db.ensure_baseline_run("acme")
    assert base["id"] == "good"
