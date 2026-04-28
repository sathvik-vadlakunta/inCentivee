#!/usr/bin/env python3
"""Pre-fill the client welcome guide by scraping a practice website + Google Places.

Usage:
    python scripts/prefill_welcome_guide.py \
        --name "Hilltop Dental" \
        --url "https://www.hilltopdental.com" \
        --contact-name "Dr. David Gallup" \
        --contact-email "info@hilltopdental.com"

Requires env vars:
    GOOGLE_PLACES_API_KEY  — for verified business data + competitors
    ANTHROPIC_API_KEY      — for Claude extraction from scraped content
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

import anthropic
import httpx

# Add parent dir so we can import geo_agent modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.google_places import (
    fetch_nearby_competitors,
    fetch_place_data,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "docs" / "client-welcome-guide.md"

# Pages we want to scrape (common dental site slugs)
SCRAPE_SLUGS = [
    "/",
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/doctors",
    "/services",
    "/our-services",
    "/contact",
    "/contact-us",
    "/insurance",
    "/patient-info",
    "/new-patients",
    "/faq",
    "/reviews",
    "/testimonials",
]


def scrape_page(url: str, timeout: float = 15.0) -> str:
    """Fetch a URL and return cleaned text content."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "PracticeRank-Onboarding/1.0"})
            if resp.status_code != 200:
                return ""
            html = resp.text
    except Exception:
        return ""

    # Strip scripts, styles, then tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]  # cap per page to stay within Claude context


def scrape_site(base_url: str) -> dict[str, str]:
    """Scrape common pages from a dental practice website."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    pages = {}
    for slug in SCRAPE_SLUGS:
        url = f"{origin}{slug}"
        logger.info(f"Scraping {url}...")
        text = scrape_page(url)
        if text and len(text) > 100:
            pages[slug] = text

    logger.info(f"Scraped {len(pages)} pages with content")
    return pages


def extract_social_links(base_url: str) -> dict[str, str]:
    """Pull social media links from the homepage HTML."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(base_url, headers={"User-Agent": "PracticeRank-Onboarding/1.0"})
            html = resp.text
    except Exception:
        return {}

    socials = {}
    patterns = {
        "facebook": r'href=["\']?(https?://(?:www\.)?facebook\.com/[^"\'>\s]+)',
        "instagram": r'href=["\']?(https?://(?:www\.)?instagram\.com/[^"\'>\s]+)',
        "yelp": r'href=["\']?(https?://(?:www\.)?yelp\.com/biz/[^"\'>\s]+)',
        "google_business": r'href=["\']?(https?://(?:www\.)?google\.com/maps/place/[^"\'>\s]+)',
        "healthgrades": r'href=["\']?(https?://(?:www\.)?healthgrades\.com/[^"\'>\s]+)',
        "zocdoc": r'href=["\']?(https?://(?:www\.)?zocdoc\.com/[^"\'>\s]+)',
    }

    for name, pattern in patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            socials[name] = match.group(1).rstrip('"').rstrip("'")

    return socials


def extract_with_claude(
    practice_name: str,
    contact_name: str,
    contact_email: str,
    scraped_pages: dict[str, str],
    social_links: dict[str, str],
    places_data: dict | None,
    competitors: list[dict],
) -> dict:
    """Use Claude to extract structured practice info from scraped content."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — cannot extract practice info")
        return {}

    # Build context for Claude
    page_text = ""
    for slug, content in scraped_pages.items():
        page_text += f"\n\n--- PAGE: {slug} ---\n{content}"

    places_section = ""
    if places_data:
        places_section = f"""
GOOGLE PLACES VERIFIED DATA:
- Name: {places_data.get('name', '')}
- Address: {places_data.get('address', '')}
- City: {places_data.get('city', '')}
- State: {places_data.get('state', '')}
- ZIP: {places_data.get('zip_code', '')}
- Phone: {places_data.get('phone', '')}
- Rating: {places_data.get('rating', '')}
- Review Count: {places_data.get('review_count', '')}
- Website: {places_data.get('website', '')}
"""

    competitor_section = ""
    if competitors:
        competitor_section = "TOP COMPETITORS (from Google):\n"
        for c in competitors[:5]:
            competitor_section += f"- {c['name']} — {c['rating']} stars, {c['review_count']} reviews ({c['address']})\n"

    social_section = ""
    if social_links:
        social_section = "SOCIAL LINKS FOUND ON SITE:\n"
        for name, url in social_links.items():
            social_section += f"- {name}: {url}\n"

    prompt = f"""Extract structured practice information from the following scraped website content.
The practice is "{practice_name}" and the main contact is {contact_name} ({contact_email}).

{places_section}
{competitor_section}
{social_section}

SCRAPED WEBSITE CONTENT:
{page_text}

Return a JSON object with ONLY fields you can confidently extract. Use null for anything you cannot determine.
Do NOT guess or fabricate — only include data that is clearly stated on the website or in the Google Places data.

Required JSON structure:
{{
    "practice_name": "string",
    "website_url": "string",
    "street_address": "string or null",
    "city": "string or null",
    "state": "string or null",
    "zip_code": "string or null",
    "phone": "string or null",
    "email": "string or null",
    "office_hours": "string or null",
    "emergency_available": "yes/no/null",
    "year_established": "string or null",
    "languages_spoken": "string or null",
    "providers": [
        {{
            "name": "string",
            "credentials": "DDS/DMD/etc or null",
            "specialties": "string or null",
            "years_experience": "string or null",
            "bio": "2-3 sentence bio or null"
        }}
    ],
    "primary_services": "string or null",
    "specialty_services": "string or null",
    "signature_procedure": "string or null",
    "insurance_accepted": "string or null",
    "financing_options": "string or null",
    "payment_methods": "string or null",
    "brand_voice": "friendly/professional/clinical/warm — your assessment based on site tone",
    "neighborhoods_served": "string or null",
    "what_makes_different": "string or null",
    "google_rating": "number or null",
    "google_review_count": "number or null",
    "facebook_url": "string or null",
    "instagram_url": "string or null",
    "yelp_url": "string or null",
    "google_business_url": "string or null",
    "other_profiles": "string or null",
    "competitor_names": "string or null"
}}

Return ONLY the JSON object, no other text."""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Extract JSON from response (handle markdown code blocks)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Claude response as JSON:\n{text[:500]}")
        return {}


def fill_welcome_guide(data: dict, competitors: list[dict]) -> str:
    """Fill in the welcome guide template with extracted data."""
    template = TEMPLATE_PATH.read_text()

    def val(key: str, default: str = "") -> str:
        v = data.get(key)
        if v is None:
            return default
        return str(v)

    # Practice Details table
    replacements = {
        "| **Practice Name** | |": f"| **Practice Name** | {val('practice_name')} |",
        "| **Website URL** | |": f"| **Website URL** | {val('website_url')} |",
        "| **Street Address** | |": f"| **Street Address** | {val('street_address')} |",
        "| **City, State, ZIP** | |": f"| **City, State, ZIP** | {val('city')}{', ' + val('state') if val('state') else ''} {val('zip_code')} |".replace("  ", " "),
        "| **Main Phone Number** | |": f"| **Main Phone Number** | {val('phone')} |",
        "| **Public Email Address** | |": f"| **Public Email Address** | {val('email')} |",
        "| **Office Hours** | |": f"| **Office Hours** | {val('office_hours')} |",
        "| **Emergency/After-Hours Available?** | Yes / No |": f"| **Emergency/After-Hours Available?** | {val('emergency_available', 'Yes / No')} |",
        "| **Year Established** | |": f"| **Year Established** | {val('year_established')} |",
        "| **Languages Spoken** | |": f"| **Languages Spoken** | {val('languages_spoken')} |",
    }

    # Providers table
    providers = data.get("providers", [])
    if providers:
        p1 = providers[0] if len(providers) > 0 else {}
        p2 = providers[1] if len(providers) > 1 else {}
        p3 = providers[2] if len(providers) > 2 else {}

        def pval(p: dict, key: str) -> str:
            v = p.get(key)
            return str(v) if v else ""

        replacements.update({
            "| **Full Name** | | | |": f"| **Full Name** | {pval(p1, 'name')} | {pval(p2, 'name')} | {pval(p3, 'name')} |",
            "| **Credentials** (DDS, DMD, etc.) | | | |": f"| **Credentials** (DDS, DMD, etc.) | {pval(p1, 'credentials')} | {pval(p2, 'credentials')} | {pval(p3, 'credentials')} |",
            "| **Specialties** | | | |": f"| **Specialties** | {pval(p1, 'specialties')} | {pval(p2, 'specialties')} | {pval(p3, 'specialties')} |",
            "| **Years of Experience** | | | |": f"| **Years of Experience** | {pval(p1, 'years_experience')} | {pval(p2, 'years_experience')} | {pval(p3, 'years_experience')} |",
            "| **Short Bio** (2-3 sentences) | | | |": f"| **Short Bio** (2-3 sentences) | {pval(p1, 'bio')} | {pval(p2, 'bio')} | {pval(p3, 'bio')} |",
        })

    # Services
    replacements.update({
        "| **Primary Services** (cleanings, fillings, crowns, etc.) | |": f"| **Primary Services** (cleanings, fillings, crowns, etc.) | {val('primary_services')} |",
        "| **Specialty Services** (implants, Invisalign, sedation, etc.) | |": f"| **Specialty Services** (implants, Invisalign, sedation, etc.) | {val('specialty_services')} |",
        "| **Signature Procedure** (what are you best known for?) | |": f"| **Signature Procedure** (what are you best known for?) | {val('signature_procedure')} |",
    })

    # Insurance
    replacements.update({
        "| **Insurance Plans Accepted** | |": f"| **Insurance Plans Accepted** | {val('insurance_accepted')} |",
        "| **Financing Options** (CareCredit, in-house plans, etc.) | |": f"| **Financing Options** (CareCredit, in-house plans, etc.) | {val('financing_options')} |",
        "| **Payment Methods** | |": f"| **Payment Methods** | {val('payment_methods')} |",
    })

    # Brand
    competitor_str = val("competitor_names", "")
    if not competitor_str and competitors:
        competitor_str = ", ".join(c["name"] for c in competitors[:3])

    replacements.update({
        "| **How should your practice sound online?** (friendly, professional, clinical, warm, etc.) | |": f"| **How should your practice sound online?** (friendly, professional, clinical, warm, etc.) | {val('brand_voice')} |",
        "| **Who are your top competitors?** (practice names or websites) | |": f"| **Who are your top competitors?** (practice names or websites) | {competitor_str} |",
        "| **Neighborhoods or areas you serve** | |": f"| **Neighborhoods or areas you serve** | {val('neighborhoods_served')} |",
        "| **What makes your practice different?** | |": f"| **What makes your practice different** | {val('what_makes_different')} |",
    })

    # Online presence
    replacements.update({
        "| **Google Business Profile URL** | |": f"| **Google Business Profile URL** | {val('google_business_url')} |",
        "| **Facebook Page URL** | |": f"| **Facebook Page URL** | {val('facebook_url')} |",
        "| **Instagram Handle** | |": f"| **Instagram Handle** | {val('instagram_url')} |",
        "| **Yelp Page URL** | |": f"| **Yelp Page URL** | {val('yelp_url')} |",
        "| **Other Profiles** (Healthgrades, Zocdoc, etc.) | |": f"| **Other Profiles** (Healthgrades, Zocdoc, etc.) | {val('other_profiles')} |",
    })

    result = template
    for old, new in replacements.items():
        result = result.replace(old, new)

    return result


def main():
    parser = argparse.ArgumentParser(description="Pre-fill PracticeRank client welcome guide")
    parser.add_argument("--name", required=True, help="Practice name (e.g. 'Hilltop Dental')")
    parser.add_argument("--url", required=True, help="Practice website URL")
    parser.add_argument("--contact-name", default="", help="Main contact person name")
    parser.add_argument("--contact-email", default="", help="Main contact email")
    parser.add_argument("--output", default=None, help="Output file path (default: data/output/<slug>-welcome-guide.md)")
    args = parser.parse_args()

    # Normalize URL
    url = args.url if "://" in args.url else f"https://{args.url}"
    domain = urlparse(url).netloc.removeprefix("www.")

    # Step 1: Google Places lookup
    logger.info("Step 1: Looking up practice on Google Places...")
    places_api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    places_data = None
    competitors_raw = []

    if places_api_key:
        # Try to extract city/state from Google Places
        verified = fetch_place_data(
            name=args.name,
            city="",  # don't filter by city — we don't know it yet
            state="",
            domain=domain,
            phone="",
            api_key=places_api_key,
        )
        if verified:
            places_data = {
                "name": verified.name,
                "address": verified.address,
                "city": verified.city,
                "state": verified.state,
                "zip_code": verified.zip_code,
                "phone": verified.phone,
                "rating": verified.rating,
                "review_count": verified.review_count,
                "website": verified.website,
                "match_confidence": verified.match_confidence,
            }
            logger.info(f"  Found: {verified.name} ({verified.match_confidence} confidence)")
            logger.info(f"  Rating: {verified.rating} ({verified.review_count} reviews)")

            # Fetch competitors
            if verified.lat and verified.lng:
                comps = fetch_nearby_competitors(
                    lat=verified.lat,
                    lng=verified.lng,
                    practice_name=args.name,
                    api_key=places_api_key,
                )
                competitors_raw = [
                    {"name": c.name, "rating": c.rating, "review_count": c.review_count, "address": c.address}
                    for c in comps
                ]
                logger.info(f"  Found {len(competitors_raw)} competitors nearby")
        else:
            logger.warning("  No match found on Google Places")
    else:
        logger.warning("  GOOGLE_PLACES_API_KEY not set — skipping Places lookup")

    # Step 2: Scrape website
    logger.info("Step 2: Scraping practice website...")
    scraped_pages = scrape_site(url)

    # Step 3: Extract social links from HTML
    logger.info("Step 3: Extracting social media links...")
    social_links = extract_social_links(url)
    if social_links:
        logger.info(f"  Found: {', '.join(social_links.keys())}")

    # Step 4: Claude extraction
    logger.info("Step 4: Analyzing content with Claude...")
    extracted = extract_with_claude(
        practice_name=args.name,
        contact_name=args.contact_name,
        contact_email=args.contact_email,
        scraped_pages=scraped_pages,
        social_links=social_links,
        places_data=places_data,
        competitors=competitors_raw,
    )

    if not extracted:
        logger.error("Claude extraction failed — outputting empty template")
        extracted = {"practice_name": args.name, "website_url": url}

    # Ensure basics are set
    extracted.setdefault("practice_name", args.name)
    extracted.setdefault("website_url", url)
    if args.contact_email:
        extracted.setdefault("email", args.contact_email)

    # Override with Google Places verified data when available
    if places_data:
        if places_data.get("match_confidence") in ("high", "medium"):
            extracted["google_rating"] = places_data["rating"]
            extracted["google_review_count"] = places_data["review_count"]
        if places_data.get("match_confidence") == "high":
            extracted.setdefault("street_address", places_data.get("address", ""))
            extracted.setdefault("phone", places_data.get("phone", ""))
            extracted.setdefault("city", places_data.get("city", ""))
            extracted.setdefault("state", places_data.get("state", ""))
            extracted.setdefault("zip_code", places_data.get("zip_code", ""))

    # Step 5: Fill template
    logger.info("Step 5: Generating pre-filled welcome guide...")
    filled = fill_welcome_guide(extracted, competitors_raw)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
        output_dir = Path(__file__).resolve().parent.parent / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{slug}-welcome-guide.md"

    output_path.write_text(filled)
    logger.info(f"\nDone! Pre-filled guide saved to: {output_path}")

    # Print summary of what was filled vs what still needs manual input
    filled_count = 0
    empty_count = 0
    for key, value in extracted.items():
        if key == "providers":
            continue
        if value and value != "null":
            filled_count += 1
        else:
            empty_count += 1

    provider_count = len(extracted.get("providers", []))
    logger.info(f"  Auto-filled: {filled_count} fields")
    logger.info(f"  Still empty: {empty_count} fields")
    logger.info(f"  Providers found: {provider_count}")
    logger.info(f"  Competitors found: {len(competitors_raw)}")

    if places_data:
        logger.info(f"  Google rating: {places_data['rating']} ({places_data['review_count']} reviews)")


if __name__ == "__main__":
    main()
