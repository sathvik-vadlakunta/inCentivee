"""Share-of-voice aggregator filtering + customer rank."""

from __future__ import annotations

import pytest

from geo_agent.db import CustomerDB
from geo_agent.entity_extractor import is_platform_or_directory


@pytest.mark.parametrize("name,expected", [
    ("trustpilot", True),
    ("bbb accredited", True),       # exact set miss, token match
    ("trustpilot reviews", True),   # token match
    ("yelp", True),
    ("google reviews", True),
    ("biotech peptides", False),    # real competitor
    ("alexandria gold and silver", False),
    ("paradigm experts", False),
])
def test_is_platform_or_directory(name, expected):
    assert is_platform_or_directory(name) is expected


@pytest.fixture
def db(tmp_path):
    database = CustomerDB(db_path=str(tmp_path / "sov.db"))
    database.add_customer(id="acme", name="Acme Dental", domain="acme.com", city="Austin", state="TX")
    yield database
    database.close()


def _run(db, rid):
    db.save_ai_mention_run({
        "id": rid, "customer_id": "acme", "run_date": "2026-06-11",
        "total_mentions": 5, "total_queries": 10, "mention_rate": 0.5,
        "avg_position": 1.5, "engines": {}, "prompt_set": "benchmark",
    })
    # One result row to satisfy the entities FK (result_id -> ai_mention_results.id)
    cur = db.conn.execute(
        "INSERT INTO ai_mention_results (run_id, customer_id, engine, prompt, mentioned) "
        "VALUES (?,?,?,?,?)", (rid, "acme", "Claude", "q", 1))
    db.conn.commit()
    return cur.lastrowid


def _ent(db, rid, result_id, name, is_customer, n):
    for i in range(n):
        db.save_ai_response_entity({
            "result_id": result_id, "run_id": rid, "customer_id": "acme",
            "entity_name": name, "entity_name_normalized": name.lower(),
            "is_customer": is_customer, "position": 1, "engine": "Claude",
            "prompt": f"q{i}", "prompt_category": "general", "run_date": "2026-06-11",
        })


def test_aggregators_excluded_and_rank(db):
    res_id = _run(db, "r1")
    _ent(db, "r1", res_id, "Acme Dental", True, 8)        # customer
    _ent(db, "r1", res_id, "Trustpilot", False, 9)        # directory — must be dropped
    _ent(db, "r1", res_id, "BBB Accredited", False, 6)    # directory — must be dropped
    _ent(db, "r1", res_id, "Bright Smiles", False, 4)     # real competitor

    sov = db.get_share_of_voice("acme", last_n_runs=1)
    names = {c["name"] for c in sov["competitors"]}
    assert "Trustpilot" not in names
    assert "BBB Accredited" not in names
    assert "Bright Smiles" in names
    # Denominator excludes directories: 8 customer + 4 competitor = 12
    assert sov["total_entity_mentions"] == 12
    assert sov["customer_share"] == round(8 / 12, 4)
    assert sov["customer_rank"] == 1  # 8 > 4, customer ranks first


# --- Flagship score module (geo_agent/share_of_voice.py) ---

from geo_agent import share_of_voice as sov_mod  # noqa: E402


def _seed_run(db, rid, date, customer_n, competitors):
    db.save_ai_mention_run({
        "id": rid, "customer_id": "acme", "run_date": date,
        "total_mentions": customer_n, "total_queries": 10,
        "mention_rate": customer_n / 10, "engines": {}, "prompt_set": "benchmark",
    })
    cur = db.conn.execute(
        "INSERT INTO ai_mention_results (run_id, customer_id, engine, prompt, mentioned) "
        "VALUES (?,?,?,?,?)", (rid, "acme", "Claude", "q", 1))
    result_id = cur.lastrowid
    db.conn.commit()
    _ent(db, rid, result_id, "Acme Dental", True, customer_n)
    for name, n in competitors.items():
        _ent(db, rid, result_id, name, False, n)


def test_sov_summary_none_without_data(db):
    assert sov_mod.sov_summary(db, "acme") is None
    assert sov_mod.sov_score(db, "acme") == (None, None)


def test_flagship_score_rank_and_delta(db):
    # pooled: acme 7, Bright 8, City 5 → total 20 → 35%, rank #2
    _seed_run(db, "r1", "2026-05-01", 2, {"Bright Smile": 5, "City Dental": 3})  # 20%
    _seed_run(db, "r2", "2026-06-01", 5, {"Bright Smile": 3, "City Dental": 2})  # 50%
    s = sov_mod.sov_summary(db, "acme")
    assert s["score"] == 35
    assert s["rank"] == 2
    assert s["leads"] is False
    assert [h["sov_pct"] for h in s["history"]] == [20.0, 50.0]
    assert s["delta"] == 15  # pooled 35 − first tracked 20
    assert sov_mod.sov_score(db, "acme") == (35, 15)


def test_leads_when_rank_one(db):
    _seed_run(db, "r1", "2026-06-01", 9, {"Bright Smile": 1})  # 90%, #1
    s = sov_mod.sov_summary(db, "acme")
    assert s["rank"] == 1 and s["leads"] is True
