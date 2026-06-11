"""Tests for the 'adapt over time' loop: uncited queries -> FAQ plan."""

from __future__ import annotations

import pytest

from geo_agent.db import CustomerDB
from geo_agent.llms_adaptation import build_adaptation_plan, prompt_to_question


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "t.db"))
    d.add_customer(id="acme", name="Acme Dental", domain="acme.com", city="Austin", state="TX")
    yield d
    d.close()


def _run(db, rid, date):
    db.save_ai_mention_run({
        "id": rid, "customer_id": "acme", "run_date": date, "total_mentions": 1,
        "total_queries": 2, "mention_rate": 0.5, "avg_position": 2.0, "engines": {},
        "prompt_set": "benchmark",
    })


def _res(db, rid, prompt, mentioned):
    db.save_ai_mention_result({
        "run_id": rid, "customer_id": "acme", "engine": "Claude", "prompt": prompt,
        "prompt_category": "services", "mentioned": mentioned, "full_response": "x",
    })


def test_prompt_to_question():
    assert prompt_to_question("best dentist in Austin").endswith("?")
    q = prompt_to_question("Acme Dental reviews", "Acme Dental")
    assert "acme dental" not in q.lower()  # name replaced with "we"


def test_uncited_prompts_and_plan(db):
    for rid, date in [("r1", "2026-01-01"), ("r2", "2026-02-01")]:
        _run(db, rid, date)
        _res(db, rid, "best dentist in Austin", mentioned=True)      # cited -> not a gap
        _res(db, rid, "who does dental implants in Austin", mentioned=False)  # never cited -> gap

    uncited = db.get_uncited_prompts("acme")
    prompts = [u["prompt"] for u in uncited]
    assert "who does dental implants in Austin" in prompts
    assert "best dentist in Austin" not in prompts

    plan = build_adaptation_plan(db, "acme")
    assert plan["customer_name"] == "Acme Dental"
    assert any("implants" in f["question"].lower() for f in plan["suggested_faqs"])
    assert plan["actions"]  # at least one recommended action


def test_plan_empty_for_no_data(db):
    plan = build_adaptation_plan(db, "acme")
    assert plan["uncited_queries"] == []
    assert plan["suggested_faqs"] == []
