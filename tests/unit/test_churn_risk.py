"""Churn-risk radar: additive signals → 0–100 renewal-risk score + reasons."""

from datetime import datetime, timezone, timedelta

from geo_agent.db import CustomerDB
from geo_agent import churn_risk as cr


def _active(db, cid="a"):
    db.add_customer(cid, cid.upper(), f"{cid}.com")
    db.set_customer_status(cid, "active")
    return db.get_customer(cid)


def test_non_active_is_inert():
    db = CustomerDB(":memory:")
    db.add_customer("o", "Onb", "o.com")  # onboarding
    r = cr.churn_risk(db, db.get_customer("o"))
    assert r["score"] == 0 and r["level"] == "none"
    db.close()


def test_no_plan_and_no_report_scores_medium():
    db = CustomerDB(":memory:")
    c = _active(db)
    r = cr.churn_risk(db, c)
    # 25 (no plan) + 15 (no report ever) = 40 → medium
    assert r["score"] == 40
    assert r["level"] == "medium"
    assert "No paid plan linked" in r["reasons"]
    assert "No report ever sent" in r["reasons"]
    db.close()


def test_top_reason_is_highest_weighted_first():
    db = CustomerDB(":memory:")
    c = _active(db)
    r = cr.churn_risk(db, c)
    # "No paid plan linked" (25) outranks "No report ever sent" (15)
    assert r["top_reason"].startswith("No paid plan linked")
    db.close()


def test_score_capped_at_100():
    db = CustomerDB(":memory:")
    c = _active(db)
    # Pile on: seed a slipping SEO score + pending access; still ≤ 100.
    r = cr.churn_risk(db, dict(c, pending_count=3))
    assert r["score"] <= 100
    assert any("access item" in x for x in r["reasons"])
    db.close()


def test_recent_report_lowers_risk():
    db = CustomerDB(":memory:")
    c = _active(db)
    before = cr.churn_risk(db, c)["score"]
    # A fresh report snapshot removes the "no report ever" (+15) signal.
    now = datetime.now(timezone.utc)
    db.conn.execute(
        "INSERT INTO report_snapshots (customer_id, report_type, period_start, period_end, "
        "score, share_token, emailed_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("a", "weekly", (now - timedelta(days=7)).strftime("%Y-%m-%d"),
         now.strftime("%Y-%m-%d"), 70, "tok", now.isoformat(), now.isoformat()),
    )
    db.conn.commit()
    after = cr.churn_risk(db, c)["score"]
    assert after == before - 15
    db.close()
