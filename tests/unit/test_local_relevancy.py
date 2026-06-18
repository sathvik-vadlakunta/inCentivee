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
    # Module 3 built (no service areas configured here -> graceful no-op).
    assert mods["service_area_pages"]["status"] == "no_service_areas"
    # Modules 4-5 still stubbed.
    assert mods["review_recency"]["status"] == "not_built"


def test_run_missing_customer(db):
    r = run_local_relevancy(db, "nope", recompute=False)
    assert "not found" in r["skipped"]


# ── Module 3: nearby cities + service-area pages ────────────────────

def test_haversine_known_distance():
    from geo_agent.nearby_cities import haversine_miles
    # Reno, NV -> Sparks, NV is ~4 miles
    d = haversine_miles(39.5296, -119.8138, 39.5349, -119.7527)
    assert 2 < d < 7


def test_filter_rank_cities_radius_origin_population():
    from geo_agent.nearby_cities import filter_rank_cities
    center = (39.5296, -119.8138)  # Reno
    candidates = [
        {"name": "Reno", "lat": 39.5296, "lon": -119.8138, "population": 264000},  # origin -> dropped
        {"name": "Sparks", "lat": 39.5349, "lon": -119.7527, "population": 105000},
        {"name": "Carson City", "lat": 39.1638, "lon": -119.7674, "population": 58000},
        {"name": "Sun Valley", "lat": 39.5969, "lon": -119.7766, "population": 20000},
        {"name": "Sacramento", "lat": 38.5816, "lon": -121.4944, "population": 525000},  # ~130mi -> filtered
    ]
    out = filter_rank_cities(center[0], center[1], candidates,
                             origin_name="Reno", max_miles=18, limit=8)
    assert "Reno" not in out          # origin dropped
    assert "Sacramento" not in out    # outside radius
    assert out[0] == "Sparks"         # highest population within radius
    assert "Sun Valley" in out


def test_ensure_service_areas_returns_existing(db, monkeypatch):
    import json
    from geo_agent import nearby_cities
    db.add_customer(id="c1", name="C1", domain="c1.com", business_type="dental",
                    city="Reno", state="NV")
    db.update_customer("c1", service_areas=json.dumps(["Sparks", "Carson City"]))
    # Should not call discovery when already set.
    monkeypatch.setattr(nearby_cities, "nearby_cities", lambda *a, **k: ["SHOULD_NOT_USE"])
    assert nearby_cities.ensure_service_areas(db, "c1") == ["Sparks", "Carson City"]


def test_ensure_service_areas_discovers_and_persists(db, monkeypatch):
    from geo_agent import nearby_cities
    db.add_customer(id="c2", name="C2", domain="c2.com", business_type="legal",
                    city="Reno", state="NV")
    monkeypatch.setattr(nearby_cities, "nearby_cities", lambda *a, **k: ["Sparks", "Fernley"])
    got = nearby_cities.ensure_service_areas(db, "c2")
    assert got == ["Sparks", "Fernley"]
    # Persisted on the customer.
    assert db.get_customer("c2")["service_areas"] == ["Sparks", "Fernley"]


def test_module3_creates_service_area_recs_and_is_idempotent(db):
    import json
    db.add_customer(id="firm", name="Smith Law", domain="smithlaw.com",
                    business_type="legal", city="Reno", state="NV", phone="775-555-0000")
    db.update_customer("firm", service_areas=json.dumps(["Sparks", "Carson City"]))

    r1 = run_local_relevancy(db, "firm", recompute=False)
    m3 = r1["modules"]["service_area_pages"]
    assert m3["status"] == "ok"
    assert m3["created"] > 0
    recs = db.get_content_recommendations("firm", limit=500)
    sa = [x for x in recs if x.get("category") == "service_area"]
    assert sa, "expected service_area recommendations"
    titles = {x["title"] for x in sa}
    assert "Free Consultation in Sparks" in titles  # legal default service x city
    assert any(x["rec_type"] == "new_page" and x["target_page"].startswith("/") for x in sa)

    # Second run: title de-dupe -> no new recs created.
    r2 = run_local_relevancy(db, "firm", recompute=False)
    assert r2["modules"]["service_area_pages"]["created"] == 0


def test_module3_no_service_areas(db):
    # No service_areas + no GEONAMES -> graceful no-op (no network in tests).
    db.add_customer(id="bare", name="Bare", domain="bare.com", business_type="dental")
    r = run_local_relevancy(db, "bare", recompute=False)
    assert r["modules"]["service_area_pages"]["status"] == "no_service_areas"


def test_content_schema_and_service_terms():
    from geo_agent.directory_profiles import content_schema, default_service_terms
    assert content_schema("dental") == "Dentist"
    assert content_schema("legal") == "Attorney"
    assert content_schema("precious_metals_buyer") == "Store"
    assert "Sell Gold" in default_service_terms("precious_metals_buyer")
    assert default_service_terms("ecommerce") == ["Our Services"]  # default fallback
