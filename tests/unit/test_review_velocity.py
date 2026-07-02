"""Review velocity: trailing-window counts vs target (the local-pack stall signal)."""

from datetime import datetime, timezone, timedelta

from geo_agent.db import CustomerDB


def _db():
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C One", "c1.com")
    return db


def _d(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_current_vs_previous_window():
    db = _db()
    for n in (2, 10):          # 2 in trailing 30d
        db.add_review("c1", 5, review_date=_d(n))
    for n in (35, 40, 45, 50, 55):  # 5 in prior 30d
        db.add_review("c1", 5, review_date=_d(n))
    v = db.review_velocity("c1")
    assert v["current"] == 2
    assert v["previous"] == 5
    db.close()


def test_default_target_and_on_track():
    db = _db()  # default target 4
    for n in range(5):
        db.add_review("c1", 5, review_date=_d(n + 1))  # 5 in window
    v = db.review_velocity("c1")
    assert v["target"] == 4
    assert v["on_track"] is True
    db.close()


def test_custom_target_flips_on_track():
    db = _db()
    db.add_review("c1", 5, review_date=_d(1))  # 1 review
    assert db.review_velocity("c1")["on_track"] is False  # target 4
    db.update_customer("c1", review_target_pm=1)
    assert db.review_velocity("c1")["on_track"] is True
    db.close()


def test_empty_reviews():
    db = _db()
    v = db.review_velocity("c1")
    assert v["current"] == 0 and v["previous"] == 0
    assert v["on_track"] is False
    db.close()
