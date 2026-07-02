"""Day-1 quick-win pass: top-pick helper + onboarding gate."""

from geo_agent.db import CustomerDB
from geo_agent import action_items as ai
from geo_agent.quick_wins import first_quick_win, QuickWin


def test_first_quick_win_prefers_auto_actionable(monkeypatch):
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C1", "c1.com")
    wins = [
        QuickWin("w1", "Manual big", "", "content", "high", "low", 10, "/x", "Go", auto_actionable=False),
        QuickWin("w2", "Auto small", "", "technical", "medium", "low", 5, "/y", "Go", auto_actionable=True),
    ]
    monkeypatch.setattr("geo_agent.quick_wins.detect_quick_wins", lambda db, cid: wins)
    fw = first_quick_win(db, "c1")
    assert fw.id == "w2"  # auto-actionable wins the Day-1 slot
    db.close()


def test_first_quick_win_none_when_empty(monkeypatch):
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C1", "c1.com")
    monkeypatch.setattr("geo_agent.quick_wins.detect_quick_wins", lambda db, cid: [])
    assert first_quick_win(db, "c1") is None
    db.close()


def test_onboarding_gate_fires_until_shipped():
    db = CustomerDB(":memory:")
    db.add_customer("o", "Onb", "o.com")  # onboarding by default
    cust = dict(db.get_customer("o"), pending_count=0)
    keys = {i["key"] for i in ai.customer_action_items(db, cust)}
    assert "quickwin" in keys

    db.update_customer("o", quick_win_shipped_at="2026-07-01T00:00:00Z")
    cust2 = dict(db.get_customer("o"), pending_count=0)
    keys2 = {i["key"] for i in ai.customer_action_items(db, cust2)}
    assert "quickwin" not in keys2
    db.close()


def test_gate_only_for_onboarding():
    db = CustomerDB(":memory:")
    db.add_customer("a", "Active", "a.com")
    db.set_customer_status("a", "active")
    cust = dict(db.get_customer("a"), pending_count=0)
    keys = {i["key"] for i in ai.customer_action_items(db, cust)}
    assert "quickwin" not in keys  # live accounts don't get the Day-1 gate
    db.close()
