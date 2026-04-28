#!/usr/bin/env python3
"""Seed the database with existing customer data (Hilltop + Downtown Dental)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
db = CustomerDB()

# 1. Import Hilltop from customers.json
print("Importing from customers.json...")
db.import_from_json(str(DATA_DIR / "customers.json"))

# 2. Import Downtown Dental from profile.json
print("Importing Downtown Dental from profile.json...")
profile_path = DATA_DIR / "customers" / "downtown-dental" / "profile.json"
with open(profile_path) as f:
    p = json.load(f)

if not db.get_customer("downtown-dental"):
    # Format hours
    hours_obj = p.get("hours", {})
    if isinstance(hours_obj, dict):
        hours_str = ", ".join(
            f"{day.title()}: {time}" for day, time in hours_obj.items() if time != "Closed"
        )
    else:
        hours_str = str(hours_obj)

    db.add_customer(
        id="downtown-dental",
        name=p["name"],
        domain=p["domain"],
        platform=p.get("website_platform", "squarespace"),
        city=p["city"],
        state=p["state"],
        zip=p["zip_code"],
        address=p["address"],
        phone=p["phone"],
        email=p.get("email", ""),
        brand_voice=p.get("brand_voice", ""),
        hours=hours_str,
    )

    # Add providers
    for prov in p.get("providers", []):
        db.add_provider(
            customer_id="downtown-dental",
            name=prov["name"],
            credentials=prov.get("credentials", ""),
            specialties=prov.get("specialties", []),
            bio=prov.get("bio") or "",
            is_primary=True,
        )

    # Add contacts
    contacts = p.get("contacts", {})
    if contacts.get("owner"):
        owner = contacts["owner"]
        db.add_contact("downtown-dental", owner["name"], owner.get("email", ""), role="owner")
    if contacts.get("introducer"):
        intro = contacts["introducer"]
        db.add_contact("downtown-dental", intro["name"], role="introducer")

    # Add Google Places data
    gp = p.get("google_places", {})
    if gp.get("place_id"):
        db.upsert_google_places(
            customer_id="downtown-dental",
            place_id=gp["place_id"],
            rating=gp.get("rating", 0.0),
            review_count=gp.get("review_count", 0),
            match_confidence=gp.get("match_confidence", "high"),
        )

    # Add competitors
    comps = p.get("competitors", [])
    if comps:
        db.replace_competitors("downtown-dental", [
            {"name": c["name"], "rating": c["rating"], "review_count": c.get("reviews", 0),
             "location": c.get("location", "")}
            for c in comps
        ])

    # Set up platform access tracking
    for platform in ["gsc", "ga", "gbp", "squarespace", "cloudflare"]:
        db.add_platform_access("downtown-dental", platform)

    print(f"  Added Downtown Dental with {len(comps)} competitors")
else:
    print("  Downtown Dental already exists, skipping")

# Summary
print("\nDatabase ready:")
for c in db.list_customers():
    places = db.get_google_places(c["id"])
    providers = db.get_providers(c["id"])
    comps = db.get_competitors(c["id"])
    rating_str = f"{places['rating']} stars ({places['review_count']} reviews)" if places else "no Places data"
    print(f"  [{c['status'].upper():11}] {c['name']} ({c['domain']}) — {rating_str}, {len(providers)} providers, {len(comps)} competitors")

db.close()
