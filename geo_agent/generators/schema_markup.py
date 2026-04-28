"""Generate JSON-LD schema markup for dental practices.

Schemas that matter for AI/LLM discoverability:
- Dentist (extends LocalBusiness) — homepage
- FAQPage — on service pages (highest priority for GEO)
- Service — for each dental service
- AggregateRating + Review
- Person — for each provider
"""

from __future__ import annotations

import json

from geo_agent.config import Customer
from geo_agent.google_places import (
    CONFIDENCE_FOR_ADDRESS,
    CONFIDENCE_FOR_REVIEWS,
    VerifiedBusinessData,
    is_trusted,
)


def generate_dentist_schema(customer: Customer, verified_data: VerifiedBusinessData | None = None) -> dict:
    """Generate the main Dentist/LocalBusiness schema for the homepage."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Dentist",
        "@id": f"https://{customer.domain}/#dentist",
        "name": customer.name,
        "url": f"https://{customer.domain}/",
        "telephone": customer.phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": customer.address,
            "addressLocality": customer.city,
            "addressRegion": customer.state,
            "postalCode": customer.zip_code,
            "addressCountry": "US",
        },
        "priceRange": "$$-$$$$",
        "medicalSpecialty": customer.specialties or ["General Dentistry"],
    }

    if customer.hours:
        schema["openingHours"] = customer.hours

    if customer.insurance_accepted:
        schema["paymentAccepted"] = "Cash, Credit Card, Insurance"
        schema["currenciesAccepted"] = "USD"

    if customer.emergency_available:
        schema["availableService"] = {
            "@type": "MedicalProcedure",
            "name": "Emergency Dental Care",
            "description": f"Same-day emergency dental appointments available at {customer.name}.",
        }

    # Add AggregateRating from verified Google review data
    # Only when confidence meets threshold — prevents using another business's reviews
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


def generate_provider_schemas(customer: Customer) -> list[dict]:
    """Generate Person schema for each dentist/provider."""
    schemas = []
    for provider in customer.providers:
        schema = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": provider.name,
            "jobTitle": provider.credentials,
            "worksFor": {
                "@type": "Dentist",
                "@id": f"https://{customer.domain}/#dentist",
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
    """Generate Service schema for a dental service page."""
    return {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": service_name,
        "description": description[:300],
        "url": url,
        "provider": {
            "@type": "Dentist",
            "@id": f"https://{customer.domain}/#dentist",
            "name": customer.name,
        },
        "areaServed": {
            "@type": "City",
            "name": customer.city,
        },
    }


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


def generate_all_schemas(customer: Customer, verified_data: VerifiedBusinessData | None = None) -> str:
    """Generate all schema markup as injectable HTML script tags."""
    tags = []

    # Main dentist schema
    tags.append(schema_to_script_tag(generate_dentist_schema(customer, verified_data=verified_data)))

    # Provider schemas
    for provider_schema in generate_provider_schemas(customer):
        tags.append(schema_to_script_tag(provider_schema))

    return "\n".join(tags)
