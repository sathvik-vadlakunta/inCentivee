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
        domain: The domain to check (e.g., "hilltopfamilydental.com")
        pages: Optional list of page paths to check. If None, checks homepage + common pages.

    Returns:
        List of SchemaValidationResult for each checked page.
    """
    if pages is None:
        pages = [
            "/",
            "/about",
            "/services",
            "/contact",
        ]

    results = []
    base_url = f"https://{domain}"

    for page_path in pages:
        url = base_url + page_path
        result = _validate_page_schema(url)
        results.append(result)

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
        required = ["name", "address"]
        recommended = ["telephone", "url", "openingHours", "geo"]
        for field in required:
            if field not in schema:
                issues.append(f"{schema_type}: missing required field '{field}'")
        for field in recommended:
            if field not in schema:
                issues.append(f"{schema_type}: missing recommended field '{field}'")

        # Validate address sub-fields
        address = schema.get("address", {})
        if isinstance(address, dict):
            for addr_field in ["streetAddress", "addressLocality", "addressRegion", "postalCode"]:
                if addr_field not in address:
                    issues.append(f"{schema_type}: address missing '{addr_field}'")

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

    # MedicalProcedure / Service
    elif schema_type in ("MedicalProcedure", "Service", "MedicalTherapy"):
        if "name" not in schema:
            issues.append(f"{schema_type}: missing 'name'")
        if "description" not in schema:
            issues.append(f"{schema_type}: missing 'description'")

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
