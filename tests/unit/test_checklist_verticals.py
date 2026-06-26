"""Industry-aware checklist: vertical mapping + task filtering + content auto-tick.

See specs/active/checklist-overhaul.html.
"""

from __future__ import annotations

from dashboard.app import _get_seo_tasks, vertical_for
from geo_agent.status_checker import _content_task_status


def _keys(business_type, **kw):
    return {t["key"] for t in _get_seo_tasks({}, business_type=business_type, **kw)}


def _label(business_type, key):
    for t in _get_seo_tasks({}, business_type=business_type):
        if t["key"] == key:
            return t["task"]
    return None


def test_vertical_mapping():
    assert vertical_for("practice") == "practice"
    assert vertical_for("legal") == "legal"
    assert vertical_for("precious_metals_buyer") == "local_retail"
    assert vertical_for("technology") == "saas"
    assert vertical_for("ecommerce") == "ecommerce"
    assert vertical_for("consulting") == "professional_services"
    assert vertical_for("") == "default"
    assert vertical_for("something_unknown") == "default"


def test_legal_does_not_get_dental_tasks():
    k = _keys("legal")
    assert "seo_schema_medical" not in k       # MedicalProcedure
    assert "seo_emergency_page" not in k        # dental content
    assert "seo_schema_legalservice" in k       # legal-specific schema
    assert "seo_attorney_bios" in k


def test_local_retail_no_saas_tasks():
    k = _keys("precious_metals_buyer")          # -> local_retail
    assert "seo_schema_software" not in k
    assert "seo_schema_product" not in k
    assert "seo_use_cases" not in k
    assert "seo_comparison_pages" not in k
    # …but does get local-business essentials + Store schema label
    assert "seo_schema_localbusiness" in k
    assert "seo_gbp_optimized" in k             # GBP relevant to all local biz
    assert _label("precious_metals_buyer", "seo_schema_localbusiness") == "LocalBusiness / Store schema markup"


def test_saas_gets_product_and_usecases():
    k = _keys("technology")                     # -> saas
    assert "seo_schema_software" in k
    assert "seo_use_cases" in k
    assert "seo_comparison_pages" in k
    assert "seo_schema_medical" not in k
    assert "seo_emergency_page" not in k


def test_practice_still_intact():
    k = _keys("practice")
    assert "seo_schema_medical" in k
    assert "seo_emergency_page" in k
    assert "seo_gbp_optimized" in k
    assert "seo_use_cases" not in k             # SaaS task stays out of practice


def test_universal_tasks_show_everywhere():
    for bt in ("practice", "legal", "precious_metals_buyer", "technology"):
        k = _keys(bt)
        assert "seo_llms_txt" in k
        assert "seo_schema_faq" in k
        assert "seo_blog_cadence" in k


def test_content_auto_tick_from_published_recs():
    recs = [
        {"rec_type": "faq_update", "status": "published"},
        {"rec_type": "blog_post", "status": "published"},
        {"rec_type": "expert_quote", "status": "pending"},   # not published -> no tick
    ]
    ticks = _content_task_status(recs)
    assert ticks.get("seo_faq_sections") is True
    assert ticks.get("seo_blog_cadence") is True
    assert "seo_expert_quotes" not in ticks


def test_unmapped_business_type_falls_back_to_baseline_not_empty():
    # P2 #6: an unknown business_type must NOT yield a silent empty checklist.
    from dashboard.app import _get_seo_tasks
    tasks = _get_seo_tasks({}, business_type="underwater_basket_weaving")
    assert tasks, "unmapped business_type should fall back to a baseline checklist, not empty"
