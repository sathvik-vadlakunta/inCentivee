"""Post-generation validator to catch business-type contamination.

After the agent generates llms.txt, schema.html, robots.txt, etc.,
this validator scans the output for terms that belong to a DIFFERENT
business type than the customer's. If a precious metals buyer's
llms.txt says "Dentist" or "dental services", that's a bug.
"""

from __future__ import annotations

import logging
import re

from geo_agent.business_profiles import BusinessProfile, get_profile

logger = logging.getLogger(__name__)

# Terms that should ONLY appear for dental/practice customers
DENTAL_MARKERS = [
    "dentist", "dental", "orthodont", "periodon", "endodont",
    "oral surgery", "tooth whitening", "teeth whitening",
    "dental implant", "dental crown", "dental filling",
    "root canal", "dental insurance", "dental emergency",
    "dental care", "dental hygien", "dental cleaning",
    "dental patient", "new patient", "dental practice",
    "cosmetic dentistry", "restorative dentistry",
    "general dentistry", "pediatric dentistry",
    "sedation dentistry", "dental lab",
]

# Terms that should ONLY appear for ecommerce customers
ECOMMERCE_MARKERS = [
    "add to cart", "checkout", "shopping cart",
    "free shipping", "return policy",
]

# Map: business type -> terms that should NOT appear
FORBIDDEN_TERMS: dict[str, list[str]] = {}

# For non-dental businesses, dental terms are forbidden
for _bt in ["technology", "product", "service", "ecommerce", "precious_metals_buyer"]:
    FORBIDDEN_TERMS[_bt] = DENTAL_MARKERS

# For non-ecommerce, ecommerce terms are forbidden
for _bt in ["practice", "technology", "service", "precious_metals_buyer"]:
    FORBIDDEN_TERMS.setdefault(_bt, []).extend(ECOMMERCE_MARKERS)


def validate_output(
    profile: BusinessProfile,
    files: dict[str, str],
    business_type: str = "",
) -> list[str]:
    """Check generated files for business-type contamination.

    Args:
        profile: The customer's resolved BusinessProfile.
        files: Dict of filename -> content (e.g. {"llms.txt": "...", "schema.html": "..."}).
        business_type: The raw business_type string from DB.

    Returns:
        List of warning strings. Empty list = all clean.
    """
    warnings = []
    btype = business_type or profile.industry

    # Get forbidden terms for this business type
    forbidden = FORBIDDEN_TERMS.get(btype, [])
    if not forbidden:
        # If we don't have explicit forbidden terms, skip
        return warnings

    for filename, content in files.items():
        if not content:
            continue
        content_lower = content.lower()

        for marker in forbidden:
            # Use word boundary matching to avoid false positives
            # e.g. "dental" in "accidental" would be a false positive
            pattern = r'\b' + re.escape(marker) + r'\b'
            matches = re.findall(pattern, content_lower)
            if matches:
                warnings.append(
                    f"[{filename}] Contains '{marker}' ({len(matches)}x) "
                    f"but business type is '{btype}'"
                )

    if warnings:
        logger.warning(
            f"Business-type validation found {len(warnings)} issue(s) "
            f"for {btype} business:"
        )
        for w in warnings:
            logger.warning(f"  {w}")

    return warnings


def validate_schema_type(
    profile: BusinessProfile,
    schema_html: str,
) -> list[str]:
    """Check that schema @type matches the business profile.

    For example, a precious metals buyer should NOT have @type: Dentist.
    """
    warnings = []

    if not schema_html:
        return warnings

    # Extract all @type values
    types_found = re.findall(r'"@type"\s*:\s*"([^"]+)"', schema_html)

    if not profile.is_practice:
        # Non-practice businesses should NOT have Dentist type
        if "Dentist" in types_found:
            warnings.append(
                f"[schema.html] Uses @type 'Dentist' but business is "
                f"'{profile.industry}' — should be '{profile.schema_type}'"
            )
        # Should not have medicalSpecialty unless it's a medical business
        if not profile.schema_specialty and "medicalSpecialty" in schema_html:
            warnings.append(
                f"[schema.html] Contains 'medicalSpecialty' but business "
                f"type '{profile.industry}' has no medical specialty"
            )

    return warnings
