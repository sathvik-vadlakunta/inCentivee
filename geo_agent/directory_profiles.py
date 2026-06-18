"""Per-business-type local directory profiles + canonical NAP.

The Local Relevancy Engine targets a different set of directories for each kind
of customer. Dental and medical both map to the ``practice`` vertical but need
DISTINCT directory sets, so profiles are keyed by ``business_type`` (finer than
``vertical_for()``), falling back to a vertical-ish key, then ``default``.

Every local business gets the UNIVERSAL set + the DATA AGGREGATORS (which
syndicate NAP everywhere). Non-local business types (ecommerce/saas) have no
profile — the engine no-ops for them.

A directory entry is ``{"key", "name", "tier"}`` where tier ∈
core | vertical | aggregator.  See specs/active/local-relevancy-engine.html.
"""

from __future__ import annotations


def _d(key: str, name: str, tier: str) -> dict:
    return {"key": key, "name": name, "tier": tier}


# Every local business, regardless of vertical.
UNIVERSAL_DIRECTORIES: list[dict] = [
    _d("google_business_profile", "Google Business Profile", "core"),
    _d("apple_business_connect", "Apple Business Connect", "core"),
    _d("bing_places", "Bing Places", "core"),
    _d("yelp", "Yelp", "core"),
    _d("facebook", "Facebook", "core"),
    _d("bbb", "Better Business Bureau", "core"),
    _d("nextdoor", "Nextdoor", "core"),
    _d("chamber_of_commerce", "Local Chamber of Commerce", "core"),
]

# Data aggregators that push NAP to hundreds of downstream sites. BrightLocal's
# Citation Builder submits to these — listing here = "the engine targets them".
DATA_AGGREGATORS: list[dict] = [
    _d("data_axle", "Data Axle (Infogroup)", "aggregator"),
    _d("foursquare", "Foursquare", "aggregator"),
    _d("localeze", "Localeze / Neustar", "aggregator"),
]

# Vertical-specific directories, added on top of the universal + aggregator sets.
VERTICAL_DIRECTORIES: dict[str, list[dict]] = {
    "dental": [
        _d("healthgrades", "Healthgrades", "vertical"),
        _d("zocdoc", "Zocdoc", "vertical"),
        _d("vitals", "Vitals", "vertical"),
        _d("ratemds", "RateMDs", "vertical"),
        _d("1800dentist", "1-800-Dentist", "vertical"),
        _d("ada_find_a_dentist", "ADA Find-a-Dentist", "vertical"),
        _d("wellness_com", "Wellness.com", "vertical"),
        _d("caredash", "CareDash", "vertical"),
    ],
    "medical": [
        _d("healthgrades", "Healthgrades", "vertical"),
        _d("vitals", "Vitals", "vertical"),
        _d("zocdoc", "Zocdoc", "vertical"),
        _d("webmd", "WebMD Physician Directory", "vertical"),
        _d("ratemds", "RateMDs", "vertical"),
        _d("doximity", "Doximity", "vertical"),
        _d("sharecare", "Sharecare", "vertical"),
        _d("usnews_doctors", "US News Doctor Finder", "vertical"),
        _d("caredash", "CareDash", "vertical"),
    ],
    "legal": [
        _d("avvo", "Avvo", "vertical"),
        _d("justia", "Justia", "vertical"),
        _d("findlaw", "FindLaw", "vertical"),
        _d("lawyers_com", "Lawyers.com", "vertical"),
        _d("martindale", "Martindale-Hubbell", "vertical"),
        _d("super_lawyers", "Super Lawyers", "vertical"),
        _d("nolo", "Nolo", "vertical"),
        _d("legalmatch", "LegalMatch", "vertical"),
        _d("state_bar", "State Bar Directory", "vertical"),
    ],
    "precious_metals": [
        _d("png", "Professional Numismatists Guild", "vertical"),
        _d("icta", "ICTA (Industry Council for Tangible Assets)", "vertical"),
        _d("jbt", "Jewelers Board of Trade", "vertical"),
        _d("coin_dealer_dirs", "Coin/Bullion Dealer Directories", "vertical"),
        _d("we_buy_gold_dirs", "\"We Buy Gold\" Local Directories", "vertical"),
    ],
    "local_retail": [
        _d("yellowpages", "YellowPages", "vertical"),
        _d("manta", "Manta", "vertical"),
        _d("local_com", "Local.com", "vertical"),
    ],
    "professional_services": [
        _d("clutch", "Clutch", "vertical"),
        _d("upcity", "UpCity", "vertical"),
        _d("manta", "Manta", "vertical"),
    ],
    "finance": [
        _d("napfa", "NAPFA (fee-only advisors)", "vertical"),
        _d("cpa_directory", "CPA Directory", "vertical"),
        _d("smartvestor", "Advisor Directories", "vertical"),
    ],
    "default": [],
}

# business_type -> profile key. Dental and medical are deliberately distinct.
# 'practice' defaults to dental (our core), 'medical'/'doctor' to medical.
_PROFILE_KEY: dict[str, str] = {
    "dental": "dental",
    "practice": "dental",
    "medical": "medical",
    "doctor": "medical",
    "legal": "legal",
    "precious_metals_buyer": "precious_metals",
    "jeweler": "precious_metals",
    "retail": "local_retail",
    "shop": "local_retail",
    "consulting": "professional_services",
    "advisory": "professional_services",
    "agency": "professional_services",
    "finance": "finance",
}

# Business types that are NOT local foot-traffic businesses — no profile.
NON_LOCAL_TYPES = {"ecommerce", "product", "technology", "saas", "software"}


def is_local(business_type: str | None) -> bool:
    return (business_type or "").lower() not in NON_LOCAL_TYPES


def profile_key(business_type: str | None) -> str:
    return _PROFILE_KEY.get((business_type or "").lower(), "default")


def directory_profile(business_type: str | None) -> list[dict] | None:
    """Ordered, de-duped directory targets for a business type.

    Returns None for non-local business types (engine no-ops). Order is
    universal core → vertical-specific → data aggregators.
    """
    if not is_local(business_type):
        return None
    vertical = VERTICAL_DIRECTORIES.get(profile_key(business_type), [])
    seen: set[str] = set()
    out: list[dict] = []
    for entry in [*UNIVERSAL_DIRECTORIES, *vertical, *DATA_AGGREGATORS]:
        if entry["key"] in seen:
            continue
        seen.add(entry["key"])
        out.append(entry)
    return out


def profile_target_count(business_type: str | None) -> int:
    profile = directory_profile(business_type)
    return len(profile) if profile else 0


# schema.org type for service-area / on-site pages, by profile key.
CONTENT_SCHEMA: dict[str, str] = {
    "dental": "Dentist",
    "medical": "Physician",
    "legal": "Attorney",
    "precious_metals": "Store",
    "local_retail": "Store",
    "professional_services": "ProfessionalService",
    "finance": "FinancialService",
    "default": "LocalBusiness",
}

# Fallback "service" terms used to build {service} in {city} pages when the
# customer has no explicit services on file.
_DEFAULT_SERVICE_TERMS: dict[str, list[str]] = {
    "dental": ["Dental Implants", "Invisalign", "Teeth Whitening", "Emergency Dentist"],
    "medical": ["Primary Care", "Urgent Care", "Telehealth Visits"],
    "legal": ["Free Consultation", "Personal Injury", "Family Law"],
    "precious_metals": ["Sell Gold", "Sell Silver", "Sell Coins", "Jewelry Buyer"],
    "local_retail": ["Shop Local", "Our Services"],
    "professional_services": ["Consulting Services"],
    "finance": ["Financial Planning", "Tax Preparation"],
    "default": ["Our Services"],
}


# Suggested Google Business Profile primary category, by profile key.
GBP_PRIMARY_CATEGORY: dict[str, str] = {
    "dental": "Dentist",
    "medical": "Doctor / Medical Clinic",
    "legal": "Law Firm",
    "precious_metals": "Gold Dealer / Jewelry Buyer",
    "local_retail": "Store",
    "professional_services": "Consultant",
    "finance": "Financial Consultant",
    "default": "Local Business",
}


def content_schema(business_type: str | None) -> str:
    return CONTENT_SCHEMA.get(profile_key(business_type), "LocalBusiness")


def gbp_primary_category(business_type: str | None) -> str:
    return GBP_PRIMARY_CATEGORY.get(profile_key(business_type), "Local Business")


def default_service_terms(business_type: str | None) -> list[str]:
    return _DEFAULT_SERVICE_TERMS.get(profile_key(business_type), ["Our Services"])


def canonical_nap(customer: dict) -> dict:
    """The single source of truth every directory is checked/rendered against.

    Built from the customer's verified record. Keep ONE format and reuse it
    everywhere — inconsistent NAP is the top local-trust killer.
    """
    parts = [customer.get("address"), customer.get("city"), customer.get("state"), customer.get("zip")]
    full_address = ", ".join(p for p in parts if p)
    domain = (customer.get("domain") or "").strip()
    url = domain if domain.startswith("http") else (f"https://{domain}" if domain else "")
    return {
        "name": (customer.get("name") or "").strip(),
        "address": full_address,
        "phone": (customer.get("phone") or "").strip(),
        "url": url,
    }
