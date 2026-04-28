#!/usr/bin/env python3
"""PracticeRank Onboarding CLI — VA-friendly interactive customer setup.

Usage:
    python scripts/onboard.py                          # Interactive onboarding
    python scripts/onboard.py --update-access <id>     # Update platform access status
    python scripts/onboard.py --test                   # Dry run with mock data
    python scripts/onboard.py --import-json             # Import from legacy customers.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add parent dir so we can import geo_agent modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def detect_platform(domain: str) -> str:
    """Try to detect the website platform by inspecting HTML."""
    try:
        import httpx
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(
                f"https://{domain}",
                headers={"User-Agent": "PracticeRank-Onboarding/1.0"},
            )
            html = resp.text.lower()
    except Exception:
        return "unknown"

    if "squarespace" in html or "sqsp" in html:
        return "squarespace"
    if "webflow" in html or "wf-" in html:
        return "webflow"
    if "wp-content" in html or "wordpress" in html:
        return "wordpress"
    return "unknown"


def auto_discover(name: str, domain: str) -> dict:
    """Run auto-discovery: scrape site + Google Places lookup."""
    result = {
        "platform": "unknown",
        "places_data": None,
        "competitors": [],
        "social_links": {},
        "extracted": {},
    }

    # Detect platform
    print("\n  Detecting website platform...")
    result["platform"] = detect_platform(domain)
    if result["platform"] != "unknown":
        print(f"  Platform: {result['platform'].title()} detected")
    else:
        print("  Platform: Could not auto-detect")

    # Google Places lookup
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if api_key:
        print("  Looking up on Google Places...")
        try:
            from geo_agent.google_places import fetch_place_data, fetch_nearby_competitors

            verified = fetch_place_data(
                name=name, city="", state="", domain=domain, phone="", api_key=api_key,
            )
            if verified:
                result["places_data"] = {
                    "name": verified.name,
                    "address": verified.address,
                    "city": verified.city,
                    "state": verified.state,
                    "zip_code": verified.zip_code,
                    "phone": verified.phone,
                    "rating": verified.rating,
                    "review_count": verified.review_count,
                    "place_id": verified.place_id,
                    "lat": verified.lat,
                    "lng": verified.lng,
                    "match_confidence": verified.match_confidence,
                }
                print(f"  Found: {verified.name} -- {verified.address}")
                print(f"  Rating: {verified.rating} ({verified.review_count} reviews)")

                if verified.lat and verified.lng:
                    comps = fetch_nearby_competitors(
                        lat=verified.lat, lng=verified.lng,
                        practice_name=name, api_key=api_key,
                    )
                    result["competitors"] = [
                        {"name": c.name, "rating": c.rating, "review_count": c.review_count,
                         "address": c.address, "place_id": c.place_id}
                        for c in comps
                    ]
                    print(f"  Competitors: {len(result['competitors'])} nearby practices found")
            else:
                print("  No match found on Google Places")
        except Exception as e:
            print(f"  Google Places lookup failed: {e}")
    else:
        print("  GOOGLE_PLACES_API_KEY not set -- skipping Places lookup")

    # Scrape site for social links
    try:
        from scripts.prefill_welcome_guide import extract_social_links
        print("  Checking for social media links...")
        result["social_links"] = extract_social_links(f"https://{domain}")
        if result["social_links"]:
            print(f"  Social: {', '.join(result['social_links'].keys())} found")
    except Exception:
        pass

    return result


def prompt_input(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {label}{suffix}: ").strip()
    return value or default


def confirm(msg: str) -> bool:
    return input(f"  {msg} (y/n): ").strip().lower() in ("y", "yes")


def interactive_onboard(db: CustomerDB, test_mode: bool = False):
    """Run the interactive onboarding flow."""
    print()
    print("Welcome to PracticeRank Onboarding")
    print("=" * 40)

    # Step 1: Basic Info
    print("\nStep 1: Basic Info")
    name = prompt_input("Practice name")
    url = prompt_input("Website URL")

    # Normalize URL and extract domain
    if url and "://" not in url:
        url = "https://" + url
    domain = urlparse(url).netloc.removeprefix("www.") if url else ""

    contact_name = prompt_input("Contact name")
    contact_email = prompt_input("Contact email")
    contact_phone = prompt_input("Contact phone", "")

    # Step 2: Auto-Discovery
    print("\nStep 2: Auto-Discovery (scraping site + Google Places)...")
    if test_mode:
        print("  [TEST MODE] Skipping auto-discovery")
        discovery = {
            "platform": "squarespace",
            "places_data": {
                "name": name, "address": "123 Main St", "city": "Test City",
                "state": "TX", "zip_code": "12345", "phone": "(555) 555-5555",
                "rating": 4.8, "review_count": 150, "place_id": "test123",
                "lat": 30.0, "lng": -97.0, "match_confidence": "high",
            },
            "competitors": [
                {"name": "Test Competitor", "rating": 4.5, "review_count": 100,
                 "address": "456 Oak Ave", "place_id": "comp1"},
            ],
            "social_links": {"facebook": "https://facebook.com/test"},
            "extracted": {},
        }
    else:
        discovery = auto_discover(name, domain)

    places = discovery.get("places_data") or {}
    platform = discovery.get("platform", "unknown")

    # Step 3: Review & Confirm
    print("\nStep 3: Review & Confirm")

    customer_id = slugify(name)
    customer_id = prompt_input("Customer ID", customer_id)

    city = prompt_input("City", places.get("city", ""))
    state = prompt_input("State", places.get("state", ""))
    zip_code = prompt_input("ZIP", places.get("zip_code", ""))
    address = prompt_input("Address", places.get("address", ""))
    phone = prompt_input("Phone", places.get("phone", ""))

    if platform == "unknown":
        platform = prompt_input("Platform (webflow/squarespace/wordpress)", "squarespace")
    else:
        platform = prompt_input("Platform", platform)

    # Step 4: Save to database
    print("\nStep 4: Saving to database...")
    try:
        db.add_customer(
            id=customer_id,
            name=name,
            domain=domain,
            platform=platform,
            city=city,
            state=state,
            zip=zip_code,
            address=address,
            phone=phone,
            email=contact_email,
        )

        # Add primary contact
        db.add_contact(
            customer_id=customer_id,
            name=contact_name,
            email=contact_email,
            phone=contact_phone,
            role="owner",
        )

        # Add Google Places data
        if places.get("place_id"):
            db.upsert_google_places(
                customer_id=customer_id,
                place_id=places["place_id"],
                rating=places.get("rating", 0.0),
                review_count=places.get("review_count", 0),
                match_confidence=places.get("match_confidence", "low"),
                lat=places.get("lat", 0.0),
                lng=places.get("lng", 0.0),
            )

        # Add competitors
        comps = discovery.get("competitors", [])
        if comps:
            db.replace_competitors(customer_id, comps)

        # Set up platform access tracking
        access_platforms = _get_required_access(platform)
        for p in access_platforms:
            db.add_platform_access(customer_id, p)

        print(f"  Saved to database: {customer_id}")

    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # Step 5: Generate onboarding email
    print("\nStep 5: Generating onboarding email...")
    customer_dir = Path(__file__).resolve().parent.parent / "data" / "customers" / customer_id
    customer_dir.mkdir(parents=True, exist_ok=True)

    email_text = _generate_onboarding_email(
        contact_name=contact_name,
        practice_name=name,
        platform=platform,
    )
    email_path = customer_dir / "onboarding-email.txt"
    email_path.write_text(email_text)
    print(f"  Email saved to {email_path}")

    print(f"\nDone! Next: Send the onboarding email and track access grants.")
    print(f"  Update access: python scripts/onboard.py --update-access {customer_id}")


def _get_required_access(platform: str) -> list[str]:
    """Determine which platform access grants we need based on platform."""
    access = ["gsc", "ga", "gbp", "cloudflare"]
    if platform == "webflow":
        access.append("webflow")
    elif platform == "squarespace":
        access.append("squarespace")
    elif platform == "wordpress":
        access.append("wordpress")
    return access


def _generate_onboarding_email(contact_name: str, practice_name: str, platform: str) -> str:
    """Generate the onboarding access request email."""
    # Try to load template
    template_path = (
        Path(__file__).resolve().parent.parent
        / "templates" / "emails" / "01-initial-access-request.md"
    )

    if template_path.exists():
        text = template_path.read_text()
        text = text.replace("{contact_name}", contact_name)
        text = text.replace("{practice_name}", practice_name)
        text = text.replace("{platform}", platform.title())

        access_steps = _get_platform_access_steps(platform)
        text = text.replace("{platform_access_steps}", access_steps)
        return text

    # Fallback inline template
    access_steps = _get_platform_access_steps(platform)
    return f"""Hi {contact_name},

Welcome to PracticeRank! We're excited to start optimizing {practice_name}'s online presence.

To get started, we need access to a few platforms. Here's what we need:

1. Google Search Console — Add jon@practicerank.ai as a Full User
2. Google Analytics — Add jon@practicerank.ai as an Editor
3. Google Business Profile — Add jon@practicerank.ai as a Manager

{access_steps}

All access is used solely for SEO optimization and reporting. We never modify your
site without your explicit approval.

If you have any questions about granting access, just reply to this email.

Best,
Jon Lucas
PracticeRank
"""


def _get_platform_access_steps(platform: str) -> str:
    if platform == "squarespace":
        return """4. Squarespace — Add jon@practicerank.ai as a contributor
   (Settings > Permissions > Contributors > Invite Contributor)
5. What Squarespace plan are you on? (Business, Commerce Basic, Commerce Advanced)"""
    elif platform == "webflow":
        return """4. Webflow — Add jon@practicerank.ai as a site collaborator
5. Webflow API Token — Generate at Settings > Apps & Integrations > API Access
6. Your Webflow Site ID (found in Site Settings > General)"""
    elif platform == "wordpress":
        return """4. WordPress — Create an admin account for jon@practicerank.ai
   Or provide hosting panel access (WP Engine, SiteGround, etc.)"""
    return "4. Website platform access (details TBD based on your setup)"


def update_access(db: CustomerDB, customer_id: str):
    """Interactive flow to update platform access status."""
    customer = db.get_customer(customer_id)
    if not customer:
        print(f"Customer not found: {customer_id}")
        return

    print(f"\nPlatform Access for: {customer['name']}")
    print("-" * 40)

    access_list = db.get_platform_access(customer_id)
    if not access_list:
        print("No platform access records found.")
        return

    for i, a in enumerate(access_list, 1):
        status_icon = {"pending": "[ ]", "granted": "[x]", "not_needed": "[-]"}.get(
            a["status"], "[?]"
        )
        print(f"  {i}. {status_icon} {a['platform'].upper()} — {a['status']}")

    print()
    while True:
        choice = input("Update which platform? (number, or 'q' to quit): ").strip()
        if choice.lower() == "q":
            break
        try:
            idx = int(choice) - 1
            item = access_list[idx]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue

        new_status = input(f"  New status for {item['platform'].upper()} (granted/not_needed): ").strip()
        if new_status in ("granted", "not_needed"):
            db.update_access_status(customer_id, item["platform"], new_status)
            print(f"  Updated {item['platform']} to {new_status}")
        else:
            print("  Invalid status.")

    # Check if all access is granted
    pending = db.get_pending_access(customer_id)
    if not pending:
        print("\nAll access granted! Setting customer status to active.")
        db.set_customer_status(customer_id, "active")
    else:
        print(f"\n{len(pending)} platform(s) still pending.")


def main():
    parser = argparse.ArgumentParser(description="PracticeRank Onboarding CLI")
    parser.add_argument("--update-access", metavar="CUSTOMER_ID", help="Update platform access for a customer")
    parser.add_argument("--test", action="store_true", help="Test mode — use mock data")
    parser.add_argument("--import-json", action="store_true", help="Import from legacy customers.json")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)

    try:
        if args.import_json:
            json_path = str(Path(__file__).resolve().parent.parent / "data" / "customers.json")
            print(f"Importing from {json_path}...")
            db.import_from_json(json_path)
            print("Done!")
        elif args.update_access:
            update_access(db, args.update_access)
        else:
            interactive_onboard(db, test_mode=args.test)
    finally:
        db.close()


if __name__ == "__main__":
    main()
