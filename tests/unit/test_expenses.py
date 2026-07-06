"""Tests for the operating-cost (Expenses) ledger."""

from __future__ import annotations

from geo_agent.expenses import EXPENSE_ITEMS, compute_expenses


def test_every_item_has_required_fields():
    for it in EXPENSE_ITEMS:
        for f in ("category", "name", "vendor", "purpose", "billing", "monthly", "charged"):
            assert f in it, f"{it.get('name')} missing {f}"
        assert it["billing"] in ("fixed", "per_customer", "annual", "free", "variable", "onetime")


def test_usage_scales_with_customers():
    one = compute_expenses(1)["totals"]["usage"]
    ten = compute_expenses(10)["totals"]["usage"]
    assert ten == round(one * 10, 2)


def test_recurring_excludes_setup_and_variable():
    d = compute_expenses(5)
    t = d["totals"]
    # recurring = fixed + usage + annual only
    assert t["recurring"] == round(t["fixed"] + t["usage"] + t["annual"], 2)
    # setup totals are reported separately and not folded into recurring
    assert t["setup_per_customer"] > t["setup_per_customer_base"]  # redesign adds to it
    assert t["setup_per_customer_base"] > 0


def test_setup_base_excludes_redesign():
    d = compute_expenses(1)
    # the ~$5k designer is in the full setup but not the base
    assert d["totals"]["setup_per_customer"] - d["totals"]["setup_per_customer_base"] >= 4000


# --------------------------------------------------------------------------- #
# Real monthly reimbursement ledger (expense_entries)                          #
# --------------------------------------------------------------------------- #
import os
import tempfile

import pytest

from geo_agent.db import CustomerDB
from geo_agent.expenses import RECURRING_TEMPLATES


@pytest.fixture
def db():
    path = os.path.join(tempfile.mkdtemp(), "ledger.db")
    d = CustomerDB(db_path=path)
    yield d
    d.close()


def test_recurring_templates_include_google_workspace():
    keys = {t["key"] for t in RECURRING_TEMPLATES}
    assert "google_workspace" in keys
    ws = next(t for t in RECURRING_TEMPLATES if t["key"] == "google_workspace")
    assert ws["vendor"] == "Google" and ws["amount"] >= 0
    # every template needs the fields the seeder + UI rely on
    for t in RECURRING_TEMPLATES:
        for f in ("key", "category", "vendor", "name", "amount"):
            assert f in t, f"{t.get('key')} missing {f}"


def test_all_five_ai_providers_present():
    """We run Claude, ChatGPT, Gemini, Perplexity and Grok — each needs a line."""
    ai = [t for t in RECURRING_TEMPLATES if t["category"] == "AI / LLM APIs"]
    keys = {t["key"] for t in ai}
    assert {"anthropic", "openai", "gemini", "perplexity", "xai"} <= keys
    assert len(ai) >= 5


def test_seed_is_idempotent(db):
    m = "2026-07"
    n = db.seed_recurring_expenses(m, RECURRING_TEMPLATES)
    assert n == len(RECURRING_TEMPLATES)
    # re-seeding the same month inserts nothing (no double-charge)
    assert db.seed_recurring_expenses(m, RECURRING_TEMPLATES) == 0
    assert len(db.list_expense_entries(m)) == len(RECURRING_TEMPLATES)


def test_add_update_delete_and_month_scoping(db):
    db.seed_recurring_expenses("2026-07", RECURRING_TEMPLATES)
    # a one-off in a *different* month must not bleed into July
    eid = db.add_expense_entry(month="2026-08", name="Domain renewal",
                               amount_usd=18.0, category="Domains")
    assert all(r["month"] == "2026-07" for r in db.list_expense_entries("2026-07"))
    assert len(db.list_expense_entries("2026-08")) == 1
    # editing the real invoice amount sticks
    row = db.list_expense_entries("2026-08")[0]
    db.update_expense_entry(row["id"], amount_usd=21.5, note="registrar")
    row = db.list_expense_entries("2026-08")[0]
    assert row["amount_usd"] == 21.5 and row["note"] == "registrar"
    db.delete_expense_entry(eid)
    assert db.list_expense_entries("2026-08") == []


def test_recurring_flag_and_category_split(db):
    m = "2026-07"
    db.seed_recurring_expenses(m, RECURRING_TEMPLATES)
    db.add_expense_entry(month=m, name="BrightLocal", amount_usd=39.0,
                         category="SEO & Data APIs")
    rows = db.list_expense_entries(m)
    # seeded rows are flagged recurring; the manual one is not
    assert all(r["recurring"] == 1 for r in rows if r["template_key"])
    assert any(r["recurring"] == 0 and r["name"] == "BrightLocal" for r in rows)
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = round(by_cat.get(r["category"], 0) + r["amount_usd"], 2)
    # Moz ($20) + BrightLocal ($39) land in the same bucket
    assert by_cat["SEO & Data APIs"] == 59.0
    assert "Google" in by_cat  # Google Workspace bucket exists


def test_expense_months_sorted_desc(db):
    db.add_expense_entry(month="2026-05", name="x", amount_usd=1)
    db.add_expense_entry(month="2026-07", name="y", amount_usd=1)
    db.add_expense_entry(month="2026-06", name="z", amount_usd=1)
    assert db.expense_months() == ["2026-07", "2026-06", "2026-05"]


def test_set_amount_by_template_powers_usage_sync(db):
    db.seed_recurring_expenses("2026-07", RECURRING_TEMPLATES)
    assert db.set_expense_amount_by_template("2026-07", "anthropic", 63.4, note="synced")
    row = next(r for r in db.list_expense_entries("2026-07") if r["template_key"] == "anthropic")
    assert row["amount_usd"] == 63.4 and row["note"] == "synced"
    # unknown key → no-op, returns False (never creates a stray row)
    assert db.set_expense_amount_by_template("2026-07", "does_not_exist", 5.0) is False


def test_offsite_spend_month_powers_fatjoe_line(db):
    import datetime
    db.add_customer("c1", name="C", domain="c.com")
    db.add_offsite_order("c1", "link", cost_usd=41.0, status="ordered")
    db.add_offsite_order("c1", "citation", cost_usd=135.0, status="cancelled")  # excluded
    cur = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    cost, n = db.offsite_spend_month(cur)
    assert cost == 41.0 and n == 1  # cancelled order not counted
    assert db.offsite_spend_month("2020-01") == (0.0, 0)


def test_usage_sync_without_keys_is_graceful(monkeypatch, db):
    from geo_agent import usage_sync
    for env in ("ANTHROPIC_ADMIN_KEY", "OPENAI_ADMIN_KEY", "GEMINI_ADMIN_KEY"):
        monkeypatch.delenv(env, raising=False)
    db.seed_recurring_expenses("2026-07", RECURRING_TEMPLATES)
    res = usage_sync.sync_ai_usage(db, "2026-07")
    assert set(res) == {"anthropic", "openai", "gemini"}
    assert all(v["status"] == "no_key" for v in res.values())
    assert "no admin key" in usage_sync.summarize(res)
