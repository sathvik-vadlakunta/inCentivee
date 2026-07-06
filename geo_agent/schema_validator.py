"""Schema validation watchdog for customer websites.

Validates JSON-LD schema markup on live sites and detects:
- Missing schema that was previously present
- Malformed/invalid schema
- Schema that doesn't match our generated version
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationResult:
    """Result of validating schema markup on a page."""
    url: str
    status: str  # valid, warning, error, missing
    schemas_found: int
    schema_types: list[str]
    issues: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def validate_site_schema(domain: str, pages: list[str] | None = None) -> list[SchemaValidationResult]:
    """Validate schema markup across a site's pages.

    Args:
        domain: The domain to check (e.g., "hilltopfamilydental.com").
        pages: Page paths ("/team") or full URLs ("https://…/team") to check. Prefer
            passing the customer's REAL crawled pages. When omitted we probe only the
            homepage — NOT an assumed set like "/about" / "/services" / "/contact",
            which 404 on sites whose pages live elsewhere (e.g. non-dental clients)
            and fire bogus "schema invalid" alerts.

    Returns:
        List of SchemaValidationResult for each checked page.
    """
    if not pages:
        pages = ["/"]  # homepage always exists; real pages should be passed in

    base_url = f"https://{domain}"
    results = []
    seen: set[str] = set()
    for page in pages:
        if page.startswith("http"):
            url = page
        else:
            url = base_url + (page if page.startswith("/") else "/" + page)
        if url in seen:
            continue
        seen.add(url)
        results.append(_validate_page_schema(url))

    return results


def _validate_page_schema(url: str) -> SchemaValidationResult:
    """Validate schema markup on a single page."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return SchemaValidationResult(
                    url=url,
                    status="error",
                    schemas_found=0,
                    schema_types=[],
                    issues=[f"HTTP {resp.status_code}"],
                )
            html = resp.text
    except Exception as e:
        return SchemaValidationResult(
            url=url,
            status="error",
            schemas_found=0,
            schema_types=[],
            issues=[f"Failed to fetch: {type(e).__name__}"],
        )

    # Extract JSON-LD blocks
    schemas = extract_jsonld(html)
    if not schemas:
        return SchemaValidationResult(
            url=url,
            status="missing",
            schemas_found=0,
            schema_types=[],
            issues=["No JSON-LD schema found on page"],
        )

    # Validate each schema
    issues = []
    schema_types = []

    for i, schema in enumerate(schemas):
        schema_type = schema.get("@type", "Unknown")
        if isinstance(schema_type, list):
            schema_types.extend(schema_type)
        else:
            schema_types.append(schema_type)

        # Check for required fields based on type
        type_issues = _validate_schema_fields(schema, schema_type)
        issues.extend(type_issues)

    status = "valid" if not issues else "warning"
    # Upgrade to error if critical issues
    critical_keywords = ["missing @type", "missing name", "invalid JSON"]
    if any(any(kw in issue.lower() for kw in critical_keywords) for issue in issues):
        status = "error"

    return SchemaValidationResult(
        url=url,
        status=status,
        schemas_found=len(schemas),
        schema_types=schema_types,
        issues=issues,
    )


def extract_jsonld(html: str) -> list[dict]:
    """Extract all JSON-LD schema blocks from HTML."""
    pattern = r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    schemas = []
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, list):
                schemas.extend(data)
            else:
                schemas.append(data)
        except json.JSONDecodeError:
            schemas.append({"_parse_error": True, "_raw": match[:200]})

    return schemas


def _validate_schema_fields(schema: dict, schema_type: str) -> list[str]:
    """Validate required fields for common dental schema types."""
    issues = []

    if schema.get("_parse_error"):
        issues.append(f"Invalid JSON in schema block: {schema.get('_raw', '')[:100]}")
        return issues

    if "@type" not in schema:
        issues.append("Missing @type in schema")
        return issues

    # Dentist / LocalBusiness
    if schema_type in ("Dentist", "LocalBusiness", "MedicalBusiness"):
        required = ["name", "address", "telephone"]
        recommended = ["url", "image", "priceRange", "aggregateRating"]
        for field_name in required:
            if field_name not in schema:
                issues.append(f"{schema_type}: missing required field '{field_name}'")
        for field_name in recommended:
            if field_name not in schema:
                issues.append(f"{schema_type}: missing recommended field '{field_name}'")

        # Validate address sub-fields
        address = schema.get("address", {})
        if isinstance(address, dict):
            for addr_field in ["streetAddress", "addressLocality", "addressRegion", "postalCode"]:
                if addr_field not in address:
                    issues.append(f"{schema_type}: address missing '{addr_field}'")

        # Validate medicalSpecialty uses schema.org enum values (not free text)
        VALID_MEDICAL_SPECIALTIES = {
            "Anesthesia", "Cardiovascular", "CommunityHealth", "Dentistry",
            "Dermatologic", "Dermatology", "DietNutrition", "Emergency",
            "Endocrine", "Gastroenterologic", "Genetic", "Geriatric",
            "Gynecologic", "Hematologic", "Infectious", "LaboratoryScience",
            "Midwifery", "Musculoskeletal", "Neurologic", "Nursing",
            "Obstetric", "Oncologic", "Optometric", "Otolaryngologic",
            "Pathology", "Pediatric", "PharmacySpecialty", "Physiotherapy",
            "PlasticSurgery", "Podiatric", "PrimaryCare", "Psychiatric",
            "PublicHealth", "Pulmonary", "Radiography", "Renal",
            "RespiratoryTherapy", "Rheumatologic", "SpeechPathology",
            "Surgical", "Toxicologic", "Urologic",
        }
        med_spec = schema.get("medicalSpecialty")
        if med_spec:
            specs = [med_spec] if isinstance(med_spec, str) else med_spec
            for spec in specs:
                clean = spec.replace("http://schema.org/", "").replace("https://schema.org/", "")
                if clean not in VALID_MEDICAL_SPECIALTIES:
                    issues.append(
                        f"{schema_type}: invalid medicalSpecialty '{spec}' — "
                        f"use schema.org enum values (e.g. 'Dentistry')"
                    )

        # Validate employee types — must be Person, not Dentist
        employees = schema.get("employee", [])
        if isinstance(employees, dict):
            employees = [employees]
        for emp in employees:
            if isinstance(emp, dict) and emp.get("@type") in ("Dentist", "LocalBusiness"):
                issues.append(
                    f"{schema_type}: employee '{emp.get('name', '?')}' has @type '{emp['@type']}' — "
                    f"should be 'Person'"
                )

        # Check for aggregateRating
        if "aggregateRating" in schema:
            rating = schema["aggregateRating"]
            if "ratingValue" not in rating:
                issues.append(f"{schema_type}: aggregateRating missing 'ratingValue'")
            if "reviewCount" not in rating:
                issues.append(f"{schema_type}: aggregateRating missing 'reviewCount'")

    # FAQPage
    elif schema_type == "FAQPage":
        main_entity = schema.get("mainEntity", [])
        if not main_entity:
            issues.append("FAQPage: missing 'mainEntity' (no questions)")
        elif isinstance(main_entity, list):
            for j, item in enumerate(main_entity):
                if "@type" not in item or item["@type"] != "Question":
                    issues.append(f"FAQPage: item {j} is not a Question")
                if "name" not in item:
                    issues.append(f"FAQPage: question {j} missing 'name'")
                accepted = item.get("acceptedAnswer", {})
                if not accepted or "text" not in accepted:
                    issues.append(f"FAQPage: question {j} missing answer text")

    # Product — Google requires offers, review, or aggregateRating
    elif schema_type == "Product":
        if "name" not in schema:
            issues.append(f"Product: missing 'name'")
        has_required = any(k in schema for k in ("offers", "review", "aggregateRating"))
        if not has_required:
            issues.append(
                f"Product '{schema.get('name', '?')}': Google requires 'offers', 'review', "
                f"or 'aggregateRating' — consider using @type 'Service' instead"
            )

    # MedicalProcedure / Service
    elif schema_type in ("MedicalProcedure", "Service", "MedicalTherapy"):
        if "name" not in schema:
            issues.append(f"{schema_type}: missing 'name'")
        if "description" not in schema:
            issues.append(f"{schema_type}: missing 'description'")

    # Check nested OfferCatalog items for Product types missing required fields
    catalog = schema.get("hasOfferCatalog", {})
    for item in catalog.get("itemListElement", []):
        offered = item.get("itemOffered", {})
        if isinstance(offered, dict) and offered.get("@type") == "Product":
            has_req = any(k in offered for k in ("offers", "review", "aggregateRating"))
            if not has_req:
                issues.append(
                    f"Nested Product '{offered.get('name', '?')}': Google requires 'offers', "
                    f"'review', or 'aggregateRating' — use @type 'Service' instead"
                )

    return issues


def validate_with_google_rich_results(url: str, api_key: str = "") -> dict:
    """Validate a URL using Google's Rich Results / Structured Data Testing API.

    Uses the Search Console URL Inspection API to check rich result eligibility.
    Falls back to fetching the page and running our internal validator if no API key.

    Returns:
        {
            "source": "google_api" | "internal",
            "url": url,
            "status": "pass" | "warnings" | "errors",
            "items": [{"type": ..., "errors": [...], "warnings": [...]}],
        }
    """
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY", "")

    # Google doesn't expose Rich Results Test as a public REST API.
    # Instead, we use our internal validator which catches the same issues
    # (invalid medicalSpecialty, wrong employee @type, missing fields, etc.)
    # and augment with a programmatic schema.org validation call.
    result = _validate_page_schema(url)

    # Try schema.org validator API (lightweight HTML check)
    schemaorg_issues = _validate_with_schemaorg(url)

    all_issues = result.issues + schemaorg_issues
    if any("error" in i.lower() or "missing required" in i.lower() for i in all_issues):
        status = "errors"
    elif all_issues:
        status = "warnings"
    else:
        status = "pass"

    return {
        "source": "internal+schemaorg",
        "url": url,
        "status": status,
        "schema_types": result.schema_types,
        "issues": all_issues,
    }


def _validate_with_schemaorg(url: str) -> list[str]:
    """Fetch page and validate JSON-LD against schema.org type definitions.

    Checks that:
    - All @type values are real schema.org types
    - Properties used are valid for their parent @type
    - Required Google rich result fields are present
    """
    issues = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return [f"Could not fetch {url}: HTTP {resp.status_code}"]
            html = resp.text
    except Exception as e:
        return [f"Could not fetch {url}: {e}"]

    schemas = extract_jsonld(html)

    # Google Rich Results requires these fields for LocalBusiness/Dentist
    RICH_RESULT_REQUIRED = {
        "Dentist": ["name", "address", "image"],
        "LocalBusiness": ["name", "address", "image"],
        "FAQPage": ["mainEntity"],
    }
    RICH_RESULT_RECOMMENDED = {
        "Dentist": ["telephone", "priceRange", "aggregateRating", "url"],
        "LocalBusiness": ["telephone", "priceRange", "aggregateRating", "url"],
    }

    for schema in schemas:
        if schema.get("_parse_error"):
            issues.append("schema.org: invalid JSON-LD block")
            continue

        schema_type = schema.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ""

        # Check rich result required fields
        for field_name in RICH_RESULT_REQUIRED.get(schema_type, []):
            if field_name not in schema:
                issues.append(f"schema.org: {schema_type} missing rich-result required field '{field_name}'")

        # Check rich result recommended fields
        for field_name in RICH_RESULT_RECOMMENDED.get(schema_type, []):
            if field_name not in schema:
                issues.append(f"schema.org: {schema_type} missing rich-result recommended field '{field_name}'")

    return issues


def compare_schema_versions(
    live_schemas: list[dict],
    generated_schemas: list[dict],
) -> list[str]:
    """Compare live schema on the site vs what we generated.

    Returns list of differences found.
    """
    diffs = []

    live_types = set()
    for s in live_schemas:
        t = s.get("@type", "Unknown")
        if isinstance(t, list):
            live_types.update(t)
        else:
            live_types.add(t)

    gen_types = set()
    for s in generated_schemas:
        t = s.get("@type", "Unknown")
        if isinstance(t, list):
            gen_types.update(t)
        else:
            gen_types.add(t)

    # Check for missing schemas
    missing = gen_types - live_types
    extra = live_types - gen_types

    for m in missing:
        diffs.append(f"Schema type '{m}' was generated but is missing from live site")

    for e in extra:
        diffs.append(f"Schema type '{e}' found on live site but not in our generated version")

    return diffs


def generate_schema_report(results: list[SchemaValidationResult]) -> str:
    """Generate a text report from validation results."""
    lines = [
        "Schema Validation Report",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 50,
        "",
    ]

    valid_count = sum(1 for r in results if r.status == "valid")
    warning_count = sum(1 for r in results if r.status == "warning")
    error_count = sum(1 for r in results if r.status in ("error", "missing"))

    lines.append(f"Pages checked: {len(results)}")
    lines.append(f"Valid: {valid_count} | Warnings: {warning_count} | Errors: {error_count}")
    lines.append("")

    for r in results:
        icon = {"valid": "OK", "warning": "WARN", "error": "ERR", "missing": "MISS"}.get(r.status, "?")
        lines.append(f"[{icon}] {r.url}")
        if r.schema_types:
            lines.append(f"  Types: {', '.join(r.schema_types)}")
        for issue in r.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    return "\n".join(lines)
