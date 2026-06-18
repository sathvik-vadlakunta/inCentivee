"""Tests for the Local Relevancy Engine — directory profiles + orchestrator."""

import pytest

from geo_agent.db import CustomerDB
from geo_agent.directory_profiles import (
    canonical_nap,
    directory_profile,
    is_local,
    profile_key,
    profile_target_count,
)
from geo_agent.local_relevancy import directory_breadth, run_local_relevancy


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "lr.db"))
    yield d
    d.close()


# ── Directory profiles ──────────────────────────────────────────────

def test_dental_and_medical_get_distinct_profiles():
    dental = {e["key"] for e in directory_profile("dental")}
    medical = {e["key"] for e in directory_profile("medical")}
    # Both are "practice" vertical but must differ.
    assert profile_key("dental") == "dental"
    assert profile_key("medical") == "medical"
    assert "1800dentist" in dental and "1800dentist" not in medical
    assert "doximity" in medical and "doximity" not in dental


def test_legal_profile_has_legal_dirs():
    keys = {e["key"] for e in directory_profile("legal")}
    assert {"avvo", "justia", "findlaw"}.issubset(keys)


def test_precious_metals_profile():
    keys = {e["key"] for e in directory_profile("precious_metals_buyer")}
    assert "png" in keys and "icta" in keys


def test_every_local_profile_includes_universal_and_aggregators():
    for bt in ("dental", "legal", "precious_metals_buyer", "consulting", "default"):
        keys = {e["key"] for e in directory_profile(bt)}
        assert "google_business_profile" in keys  # universal
        assert "data_axle" in keys                # aggregator


def test_profile_is_deduped():
    profile = directory_profile("dental")
    keys = [e["key"] for e in profile]
    assert len(keys) == len(set(keys))


def test_non_local_types_have_no_profile():
    for bt in ("ecommerce", "saas", "software", "product"):
        assert is_local(bt) is False
        assert directory_profile(bt) is None
        assert profile_target_count(bt) == 0


def test_practice_defaults_to_dental():
    assert profile_key("practice") == "dental"


def test_canonical_nap_builds_full_address():
    nap = canonical_nap({
        "name": "Acme Dental",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "phone": "512-555-1212",
        "domain": "acmedental.com",
    })
    assert nap["name"] == "Acme Dental"
    assert nap["address"] == "123 Main St, Austin, TX, 78701"
    assert nap["url"] == "https://acmedental.com"
    assert nap["phone"] == "512-555-1212"


# ── Module 2: directory breadth ─────────────────────────────────────

def test_breadth_counts_only_listed_and_nap_matching(db):
    db.add_customer(id="acme", name="Acme Dental", domain="acme.com",
                    business_type="dental", city="Austin", state="TX")
    target = profile_target_count("dental")
    db.save_citation("acme", directory="Google Business Profile", listed=True, nap_match=True)
    db.save_citation("acme", directory="Yelp", listed=True, nap_match=True)
    db.save_citation("acme", directory="Healthgrades", listed=True, nap_match=False)  # wrong NAP
    db.save_citation("acme", directory="Zocdoc", listed=False, nap_match=False)       # not listed

    br = directory_breadth(db, "acme", "dental")
    assert br["target"] == target
    assert br["listed_ok"] == 2  # only GBP + Yelp count
    assert br["tracked"] == 4
    assert 0 < br["pct"] < 100
    # A targeted dir we never wrote shows up as missing.
    assert any("Apple" in m for m in br["missing"])


def test_breadth_zero_when_no_citations(db):
    db.add_customer(id="empty", name="Empty", domain="e.com", business_type="legal")
    br = directory_breadth(db, "empty", "legal")
    assert br["listed_ok"] == 0
    assert br["pct"] == 0.0
    assert br["target"] == profile_target_count("legal")


# ── Orchestrator ────────────────────────────────────────────────────

def test_run_skips_non_local(db):
    db.add_customer(id="shop", name="Web Shop", domain="shop.com", business_type="ecommerce")
    r = run_local_relevancy(db, "shop", recompute=False)
    assert "non-local" in r["skipped"]


def test_run_local_customer_returns_modules(db):
    db.add_customer(id="firm", name="Smith Law", domain="smithlaw.com",
                    business_type="legal", city="Reno", state="NV", phone="775-555-0000")
    r = run_local_relevancy(db, "firm", recompute=False)
    assert r["business_type"] == "legal"
    assert r["canonical_nap"]["name"] == "Smith Law"
    mods = r["modules"]
    # Module 1 no-op (no BrightLocal account) -> configured False, run continues.
    assert mods["citations"]["configured"] is False
    # Module 2 ran.
    assert mods["directory_breadth"]["target"] == profile_target_count("legal")
    # Modules 3-5 stubbed.
    assert mods["service_area_pages"]["status"] == "not_built"


def test_run_missing_customer(db):
    r = run_local_relevancy(db, "nope", recompute=False)
    assert "not found" in r["skipped"]
