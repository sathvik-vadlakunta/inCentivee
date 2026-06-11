"""Generate JSON-LD schema markup for businesses.

Schemas that matter for AI/LLM discoverability:
- LocalBusiness/Dentist/Organization — homepage
- FAQPage — on service pages (highest priority for GEO)
- Service — for each service
- AggregateRating + Review
- Person — for each provider/team member
"""

from __future__ import annotations

import json

from geo_agent.business_profiles import BusinessProfile, get_profile
from geo_agent.config import Customer
from geo_agent.google_places import (
    CONFIDENCE_FOR_ADDRESS,
    CONFIDENCE_FOR_REVIEWS,
    VerifiedBusinessData,
    is_trusted,
)


def generate_primary_schema(customer: Customer, verified_data: VerifiedBusinessData | None = None) -> dict:
    """Generate the main schema for the homepage, adapted by business profile."""
    profile = get_profile(customer)
    is_practice = profile.is_practice

    schema = {
        "@context": "https://schema.org",
        "@type": profile.schema_type,
        "@id": f"https://{customer.domain}/#{profile.schema_id_suffix}",
        "name": customer.name,
        "url": f"https://{customer.domain}/",
    }

    # telephone — always include for practices even if empty (Google flags it as missing)
    if customer.phone:
        schema["telephone"] = customer.phone

    # Build address — always include for practices (Google flags missing address)
    address_fields = {"@type": "PostalAddress", "addressCountry": "US"}
    if customer.address:
        address_fields["streetAddress"] = customer.address
    if customer.city:
        address_fields["addressLocality"] = customer.city
    if customer.state:
        address_fields["addressRegion"] = customer.state
    if customer.zip_code:
        address_fields["postalCode"] = customer.zip_code
    # Only include address block if we have at least city or street
    if customer.address or customer.city:
        schema["address"] = address_fields

    # image — Google expects this on LocalBusiness types
    if is_practice:
        if customer.image:
            schema["image"] = customer.image
        else:
            schema["image"] = f"https://{customer.domain}/logo.png"

    # Practice-specific fields — always include priceRange (Google flags it as missing)
    if is_practice:
        schema["priceRange"] = "$$"
    # medicalSpecialty — only for businesses with a medical specialty
    if profile.schema_specialty:
        schema["medicalSpecialty"] = profile.schema_specialty
    # knowsAbout — specialties as free text
    if customer.specialties:
        schema["knowsAbout"] = customer.specialties

    if customer.hours:
        schema["openingHours"] = customer.hours

    if is_practice and customer.insurance_accepted:
        schema["paymentAccepted"] = "Cash, Credit Card, Insurance"
        schema["currenciesAccepted"] = "USD"

    if is_practice and customer.emergency_available:
        schema["hasOfferCatalog"] = {
            "@type": "OfferCatalog",
            "name": "Emergency Services",
            "itemListElement": [{
                "@type": "Offer",
                "itemOffered": {
                    "@type": "Service",
                    "name": f"Emergency {profile.service_category.title()}",
                    "description": f"Same-day emergency appointments available at {customer.name}.",
                },
            }],
        }

    # Additional schema type (e.g. SoftwareApplication for tech companies)
    if profile.additional_schema_type:
        schema["additionalType"] = profile.additional_schema_type

    # Embed employees as Person (not Dentist — Dentist is a LocalBusiness type)
    if customer.providers:
        employees = []
        for provider in customer.providers:
            person = {"@type": "Person", "name": provider.name}
            if provider.credentials:
                person["jobTitle"] = provider.credentials
            if provider.bio:
                person["description"] = provider.bio
            if provider.specialties:
                person["knowsAbout"] = provider.specialties
            if getattr(provider, "alumni_of", None):
                person["alumniOf"] = [
                    {"@type": "CollegeOrUniversity", "name": school}
                    for school in provider.alumni_of
                ]
            employees.append(person)
        schema["employee"] = employees

    # Services as OfferCatalog (valid on LocalBusiness/Dentist)
    if customer.services and "hasOfferCatalog" not in schema:
        schema["hasOfferCatalog"] = {
            "@type": "OfferCatalog",
            "name": "Services",
            "itemListElement": [
                {"@type": "OfferCatalog", "name": svc}
                for svc in customer.services
            ],
        }

    # Add AggregateRating from verified Google review data
    if is_trusted(verified_data, CONFIDENCE_FOR_REVIEWS) and verified_data.review_count > 0:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(verified_data.rating),
            "reviewCount": str(verified_data.review_count),
            "bestRating": "5",
            "worstRating": "1",
        }

    # Override address with Google-verified data when confidence is high
    if is_trusted(verified_data, CONFIDENCE_FOR_ADDRESS):
        if "address" not in schema:
            schema["address"] = {"@type": "PostalAddress", "addressCountry": "US"}
        if verified_data.address:
            schema["address"]["streetAddress"] = verified_data.address
        if verified_data.city:
            schema["address"]["addressLocality"] = verified_data.city
        if verified_data.state:
            schema["address"]["addressRegion"] = verified_data.state
        if verified_data.zip_code:
            schema["address"]["postalCode"] = verified_data.zip_code
        if verified_data.phone:
            schema["telephone"] = verified_data.phone
        if verified_data.lat and verified_data.lng:
            schema["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": verified_data.lat,
                "longitude": verified_data.lng,
            }

    # sameAs for social profiles would go here
    # schema["sameAs"] = [...]

    return schema


# Keep backward-compatible alias
generate_dentist_schema = generate_primary_schema


def generate_provider_schemas(customer: Customer) -> list[dict]:
    """Generate Person schema for each provider/team member."""
    profile = get_profile(customer)
    works_for_type = profile.schema_type
    works_for_id = f"https://{customer.domain}/#{profile.schema_id_suffix}"

    schemas = []
    for provider in customer.providers:
        schema = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": provider.name,
            "jobTitle": provider.credentials,
            "worksFor": {
                "@type": works_for_type,
                "@id": works_for_id,
                "name": customer.name,
            },
        }
        if provider.specialties:
            schema["knowsAbout"] = provider.specialties
        if provider.bio:
            schema["description"] = provider.bio
        schemas.append(schema)
    return schemas


def generate_service_schema(
    service_name: str,
    description: str,
    url: str,
    customer: Customer,
) -> dict:
    """Generate Service schema for a service page."""
    profile = get_profile(customer)
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": service_name,
        "description": description[:300],
        "url": url,
        "provider": {
            "@type": profile.schema_type,
            "@id": f"https://{customer.domain}/#{profile.schema_id_suffix}",
            "name": customer.name,
        },
    }
    if customer.city:
        schema["areaServed"] = {
            "@type": "City",
            "name": customer.city,
        }
    return schema


def generate_faq_schema(questions: list[dict]) -> dict:
    """Generate FAQPage schema from a list of Q&A pairs.

    Args:
        questions: List of {"question": "...", "answer": "..."} dicts.
    """
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": q["answer"],
                },
            }
            for q in questions
        ],
    }


def schema_to_script_tag(schema: dict) -> str:
    """Wrap a schema dict in a <script> tag for HTML injection."""
    return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'


def schema_to_js_injection(schema: dict) -> str:
    """Wrap a schema dict in a JS snippet that injects JSON-LD at runtime.

    Webflow's code editor word-wraps long lines, inserting real newlines into
    JSON strings which breaks JSON-LD. This generates a <script> that creates
    the JSON-LD element via JS, avoiding the line-break issue entirely.
    """
    # Minified JSON on a single line — wrapped in a JS string
    json_str = json.dumps(schema, separators=(",", ":"))
    # Escape for JS string (single quotes around it, escape internal single quotes)
    js_safe = json_str.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "<script>"
        'var s=document.createElement("script");'
        's.type="application/ld+json";'
        f"s.textContent='{js_safe}';"
        "document.head.appendChild(s);"
        "</script>"
    )


def generate_all_schemas(
    customer: Customer,
    verified_data: VerifiedBusinessData | None = None,
    webflow_safe: bool = False,
    faqs: list[tuple[str, str]] | None = None,
) -> str:
    """Generate all schema markup as injectable HTML script tags.

    Args:
        webflow_safe: If True, output JS injection wrappers instead of raw
            JSON-LD <script> tags. This prevents Webflow's code editor from
            breaking JSON by inserting line breaks.
        faqs: (question, answer) pairs to emit as FAQPage schema — pass the SAME
            Q&A used in llms.txt so the on-page schema and llms.txt corroborate.
            Falls back to the industry seed questions answered from verified facts.
    """
    wrap = schema_to_js_injection if webflow_safe else schema_to_script_tag
    profile = get_profile(customer)
    tags = []

    # Main business schema (Dentist for practices, Organization for others)
    tags.append(wrap(generate_primary_schema(customer, verified_data=verified_data)))

    # Provider schemas
    for provider_schema in generate_provider_schemas(customer):
        tags.append(wrap(provider_schema))

    # FAQPage schema — the highest-impact schema for AI citation. Build from the
    # passed Q&A, or from seed questions answered with verified facts.
    if faqs is None:
        from geo_agent.generators.llms_txt import _answer_seed_faq
        faqs = []
        for seed_q in (profile.faq_seeds or []):
            ans = _answer_seed_faq(seed_q, customer, profile)
            if ans:
                faqs.append((seed_q, ans))
    if faqs:
        tags.append(wrap(generate_faq_schema(
            [{"question": q, "answer": a} for q, a in faqs]
        )))

    # Service schema per offered service (top few)
    home = f"https://{customer.domain}/"
    for svc in (customer.services or [])[:6]:
        desc = f"{svc} at {customer.name}" + (f" in {customer.city}, {customer.state}" if customer.city else "")
        tags.append(wrap(generate_service_schema(svc, desc, home, customer)))

    return "\n".join(tags)
