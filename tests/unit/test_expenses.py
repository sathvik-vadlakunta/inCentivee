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
