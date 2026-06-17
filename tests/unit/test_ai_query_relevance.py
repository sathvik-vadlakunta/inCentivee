"""AI-mention queries must be industry-relevant, not raw business_type."""

from __future__ import annotations

from scripts.check_ai_mentions import build_comprehensive_prompts, business_label


def _prompts(**kw):
    defs = build_comprehensive_prompts("Paradigm Experts", "Springfield", "VA", [], **kw)
    return [d["prompt"] for d in defs]


def test_business_label_humanizes():
    assert business_label("precious_metals_buyer") == "gold and silver buyer"
    assert business_label("some_new_type") == "some new type"  # no underscores


def test_metals_buyer_seller_intent():
    p = _prompts(business_type="precious_metals_buyer")
    joined = " || ".join(p).lower()
    # seller intent present
    assert any("sell my gold" in x.lower() for x in p)
    assert any("sell my silver" in x.lower() for x in p)
    assert any("cash for gold" in x.lower() for x in p)
    assert any("who buys gold" in x.lower() for x in p)
    # NO raw business_type leaking
    assert "precious_metals_buyer" not in joined
    assert "patients" not in joined


def test_service_area_coverage():
    p = _prompts(business_type="precious_metals_buyer",
                 service_areas=["Fairfax VA", "Vienna VA", "Tysons VA"])
    assert any("Fairfax VA" in x for x in p)
    assert any("Vienna VA" in x for x in p)


def test_generic_branch_uses_label_not_raw_type():
    p = _prompts(business_type="precious_metals_buyer")  # has dedicated branch
    # an unmapped generic type should still humanize
    p2 = _prompts(business_type="widget_maker")
    assert "widget_maker" not in " ".join(p2)
    assert any("widget maker" in x.lower() for x in p2)
